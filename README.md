# polygon_centerline

This tool runs with Python 3.6 and reads Polygon/MultiPolygon datasets
such as i.e. the [geographic
regions](http://www.naturalearthdata.com/http//www.naturalearthdata.com/download/10m/physical/ne_10m_geography_regions_polys.zip)
from [Natural Earth](http://www.naturalearthdata.com/) and extracts
smoothed centerlines for better label placement. This method is used to
create the label layer of [EOX Maps](http://maps.eox.at).

To do so, it a [Voronoi
diagram](https://en.wikipedia.org/wiki/Voronoi_diagram) is created to
get the polygon skeleton where the skeleton centerline is selected and
smoothed.

![](img/centerline.gif)

Steps:

1.  Extract outline.
2.  Segmentize outline to get more evenly distributed outline points.
3.  Extract points.
4.  If there are too many points, simplify the segmentized outline and
    Extract points again.
5.  Create Voronoi diagram.
6.  Select all Voronoi edges which are inside the source polygon.
7.  Determine the best line.
8.  Smooth line.

## Installation

Networkit is added to speedup the path finding.

## Installation

clone repository and run

``` shell
pip install -r requirements.txt
python setup.py install
```

or by conda .. code-block:: shell conda install -c appliedgrg
polygon_centerline

## CLI

``` shell
$ polygon_centerline --help

Usage: polygon_centerline [OPTIONS] INPUT_PATH OUTPUT_PATH

  Read features, convert to centerlines and write to output.

  Multipart features (MultiPolygons) from input will be converted to
  singlepart features, i.e. all output features written will be LineString
  geometries, not MultiLineString geometries.

Options:
  --version                       Show the version and exit.
  --segmentize_maxlen FLOAT       Maximum segment length for polygon borders.
                                  (default: 0.5)
  --max_points INTEGER            Number of points per geometry allowed before
                                  simplifying. (default: 3000)
  --simplification FLOAT          Simplification threshold. (default: 0.05)
  --smooth INTEGER                Smoothness of the output centerlines.
                                  (default: 5)
  --max_paths INTEGER             Number of longest paths used to create the centerlines.
                                  (default: 5)
  --output_driver [GeoJSON|GPKG]  Output format. (default: 'GeoJSON')
  --src-point TEXT                Source endpoint as 'x,y'.
  --dst-point TEXT                Destination endpoint as 'x,y'.
  --guided-strategy [candidate|virtual|main_route|legacy]
                                  Guided extraction strategy. (default: 'virtual')
  --endpoint-mode [strict|soft]   Endpoint policy for guided extraction.
  --snap-tolerance FLOAT          Soft-mode snap tolerance in geometry units.
  --endpoint-candidate-k INTEGER  Number of endpoint graph candidates.
  --max-terminal-angle FLOAT      Maximum terminal deflection angle in degrees.
  --alpha FLOAT                   Medial weighting exponent for guided path extraction.
  --verbose                       show information on processed features
  --debug                         show debug log messages
  --help                          Show this message and exit.
```

Endpoint-guided CLI example:

``` shell
polygon_centerline input.geojson output.geojson \
  --src-point "5.55,44.25" \
  --dst-point "15.9,47.85" \
  --endpoint-mode strict
```

## API

``` 
>>> from polygon_centerline import get_centerline
>>> help(get_centerline)

get_centerline(
    geom,
    segmentize_maxlen=0.5,
    max_points=3000,
    simplification=0.05,
    smooth_sigma=5,
    max_paths=5,
    src_geom=None,
    dst_geom=None,
    guided_strategy="virtual",
    endpoint_mode="strict",
    snap_tolerance=None,
    endpoint_candidate_k=5,
    max_terminal_angle=40,
    alpha=0.5,
)
Return centerline from geometry.

Parameters:
-----------
geom : shapely Polygon or MultiPolygon
segmentize_maxlen : Maximum segment length for polygon borders.
    (default: 0.5)
max_points : Number of points per geometry allowed before simplifying.
    (default: 3000)
simplification : Simplification threshold.
    (default: 0.05)
smooth_sigma : Smoothness of the output centerlines.
    (default: 5)
max_paths : Number of longest paths used to create the centerlines.
    (default: 5)
src_geom, dst_geom : Optional endpoint guidance geometries.
guided_strategy : "candidate", "virtual", or "main_route".
endpoint_mode : "strict" or "soft".
snap_tolerance : Maximum endpoint snap distance for soft mode.
endpoint_candidate_k : Number of endpoint graph candidates.
max_terminal_angle : Maximum allowed terminal deflection angle in degrees.
alpha : Exponent for medial-aware edge weighting.

Returns:
--------
geometry : LineString or MultiLineString

Raises:
-------
CenterlineError : if centerline cannot be extracted from Polygon
TypeError : if input geometry is not Polygon or MultiPolygon
```

## License

MIT License

Copyright (c) 2015, 2016, 2017, 2018 [EOX IT Services](https://eox.at/)

(see LICENSE file for more details)
