import json
import io
from pathlib import Path
import xml.etree

import pyproj
import pytest
import rasterio.coords

import stac_vrt

HERE = Path(__name__).parent.absolute()


@pytest.fixture
def response():
    with open(HERE / "tests/response.json") as f:
        resp = json.load(f)

    return resp


def assert_vrt_equal(result, expected):
    for path in [
        ".",
        "SRS",
        "GeoTransform",
        "VRTRasterBand",
        "VRTRasterBand/ColorInterp",
        "VRTRasterBand/SimpleSource",
        "VRTRasterBand/SimpleSource/SourceFilename",
        "VRTRasterBand/SimpleSource/SourceBand",
        "VRTRasterBand/SimpleSource/SourceProperties",
        "VRTRasterBand/SimpleSource/SrcRect",
        "VRTRasterBand/SimpleSource/DstRect",
    ]:
        rchild = result.findall(path)
        echild = expected.findall(path)

        assert len(echild)
        if path != "VRTRasterBand/ColorInterp":
            # TODO: check on the expected.
            assert len(echild) == len(rchild)

        for a, b in zip(echild, rchild):
            assert a.attrib == b.attrib
            if path == "GeoTransform":
                x = list(map(lambda x: round(float(x)), a.text.split(",")))
                y = list(map(lambda x: round(float(x)), a.text.split(",")))
                assert x == y

            else:
                assert a.text == b.text


def test_fixture(response):
    assert set(response) == {"context", "features", "links", "type"}


def test_integration(response):
    stac_items = response["features"]
    # TODO: remove when fixed in NAIP data
    # Have to at least fix the CRS....
    for item in stac_items:
        item["properties"]["proj:epsg"] = 26917
    crs = pyproj.crs.CRS("epsg:26917")

    # TODO: remove when added to NAIP data
    res_x = res_y = 0.6

    # TODO: remove when added to NAIP data
    bboxes = [
        rasterio.coords.BoundingBox(
            left=530802.0, bottom=2979348.0, right=537426.0, top=2986692.0
        ),
        rasterio.coords.BoundingBox(
            left=524604.0, bottom=2979336.0, right=531222.0, top=2986674.0
        ),
    ]

    # TODO: remove when added to NAIP data
    shapes = [(12240, 11040), (12230, 11030)]

    # TODO: Remove when added to STAC
    data_type = "Byte"

    # TODO: Remove when added to STAC
    block_width = 512
    block_height = 512

    # --------------------------
    # Now for the test.
    result = stac_vrt.build_vrt(
        stac_items,
        crs=crs,
        res_x=res_x,
        res_y=res_y,
        shapes=shapes,
        bboxes=bboxes,
        data_type=data_type,
        block_width=block_width,
        block_height=block_height,
    )

    expected_tree = xml.etree.ElementTree.parse(HERE / "tests/expected.vrt").getroot()
    result_tree = xml.etree.ElementTree.parse(io.StringIO(result)).getroot()
    assert_vrt_equal(result_tree, expected_tree)


def test_integration_fixed():
    with open(HERE / "tests/response-fixed.json") as f:
        resp = json.load(f)

    stac_items = resp["features"]
    vrt = stac_vrt.build_vrt(
        stac_items, data_type="Byte", block_width=512, block_height=512
    )

    ds = rasterio.open(vrt)
    ds.transform


def test_no_items():
    with pytest.raises(ValueError, match="Must provide"):
        stac_vrt.build_vrt([])


def test_incorrect_bboxes():
    with pytest.raises(ValueError, match="2 != 1"):
        stac_vrt.build_vrt(
            [{"test": 1}],
            bboxes=[[1, 2, 3, 4], [5, 6, 7, 8]],
            crs=pyproj.crs.CRS("epsg:26917"),
            res_x=1,
            res_y=1,
        )


def test_incorrect_shapes():
    with pytest.raises(ValueError, match="2 != 1"):
        stac_vrt.build_vrt(
            [{"test": 1}],
            bboxes=[[1, 2, 3, 4]],
            shapes=[[1, 2], [3, 4]],
            crs=pyproj.crs.CRS("epsg:26917"),
            res_x=1,
            res_y=1,
        )


def test_multiple_crs_raises():
    with open(HERE / "tests/response-fixed.json") as f:
        resp = json.load(f)
    resp["features"][0]["properties"]["proj:epsg"] = 26918

    with pytest.raises(ValueError, match="same CRS"):
        stac_vrt.build_vrt(
            resp["features"], data_type="Byte", block_width=512, block_height=512
        )


def test_missing_crs_raises():
    with open(HERE / "tests/response-fixed.json") as f:
        resp = json.load(f)
    del resp["features"][0]["properties"]["proj:epsg"]

    with pytest.raises(KeyError, match="proj:epsg"):
        stac_vrt.build_vrt(
            resp["features"], data_type="Byte", block_width=512, block_height=512
        )
