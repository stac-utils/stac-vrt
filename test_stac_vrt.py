import json
import io
from pathlib import Path
import xml.etree

import pyproj
import pytest
import rasterio.coords

import vrstac


HERE = Path(__name__).parent


@pytest.fixture
def response():
    with open(HERE / "response.json") as f:
        resp = json.load(f)

    return resp


def test_fixture(response):
    assert set(response) == {"context", "features", "links", "type"}


def test_integration(response):
    stac_items = response["features"]
    # TODO: remove when fixed in NAIP data
    crs = pyproj.crs.CRS("epsg:26917")

    # TODO: remove when added to NAIP data
    res_x = res_y = 0.6

    # TODO: remove when added to NAIP data
    bboxes = [
        rasterio.coords.BoundingBox(left=530802.0, bottom=2979348.0, right=537426.0, top=2986692.0),
        rasterio.coords.BoundingBox(left=524604.0, bottom=2979336.0, right=531222.0, top=2986674.0)
    ]

    # TODO: remove when added to NAIP data
    shapes = [
        (12240, 11040),
        (12230, 11030)
    ]

    # TODO: Remove when added to STAC
    data_type = "Byte"

    # TODO: Remove when added to STAC
    block_width = 512
    block_height = 512

    # --------------------------
    # Now for the test.
    result = vrstac.build_vrt(stac_items, crs=crs, res_x=res_x, res_y=res_y,
                              shapes=shapes, bboxes=bboxes, data_type="Byte",
                              block_width=block_width, block_height=block_height)

    expected_tree = xml.etree.ElementTree.parse("expected.vrt").getroot()
    result_tree = xml.etree.ElementTree.parse(io.StringIO(result)).getroot()

    for path in [".", "SRS", "GeoTransform", "VRTRasterBand", "VRTRasterBand/ColorInterp",
                 "VRTRasterBand/SimpleSource", "VRTRasterBand/SimpleSource/SourceFilename",
                 "VRTRasterBand/SimpleSource/SourceBand",
                 "VRTRasterBand/SimpleSource/SourceProperties",
                 "VRTRasterBand/SimpleSource/SrcRect",
                 "VRTRasterBand/SimpleSource/DstRect",
                 ]:
        echild = expected_tree.findall(path)
        rchild = result_tree.findall(path)

        assert len(echild)
        if path != "VRTRasterBand/ColorInterp":
            # TODO: check on the expected.
            assert len(echild) == len(rchild)

        for a, b in zip(echild, rchild):
            assert a.attrib == b.attrib
            if path == "GeoTransform":
                x = list(map(lambda x: round(float(x)), a.text.split(',')))
                y = list(map(lambda x: round(float(x)), a.text.split(',')))
                assert x == y

            else:
                assert a.text == b.text

    ds = rasterio.open(result)
    ds.transform