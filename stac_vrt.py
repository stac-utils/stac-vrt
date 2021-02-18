"""
Construct a GDAL VRT from a collection of STAC Items.

Examples
--------
>>> import vrstac, rioxarray
>>> items = ...
>>> vrt = vrstac.build_vrt(items)
>>> ds = rioxarray.open_rasterio(vrt)
>>> ds
...
"""
__version__ = "1.0.0"

from typing import List, Optional, Tuple

import affine
import pyproj
import rasterio
import rasterio.warp
import numpy as np

# TODO: change to types to a Protocol


def _build_bboxes(stac_items, crs) -> List[rasterio.coords.BoundingBox]:
    has_proj_bbox = "proj:bbox" in stac_items[0]["properties"]
    crs = pyproj.crs.CRS(crs)
    if has_proj_bbox:
        bboxes = [
            rasterio.coords.BoundingBox(*item["properties"]["proj:bbox"])
            for item in stac_items
        ]
    else:
        bboxes = []
        for stac_item in stac_items:
            bboxes.append(
                rasterio.coords.BoundingBox(
                    *rasterio.warp.transform_bounds(
                        "epsg:4326", crs, *stac_item["bbox"]
                    )
                )
            )
    return bboxes


def _build_bbox(bboxes):
    arr = np.array(bboxes)
    minima = arr.min(0)
    maxima = arr.max(0)

    out_bbox = rasterio.coords.BoundingBox(minima[0], minima[1], maxima[2], maxima[3])
    return out_bbox


def build_transform(
    bbox: rasterio.coords.BoundingBox, res_x: float, res_y: float
) -> affine.Affine:
    """
    Build the geo transform from the bounding box of the output dataset.

    Notes
    -----
    This uses `affine.Affine`. Convert to GDAL prior to writing the VRT.
    It currently assumes that the "rotation" values are 0. What are those?
    """
    out_transform = affine.Affine(res_x, 0, bbox.left, 0, -res_y, bbox.top)
    return out_transform


# TODO: figure out dataAxisToSRSAxisMapping
_vrt_template = """\
<VRTDataset rasterXSize="{width}" rasterYSize="{height}">
  <SRS dataAxisToSRSAxisMapping="1,2">{srs}</SRS>
  <GeoTransform>{transform}</GeoTransform>
{raster_bands}
</VRTDataset>
"""

_raster_band_template = """\
  <VRTRasterBand dataType="{data_type}" band="{band_number}">{color_interp}
{simple_sources}
  </VRTRasterBand>
"""

# TODO: Check assumptions on block width matching xSize in srcRect.
# i.e. always reading all of the input.

_simple_source_template = """\
    <SimpleSource>
      <SourceFilename relativeToVRT="0">{url}</SourceFilename>
      <SourceBand>{band_number}</SourceBand>
      <SourceProperties RasterXSize="{width}" RasterYSize="{height}" \
DataType="{data_type}" BlockXSize="{block_width}" BlockYSize="{block_height}" />
      <SrcRect xOff="0" yOff="0" xSize="{width}" ySize="{height}" />
      <DstRect xOff="{x_off}" yOff="{y_off}" xSize="{width}" ySize="{height}" />
    </SimpleSource>
"""


def _format_vrt():
    pass


def build_vrt(
    stac_items,
    *,
    crs: Optional[pyproj.crs.CRS] = None,
    res_x: Optional[float] = None,
    res_y: Optional[float] = None,
    shapes: Optional[List[Tuple]] = None,
    bboxes: Optional[List[rasterio.coords.BoundingBox]] = None,
    data_type=None,
    block_width=None,
    block_height=None,
    add_prefix=True,
):
    """
    Build a GDAL VRT from a STAC Metadata.
    """
    if not stac_items:
        raise ValueError("Must provide at least one stac item to 'build_vrt'.")

    if crs is None:
        crs = pyproj.CRS.from_epsg(stac_items[0]["properties"]["proj:epsg"])

    crs_code = crs.to_epsg()

    if res_x is None or res_y is None:
        # TODO: proj:transform might not exist.
        trn = stac_items[0]["properties"]["proj:transform"]
        trn = affine.Affine(*trn[:6])  # may be 6 or 9 elements.
        res_x = res_x or trn[0]
        res_y = res_y or abs(trn[4])

    if bboxes is None:
        bboxes = _build_bboxes(stac_items, crs)
    elif len(bboxes) != len(stac_items):
        raise ValueError(
            "Number of user-provided 'bboxes' does not match the number of "
            "'stac_items' ({} != {})".format(len(bboxes), len(stac_items))
        )

    if shapes is None:
        shapes = [stac_item["properties"]["proj:shape"] for stac_item in stac_items]

    elif len(shapes) != len(stac_items):
        raise ValueError(
            "Number of user-provided 'shapes' does not match the number of "
            "'stac_items' ({} != {})".format(len(shapes), len(stac_items))
        )

    out_bbox = _build_bbox(bboxes)
    out_transform = build_transform(out_bbox, res_x, res_y)
    inv_transform = ~out_transform
    out_width, out_height = map(int, inv_transform * (out_bbox.right, out_bbox.bottom))

    simple_sources = []

    image = stac_items[0]["assets"]["image"]
    simple_sources = [[] for _ in image["eo:bands"]]

    assert len(stac_items) == len(bboxes) == len(shapes)
    assert len(stac_items) == len(bboxes) == len(shapes)

    for i, (stac_item, bbox, (height, width)) in enumerate(
        zip(stac_items, bboxes, shapes)
    ):
        image_crs = stac_item.get("properties", {}).get("proj:epsg")
        if image_crs and image_crs != crs_code:
            raise ValueError(
                "STAC item {} (position {}) does not have the "
                "same CRS. {} != {}".format(stac_item["id"], i, image_crs, crs_code)
            )
        image = stac_item["assets"]["image"]
        x_off, y_off = ~out_transform * (bbox.left, bbox.top)
        for j, band in enumerate(image["eo:bands"], 1):
            url = image["href"]
            if add_prefix and url.startswith("http"):
                url = "/vsicurl/" + url

            simple_sources[j - 1].append(
                _simple_source_template.format(
                    url=url,
                    band_number=j,
                    width=width,
                    height=height,
                    data_type=data_type,
                    block_width=block_width,
                    block_height=block_height,
                    x_off=int(x_off),
                    y_off=int(y_off),
                )
            )

    sources = ["".join(x) for x in simple_sources]
    rendered_bands = []
    for band_number, band in enumerate(image["eo:bands"], 1):
        color_interp = "\n    <ColorInterp>{}</ColorInterp>".format(band["name"])
        rendered_bands.append(
            _raster_band_template.format(
                simple_sources=sources[band_number - 1],
                data_type=data_type,
                band_number=band_number,
                color_interp=color_interp,
            )
        )

    transform = ", ".join(map(str, out_transform.to_gdal()))
    result = _vrt_template.format(
        width=out_width,
        height=out_height,
        srs=crs.to_wkt(pyproj.enums.WktVersion.WKT1_GDAL),
        transform=transform,
        raster_bands="".join(rendered_bands),
    )
    return result
