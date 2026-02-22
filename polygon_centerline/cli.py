import click
import concurrent.futures
from contextlib import ExitStack
import fiona
import logging
from shapely.geometry import Point, shape, mapping
import time
import tqdm

from polygon_centerline import __version__, get_centerline
from polygon_centerline.exceptions import CenterlineError


class TqdmHandler(logging.StreamHandler):
    """Custom handler to avoid log outputs to interfere with progress bar."""

    def __init__(self):
        logging.StreamHandler.__init__(self)

    def emit(self, record):
        msg = self.format(record)
        tqdm.tqdm.write(msg)


formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
stream_handler = TqdmHandler()
stream_handler.setFormatter(formatter)
stream_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(stream_handler)

logger = logging.getLogger(__name__)


def _parse_point_option(value, option_name):
    if value is None:
        return None
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        raise click.BadParameter(
            "%s must be in 'x,y' format" % option_name,
            param_hint=option_name,
        )
    try:
        return float(parts[0]), float(parts[1])
    except ValueError as exc:
        raise click.BadParameter(
            "%s must contain numeric coordinates" % option_name,
            param_hint=option_name,
        ) from exc


@click.command()
@click.version_option(version=__version__, message="%(version)s")
@click.argument("input_path")
@click.argument("output_path")
@click.option(
    "--segmentize_maxlen",
    type=float,
    help="Maximum segment length for polygon borders. (default: 0.5)",
    default=0.5,
)
@click.option(
    "--max_points",
    type=int,
    help="Number of points per geometry allowed before simplifying. (default: 3000)",
    default=3000,
)
@click.option(
    "--simplification",
    type=float,
    help="Simplification threshold. (default: 0.05)",
    default=0.05,
)
@click.option(
    "--smooth",
    type=int,
    help="Smoothness of the output centerlines. (default: 5)",
    default=5,
)
@click.option(
    "--max_paths",
    type=int,
    help="Number of longest paths used to create the centerlines. (default: 5)",
    default=5,
)
@click.option(
    "--output_driver",
    type=click.Choice(["GeoJSON", "GPKG"]),
    help="Output format. (default: 'GeoJSON')",
    default="GeoJSON",
)
@click.option(
    "--src-point",
    type=str,
    default=None,
    help="Source endpoint as 'x,y'.",
)
@click.option(
    "--dst-point",
    type=str,
    default=None,
    help="Destination endpoint as 'x,y'.",
)
@click.option(
    "--guided-strategy",
    type=click.Choice(["candidate", "virtual", "main_route", "legacy"]),
    default="virtual",
    help="Guided extraction strategy. ('legacy' is a deprecated alias for 'main_route')",
)
@click.option(
    "--endpoint-mode",
    type=click.Choice(["strict", "soft"]),
    default="strict",
    help="Endpoint policy for guided extraction.",
)
@click.option(
    "--snap-tolerance",
    type=float,
    default=None,
    help="Soft-mode snap tolerance in geometry units.",
)
@click.option(
    "--endpoint-candidate-k",
    type=int,
    default=5,
    help="Number of endpoint graph candidates.",
)
@click.option(
    "--max-terminal-angle",
    type=float,
    default=40,
    help="Maximum terminal deflection angle in degrees.",
)
@click.option(
    "--alpha",
    type=float,
    default=0.5,
    help="Medial weighting exponent for guided path extraction.",
)
@click.option("--verbose", is_flag=True, help="show information on processed features")
@click.option("--debug", is_flag=True, help="show debug log messages")
def main(
    input_path,
    output_path,
    segmentize_maxlen,
    max_points,
    simplification,
    smooth,
    max_paths,
    output_driver,
    src_point,
    dst_point,
    guided_strategy,
    endpoint_mode,
    snap_tolerance,
    endpoint_candidate_k,
    max_terminal_angle,
    alpha,
    verbose,
    debug,
):
    """
    Read features, convert to centerlines and write to output.

    Multipart features (MultiPolygons) from input will be converted to
    singlepart features, i.e. all output features written will be LineString
    geometries, not MultiLineString geometries.
    """
    # set up logger
    log_level = logging.DEBUG if debug else logging.INFO
    logging.getLogger("polygon_centerline").setLevel(log_level)
    stream_handler.setLevel(log_level)

    src_point = _parse_point_option(src_point, "--src-point")
    dst_point = _parse_point_option(dst_point, "--dst-point")
    if (src_point is None) != (dst_point is None):
        raise click.UsageError(
            "Both --src-point and --dst-point must be provided together"
        )

    with ExitStack() as es:
        # set up context managers for fiona & process pool
        src = es.enter_context(fiona.open(input_path, "r"))
        out_schema = dict(src.schema or {})
        if "properties" not in out_schema:
            out_schema["properties"] = {}
        out_schema["geometry"] = "LineString"
        dst = es.enter_context(
            fiona.open(
                output_path,
                "w",
                schema=out_schema,
                crs=src.crs,
                driver=output_driver,
            )
        )
        executor = es.enter_context(concurrent.futures.ProcessPoolExecutor())

        tasks = (
            executor.submit(
                _feature_worker,
                feature,
                segmentize_maxlen,
                max_points,
                simplification,
                smooth,
                max_paths,
                src_point,
                dst_point,
                guided_strategy,
                endpoint_mode,
                snap_tolerance,
                endpoint_candidate_k,
                max_terminal_angle,
                alpha,
            )
            for feature in src
        )
        for task in tqdm.tqdm(
            concurrent.futures.as_completed(tasks), disable=debug, total=len(src)
        ):
            # output is split up into parts of single part geometries to meet
            # GeoPackage requirements
            for part in task.result():
                feature, elapsed = part
                if "geometry" in feature:
                    dst.write(feature)
                else:
                    logger.error(
                        "centerline could not be extracted from feature %s",
                        feature["properties"],
                    )
                if verbose:
                    tqdm.tqdm.write("%ss: %s" % (elapsed, feature["properties"]))


def _feature_worker(
    feature,
    segmentize_maxlen,
    max_points,
    simplification,
    smooth,
    max_paths,
    src_point,
    dst_point,
    guided_strategy,
    endpoint_mode,
    snap_tolerance,
    endpoint_candidate_k,
    max_terminal_angle,
    alpha,
):
    start = time.time()
    src_geom = Point(src_point) if src_point is not None else None
    dst_geom = Point(dst_point) if dst_point is not None else None
    try:
        centerline = get_centerline(
            shape(feature["geometry"]),
            segmentize_maxlen,
            max_points,
            simplification,
            smooth,
            max_paths,
            src_geom,
            dst_geom,
            guided_strategy,
            endpoint_mode,
            snap_tolerance,
            endpoint_candidate_k,
            max_terminal_angle,
            alpha,
        )
    except CenterlineError:
        return [(dict(properties=feature["properties"]), round(time.time() - start, 3))]
    finally:
        elapsed = round(time.time() - start, 3)

    if centerline.geom_type == "LineString":
        return [(dict(feature, geometry=mapping(centerline)), elapsed)]
    elif centerline.geom_type == "MultiLineString":
        return [
            (dict(feature, geometry=mapping(subgeom)), elapsed)
            for subgeom in getattr(centerline, "geoms", [])
        ]
    return [(dict(properties=feature["properties"]), elapsed)]
