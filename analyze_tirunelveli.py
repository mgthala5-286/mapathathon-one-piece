import base64
import csv
import json
import math
import os
from collections import deque, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
IMG_DIR = ROOT / 'imagery_crop'
OUT_DIR = ROOT / 'outputs'
OUT_DIR.mkdir(exist_ok=True)

BBOX = (77.42, 8.64, 77.60, 8.75)  # min lon, min lat, max lon, max lat
DATES = ['2026-03-20', '2026-04-22', '2026-09-04', '2026-09-29']
BANDS = ['B03', 'B04', 'B08', 'B11']

CLASS_COLORS = {
    'paddy': (40, 125, 210, 175),
    'banana': (220, 70, 55, 185),
    'other_cropland': (95, 180, 90, 155),
}


def read_band(date, band):
    arr = np.array(Image.open(IMG_DIR / f'{date}_{band}.png'))
    # Single-band PNGs are returned as L+A or RGBA; the first channel is the data.
    return arr[:, :, 0].astype(np.float32) / 255.0


def connected_components(mask, min_size=16):
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    components = []
    label = 0
    for r in range(h):
        for c in range(w):
            if not mask[r, c] or labels[r, c]:
                continue
            label += 1
            stack = [(r, c)]
            labels[r, c] = label
            cells = []
            while stack:
                rr, cc = stack.pop()
                cells.append((rr, cc))
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = rr + dr, cc + dc
                        if 0 <= nr < h and 0 <= nc < w and mask[nr, nc] and not labels[nr, nc]:
                            labels[nr, nc] = label
                            stack.append((nr, nc))
            if len(cells) >= min_size:
                components.append(cells)
    return components


def majority_filter(mask, iterations=1):
    out = mask.copy()
    for _ in range(iterations):
        padded = np.pad(out.astype(np.uint8), 1, mode='edge')
        count = np.zeros_like(out, dtype=np.uint8)
        for dr in range(3):
            for dc in range(3):
                count += padded[dr:dr + out.shape[0], dc:dc + out.shape[1]]
        out = count >= 5
    return out


def component_geometry(cells, h, w):
    # Use a compact envelope for each connected image patch. The exact raster
    # class mask remains in the PNG map; the GeoJSON is intentionally light.
    rows = [rc[0] for rc in cells]
    cols = [rc[1] for rc in cells]
    r0, r1, c0, c1 = min(rows), max(rows), min(cols), max(cols)
    west, south, east, north = BBOX
    x0 = west + (east - west) * c0 / w
    x1 = west + (east - west) * (c1 + 1) / w
    y1 = north - (north - south) * r0 / h
    y0 = north - (north - south) * (r1 + 1) / h
    return {'type': 'Polygon', 'coordinates': [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


def clamp(value, lower=0.0, upper=1.0):
    return max(lower, min(upper, value))


def confidence_for(kind, med_ndvi, amp, med_ndmi):
    if kind == 'banana':
        if med_ndvi >= 0.38 and amp <= 0.28 and med_ndmi >= 0.05:
            return 'high'
        return 'medium'
    if kind == 'paddy':
        if amp >= 0.30 and med_ndvi >= 0.25:
            return 'high'
        return 'medium'
    return 'medium'


def confidence_score(kind, med_ndvi, min_ndvi, amp, med_ndmi):
    """Return an explainable 0-100 screening score, not a probability."""
    if kind == 'banana':
        parts = [
            clamp((med_ndvi - 0.32) / 0.30),
            clamp((min_ndvi - 0.20) / 0.30),
            clamp((0.32 - amp) / 0.32),
            clamp((med_ndmi - 0.03) / 0.30),
        ]
        return round(sum(parts) / len(parts) * 100, 1)
    if kind == 'paddy':
        parts = [
            clamp((med_ndvi + amp - 0.40) / 0.30),
            clamp((amp - 0.22) / 0.40),
            clamp((med_ndvi - 0.22) / 0.35),
        ]
        return round(sum(parts) / len(parts) * 100, 1)
    return round(clamp((med_ndvi - 0.28) / 0.40) * 100, 1)


def main():
    bands = {date: {band: read_band(date, band) for band in BANDS} for date in DATES}
    sample = bands[DATES[0]]['B03']
    h, w = sample.shape
    ndvi = []
    ndwi = []
    ndmi = []
    for date in DATES:
        b = bands[date]
        ndvi.append((b['B08'] - b['B04']) / (b['B08'] + b['B04'] + 1e-6))
        ndwi.append((b['B03'] - b['B08']) / (b['B03'] + b['B08'] + 1e-6))
        ndmi.append((b['B08'] - b['B11']) / (b['B08'] + b['B11'] + 1e-6))
    ndvi = np.stack(ndvi)
    ndwi = np.stack(ndwi)
    ndmi = np.stack(ndmi)

    ndvi_min = np.min(ndvi, axis=0)
    ndvi_max = np.max(ndvi, axis=0)
    ndvi_med = np.median(ndvi, axis=0)
    ndvi_amp = ndvi_max - ndvi_min
    ndwi_med = np.median(ndwi, axis=0)
    ndmi_med = np.median(ndmi, axis=0)

    valid = np.all(np.stack([bands[d]['B03'] > 0.005 for d in DATES]), axis=0)
    # The rules are deliberately conservative: persistent high greenness is treated as
    # banana candidate, while strong seasonal change is treated as paddy candidate.
    banana = valid & (ndvi_med >= 0.32) & (ndvi_min >= 0.20) & (ndvi_amp <= 0.32) & (ndmi_med >= 0.03)
    paddy = valid & (~banana) & (ndvi_max >= 0.40) & (ndvi_amp >= 0.22) & (ndvi_med >= 0.22)
    other_crop = valid & (~banana) & (~paddy) & (ndvi_med >= 0.28) & (ndvi_max >= 0.40)

    banana = majority_filter(banana, 1)
    paddy = majority_filter(paddy, 1)
    other_crop = majority_filter(other_crop & ~(banana | paddy), 1)

    classes = np.zeros((h, w), dtype=np.uint8)
    classes[paddy] = 1
    classes[banana] = 2
    classes[other_crop] = 3

    # Local flood-impact proxy. The first two dates represent the pre-event
    # baseline and the latest date is the observation date. A real flood event
    # should be confirmed with Sentinel-1 radar and field observations.
    flood_pre_ndwi = np.median(ndwi[:2], axis=0)
    flood_pre_ndvi = np.median(ndvi[:2], axis=0)
    flood_during_ndwi = ndwi[-1]
    flood_during_ndvi = ndvi[-1]
    flood_ndwi_increase = flood_during_ndwi - flood_pre_ndwi
    flood_ndvi_drop = flood_pre_ndvi - flood_during_ndvi
    flood_proxy = valid & (
        ((flood_during_ndwi >= 0.05) & (flood_ndwi_increase >= 0.12)) |
        ((flood_during_ndwi >= 0.12) & (flood_ndvi_drop >= 0.15))
    )

    print('array shape', w, 'x', h)
    for label, mask in [('paddy', classes == 1), ('banana', classes == 2), ('other_cropland', classes == 3)]:
        print(label, int(mask.sum()), 'pixels')

    # Approximate area from the geographic output grid.
    mean_lat = math.radians((BBOX[1] + BBOX[3]) / 2)
    width_m = (BBOX[2] - BBOX[0]) * 111320 * math.cos(mean_lat)
    height_m = (BBOX[3] - BBOX[1]) * 110574
    study_area_m2 = width_m * height_m
    pixel_area_km2 = study_area_m2 / (w * h) / 1e6
    analysis_grid_m = (width_m / w + height_m / h) / 2

    features = []
    parcel_id = 1
    class_masks = {'paddy': classes == 1, 'banana': classes == 2, 'other_cropland': classes == 3}
    for kind, mask in class_masks.items():
        components = connected_components(mask, min_size=18)
        for cells in components:
            geom = component_geometry(cells, h, w)
            vals = np.array([ndvi_med[r, c] for r, c in cells])
            amps = np.array([ndvi_amp[r, c] for r, c in cells])
            nmis = np.array([ndmi_med[r, c] for r, c in cells])
            mean_ndvi = float(vals.mean())
            mean_min_ndvi = float(np.array([ndvi_min[r, c] for r, c in cells]).mean())
            mean_amp = float(amps.mean())
            mean_ndmi = float(nmis.mean())
            flood_fraction = float(np.array([flood_proxy[r, c] for r, c in cells]).mean())
            mean_ndvi_drop = float(np.array([flood_ndvi_drop[r, c] for r, c in cells]).mean())
            risk_score = round(min(100, flood_fraction * 70 + clamp((mean_ndvi_drop - 0.05) / 0.25) * 30), 1)
            if flood_fraction >= 0.50 or risk_score >= 65:
                risk_level = 'high'
            elif flood_fraction >= 0.15 or risk_score >= 30:
                risk_level = 'medium'
            else:
                risk_level = 'low'
            flood_status = 'potentially_affected' if flood_fraction >= 0.05 else 'no_potential_inundation_signal'
            lon_center = sum(pixel_polygon_col for _, pixel_polygon_col in cells) / len(cells)
            lon_center = BBOX[0] + (BBOX[2] - BBOX[0]) * (lon_center + 0.5) / w
            side = 'Ambasamudram-side' if lon_center < 77.50 else 'Cheranmahadevi-side'
            area_m2 = len(cells) * pixel_area_km2 * 1e6
            features.append({
                'type': 'Feature',
                'geometry': geom,
                'properties': {
                    'parcel_id': f'TIR-{parcel_id:04d}',
                    'class': kind,
                    'side': side,
                    'area_ha': round(area_m2 / 10000, 3),
                    'mean_ndvi': round(mean_ndvi, 3),
                    'seasonal_ndvi_amplitude': round(mean_amp, 3),
                    'mean_ndmi': round(mean_ndmi, 3),
                    'confidence': confidence_for(kind, mean_ndvi, mean_amp, mean_ndmi),
                    'confidence_score': confidence_score(kind, mean_ndvi, mean_min_ndvi, mean_amp, mean_ndmi),
                    'flood_status': flood_status,
                    'flooded_percent': round(flood_fraction * 100, 1),
                    'vegetation_drop': round(mean_ndvi_drop, 3),
                    'flood_risk_score': risk_score,
                    'flood_risk_level': risk_level,
                    'source_resolution_m': 10,
                    'analysis_grid_m': round(analysis_grid_m, 1),
                    'interpretation': 'remote-sensing patch; not cadastral boundary',
                },
            })
            parcel_id += 1

    geojson = {'type': 'FeatureCollection', 'name': 'Tirunelveli crop patches', 'features': features}
    (OUT_DIR / 'tirunelveli_crop_parcels.geojson').write_text(json.dumps(geojson, separators=(',', ':')), encoding='utf-8')

    crop_features = [feature for feature in features if feature['properties']['class'] in ('paddy', 'banana')]
    priority_counts = {
        level: sum(
            1 for feature in crop_features
            if feature['properties']['flood_status'] == 'potentially_affected'
            and feature['properties']['flood_risk_level'] == level
        )
        for level in ('high', 'medium', 'low')
    }
    flood_summary = {
        'method': 'Sentinel-2 NDWI water expansion plus NDVI decline proxy',
        'baseline_dates': f'{DATES[0]} and {DATES[1]}',
        'observation_date': DATES[-1],
        'potential_inundation_km2': round(float(flood_proxy.sum() * pixel_area_km2), 2),
        'paddy_affected_km2': round(float((flood_proxy & paddy).sum() * pixel_area_km2), 2),
        'banana_affected_km2': round(float((flood_proxy & banana).sum() * pixel_area_km2), 2),
        'other_cropland_affected_km2': round(float((flood_proxy & other_crop).sum() * pixel_area_km2), 2),
        'high_priority_fields': priority_counts['high'],
        'medium_priority_fields': priority_counts['medium'],
        'low_priority_fields': priority_counts['low'],
        'interpretation': 'Potential flood-impact indicator only; verify with Sentinel-1 and field inspection before damage decisions.',
    }
    (OUT_DIR / 'tirunelveli_flood_impact_summary.json').write_text(
        json.dumps(flood_summary, separators=(',', ':')), encoding='utf-8'
    )
    aoi_coords = [[[BBOX[0], BBOX[1]], [BBOX[2], BBOX[1]], [BBOX[2], BBOX[3]], [BBOX[0], BBOX[3]], [BBOX[0], BBOX[1]]]]
    aoi_geojson = {
        'type': 'FeatureCollection',
        'name': 'Tirunelveli study window',
        'features': [{
            'type': 'Feature',
            'geometry': {'type': 'Polygon', 'coordinates': aoi_coords},
            'properties': {'area_km2': round(study_area_m2 / 1e6, 1), 'coverage': 'Ambasamudram-side and Cheranmahadevi-side study window'},
        }],
    }
    (OUT_DIR / 'tirunelveli_study_window.geojson').write_text(json.dumps(aoi_geojson, separators=(',', ':')), encoding='utf-8')

    # Export a compact phenology table for the dashboard and a first-vs-last
    # NDVI change map. These are local equivalents of the optional GEE modules.
    def masked_mean(array, mask):
        selected = array[mask]
        return round(float(selected.mean()), 3) if selected.size else None

    phenology = []
    for index, date in enumerate(DATES):
        phenology.append({
            'date': date,
            'ndvi': round(float(ndvi[index].mean()), 3),
            'ndmi': round(float(ndmi[index].mean()), 3),
            'paddy_ndvi': masked_mean(ndvi[index], classes == 1),
            'banana_ndvi': masked_mean(ndvi[index], classes == 2),
        })
    (OUT_DIR / 'tirunelveli_phenology.json').write_text(
        json.dumps(phenology, separators=(',', ':')), encoding='utf-8'
    )

    ndvi_change = ndvi[-1] - ndvi[0]
    change_classes = np.zeros((h, w), dtype=np.uint8)
    change_classes[valid & (ndvi_change >= 0.20)] = 1  # greening
    change_classes[valid & (ndvi_change <= -0.20)] = 2  # decline/harvest
    change_classes[valid & (np.abs(ndvi_change) < 0.20)] = 3  # stable
    change_summary = {
        'greening_km2': round(float((change_classes == 1).sum() * pixel_area_km2), 2),
        'decline_km2': round(float((change_classes == 2).sum() * pixel_area_km2), 2),
        'stable_km2': round(float((change_classes == 3).sum() * pixel_area_km2), 2),
        'threshold': 0.20,
        'comparison': f'{DATES[0]} to {DATES[-1]}',
    }
    (OUT_DIR / 'tirunelveli_change_summary.json').write_text(
        json.dumps(change_summary, separators=(',', ':')), encoding='utf-8'
    )
    change_base = Image.open(IMG_DIR / '2026-09-29_TCI.png').convert('RGBA')
    change_overlay = Image.new('RGBA', change_base.size, (0, 0, 0, 0))
    change_px = change_overlay.load()
    change_colors = {1: (49, 163, 84, 135), 2: (215, 48, 39, 135), 3: (189, 189, 189, 95)}
    for r in range(h):
        for c in range(w):
            if change_classes[r, c] in change_colors:
                change_px[c, r] = change_colors[change_classes[r, c]]
    change_rendered = Image.alpha_composite(change_base, change_overlay)
    change_draw = ImageDraw.Draw(change_rendered, 'RGBA')
    change_draw.rectangle((14, 14, 430, 55), fill=(0, 0, 0, 160))
    change_draw.text((24, 23), 'NDVI change: early to late season', fill=(255, 255, 255, 255))
    change_rendered.save(OUT_DIR / 'tirunelveli_change_map.png')

    # Local water/moisture proxy from median NDWI. This is a presentation layer;
    # the live GEE App provides the more rigorous Global Surface Water distance.
    water_proxy = ndwi_med >= 0.25
    water_base = Image.open(IMG_DIR / '2026-09-29_TCI.png').convert('RGBA')
    water_overlay = Image.new('RGBA', water_base.size, (0, 0, 0, 0))
    water_px = water_overlay.load()
    for r in range(h):
        for c in range(w):
            if water_proxy[r, c]:
                water_px[c, r] = (0, 145, 210, 145)
    water_rendered = Image.alpha_composite(water_base, water_overlay)
    water_draw = ImageDraw.Draw(water_rendered, 'RGBA')
    water_draw.rectangle((14, 14, 455, 55), fill=(0, 0, 0, 160))
    water_draw.text((24, 23), 'Median NDWI water/moisture proxy', fill=(255, 255, 255, 255))
    water_rendered.save(OUT_DIR / 'tirunelveli_water_proxy_map.png')

    # Flood-impact display: blue is potential open-water/inundation, red is
    # potentially affected paddy and purple is potentially affected banana.
    flood_base = Image.open(IMG_DIR / '2026-09-29_TCI.png').convert('RGBA')
    flood_overlay = Image.new('RGBA', flood_base.size, (0, 0, 0, 0))
    flood_px = flood_overlay.load()
    for r in range(h):
        for c in range(w):
            if not flood_proxy[r, c]:
                continue
            if paddy[r, c]:
                flood_px[c, r] = (225, 52, 52, 185)
            elif banana[r, c]:
                flood_px[c, r] = (121, 65, 164, 190)
            else:
                flood_px[c, r] = (0, 143, 210, 155)
    flood_rendered = Image.alpha_composite(flood_base, flood_overlay)
    flood_draw = ImageDraw.Draw(flood_rendered, 'RGBA')
    flood_draw.rectangle((14, 14, 590, 55), fill=(0, 0, 0, 170))
    flood_draw.text((24, 23), 'Potential flood impact: red paddy | purple banana | blue water', fill=(255, 255, 255, 255))
    flood_rendered.save(OUT_DIR / 'tirunelveli_flood_risk_map.png')

    # Summary table by class and west/east study side.
    summary = defaultdict(lambda: {'patches': 0, 'area_ha': 0.0})
    for feat in features:
        key = (feat['properties']['side'], feat['properties']['class'])
        summary[key]['patches'] += 1
        summary[key]['area_ha'] += feat['properties']['area_ha']
    with (OUT_DIR / 'tirunelveli_crop_summary.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['study_side', 'class', 'remote_sensing_patches', 'area_ha', 'area_km2', 'note'])
        for (side, kind), values in sorted(summary.items()):
            writer.writerow([side, kind, values['patches'], round(values['area_ha'], 2), round(values['area_ha'] / 100, 3), 'side is an orientation proxy, not an administrative taluk boundary'])

    # Render a compact static map from the September true-colour image.
    base = Image.open(IMG_DIR / '2026-09-29_TCI.png').convert('RGBA')
    overlay = Image.new('RGBA', base.size, (0, 0, 0, 0))
    px = overlay.load()
    for r in range(h):
        for c in range(w):
            value = classes[r, c]
            if value == 1:
                px[c, r] = CLASS_COLORS['paddy']
            elif value == 2:
                px[c, r] = CLASS_COLORS['banana']
            elif value == 3:
                px[c, r] = CLASS_COLORS['other_cropland']
    rendered = Image.alpha_composite(base, overlay)
    draw = ImageDraw.Draw(rendered, 'RGBA')
    draw.rectangle((14, 14, 485, 80), fill=(0, 0, 0, 160))
    draw.text((24, 22), 'Tirunelveli crop differentiation', fill=(255, 255, 255, 255))
    draw.text((24, 46), 'Sentinel-2 L2A | 10 m source | 4-date phenology', fill=(235, 235, 235, 255))
    legend_x, legend_y = 24, h - 105
    draw.rectangle((legend_x - 10, legend_y - 10, legend_x + 270, h - 14), fill=(0, 0, 0, 160))
    for i, (label, color) in enumerate([('Paddy candidate', CLASS_COLORS['paddy']), ('Banana candidate', CLASS_COLORS['banana']), ('Other cropland', CLASS_COLORS['other_cropland'])]):
        y = legend_y + i * 24
        draw.rectangle((legend_x, y, legend_x + 16, y + 16), fill=color)
        draw.text((legend_x + 25, y + 1), label, fill=(255, 255, 255, 255))
    rendered.save(OUT_DIR / 'tirunelveli_crop_map.png')

    # An interactive map with the RGB overlay and vector patches embedded in the file.
    tci_bytes = (IMG_DIR / '2026-09-29_TCI.png').read_bytes()
    tci_uri = 'data:image/png;base64,' + base64.b64encode(tci_bytes).decode('ascii')
    geojson_text = json.dumps(geojson, separators=(',', ':'))
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tirunelveli paddy and banana differentiation</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>html,body,#map{{height:100%;margin:0}} .title{{padding:10px 12px;font:600 16px Arial;background:rgba(255,255,255,.92)}} .legend{{line-height:18px;color:#222;background:rgba(255,255,255,.92);padding:8px 10px;font:12px Arial}} .swatch{{display:inline-block;width:13px;height:13px;margin-right:5px;vertical-align:-2px}}</style></head>
<body><div id="map"></div><script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const bbox=[[{BBOX[1]},{BBOX[0]}],[{BBOX[3]},{BBOX[2]}]];
const map=L.map('map').fitBounds(bbox);
const osm=L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:19,attribution:'© OpenStreetMap contributors'}}).addTo(map);
const rgb=L.imageOverlay('{tci_uri}',bbox,{{opacity:0.65}}).addTo(map);
const parcels={geojson_text};
const colors={{paddy:'#287dd2',banana:'#dc4637',other_cropland:'#5fb45a'}};
const crop=L.geoJSON(parcels,{{style:f=>({{color:colors[f.properties.class]||'#666',weight:1,fillColor:colors[f.properties.class]||'#666',fillOpacity:0.55}}),onEachFeature:(f,l)=>l.bindPopup('<b>'+f.properties.parcel_id+'</b><br>'+f.properties.class+'<br>'+f.properties.area_ha+' ha<br>confidence: '+f.properties.confidence)}}).addTo(map);
L.marker([8.67254,77.44476]).addTo(map).bindTooltip('Ambasamudram');
L.marker([8.68879,77.55094]).addTo(map).bindTooltip('Cheranmahadevi');
L.control.layers({{'OpenStreetMap':osm}},{{'Sentinel-2 RGB (29 Sep 2026)':rgb,'Crop patches':crop}},{{collapsed:false}}).addTo(map);
const title=L.control({{position:'topleft'}}); title.onAdd=()=>{{const d=L.DomUtil.create('div','title');d.innerHTML='Tirunelveli crop differentiation · 242 km² study window';return d}}; title.addTo(map);
const legend=L.control({{position:'bottomright'}}); legend.onAdd=()=>{{const d=L.DomUtil.create('div','legend');d.innerHTML='<b>Candidate classes</b><br><span class="swatch" style="background:#287dd2"></span>Paddy<br><span class="swatch" style="background:#dc4637"></span>Banana<br><span class="swatch" style="background:#5fb45a"></span>Other cropland';return d}}; legend.addTo(map);
</script></body></html>'''
    (OUT_DIR / 'tirunelveli_crop_map.html').write_text(html, encoding='utf-8')

    report = f'''# Tirunelveli crop and parcel differentiation

## Study window

- Extent: `{BBOX[0]}, {BBOX[1]}, {BBOX[2]}, {BBOX[3]}` (WGS84)
- Area: `{study_area_m2 / 1e6:.1f} km²` (exceeds the 20 km² minimum)
- Analysis grid: approximately `{analysis_grid_m:.1f} m` per output cell; Sentinel-2 source resolution is 10 m for visible/NIR bands.
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
'''
    (OUT_DIR / 'tirunelveli_analysis_report.md').write_text(report, encoding='utf-8')


if __name__ == '__main__':
    main()
