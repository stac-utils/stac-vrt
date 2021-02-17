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
from typing import List, Optional, Tuple

import affine
import pyproj
import pystac
import rasterio
import numpy as np

# TODO: change to types to a Protocol


def build_bbox(stac_items: List[pystac.Item], crs=None) -> rasterio.coords.BoundingBox:
    """
    Get the bounding box for a list of STAC Items.

    If present, this uses the `proj:bbox` field from each STAC item.
    Otherwise, it falls back to the `bbox` field, which is then
    reprojected with provided `proj:epsg` the `proj:epsg` field of the first item.
    All the items should have the smae proj_epsg.
    """
    bboxes = _build_bboxes(stac_items, crs)
    return _build_bbox(bboxes)


def _build_bboxes(stac_items: List[pystac.Item], crs=None) -> List[rasterio.coords.BoundingBox]:
    if not stac_items:
        raise ValueError("Must provide at least one item")
    if crs is None:
        crs = stac_items[0]["properties"]["proj:epsg"]  # TODO: handle missing proj

    has_proj_bbox = "proj:bbox" in stac_items[0]["properties"]
    crs = pyproj.crs.CRS(crs)
    if has_proj_bbox:
        bboxes = [rasterio.coords.BoundBox(*item["properties"]["proj:bbox"]) for item in stac_items]
    else:
        bboxes = []
        for stac_item in stac_items:
            bboxes.append(
                rasterio.coords.BoundingBox(*rasterio.warp.transform_bounds("epsg:4326", crs, *stac_item["bbox"]))
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

# TODO: Check assumptions on block width matching xSize in srcRect. i.e. always reading all of the input.

_simple_source_template = """\
    <SimpleSource>
      <SourceFilename relativeToVRT="0">{url}</SourceFilename>
      <SourceBand>{band_number}</SourceBand>
      <SourceProperties RasterXSize="{width}" RasterYSize="{height}" DataType="{data_type}" BlockXSize="{block_width}" BlockYSize="{block_height}" />
      <SrcRect xOff="0" yOff="0" xSize="{width}" ySize="{height}" />
      <DstRect xOff="{x_off}" yOff="{y_off}" xSize="{width}" ySize="{height}" />
    </SimpleSource>
"""


def _build():
    """
    Build the structure of data, to be passed to the formatter
    """
    pass


def _format_vrt():
    pass


def build_vrt(
    stac_items: List[pystac.Item],
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
    if res_x is None:
        res_x = stac_items[0].res[0]
    if res_y is None:
        res_y = stac_items[0].res[1]

    if bboxes is None:
        bboxes = _build_bboxes(stac_items, crs)
    else:
        # TODO: validate length
        pass

    out_bbox = _build_bbox(bboxes)
    out_transform = build_transform(out_bbox, res_x, res_y)
    inv_transform = ~out_transform
    out_width, out_height = map(int, inv_transform * (out_bbox.right, out_bbox.bottom))

    simple_sources = []
    raster_bands = []

    # The iteration order here is annoying :/
    # We need to go over bands then items.
    image = stac_items[0]["assets"]["image"]
    simple_sources = [[] for _ in image["eo:bands"]]

    assert len(stac_items) == len(bboxes) == len(shapes)
    assert len(stac_items) == len(bboxes) == len(shapes)

    for i, (stac_item, bbox, (height, width)) in enumerate(zip(stac_items, bboxes, shapes)):
        image = stac_item["assets"]["image"]
        x_off, y_off = ~out_transform * (bbox.left, bbox.top)
        for j, band in enumerate(image["eo:bands"], 1):
            url = image["href"]
            if add_prefix and url.startswith("http"):
                url = "/vsicurl/" + url

            print(j)
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
                    y_off=int(y_off))
            )
            
    sources = [''.join(x) for x in simple_sources]
    rendered_bands = []
    for band_number, band in enumerate(image["eo:bands"], 1):
        color_interp = "\n    <ColorInterp>{}</ColorInterp>".format(band["name"])
        rendered_bands.append(_raster_band_template.format(
            simple_sources=sources[band_number - 1], data_type=data_type, band_number=band_number, color_interp=color_interp
            )
        )

    transform = ", ".join(map(str, out_transform.to_gdal()))
    result = _vrt_template.format(width=out_width, height=out_height, srs=crs.to_wkt(pyproj.enums.WktVersion.WKT1_GDAL), transform=transform,
                                  raster_bands="".join(rendered_bands))
    return result