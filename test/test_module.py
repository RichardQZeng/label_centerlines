from click.testing import CliRunner
import click
import pytest
from shapely.geometry import Point

from label_centerlines import __version__, get_centerline
from label_centerlines.exceptions import CenterlineError
from label_centerlines.cli import _parse_point_option, main
import label_centerlines._src as src_module


def test_cli():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_help_includes_guided_strategy():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "--guided-strategy" in result.output


def test_centerline(alps_shape):
    cl = get_centerline(alps_shape)
    assert cl.is_valid
    assert cl.geom_type == "LineString"


def test_alps_endpoint_points_are_inside_and_off_centerline(
    alps_shape, alps_endpoint_points
):
    centerline = get_centerline(alps_shape)
    src_pt, dst_pt = alps_endpoint_points

    assert alps_shape.contains(src_pt)
    assert alps_shape.contains(dst_pt)

    # Test data points represent endpoint areas, not exact centerline vertices.
    assert centerline.distance(src_pt) > 0.05
    assert centerline.distance(dst_pt) > 0.05


def test_centerline_strict_endpoint_guidance(alps_shape, alps_endpoint_points):
    src_pt, dst_pt = alps_endpoint_points
    centerline = get_centerline(
        alps_shape,
        src_geom=src_pt,
        dst_geom=dst_pt,
    )

    assert Point(centerline.coords[0]).distance(src_pt) < 1e-9
    assert Point(centerline.coords[-1]).distance(dst_pt) < 1e-9


def test_centerline_guided_strategy_legacy(alps_shape, alps_endpoint_points):
    src_pt, dst_pt = alps_endpoint_points
    centerline = get_centerline(
        alps_shape,
        src_geom=src_pt,
        dst_geom=dst_pt,
        guided_strategy="legacy",
    )
    assert centerline.is_valid
    assert centerline.geom_type == "LineString"


def test_centerline_guided_strategy_virtual(alps_shape, alps_endpoint_points):
    src_pt, dst_pt = alps_endpoint_points
    centerline = get_centerline(
        alps_shape,
        src_geom=src_pt,
        dst_geom=dst_pt,
        guided_strategy="virtual",
    )
    assert Point(centerline.coords[0]).distance(src_pt) < 1e-9
    assert Point(centerline.coords[-1]).distance(dst_pt) < 1e-9


def test_centerline_guided_failure_raises_in_strict_mode(alps_shape, monkeypatch):
    src_pt = alps_shape.representative_point()
    dst_pt = alps_shape.centroid

    monkeypatch.setattr(
        src_module, "_get_guided_path_virtual", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(src_module, "_get_guided_path", lambda *args, **kwargs: None)

    with pytest.raises(CenterlineError, match="endpoint-guided extraction failed"):
        get_centerline(
            alps_shape,
            src_geom=src_pt,
            dst_geom=dst_pt,
            guided_strategy="virtual",
            endpoint_mode="strict",
        )


def test_centerline_guided_failure_soft_mode_warns_and_falls_back(
    alps_shape, monkeypatch, caplog
):
    src_pt = alps_shape.representative_point()
    dst_pt = alps_shape.centroid

    monkeypatch.setattr(
        src_module, "_get_guided_path_virtual", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(src_module, "_get_guided_path", lambda *args, **kwargs: None)

    with caplog.at_level("WARNING"):
        centerline = get_centerline(
            alps_shape,
            src_geom=src_pt,
            dst_geom=dst_pt,
            guided_strategy="virtual",
            endpoint_mode="soft",
        )

    assert centerline.is_valid
    assert centerline.geom_type == "LineString"
    assert "endpoint-guided extraction failed in soft mode" in caplog.text


def test_parse_point_option_valid():
    assert _parse_point_option("1.5,2.25", "--src-point") == (1.5, 2.25)


def test_parse_point_option_invalid():
    with pytest.raises(click.BadParameter):
        _parse_point_option("bad", "--src-point")


def test_centerline_guided_strategy_invalid(alps_shape):
    with pytest.raises(ValueError):
        get_centerline(alps_shape, guided_strategy="unknown")
