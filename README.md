# stac-vrt

Build a GDAL VRT from a STAC response.

[![Documentation Status](https://readthedocs.org/projects/stac-vrt/badge/?version=latest)](https://stac-vrt.readthedocs.io/en/latest/?badge=latest)

## Example

```python
>>> import stac_vrt, requests, rioxarray
>>> stac_items = requests.get(
...     "http://pc-mqe-staging.westeurope.cloudapp.azure.com/collections/usda-naip/items"
... ).json()["features"]
>>> vrt = stac_vrt.build_vrt(stac_items, data_type="Byte", block_width=512, block_height=512)
>>> ds = rioxarray.open_rasterio(vrt, chunks=True)
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

## Motivation

We want to construct a single xarray Dataset from a bunch of COG files. GDAL's VRT handles this case well, but can be time-consuming to create since each COG has to be opened to read its metadata.

We can instead rely on STAC to provide the necessary metadata. We use the STAC metadata to construct the same VRT. At processing time, the behavior should be identical.

## Notes

The example above doesn't quite work on the NAIP data hosted in Azure today.
In particular, the following fields have been modified or added:

1. Corrected `proj:epsg` to `26917`.
2. Added `proj:shape` with the shape as reported by rasterio
3. Added `proj:bbox` with the bounding box as reported by rasterio
4. Added `proj:transform` with the `.transform` as reported by rasterio (this provides the resolution, assuming we can't get it from anywhere else)

That's done with:

```python
import json

with open('response.json') as f:
    response = json.load(f)

proj_epsg = 26917
res_x = res_y = 0.6
bboxes = [
    [530802.0, 2979348.0, 537426.0, 2986692.0],
    [524604.0, 2979336.0, 531222.0, 2986674.0],
]
shapes = [
    [12240, 11040],
    [12230, 11030]
]
transforms = [
    (0.6, 0.0, 530802.0, 0.0, -0.6, 2986692.0, 0.0, 0.0, 1.0),
    (0.6, 0.0, 524604.0, 0.0, -0.6, 2986674.0, 0.0, 0.0, 1.0),
]

for i, feature in enumerate(response["features"]):
    feature["properties"]["proj:epsg"] = proj_epsg
    feature["properties"]["proj:shape"] = shapes[i]
    feature["properties"]["proj:transform"] = transforms[i]
    feature["properties"]["proj:bbox"] = bboxes[i]

with open("response-fixed.json", "w") as f:
    json.dump(response, f)
```

## Initial Benchmarks

On a benchmark with 425 items, with the caveat that the stac-vrt timing doesn't include any HTTP requests to the STAC endpoint.

**With GDAL**

```python
%%time
>>> blobs_2013 = ["/vsicurl/{}".format(item.assets['image']['href'])
...               for item in search_2013.items()]
>>> mosaic2013 = gdal.BuildVRT("test.vrt", blobs_2013)
>>> mosaic2013.FlushCache()
CPU times: user 29.8 s, sys: 1.86 s, total: 31.6 s
Wall time: 1min 38s
```

**With stac-vrt**

```python
%%time
>>> result = stac_vrt.build_vrt(response["features"], block_width=512, block_height=512, data_type="Byte")
CPU times: user 28.4 ms, sys: 4.18 ms, total: 32.6 ms
Wall time: 31.6 ms
```
