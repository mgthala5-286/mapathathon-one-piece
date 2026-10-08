# Data sources and reproducibility

The analysis uses the public Microsoft Planetary Computer STAC collection `sentinel-2-l2a` and its bounding-box image endpoint. The source data are openly accessible Sentinel-2 Level-2A scenes; the item IDs used in this run are recorded below.

Study window (WGS84): `77.42, 8.64, 77.60, 8.75`.

Scenes:

- `S2B_MSIL2A_20260320T051241_R019_T43PGK_20260320T102809`
- `S2B_MSIL2A_20260422T050649_R019_T43PGK_20260422T085149`
- `S2C_MSIL2A_20260904T050651_R019_T43PGK_20260904T095815`
- `S2B_MSIL2A_20260929T050649_R019_T43PGK_20260929T091314`

Bands: B03, B04, B08, B11. The download script and analysis script are included in the project root: `download-previews.ps1` and `analyze_tirunelveli.py`.

The vector output is intentionally called `remote_sensing_patches`: it does not represent revenue/cadastral boundaries. Validate crop labels with field GPS or local agricultural records before operational decisions.
