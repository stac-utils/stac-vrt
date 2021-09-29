# stac-vrt

Build a GDAL VRT from a STAC response.

[![Documentation Status](https://readthedocs.org/projects/stac-vrt/badge/?version=latest)](https://stac-vrt.readthedocs.io/en/latest/?badge=latest)

## Other Libraries

stac-vrt is lightly maintained these days, and its use case is now better filled by other libraries:

1. GDAL now natively supports STAC items: See <https://gdal.org/drivers/raster/stacit.html>
2. [stackstac](https://stackstac.readthedocs.io/en/latest/) provides a nicer way to stack STAC items into a DataArray
 

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
