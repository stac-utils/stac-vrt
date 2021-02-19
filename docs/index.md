# stac-vrt

`stac-vrt` is a small library for quickly generating a [GDAL VRT][vrt] from a collection
of [STAC][stac] items. This makes it fast and easy to generate a mosaic of many
raster images.

## Installation

`stac-vrt` can be installed from conda-forge

    conda install -c conda-forge stac-vrt

or from PyPI

    pip install stac-vrt

## Usage

{func}`stac_vrt.build_vrt` is the primary function to use. You provide it a list of [STAC items](https://github.com/radiantearth/stac-spec/tree/master/item-spec):

```python
>>> import stac_vrt
>>> import requests
>>> stac_items = requests.get(
...     "http://pc-mqe-staging.westeurope.cloudapp.azure.com/collections/usda-naip/items"
... ).json()["features"]
```

These STAC items contain essentially all of the information needed to build a VRT.

```python
>>> vrt = stac_vrt.build_vrt(stac_items, data_type="Byte", block_width=512, block_height=512)
```

The `vrt` variable is just a Python string that's a valid VRT (an XML document). It can
be written to disk, or passed directly to [rasterio](https://rasterio.readthedocs.io/en/latest/) or [rioxarray](https://corteva.github.io/rioxarray/stable/).

```python
>>> import rioxarray
>>> ds = rioxarray.open_rasterio(vrt, chunks=(4, -1, "auto"))
>>> ds
<xarray.DataArray (band: 4, y: 11588, x: 20704)>
dask.array<open_rasterio-a61f0d99384a83218d8164684d89e2db<this-array>, shape=(4, 11588, 20704), dtype=uint8, chunksize=(1, 11520, 11520), chunktype=numpy.ndarray>
Coordinates:
  * band         (band) int64 1 2 3 4
  * y            (y) float64 2.986e+06 2.986e+06 2.986e+06 ... 2.98e+06 2.98e+06
  * x            (x) float64 5.248e+05 5.248e+05 ... 5.372e+05 5.372e+05
    spatial_ref  int64 0
Attributes:
    scale_factor:  1.0
    add_offset:    0.0
    grid_mapping:  spatial_ref
```

## Background

VRTs are a pretty cool concept in GDAL. The basic idea is to make document that's essentially just metadata; it points to *other* documents or URLs for the actual data. They're extremely useful for creating a mosiac of many images: the VRT just has information like "this sub-dataset goes at position `(x, y)` in the full dataset".

VRTs pair extremely nicely with Dask-backed xarray DataArrays: you build up a mosaic of a whole bunch of images that just involves reading some metadata and doing some geospatial reprojections. No actual data is read. Then you can (lazily) read the actual data into an xarray DataArray for your analysis, and the separate original images can be read into separate chunks.

One downside to (large) VRTs is that they can be time-consuming to build. You'd need to make at least one HTTP requests for each file going into the VRT to read the metadata (things like the CRS, shape, and transformation).

When you're using STAC to discover your assets, you *already* have all of that information avaiable. And so `stac-vrt` is able to build the VRT without any additional network requests. An informal benchmark on a set of 500 images stored in Azure Blob Storage showed that `gdal.BuildVRT` took about 90 seconds, while `stac-vrt.build_vrt` took a handful of milliseconds.

## Building stac-vrt compatible STAC Items

If you're responsible for creating STAC items, `stac-vrt` would appreciate if you include

* [`proj:epsg`](https://github.com/radiantearth/stac-spec/blob/dev/extensions/projection/README.md#projepsg)
* [`proj:shape`](https://github.com/radiantearth/stac-spec/blob/dev/extensions/projection/README.md#projshape)
* [`proj:bbox`](https://github.com/radiantearth/stac-spec/blob/dev/extensions/projection/README.md#projbbox)
* [`proj:transform`](https://github.com/radiantearth/stac-spec/blob/dev/extensions/projection/README.md#projtransform)

These are used by `stac-vrt` to build the VRT.

[vrt]: https://gdal.org/drivers/raster/vrt.html
[stac]: https://stacspec.org/

```{toctree}
api
```