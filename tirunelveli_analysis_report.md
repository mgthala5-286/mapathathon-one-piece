# Tirunelveli crop and parcel differentiation

## Study window

- Extent: `77.42, 8.64, 77.6, 8.75` (WGS84)
- Area: `240.9 km²` (exceeds the 20 km² minimum)
- Analysis grid: approximately `19.2 m` per output cell; Sentinel-2 source resolution is 10 m for visible/NIR bands.
- Coverage: a single analysis window spanning the Ambasamudram-side and Cheranmahadevi-side agricultural landscape; the west/east labels in the CSV are orientation proxies, not legal taluk boundaries.

## Imagery

Four open Sentinel-2 Level-2A acquisitions were used: 20 Mar, 22 Apr, 04 Sep and 29 Sep 2026. Bands B03 (green), B04 (red), B08 (NIR) and B11 (SWIR) were rendered from the Microsoft Planetary Computer bounding-box API at a common 1024×640 grid. The source data are 10 m for the visible/NIR bands; B11 is native 20 m. The 1024×640 render makes the working cell size approximately 19 m.

## Method

- Compute NDVI, NDWI and NDMI per date.
- Use multi-date NDVI minimum, median, maximum and seasonal amplitude.
- Identify banana candidates as persistently green, moisture-rich patches with lower seasonal amplitude.
- Identify paddy candidates as patches with strong seasonal NDVI change and high peak greenness.
- Group connected classified pixels into remote-sensing patches and report their area; these are field-like image objects, not cadastral parcels.

## Limitations

The result is a screening map, not a legal parcel map or a field-survey crop certificate. Sentinel-2’s 10 m source resolution and the coarse rendered analysis grid can mix narrow fields, trees, roads and settlements. Paddy/banana thresholds should be validated with local GPS points or field observations before operational use.
