# Round 1 presentation outline

## Problem understanding

Differentiate field-like land patches and screen paddy versus banana cultivation across a study window that covers both Ambasamudram-side and Cheranmahadevi-side landscapes in Tirunelveli District.

## Methodology

Use four cloud-filtered, open Sentinel-2 Level-2A dates. Compute NDVI, NDWI and NDMI; use NDVI seasonal amplitude to flag paddy candidates and persistent greenness/moisture to flag banana candidates; group connected image pixels into remote-sensing patches.

## Novelty

The method combines spectral indices with multi-date phenology and produces an immediately inspectable GeoJSON/HTML map. It explicitly separates image-derived crop patches from legal cadastral parcels, which avoids overstating what 10 m imagery can prove.

## Demonstration

Open `tirunelveli_crop_map.html`, toggle the Sentinel-2 RGB layer and Crop patches layer, and click a patch to see its class, area, confidence and phenology attributes.
