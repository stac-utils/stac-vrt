# stac-vrt

Build a GDAL VRT from a STAC response.

[![Documentation Status](https://readthedocs.org/projects/stac-vrt/badge/?version=latest)](https://stac-vrt.readthedocs.io/en/latest/?badge=latest)

## Example

```python
>>> import stac_vrt, requests, rasterio
>>> stac_items = requests.get(
...     "http://pct-mqe-staging.westeurope.cloudapp.azure.com/collections/usda-naip/items"
... ).json()["features"]
>>> vrt = stac_vrt.build_vrt(stac_items, data_type="Byte", block_width=512, block_height=512)
>>> ds = rasterio.open(vrt)
>>> ds.shape
(196870, 83790)
```

See [the documentation](https://stac-vrt.readthedocs.io/en/latest/) for more.