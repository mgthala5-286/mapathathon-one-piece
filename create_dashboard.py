import base64
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'outputs'
IMG = ROOT / 'imagery_crop' / '2026-09-29_TCI.png'
GEOJSON = OUT / 'tirunelveli_crop_parcels.geojson'
PHENOLOGY = OUT / 'tirunelveli_phenology.json'
CHANGE_SUMMARY = OUT / 'tirunelveli_change_summary.json'
CHANGE_IMG = OUT / 'tirunelveli_change_map.png'
WATER_IMG = OUT / 'tirunelveli_water_proxy_map.png'
FLOOD_SUMMARY = OUT / 'tirunelveli_flood_impact_summary.json'
FLOOD_IMG = OUT / 'tirunelveli_flood_risk_map.png'
# Published Google Earth Engine App URL.
GEE_APP_URL = 'https://onepiece.users.earthengine.app/view/tirunelveli-crop-dashboard'

geojson = json.loads(GEOJSON.read_text(encoding='utf-8'))
phenology = json.loads(PHENOLOGY.read_text(encoding='utf-8'))
change_summary = json.loads(CHANGE_SUMMARY.read_text(encoding='utf-8'))
flood_summary = json.loads(FLOOD_SUMMARY.read_text(encoding='utf-8'))
features = geojson['features']
classes = ['paddy', 'banana', 'other_cropland']
colors = {'paddy': '#287dd2', 'banana': '#dc4637', 'other_cropland': '#5fb45a'}
labels = {'paddy': 'Paddy candidate', 'banana': 'Banana candidate', 'other_cropland': 'Other cropland'}

summary = {name: {'area_ha': 0.0, 'patches': 0} for name in classes}
side_summary = {}
for feature in features:
    props = feature['properties']
    cls = props['class']
    summary[cls]['area_ha'] += float(props['area_ha'])
    summary[cls]['patches'] += 1
    side = props['side']
    side_summary.setdefault(side, {name: 0.0 for name in classes})
    side_summary[side][cls] += float(props['area_ha'])

for value in summary.values():
    value['area_km2'] = value['area_ha'] / 100.0
    value['area_ha'] = round(value['area_ha'], 2)
    value['area_km2'] = round(value['area_km2'], 2)
for side in side_summary:
    for cls in side_summary[side]:
        side_summary[side][cls] = round(side_summary[side][cls] / 100.0, 2)

tci_uri = 'data:image/png;base64,' + base64.b64encode(IMG.read_bytes()).decode('ascii')
change_uri = 'data:image/png;base64,' + base64.b64encode(CHANGE_IMG.read_bytes()).decode('ascii')
water_uri = 'data:image/png;base64,' + base64.b64encode(WATER_IMG.read_bytes()).decode('ascii')
flood_uri = 'data:image/png;base64,' + base64.b64encode(FLOOD_IMG.read_bytes()).decode('ascii')
geojson_text = json.dumps(geojson, separators=(',', ':'))
summary_text = json.dumps(summary, separators=(',', ':'))
side_text = json.dumps(side_summary, separators=(',', ':'))
phenology_text = json.dumps(phenology, separators=(',', ':'))
change_text = json.dumps(change_summary, separators=(',', ':'))
flood_text = json.dumps(flood_summary, separators=(',', ':'))

if GEE_APP_URL:
    gee_panel_html = (
        '<div class="panel-head"><div><h3>Live farm monitoring map</h3>'
        '<p>Interactive cloud-hosted view for crop and field management.</p></div>'
        f'<a class="ghost-button" href="{GEE_APP_URL}" target="_blank" rel="noopener">Open live farm map</a></div>'
        f'<iframe class="gee-app-frame" src="{GEE_APP_URL}" title="Tirunelveli Google Earth Engine crop dashboard" loading="lazy" allowfullscreen></iframe>'
    )
else:
    gee_panel_html = (
        '<div class="panel-head"><div><h3>Live farm monitoring map</h3>'
        '<p>The local dashboard is ready. Publish the GEE App to enable the cloud-hosted view.</p></div>'
        '<a class="ghost-button" href="https://code.earthengine.google.com/" target="_blank" rel="noopener">Open GEE workspace</a></div>'
        '<div class="gee-app-not-ready"><strong>GEE App URL is not active yet</strong>'
        '<span>In Earth Engine, open Apps → Manage Apps → New App, publish the current script, then paste the resulting <code>/view/...</code> URL into <code>create_dashboard.py</code>.</span></div>'
    )

html = '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Tirunelveli farm management dashboard</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <style>
    :root { --ink:#16283b; --muted:#647487; --soft:#eef4f8; --line:rgba(255,255,255,.62); --bg:#eaf3f8; --panel:rgba(255,255,255,.58); --navy:#102c45; --blue:#287dd2; --red:#dc4637; --green:#5fb45a; --amber:#d99b2b; --glass-shadow:0 18px 45px rgba(40,76,102,.13); }
    * { box-sizing:border-box; }
    body { margin:0; background:radial-gradient(circle at 8% 3%, rgba(98,185,231,.30), transparent 31%), radial-gradient(circle at 92% 12%, rgba(110,199,155,.22), transparent 28%), linear-gradient(135deg,#e8f2f8 0%,#f7fbfd 47%,#e7f3ed 100%); color:var(--ink); font:14px/1.45 Inter, Segoe UI, Arial, sans-serif; }
    .app-shell { max-width:1480px; margin:0 auto; padding:22px 26px 34px; }
    .topbar { display:flex; align-items:center; justify-content:space-between; gap:18px; padding:14px 18px; background:linear-gradient(135deg,rgba(16,44,69,.90),rgba(28,88,125,.72)); color:#fff; border:1px solid rgba(255,255,255,.23); border-radius:18px; box-shadow:var(--glass-shadow); backdrop-filter:blur(18px) saturate(135%); -webkit-backdrop-filter:blur(18px) saturate(135%); }
    .brand { display:flex; align-items:center; gap:12px; min-width:0; }
    .brand-mark { display:grid; place-items:center; width:42px; height:42px; border-radius:11px; color:#fff; background:linear-gradient(135deg,#53a9ee,#1d5c9e); font-size:14px; font-weight:800; letter-spacing:.4px; }
    .brand-title { margin:0; font-size:19px; letter-spacing:-.25px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .eyebrow { color:#85a8c6; font-size:10px; font-weight:700; letter-spacing:1.4px; text-transform:uppercase; }
    .top-meta { display:flex; align-items:center; gap:14px; color:#b9ccdb; font-size:12px; white-space:nowrap; }
    .status { display:inline-flex; align-items:center; gap:6px; padding:6px 9px; color:#c9f0d0; background:rgba(84,180,95,.14); border:1px solid rgba(143,220,151,.3); border-radius:999px; font-size:10px; font-weight:700; letter-spacing:.7px; }
    .status:before { content:''; width:7px; height:7px; border-radius:50%; background:#7bd68c; box-shadow:0 0 0 3px rgba(123,214,140,.12); }
    .hero { display:flex; align-items:center; justify-content:space-between; gap:20px; padding:24px 4px 18px; }
    .hero h2 { margin:4px 0 4px; color:var(--ink); font-size:27px; letter-spacing:-.6px; }
    .hero p { margin:0; color:var(--muted); max-width:720px; }
    .hero-summary { min-width:165px; padding:12px 16px; text-align:right; border-left:3px solid var(--blue); }
    .hero-summary strong { display:block; color:var(--navy); font-size:29px; line-height:1.05; }
    .hero-summary span { color:var(--muted); font-size:12px; }
    .kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin-bottom:16px; }
    .kpi { position:relative; overflow:hidden; min-height:112px; padding:15px 16px 14px 19px; background:linear-gradient(135deg,rgba(255,255,255,.70),rgba(255,255,255,.38)); border:1px solid var(--line); border-radius:15px; box-shadow:var(--glass-shadow); backdrop-filter:blur(16px) saturate(125%); -webkit-backdrop-filter:blur(16px) saturate(125%); }
    .kpi:before { content:''; position:absolute; left:0; top:0; bottom:0; width:4px; background:#8aa1b4; }
    .kpi.blue:before { background:var(--blue); } .kpi.red:before { background:var(--red); } .kpi.green:before { background:var(--green); } .kpi.navy:before { background:var(--navy); }
    .kpi .label { color:var(--muted); font-size:11px; font-weight:700; letter-spacing:.7px; text-transform:uppercase; }
    .kpi .value { margin-top:8px; color:var(--navy); font-size:26px; font-weight:750; letter-spacing:-.5px; }
    .kpi .note { margin-top:3px; color:var(--muted); font-size:12px; }
    .dashboard-grid { display:grid; grid-template-columns:minmax(0,1.8fr) minmax(325px,.78fr); gap:16px; align-items:start; }
    .panel { background:linear-gradient(135deg,rgba(255,255,255,.68),rgba(255,255,255,.42)); border:1px solid var(--line); border-radius:16px; box-shadow:var(--glass-shadow); backdrop-filter:blur(18px) saturate(125%); -webkit-backdrop-filter:blur(18px) saturate(125%); }
    .map-panel { overflow:hidden; }
    .panel-head { display:flex; align-items:flex-start; justify-content:space-between; gap:14px; padding:17px 18px 13px; }
    .panel-head h3, .panel h3 { margin:0; color:var(--navy); font-size:15px; letter-spacing:-.1px; }
    .panel-head p { margin:3px 0 0; color:var(--muted); font-size:12px; }
    .map-badge { padding:5px 8px; border:1px solid rgba(255,255,255,.75); border-radius:999px; color:#3c6685; background:rgba(255,255,255,.48); font-size:11px; white-space:nowrap; backdrop-filter:blur(10px); }
    .map-toolbar { display:block; padding:10px 14px; border-top:1px solid var(--line); border-bottom:1px solid var(--line); background:rgba(255,255,255,.34); backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px); }
    .layer-toolbar-head { display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; }
    .layer-toolbar-actions { display:flex; align-items:center; gap:7px; flex-wrap:wrap; }
    .layer-menu-button, .mini-button { color:#244e6c; background:rgba(255,255,255,.58); border:1px solid rgba(255,255,255,.86); border-radius:999px; font:inherit; cursor:pointer; backdrop-filter:blur(10px); }
    .layer-menu-button { padding:7px 12px; font-size:12px; font-weight:700; }
    .mini-button { padding:5px 8px; font-size:10px; }
    .layer-menu-button:hover, .mini-button:hover { background:rgba(255,255,255,.90); }
    .layer-panel { margin-top:10px; padding:10px 2px 2px; border-top:1px solid rgba(255,255,255,.70); }
    .layer-panel.is-collapsed { display:none; }
    .layer-panel-title { margin-bottom:8px; color:#287dd2; font-size:10px; font-weight:800; letter-spacing:1px; }
    .layer-toggles { display:flex; flex-wrap:wrap; gap:8px 14px; }
    .layer-toggle { position:relative; display:inline-flex; align-items:center; gap:6px; color:#31485c; cursor:pointer; font-size:12px; }
    .layer-toggle input { position:absolute; width:1px; height:1px; opacity:0; pointer-events:none; }
    .layer-check { display:inline-grid; place-items:center; width:16px; height:16px; color:#fff; background:rgba(255,255,255,.76); border:1px solid #aec2d0; border-radius:4px; font-size:12px; font-weight:800; transition:background .16s ease, border-color .16s ease, transform .16s ease; }
    .layer-toggle input:checked + .layer-check { background:var(--blue); border-color:var(--blue); box-shadow:0 3px 8px rgba(40,125,210,.25); }
    .layer-toggle input:checked + .layer-check:after { content:'✓'; }
    .layer-toggle:hover .layer-check { transform:translateY(-1px); }
    .layer-dot { width:9px; height:9px; display:inline-block; border-radius:50%; }
    .layer-dot.rgb { background:#777; } .layer-dot.paddy { background:var(--blue); } .layer-dot.banana { background:var(--red); } .layer-dot.other { background:var(--green); } .layer-dot.boundary { background:#fff; border:1px solid #8ca0b2; } .layer-dot.confidence { background:#2171b5; } .layer-dot.change { background:#d73027; } .layer-dot.water { background:#0091d2; } .layer-dot.flood { background:#0969da; } .layer-dot.priority { background:#b42318; }
    .ghost-button { padding:7px 11px; color:#244e6c; background:rgba(255,255,255,.58); border:1px solid rgba(255,255,255,.86); border-radius:999px; box-shadow:0 5px 14px rgba(40,76,102,.08); font:inherit; font-size:12px; cursor:pointer; backdrop-filter:blur(10px); transition:transform .18s ease, background .18s ease, box-shadow .18s ease; }
    .ghost-button:hover { background:rgba(255,255,255,.88); box-shadow:0 8px 18px rgba(40,76,102,.14); transform:translateY(-1px); }
    #map { height:580px; background:#dfe9ee; }
    .map-footer { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; padding:10px 18px 12px; color:var(--muted); font-size:11px; }
    .legend { display:flex; flex-wrap:wrap; gap:11px; }
    .legend-item { display:inline-flex; align-items:center; gap:5px; }
    .legend-swatch { width:10px; height:10px; border-radius:3px; }
    .side-rail { display:grid; gap:16px; }
    .side-rail .panel { padding:17px; }
    .section-kicker { margin:3px 0 14px; color:var(--muted); font-size:12px; }
    .summary-item { margin:0 0 15px; }
    .summary-line { display:flex; align-items:center; justify-content:space-between; gap:10px; }
    .summary-label { display:flex; align-items:center; gap:7px; color:#2a4357; font-weight:650; }
    .summary-value { color:var(--navy); font-weight:750; font-variant-numeric:tabular-nums; }
    .summary-meta { display:flex; justify-content:space-between; gap:10px; margin-top:4px; color:var(--muted); font-size:11px; }
    .bar-track { height:8px; margin-top:8px; overflow:hidden; background:#e8eef3; border-radius:6px; }
    .bar { height:100%; border-radius:6px; }
    .mini-divider { height:1px; margin:14px 0; background:var(--line); }
    .total-line { display:flex; justify-content:space-between; align-items:baseline; color:var(--muted); font-size:12px; }
    .total-line strong { color:var(--navy); font-size:18px; }
    .side-table { width:100%; border-collapse:collapse; font-size:12px; }
    .side-table th, .side-table td { padding:8px 4px; text-align:right; border-bottom:1px solid var(--line); font-variant-numeric:tabular-nums; }
    .side-table th { color:var(--muted); font-size:10px; letter-spacing:.5px; text-transform:uppercase; }
    .side-table th:first-child, .side-table td:first-child { text-align:left; }
    .side-table tr:last-child td { border-bottom:0; }
    .workflow { display:grid; gap:10px; }
    .step { display:grid; grid-template-columns:24px 1fr; gap:9px; align-items:start; }
    .step-no { display:grid; place-items:center; width:23px; height:23px; color:#fff; background:var(--navy); border-radius:50%; font-size:11px; font-weight:700; }
    .step strong { display:block; color:#2a4357; font-size:12px; }
    .step span { display:block; margin-top:1px; color:var(--muted); font-size:11px; }
    .bottom-grid { display:grid; grid-template-columns:1.15fr 1fr; gap:16px; margin-top:16px; }
    .bottom-grid .panel { padding:17px; }
    .advanced-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:16px; }
    .advanced-grid .panel { padding:17px; }
    .gee-app-panel { margin-top:16px; overflow:hidden; }
    .gee-app-panel .panel-head { border-bottom:1px solid var(--line); }
    .gee-app-frame { display:block; width:100%; height:720px; border:0; background:#eef4f8; }
    .gee-app-not-ready { display:grid; gap:7px; margin:18px; padding:18px; color:var(--muted); background:#f7fafc; border:1px solid var(--line); border-left:4px solid var(--amber); border-radius:10px; }
    .gee-app-not-ready strong { color:var(--navy); }
    .gee-app-not-ready code { color:var(--navy); font-family:Consolas, monospace; font-size:11px; }
    .chart-wrap { height:210px; margin-top:10px; }
    .chart-wrap svg { width:100%; height:100%; overflow:visible; }
    .chart-axis { stroke:#c9d8e2; stroke-width:1; }
    .chart-grid { stroke:#e5edf2; stroke-width:1; }
    .chart-label { fill:var(--muted); font-size:10px; }
    .chart-line { fill:none; stroke-width:3; stroke-linecap:round; stroke-linejoin:round; }
    .feature-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:9px; margin-top:12px; }
    .feature-card { padding:11px; background:rgba(255,255,255,.42); border:1px solid rgba(255,255,255,.70); border-radius:12px; box-shadow:0 7px 18px rgba(40,76,102,.06); }
    .feature-card strong { display:block; color:var(--navy); font-size:12px; }
    .feature-card span { display:block; margin-top:3px; color:var(--muted); font-size:11px; }
    .feature-status { display:inline-flex; margin-bottom:6px; padding:3px 6px; color:#2c7250; background:#e9f7ee; border-radius:5px; font-size:9px; font-weight:700; letter-spacing:.5px; text-transform:uppercase; }
    .change-image { display:block; width:100%; margin-top:10px; border:1px solid var(--line); border-radius:9px; }
    .change-stats { display:grid; grid-template-columns:repeat(3,1fr); gap:7px; margin-top:10px; }
    .change-stat { padding:8px; border-radius:9px; background:rgba(255,255,255,.43); border:1px solid rgba(255,255,255,.65); text-align:center; }
    .change-stat strong { display:block; color:var(--navy); font-size:15px; }
    .change-stat span { color:var(--muted); font-size:10px; }
    .flood-panel { margin-top:16px; padding:17px; }
    .flood-grid { display:grid; grid-template-columns:minmax(0,1.25fr) minmax(250px,.75fr); gap:16px; margin-top:12px; }
    .flood-image { display:block; width:100%; border:1px solid var(--line); border-radius:10px; }
    .flood-stats { display:grid; grid-template-columns:repeat(2,1fr); gap:9px; align-content:start; }
    .flood-stat { padding:11px; background:rgba(255,255,255,.43); border:1px solid rgba(255,255,255,.65); border-radius:10px; }
    .flood-stat strong { display:block; color:var(--navy); font-size:18px; }
    .flood-stat span { display:block; margin-top:2px; color:var(--muted); font-size:11px; }
    .flood-caution { margin-top:11px; color:#6a4d16; font-size:11px; }
    .read-map { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-top:13px; }
    .read-card { padding:12px; background:rgba(255,255,255,.42); border:1px solid rgba(255,255,255,.70); border-radius:12px; box-shadow:0 7px 18px rgba(40,76,102,.05); }
    .read-card .read-title { display:flex; align-items:center; gap:7px; color:#2a4357; font-size:12px; font-weight:700; }
    .read-card p { margin:5px 0 0; color:var(--muted); font-size:11px; }
    .note-box { margin-top:13px; padding:11px 12px; color:#40596b; background:rgba(255,255,255,.43); border:1px solid rgba(255,255,255,.68); border-left:3px solid var(--amber); border-radius:0 10px 10px 0; font-size:12px; backdrop-filter:blur(10px); }
    .footer { display:flex; justify-content:space-between; gap:15px; margin-top:16px; padding:0 2px; color:#788999; font-size:11px; }
    .leaflet-control-layers { display:none; }
    .leaflet-popup-content { line-height:1.55; }
    @media (max-width:1020px) { .dashboard-grid { grid-template-columns:1fr; } .side-rail { grid-template-columns:repeat(3,1fr); align-items:start; } #map { height:500px; } }
    @media (max-width:760px) { .app-shell { padding:14px; } .topbar, .hero { display:block; } .top-meta { margin-top:12px; } .hero-summary { margin-top:16px; text-align:left; border-left:0; border-top:3px solid var(--blue); padding-left:0; padding-top:10px; } .kpis { grid-template-columns:repeat(2,1fr); } .side-rail, .bottom-grid, .advanced-grid, .flood-grid { grid-template-columns:1fr; } .read-map { grid-template-columns:1fr; } .footer { display:block; } .footer span { display:block; margin-top:4px; } }
    @media (max-width:480px) { .kpis { grid-template-columns:1fr; } .brand-title { font-size:16px; } #map { height:430px; } .map-toolbar { display:block; } .ghost-button { margin-top:9px; } }
  </style>
</head>
<body>
<main class="app-shell">
  <header class="topbar">
    <div class="brand"><div class="brand-mark">FM</div><div><div class="eyebrow">Farm management · satellite monitoring</div><h1 class="brand-title">Tirunelveli farm management dashboard</h1></div></div>
    <div class="top-meta"><span class="status">MONITORING ACTIVE</span><span>Satellite observations · 4 dates</span></div>
  </header>

  <section class="hero">
    <div><div class="eyebrow">Operational area</div><h2>Ambasamudram & Cheranmahadevi</h2><p>Support paddy and banana farm planning using crop maps, moisture, seasonal change and field-confidence indicators.</p></div>
    <div class="hero-summary"><strong>240.9</strong><span>km² monitored farm area</span></div>
  </section>

  <section class="kpis" aria-label="Key metrics">
    <div class="kpi navy"><div class="label">Managed area</div><div class="value">240.9 km²</div><div class="note">Selected monitoring window</div></div>
    <div class="kpi blue"><div class="label">Paddy area</div><div class="value">__PADDY_KM2__ km²</div><div class="note">__PADDY_PATCHES__ screened field units</div></div>
    <div class="kpi red"><div class="label">Banana area</div><div class="value">__BANANA_KM2__ km²</div><div class="note">__BANANA_PATCHES__ screened field units</div></div>
    <div class="kpi green"><div class="label">Farm field units</div><div class="value">__TOTAL_PATCHES__</div><div class="note">All mapped crop-management units</div></div>
    <div class="kpi navy"><div class="label">Potential flood impact</div><div class="value">__FLOOD_CROP_KM2__ km²</div><div class="note">Satellite risk indicator, not confirmed damage</div></div>
  </section>

  <section class="dashboard-grid">
    <section class="panel map-panel" aria-label="Interactive farm monitoring map">
      <div class="panel-head"><div><h3>Farm monitoring map</h3><p>Compare crop types, field confidence, seasonal change and moisture indicators.</p></div><span class="map-badge">WGS 84 · monitoring</span></div>
      <div class="map-toolbar">
        <div class="layer-toolbar-head">
          <button class="layer-menu-button" type="button" id="toggle-layer-panel" aria-expanded="true">☷ Map layers</button>
          <div class="layer-toolbar-actions"><button class="mini-button" type="button" id="select-all-layers">Select all</button><button class="mini-button" type="button" id="clear-layers">Clear</button><button class="ghost-button" type="button" id="fit-aoi">Zoom to farm area</button></div>
        </div>
        <div class="layer-panel" id="layer-panel">
          <div class="layer-panel-title">MANAGEMENT LAYERS · CLICK THE TICK TO TOGGLE</div>
          <div class="layer-toggles" role="group" aria-label="Map layers">
            <label class="layer-toggle"><input type="checkbox" id="toggle-rgb" checked><span class="layer-check"></span><span class="layer-dot rgb"></span>Satellite RGB</label>
            <label class="layer-toggle"><input type="checkbox" id="toggle-paddy" checked><span class="layer-check"></span><span class="layer-dot paddy"></span>Paddy fields</label>
            <label class="layer-toggle"><input type="checkbox" id="toggle-banana" checked><span class="layer-check"></span><span class="layer-dot banana"></span>Banana fields</label>
            <label class="layer-toggle"><input type="checkbox" id="toggle-other"><span class="layer-check"></span><span class="layer-dot other"></span>Other cropland</label>
            <label class="layer-toggle"><input type="checkbox" id="toggle-boundaries"><span class="layer-check"></span><span class="layer-dot boundary"></span>Field boundaries</label>
            <label class="layer-toggle"><input type="checkbox" id="toggle-confidence"><span class="layer-check"></span><span class="layer-dot confidence"></span>Confidence score</label>
            <label class="layer-toggle"><input type="checkbox" id="toggle-change"><span class="layer-check"></span><span class="layer-dot change"></span>Seasonal crop change</label>
            <label class="layer-toggle"><input type="checkbox" id="toggle-water"><span class="layer-check"></span><span class="layer-dot water"></span>Water/moisture indicator</label>
            <label class="layer-toggle"><input type="checkbox" id="toggle-flood"><span class="layer-check"></span><span class="layer-dot flood"></span>Potential flood impact</label>
            <label class="layer-toggle"><input type="checkbox" id="toggle-priority"><span class="layer-check"></span><span class="layer-dot priority"></span>Inspection priority</label>
          </div>
        </div>
      </div>
      <div id="map"></div>
      <div class="map-footer"><div class="legend"><span class="legend-item"><span class="legend-swatch" style="background:var(--blue)"></span>Paddy zone</span><span class="legend-item"><span class="legend-swatch" style="background:var(--red)"></span>Banana zone</span><span class="legend-item"><span class="legend-swatch" style="background:var(--green)"></span>Other crop zone</span></div><span>Click a field unit for details</span></div>
    </section>

    <aside class="side-rail">
      <section class="panel"><h3>Farm area summary</h3><p class="section-kicker">Screened crop area and field-unit count</p><div id="summary"></div><div class="mini-divider"></div><div class="total-line"><span>Total mapped farm area</span><strong id="total-area"></strong></div></section>
      <section class="panel"><h3>Taluk comparison</h3><p class="section-kicker">Estimated crop area by study zone</p><table class="side-table"><thead><tr><th>Study zone</th><th>Paddy km²</th><th>Banana km²</th></tr></thead><tbody id="side-table"></tbody></table></section>
      <section class="panel"><h3>Farm monitoring workflow</h3><p class="section-kicker">How satellite indicators support field decisions</p><div class="workflow"><div class="step"><div class="step-no">1</div><div><strong>Prepare satellite observations</strong><span>Cloud-masked Sentinel‑2 dates are combined.</span></div></div><div class="step"><div class="step-no">2</div><div><strong>Measure crop condition</strong><span>NDVI, NDWI and NDMI indicate vigor and moisture.</span></div></div><div class="step"><div class="step-no">3</div><div><strong>Identify crop patterns</strong><span>Seasonal response screens paddy and persistent greenness screens banana.</span></div></div><div class="step"><div class="step-no">4</div><div><strong>Create field units</strong><span>SNIC groups similar pixels into field-like management units.</span></div></div></div></section>
    </aside>
  </section>

  <section class="bottom-grid">
    <section class="panel"><h3>Management interpretation</h3><div class="read-map"><div class="read-card"><div class="read-title"><span class="legend-swatch" style="background:var(--blue)"></span>Blue zones</div><p>Paddy management zones identified from seasonal vegetation and moisture variation.</p></div><div class="read-card"><div class="read-title"><span class="legend-swatch" style="background:var(--red)"></span>Red zones</div><p>Banana management zones identified from persistent vegetation and moisture.</p></div><div class="read-card"><div class="read-title"><span class="legend-swatch" style="background:var(--green)"></span>Green zones</div><p>Other cropland zones that need separate field verification.</p></div></div></section>
    <section class="panel"><h3>Farm decision notes</h3><p class="section-kicker">Use the dashboard to prioritize field checks and farm planning.</p><div class="note-box">Field polygons are remote-sensing management units, not legal cadastral boundaries. Confirm crop labels with GPS or field observations before irrigation, input, harvest or crop-change decisions.</div><div class="note-box" style="border-left-color:var(--blue)">Recommended next action: select low-confidence or changed fields for targeted inspection and update the farm record.</div></section>
  </section>

  <section class="panel gee-app-panel">
    __GEE_PANEL__
  </section>

  <section class="advanced-grid">
    <section class="panel"><h3>Crop condition trend</h3><p class="section-kicker">NDVI response through the monitoring dates</p><div id="phenology-chart" class="chart-wrap" role="img" aria-label="Crop condition trend showing NDVI for paddy and banana fields"></div><div class="legend"><span class="legend-item"><span class="legend-swatch" style="background:var(--blue)"></span>Paddy NDVI</span><span class="legend-item"><span class="legend-swatch" style="background:var(--red)"></span>Banana NDVI</span><span class="legend-item"><span class="legend-swatch" style="background:var(--navy)"></span>Area NDVI</span></div></section>
    <section class="panel"><h3>Seasonal field change</h3><p class="section-kicker">Early- to late-season crop-condition difference</p><img class="change-image" src="__CHANGE_URI__" alt="Seasonal field change map showing greening, decline and stable areas"><div class="change-stats"><div class="change-stat"><strong>__GREENING_KM2__</strong><span>Improving km²</span></div><div class="change-stat"><strong>__DECLINE_KM2__</strong><span>Declining km²</span></div><div class="change-stat"><strong>__STABLE_KM2__</strong><span>Stable km²</span></div></div></section>
  </section>

  <section class="panel flood-panel"><div class="panel-head"><div><h3>Flood impact and inspection priority</h3><p>Potential inundation is screened from water expansion and vegetation decline; confirm findings with radar and field inspection.</p></div><span class="map-badge">Risk indicator</span></div><div class="flood-grid"><img class="flood-image" src="__FLOOD_URI__" alt="Potential flood impact map: red paddy, purple banana, blue water"><div><div class="flood-stats"><div class="flood-stat"><strong>__FLOOD_TOTAL_KM2__ km²</strong><span>Potential inundation</span></div><div class="flood-stat"><strong>__FLOOD_PADDY_KM2__ km²</strong><span>Paddy potentially affected</span></div><div class="flood-stat"><strong>__FLOOD_BANANA_KM2__ km²</strong><span>Banana potentially affected</span></div><div class="flood-stat"><strong>__HIGH_PRIORITY__</strong><span>High-priority field units</span></div><div class="flood-stat"><strong>__MEDIUM_PRIORITY__</strong><span>Medium-priority field units</span></div><div class="flood-stat"><strong>__LOW_PRIORITY__</strong><span>Low-priority field units</span></div></div><p class="flood-caution">__FLOOD_METHOD__. This is not a confirmed crop-damage estimate.</p></div></div></section>

  <section class="panel" style="margin-top:16px;padding:17px"><h3>Decision-support layers</h3><p class="section-kicker">Use these indicators to prioritize irrigation checks, field visits and crop monitoring.</p><div class="feature-grid"><div class="feature-card"><span class="feature-status">Local + live</span><strong>Field confidence score</strong><span>0–100 explainable score for prioritizing verification.</span></div><div class="feature-card"><span class="feature-status">Live GEE App</span><strong>Radar and optical fusion</strong><span>Sentinel‑1 VV and Sentinel‑2 signals support paddy monitoring.</span></div><div class="feature-card"><span class="feature-status">Local proxy + live</span><strong>Water-access indicator</strong><span>Moisture proxy is available above; exact water distance is available in the live App.</span></div><div class="feature-card"><span class="feature-status">Flood-risk screening</span><strong>Flood impact and priority</strong><span>Water expansion and vegetation decline identify field units for inspection.</span></div><div class="feature-card"><span class="feature-status">Optional validation</span><strong>Random Forest comparison</strong><span>Use labelled field samples for model-based crop verification.</span></div></div></section>

  <footer class="footer"><span>Data: open Sentinel‑2 surface reflectance · Processing: Google Earth Engine workflow</span><span>Built for field prioritization and crop planning</span></footer>
</main>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const bbox = [[8.64,77.42],[8.75,77.60]];
const summary = __SUMMARY__;
const sideSummary = __SIDE_SUMMARY__;
const phenology = __PHENOLOGY__;
const changeSummary = __CHANGE_SUMMARY__;
const floodSummary = __FLOOD_SUMMARY__;
const parcels = __GEOJSON__;
const colors = {paddy:'#287dd2', banana:'#dc4637', other_cropland:'#5fb45a'};
const labels = {paddy:'Paddy field', banana:'Banana field', other_cropland:'Other crop'};
const map = L.map('map', {zoomControl:false}).fitBounds(bbox);
L.control.zoom({position:'bottomright'}).addTo(map);
const rgb = L.imageOverlay('__TCI_URI__',bbox,{opacity:.72}).addTo(map);
const change = L.imageOverlay('__CHANGE_URI__', bbox, {opacity:.68});
const water = L.imageOverlay('__WATER_URI__', bbox, {opacity:.62});
const flood = L.imageOverlay('__FLOOD_URI__', bbox, {opacity:.72});
const floodDetails = p => '<br>Flood signal: '+(p.flood_status === 'potentially_affected' ? 'Potentially affected' : 'No potential inundation signal')+'<br>Estimated inundation: '+Number(p.flooded_percent || 0).toFixed(1)+'%<br>Vegetation drop: '+Number(p.vegetation_drop || 0).toFixed(3)+'<br>Inspection priority: '+(p.flood_risk_level || 'low').toUpperCase();
const layerFor = (kind) => L.geoJSON(parcels,{filter:f=>f.properties.class===kind,style:{color:colors[kind],weight:1,fillColor:colors[kind],fillOpacity:.58},onEachFeature:(f,l)=>l.bindPopup('<b>'+f.properties.parcel_id+'</b><br>'+labels[kind]+'<br>'+f.properties.area_ha+' ha<br>Field confidence: '+f.properties.confidence+'<br>Management score: '+f.properties.confidence_score+'/100'+floodDetails(f.properties))});
const paddy = layerFor('paddy').addTo(map);
const banana = layerFor('banana').addTo(map);
const other = layerFor('other_cropland');
const all = L.geoJSON(parcels,{style:{color:'#ffffff',weight:.8,fillOpacity:0},onEachFeature:(f,l)=>l.bindPopup('<b>'+f.properties.parcel_id+'</b><br>'+labels[f.properties.class]+'<br>'+f.properties.area_ha+' ha')});
function confidenceColor(score) {
  if (score < 40) return '#deebf7';
  if (score < 70) return '#6baed6';
  return '#08519c';
}
const confidenceLayer = L.geoJSON(parcels,{style:f=>{const c=confidenceColor(Number(f.properties.confidence_score||0)); return {color:c,weight:1,fillColor:c,fillOpacity:.65};},onEachFeature:(f,l)=>l.bindPopup('<b>'+f.properties.parcel_id+'</b><br>'+labels[f.properties.class]+'<br>Confidence score: '+f.properties.confidence_score+'/100<br>Confidence: '+f.properties.confidence)});
function priorityColor(level) {
  if (level === 'high') return '#d73027';
  if (level === 'medium') return '#fdae61';
  return '#fee08b';
}
const priorityLayer = L.geoJSON(parcels,{filter:f=>f.properties.flood_status === 'potentially_affected',style:f=>{const c=priorityColor(f.properties.flood_risk_level); return {color:c,weight:1.5,fillColor:c,fillOpacity:.72};},onEachFeature:(f,l)=>l.bindPopup('<b>Inspection priority · '+String(f.properties.flood_risk_level || 'low').toUpperCase()+'</b><br>'+f.properties.parcel_id+'<br>'+labels[f.properties.class]+'<br>Potential inundation: '+Number(f.properties.flooded_percent || 0).toFixed(1)+'%'+floodDetails(f.properties))});
L.marker([8.67254,77.44476]).addTo(map).bindTooltip('Ambasamudram');
L.marker([8.68879,77.55094]).addTo(map).bindTooltip('Cheranmahadevi');
const toggle = (id, layer) => document.getElementById(id).addEventListener('change', e => e.target.checked ? layer.addTo(map) : map.removeLayer(layer));
toggle('toggle-rgb', rgb); toggle('toggle-paddy', paddy); toggle('toggle-banana', banana); toggle('toggle-other', other); toggle('toggle-boundaries', all);
toggle('toggle-confidence', confidenceLayer); toggle('toggle-change', change); toggle('toggle-water', water); toggle('toggle-flood', flood); toggle('toggle-priority', priorityLayer);
document.getElementById('fit-aoi').addEventListener('click', () => map.fitBounds(bbox));
const layerIds = ['toggle-rgb','toggle-paddy','toggle-banana','toggle-other','toggle-boundaries','toggle-confidence','toggle-change','toggle-water','toggle-flood','toggle-priority'];
const layerPanel = document.getElementById('layer-panel');
const layerMenuButton = document.getElementById('toggle-layer-panel');
layerMenuButton.addEventListener('click', () => {
  const isCollapsed = layerPanel.classList.toggle('is-collapsed');
  layerMenuButton.setAttribute('aria-expanded', String(!isCollapsed));
  layerMenuButton.textContent = isCollapsed ? '☷ Show map layers' : '☷ Map layers';
});
document.getElementById('select-all-layers').addEventListener('click', () => {
  layerIds.forEach(id => { const box = document.getElementById(id); if (!box.checked) box.click(); });
});
document.getElementById('clear-layers').addEventListener('click', () => {
  layerIds.forEach(id => { const box = document.getElementById(id); if (box.checked) box.click(); });
});
const totalArea = Object.values(summary).reduce((total, item) => total + item.area_km2, 0);
document.getElementById('total-area').textContent = totalArea.toFixed(2) + ' km²';
document.getElementById('summary').innerHTML = Object.keys(summary).map(k=>{const pct = totalArea ? (summary[k].area_km2/totalArea*100) : 0; return '<div class="summary-item"><div class="summary-line"><span class="summary-label"><span class="legend-swatch" style="background:'+colors[k]+'"></span>'+labels[k]+'</span><span class="summary-value">'+summary[k].area_km2.toFixed(2)+' km²</span></div><div class="bar-track"><div class="bar" style="width:'+pct.toFixed(1)+'%;background:'+colors[k]+'"></div></div><div class="summary-meta"><span>'+pct.toFixed(1)+'% of mapped area</span><span>'+summary[k].patches+' patches</span></div></div>';}).join('');
document.getElementById('side-table').innerHTML = Object.keys(sideSummary).map(s=>'<tr><td>'+s.replace('-side','').replace(/^./, c => c.toUpperCase())+'</td><td>'+sideSummary[s].paddy.toFixed(2)+'</td><td>'+sideSummary[s].banana.toFixed(2)+'</td></tr>').join('');
const chartHost = document.getElementById('phenology-chart');
function drawPhenology() {
  const width = Math.max(chartHost.clientWidth, 320), height = 210, left = 30, right = 10, top = 10, bottom = 32;
  const plotW = width - left - right, plotH = height - top - bottom;
  const values = phenology.flatMap(d => [d.paddy_ndvi || 0, d.banana_ndvi || 0, d.ndvi || 0]);
  const maxY = Math.max(0.5, Math.ceil(Math.max(...values) * 10) / 10);
  const x = i => left + (phenology.length === 1 ? plotW / 2 : i * plotW / (phenology.length - 1));
  const y = value => top + plotH - (value / maxY) * plotH;
  const line = (key, color) => '<polyline class="chart-line" stroke="'+color+'" points="'+phenology.map((d,i)=>x(i).toFixed(1)+','+y(d[key] || 0).toFixed(1)).join(' ')+'"></polyline>';
  const points = (key, color) => phenology.map((d,i)=>'<circle cx="'+x(i).toFixed(1)+'" cy="'+y(d[key] || 0).toFixed(1)+'" r="3.5" fill="'+color+'"></circle>').join('');
  const grid = [0, maxY/2, maxY].map(v=>'<line class="chart-grid" x1="'+left+'" x2="'+(width-right)+'" y1="'+y(v).toFixed(1)+'" y2="'+y(v).toFixed(1)+'"></line><text class="chart-label" x="2" y="'+(y(v)+3).toFixed(1)+'">'+v.toFixed(1)+'</text>').join('');
  const labelsX = phenology.map((d,i)=>'<text class="chart-label" text-anchor="middle" x="'+x(i).toFixed(1)+'" y="'+(height-9)+'">'+d.date.slice(5)+'</text>').join('');
  chartHost.innerHTML = '<svg viewBox="0 0 '+width+' '+height+'" role="img" aria-label="NDVI phenology lines for paddy, banana and the study area">'+grid+'<line class="chart-axis" x1="'+left+'" x2="'+left+'" y1="'+top+'" y2="'+(height-bottom)+'"></line><line class="chart-axis" x1="'+left+'" x2="'+(width-right)+'" y1="'+(height-bottom)+'" y2="'+(height-bottom)+'"></line>'+line('paddy_ndvi','#287dd2')+points('paddy_ndvi','#287dd2')+line('banana_ndvi','#dc4637')+points('banana_ndvi','#dc4637')+line('ndvi','#102c45')+points('ndvi','#102c45')+labelsX+'</svg>';
}
drawPhenology();
window.addEventListener('resize', drawPhenology);
setTimeout(() => map.invalidateSize(), 250);
</script>
</body></html>'''

html = html.replace('__TCI_URI__', tci_uri)
html = html.replace('__GEOJSON__', geojson_text)
html = html.replace('__SUMMARY__', summary_text)
html = html.replace('__SIDE_SUMMARY__', side_text)
html = html.replace('__PHENOLOGY__', phenology_text)
html = html.replace('__CHANGE_SUMMARY__', change_text)
html = html.replace('__FLOOD_SUMMARY__', flood_text)
html = html.replace('__CHANGE_URI__', change_uri)
html = html.replace('__WATER_URI__', water_uri)
html = html.replace('__FLOOD_URI__', flood_uri)
html = html.replace('__GEE_PANEL__', gee_panel_html)
html = html.replace('__GEE_APP_URL__', GEE_APP_URL)
html = html.replace('__GREENING_KM2__', f"{change_summary['greening_km2']:.2f}")
html = html.replace('__DECLINE_KM2__', f"{change_summary['decline_km2']:.2f}")
html = html.replace('__STABLE_KM2__', f"{change_summary['stable_km2']:.2f}")
flood_crop_km2 = flood_summary['paddy_affected_km2'] + flood_summary['banana_affected_km2']
html = html.replace('__FLOOD_CROP_KM2__', f"{flood_crop_km2:.2f}")
html = html.replace('__FLOOD_TOTAL_KM2__', f"{flood_summary['potential_inundation_km2']:.2f}")
html = html.replace('__FLOOD_PADDY_KM2__', f"{flood_summary['paddy_affected_km2']:.2f}")
html = html.replace('__FLOOD_BANANA_KM2__', f"{flood_summary['banana_affected_km2']:.2f}")
html = html.replace('__HIGH_PRIORITY__', str(flood_summary['high_priority_fields']))
html = html.replace('__MEDIUM_PRIORITY__', str(flood_summary['medium_priority_fields']))
html = html.replace('__LOW_PRIORITY__', str(flood_summary['low_priority_fields']))
html = html.replace('__FLOOD_METHOD__', flood_summary['method'])
html = html.replace('__PADDY_KM2__', f"{summary['paddy']['area_km2']:.2f}")
html = html.replace('__BANANA_KM2__', f"{summary['banana']['area_km2']:.2f}")
html = html.replace('__PADDY_PATCHES__', str(summary['paddy']['patches']))
html = html.replace('__BANANA_PATCHES__', str(summary['banana']['patches']))
html = html.replace('__TOTAL_PATCHES__', str(len(features)))
(OUT / 'tirunelveli_dashboard.html').write_text(html, encoding='utf-8')
print('Created tirunelveli_dashboard.html')
