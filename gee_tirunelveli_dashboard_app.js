// Tirunelveli crop intelligence dashboard for Google Earth Engine Apps
// Paste this file into the GEE Code Editor, run it, then publish it from Apps.

// -----------------------------------------------------------------------------
// 1. Study area and parameters
// -----------------------------------------------------------------------------
var aoi = ee.Geometry.Rectangle([77.42, 8.64, 77.60, 8.75], null, false);
var scale = 10;
var cloudProbabilityLimit = 40;
var waterDistanceLimitM = 1000;
var radarWaterVvLimit = -16;
var radarChangeLimitDb = 3;
var floodNdwiMinimum = 0.05;
var floodNdwiIncrease = 0.12;
var floodNdviDrop = 0.15;
var floodVvDropDb = 1.5;
var chartPoint = ee.Geometry.Point([77.50, 8.69]);

var bananaMinMedianNdvi = 0.32;
var bananaMinNdvi = 0.20;
var bananaMaxAmplitude = 0.32;
var bananaMinMedianNdmi = 0.03;
var paddyMinPeakNdvi = 0.40;
var paddyMinAmplitude = 0.22;
var paddyMinMedianNdvi = 0.22;
var otherCropMinMedianNdvi = 0.28;

var periods = [
  {name: 'Mar 2026', start: '2026-03-01', end: '2026-04-01'},
  {name: 'Apr 2026', start: '2026-04-01', end: '2026-05-01'},
  {name: 'Sep early 2026', start: '2026-09-01', end: '2026-09-16'},
  {name: 'Sep late 2026', start: '2026-09-16', end: '2026-10-01'}
];

// -----------------------------------------------------------------------------
// 2. Sentinel-2 composites and indices
// -----------------------------------------------------------------------------
var s2Sr = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(aoi)
  .filterDate('2026-03-01', '2026-10-01')
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 40));

var s2CloudProbability = ee.ImageCollection('COPERNICUS/S2_CLOUD_PROBABILITY')
  .filterBounds(aoi)
  .filterDate('2026-03-01', '2026-10-01');

var joined = ee.Join.saveFirst('cloud_probability').apply({
  primary: s2Sr,
  secondary: s2CloudProbability,
  condition: ee.Filter.equals({
    leftField: 'system:index',
    rightField: 'system:index'
  })
});

function maskAndAddIndices(image) {
  var probability = ee.Image(image.get('cloud_probability')).select('probability');
  var scl = image.select('SCL');
  var clear = probability.lt(cloudProbabilityLimit)
    .and(scl.neq(3)).and(scl.neq(8)).and(scl.neq(9))
    .and(scl.neq(10)).and(scl.neq(11));
  var reflectance = image.updateMask(clear)
    .select(['B2', 'B3', 'B4', 'B8', 'B11']).divide(10000);
  var ndvi = reflectance.normalizedDifference(['B8', 'B4']).rename('NDVI');
  var ndwi = reflectance.normalizedDifference(['B3', 'B8']).rename('NDWI');
  var ndmi = reflectance.normalizedDifference(['B8', 'B11']).rename('NDMI');
  return reflectance.addBands([ndvi, ndwi, ndmi])
    .copyProperties(image, ['system:index', 'system:time_start']);
}

var s2 = ee.ImageCollection(joined).map(maskAndAddIndices);

function seasonalComposite(period) {
  return s2.filterDate(period.start, period.end).median().clip(aoi);
}

var composites = periods.map(seasonalComposite);
var ndviStack = ee.Image.cat(periods.map(function(period, index) {
  return ee.Image(composites[index]).select('NDVI').rename('NDVI_' + index);
}));
var ndmiStack = ee.Image.cat(periods.map(function(period, index) {
  return ee.Image(composites[index]).select('NDMI').rename('NDMI_' + index);
}));

var ndviMin = ndviStack.reduce(ee.Reducer.min()).rename('NDVI_min');
var ndviMax = ndviStack.reduce(ee.Reducer.max()).rename('NDVI_max');
var ndviMedian = ndviStack.reduce(ee.Reducer.median()).rename('NDVI_median');
var ndviAmplitude = ndviMax.subtract(ndviMin).rename('NDVI_amplitude');
var ndmiMedian = ndmiStack.reduce(ee.Reducer.median()).rename('NDMI_median');
var valid = ndviStack.reduce(ee.Reducer.count()).eq(periods.length);

// -----------------------------------------------------------------------------
// 3. Crop candidates and advanced analysis layers
// -----------------------------------------------------------------------------
var banana = valid.and(ndviMedian.gte(bananaMinMedianNdvi))
  .and(ndviMin.gte(bananaMinNdvi))
  .and(ndviAmplitude.lte(bananaMaxAmplitude))
  .and(ndmiMedian.gte(bananaMinMedianNdmi));

var paddy = valid.and(banana.not())
  .and(ndviMax.gte(paddyMinPeakNdvi))
  .and(ndviAmplitude.gte(paddyMinAmplitude))
  .and(ndviMedian.gte(paddyMinMedianNdvi));

var otherCropland = valid.and(banana.not()).and(paddy.not())
  .and(ndviMedian.gte(otherCropMinMedianNdvi))
  .and(ndviMax.gte(paddyMinPeakNdvi));

var cropClass = ee.Image(0).rename('crop_class')
  .where(paddy, 1).where(banana, 2).where(otherCropland, 3).toInt8();

var bananaConfidence = ee.Image(0)
  .add(ndviMedian.subtract(bananaMinMedianNdvi).divide(0.30).clamp(0, 1))
  .add(ndviMin.subtract(bananaMinNdvi).divide(0.30).clamp(0, 1))
  .add(ee.Image(bananaMaxAmplitude).subtract(ndviAmplitude)
    .divide(bananaMaxAmplitude).clamp(0, 1))
  .add(ndmiMedian.subtract(bananaMinMedianNdmi).divide(0.30).clamp(0, 1))
  .divide(4).multiply(100).updateMask(banana);

var paddyConfidence = ee.Image(0)
  .add(ndviMax.subtract(paddyMinPeakNdvi).divide(0.30).clamp(0, 1))
  .add(ndviAmplitude.subtract(paddyMinAmplitude).divide(0.40).clamp(0, 1))
  .add(ndviMedian.subtract(paddyMinMedianNdvi).divide(0.35).clamp(0, 1))
  .divide(3).multiply(100).updateMask(paddy);

var otherConfidence = ndviMedian.subtract(otherCropMinMedianNdvi)
  .divide(0.40).clamp(0, 1).multiply(100).updateMask(otherCropland);

var cropConfidence = paddyConfidence.unmask(0)
  .where(banana, bananaConfidence.unmask(0))
  .where(otherCropland, otherConfidence.unmask(0))
  .updateMask(cropClass.gt(0)).rename('crop_confidence');

var s1 = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(aoi).filterDate('2026-03-01', '2026-10-01')
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
  .select(['VV', 'VH']);
var s1Early = s1.filterDate('2026-03-01', '2026-05-01').median().clip(aoi);
var s1Late = s1.filterDate('2026-09-01', '2026-10-01').median().clip(aoi);
var s1VvChange = s1Late.select('VV').subtract(s1Early.select('VV')).abs();
var s1Support = s1Late.select('VV').lt(radarWaterVvLimit)
  .or(s1VvChange.gte(radarChangeLimitDb));
var paddyFusion = paddy.and(s1Support).rename('paddy_s1_s2_fusion');

var ndviChange = ee.Image(composites[3]).select('NDVI')
  .subtract(ee.Image(composites[0]).select('NDVI')).rename('NDVI_change');
var changeClass = ee.Image(0).where(ndviChange.gte(0.20), 1)
  .where(ndviChange.lte(-0.20), 2)
  .where(ndviChange.abs().lt(0.20), 3)
  .updateMask(valid).rename('change_class');

var waterOccurrence = ee.Image('JRC/GSW1_4/GlobalSurfaceWater')
  .select('occurrence').clip(aoi);
var surfaceWater = waterOccurrence.gte(50);
var distanceToWater = surfaceWater.fastDistanceTransform(128)
  .sqrt().multiply(30).rename('distance_to_water_m');
var paddyNearWater = paddy.and(distanceToWater.lte(waterDistanceLimitM));

// Flood module. For a real flood, change these pre-event and during-event
// dates to match the event being assessed.
var floodPreOptical = ee.Image(composites[2]);
var floodDuringOptical = ee.Image(composites[3]);
var floodNdwiChange = floodDuringOptical.select('NDWI')
  .subtract(floodPreOptical.select('NDWI')).rename('flood_NDWI_change');
var floodNdviDecline = floodPreOptical.select('NDVI')
  .subtract(floodDuringOptical.select('NDVI')).rename('flood_NDVI_decline');
var opticalFlood = floodDuringOptical.select('NDWI').gte(floodNdwiMinimum)
  .and(floodNdwiChange.gte(floodNdwiIncrease));

var s1FloodPre = s1.filterDate('2026-09-01', '2026-09-16').median().clip(aoi);
var s1FloodDuring = s1.filterDate('2026-09-16', '2026-10-01').median().clip(aoi);
var s1FloodVvDrop = s1FloodPre.select('VV').subtract(s1FloodDuring.select('VV'))
  .rename('flood_VV_drop');
var radarFlood = s1FloodDuring.select('VV').lt(radarWaterVvLimit)
  .and(s1FloodVvDrop.gte(floodVvDropDb));

var floodCandidate = opticalFlood.unmask(0).or(radarFlood.unmask(0))
  .and(valid).rename('potential_flood');
var floodRiskScore = ee.Image(45)
  .add(floodNdwiChange.subtract(floodNdwiIncrease).divide(0.25).clamp(0, 1).multiply(25))
  .add(floodNdviDecline.subtract(0.05).divide(0.30).clamp(0, 1).multiply(20))
  .add(s1FloodVvDrop.subtract(floodVvDropDb).divide(5).clamp(0, 1).multiply(10))
  .clamp(0, 100).updateMask(floodCandidate).rename('flood_risk_score');
var paddyFlood = paddy.and(floodCandidate).rename('paddy_potentially_affected');
var bananaFlood = banana.and(floodCandidate).rename('banana_potentially_affected');
var floodPriority = ee.Image(1).where(floodRiskScore.gte(30), 2)
  .where(floodRiskScore.gte(65), 3).updateMask(paddyFlood.or(bananaFlood))
  .rename('inspection_priority');

// -----------------------------------------------------------------------------
// 4. Dashboard UI
// -----------------------------------------------------------------------------
var map = ui.Map();
map.setOptions('HYBRID');
map.centerObject(aoi, 12);
map.setControlVisibility({all: false, zoomControl: true, mapTypeControl: true});

function addLayer(image, vis, name, shown, opacity) {
  var layer = ui.Map.Layer(image, vis, name, shown, opacity || 1);
  map.layers().add(layer);
  return layer;
}

var rgbLayer = addLayer(composites[3], {
  bands: ['B4', 'B3', 'B2'], min: 0, max: 0.30, gamma: 1.15
}, 'Sentinel-2 RGB', true, 1);
var paddyLayer = addLayer(paddy.selfMask(), {palette: ['287dd2']},
  'Paddy candidates - blue', true, 0.65);
var bananaLayer = addLayer(banana.selfMask(), {palette: ['dc4637']},
  'Banana candidates - red', true, 0.65);
var otherLayer = addLayer(otherCropland.selfMask(), {palette: ['5fb45a']},
  'Other cropland - green', false, 0.60);
var confidenceLayer = addLayer(cropConfidence, {
  min: 0, max: 100, palette: ['f7fbff', '9ecae1', '2171b5']
}, 'Confidence score 0-100', false, 0.75);
var radarLayer = addLayer(s1Late.select('VV'), {
  min: -25, max: 0, palette: ['081d58', '225ea8', '41b6c4', 'ffffcc']
}, 'Sentinel-1 VV', false, 0.75);
var fusionLayer = addLayer(paddyFusion.selfMask(), {palette: ['7b3294']},
  'Paddy after Sentinel-1 fusion', false, 0.75);
var changeLayer = addLayer(changeClass, {
  min: 1, max: 3, palette: ['31a354', 'd73027', 'bdbdbd']
}, 'Change: greening / decline / stable', false, 0.65);
var waterLayer = addLayer(distanceToWater, {
  min: 0, max: 3000, palette: ['084081', '7bccc4', 'f7fcf0']
}, 'Distance to surface water', false, 0.65);
var paddyWaterLayer = addLayer(paddyNearWater.selfMask(), {palette: ['00bfc4']},
  'Paddy within 1 km of water', false, 0.75);
var floodLayer = addLayer(floodCandidate.selfMask(), {palette: ['0969da']},
  'Potential flood / inundation', false, 0.72);
var paddyFloodLayer = addLayer(paddyFlood.selfMask(), {palette: ['d73027']},
  'Potentially affected paddy', false, 0.80);
var bananaFloodLayer = addLayer(bananaFlood.selfMask(), {palette: ['7b3294']},
  'Potentially affected banana', false, 0.80);
var floodPriorityLayer = addLayer(floodPriority, {
  min: 1, max: 3, palette: ['fee08b', 'fdae61', 'd73027']
}, 'Inspection priority: low / medium / high', false, 0.82);
var aoiLayer = addLayer(aoi, {color: 'yellow'}, 'Study window', false, 1);

var title = ui.Label('TIRUNELVELI FARM AND FLOOD MANAGEMENT', {
  fontSize: '18px', fontWeight: 'bold', color: '#102c45', margin: '0 0 4px 0'
});
var subtitle = ui.Label('Ambasamudram and Cheranmahadevi · satellite crop monitoring', {
  fontSize: '12px', color: '#5f7385', margin: '0 0 12px 0'
});
var intro = ui.Label('Support crop and flood-response planning using paddy/banana zones, moisture, radar, seasonal change and inspection priority indicators.', {
  fontSize: '12px', color: '#3b5367', whiteSpace: 'normal', margin: '0 0 12px 0'
});

function checkbox(text, layer) {
  var box = ui.Checkbox({label: text, value: layer.getShown(),
    onChange: function(value) { layer.setShown(value); }});
  box.style().set({fontSize: '12px', margin: '3px 0'});
  return box;
}

var layerHeader = ui.Label('MANAGEMENT LAYERS', {
  fontSize: '11px', fontWeight: 'bold', color: '#287dd2', margin: '10px 0 5px 0'
});
var layerPanel = ui.Panel([
  checkbox('Sentinel-2 RGB', rgbLayer),
  checkbox('Paddy fields (blue)', paddyLayer),
  checkbox('Banana fields (red)', bananaLayer),
  checkbox('Other crop zone (green)', otherLayer),
  checkbox('Field confidence score', confidenceLayer),
  checkbox('Sentinel-1 VV radar', radarLayer),
  checkbox('Paddy after S1-S2 fusion', fusionLayer),
  checkbox('Seasonal crop change', changeLayer),
  checkbox('Water/moisture indicator', waterLayer),
  checkbox('Paddy within 1 km of water', paddyWaterLayer),
  checkbox('Potential flood / inundation', floodLayer),
  checkbox('Potentially affected paddy', paddyFloodLayer),
  checkbox('Potentially affected banana', bananaFloodLayer),
  checkbox('Inspection priority', floodPriorityLayer),
  checkbox('Farm monitoring area', aoiLayer)
], ui.Panel.Layout.flow('vertical'));

var statsHeader = ui.Label('FARM AREA SUMMARY', {
  fontSize: '11px', fontWeight: 'bold', color: '#287dd2', margin: '14px 0 5px 0'
});
var statsLabel = ui.Label('Calculating crop area…', {
  fontSize: '12px', color: '#526b7e', whiteSpace: 'pre', margin: '0 0 8px 0'
});
var actionPanel = ui.Panel([
  ui.Button({
    label: 'Zoom to farm area',
    onClick: function() { map.centerObject(aoi, 11); },
    style: {fontSize: '11px', margin: '4px 4px 4px 0', color: '#287dd2'}
  }),
  ui.Button({
    label: 'Reset map message',
    onClick: function() { statsLabel.setValue('Select a field on the map for crop condition and confidence.'); },
    style: {fontSize: '11px', margin: '4px 0', color: '#287dd2'}
  })
], ui.Panel.Layout.flow('horizontal'), {margin: '0 0 5px 0'});
var areaSummary = ee.Image.pixelArea().addBands(cropClass).reduceRegion({
  reducer: ee.Reducer.sum().group({groupField: 1, groupName: 'crop_class'}),
  geometry: aoi, scale: scale, maxPixels: 1e10, tileScale: 4
});
areaSummary.evaluate(function(result) {
  var lines = ['Study window: approximately 240.9 km²'];
  var groups = (result && result.groups) || [];
  groups.forEach(function(item) {
    var label = ['Non-crop', 'Paddy', 'Banana', 'Other cropland'][item.crop_class] || 'Class ' + item.crop_class;
    lines.push(label + ': ' + (item.sum / 1e6).toFixed(2) + ' km²');
  });
  statsLabel.setValue(lines.join('\n'));
});

var floodHeader = ui.Label('FLOOD IMPACT SCREENING', {
  fontSize: '11px', fontWeight: 'bold', color: '#287dd2', margin: '12px 0 5px 0'
});
var floodLabel = ui.Label('Calculating potential inundation…', {
  fontSize: '12px', color: '#526b7e', whiteSpace: 'pre', margin: '0 0 8px 0'
});
var floodAreaSummary = ee.Image.cat([
  ee.Image.pixelArea().updateMask(floodCandidate).rename('potential_flood_m2'),
  ee.Image.pixelArea().updateMask(paddyFlood).rename('paddy_affected_m2'),
  ee.Image.pixelArea().updateMask(bananaFlood).rename('banana_affected_m2'),
  ee.Image.pixelArea().updateMask(floodPriority.eq(3)).rename('high_priority_m2')
]).reduceRegion({reducer: ee.Reducer.sum(), geometry: aoi, scale: scale, maxPixels: 1e10, tileScale: 4});
floodAreaSummary.evaluate(function(result) {
  result = result || {};
  var lines = [
    'Potential inundation: ' + ((result.potential_flood_m2 || 0) / 1e6).toFixed(2) + ' km²',
    'Paddy potentially affected: ' + ((result.paddy_affected_m2 || 0) / 1e6).toFixed(2) + ' km²',
    'Banana potentially affected: ' + ((result.banana_affected_m2 || 0) / 1e6).toFixed(2) + ' km²',
    'High-priority crop area: ' + ((result.high_priority_m2 || 0) / 1e6).toFixed(2) + ' km²'
  ];
  floodLabel.setValue(lines.join('\n'));
});

var methodHeader = ui.Label('FARM MONITORING WORKFLOW', {
  fontSize: '11px', fontWeight: 'bold', color: '#287dd2', margin: '12px 0 5px 0'
});
var methodLabel = ui.Label(
  '1  Prepare cloud-masked satellite observations\n' +
  '2  Measure crop vigor and moisture\n' +
  '3  Identify paddy and banana field patterns\n' +
  '4  Detect potential flood water using Sentinel-1 and Sentinel-2\n' +
  '5  Rank crop field units for inspection priority',
  {fontSize: '12px', color: '#526b7e', whiteSpace: 'pre', margin: '0 0 8px 0'}
);

var chartHeader = ui.Label('CROP CONDITION TREND', {
  fontSize: '11px', fontWeight: 'bold', color: '#287dd2', margin: '12px 0 4px 0'
});
var seasonalStats = ee.FeatureCollection(periods.map(function(period, index) {
  var values = ee.Image(composites[index]).select(['NDVI', 'NDMI']).reduceRegion({
    reducer: ee.Reducer.mean(), geometry: chartPoint, scale: scale, maxPixels: 1e7
  });
  return ee.Feature(null, values).set('period', period.name);
}));
var phenologyChart = ui.Chart.feature.byFeature(
  seasonalStats, 'period', ['NDVI', 'NDMI']
).setChartType('LineChart').setOptions({
  title: 'NDVI / NDMI seasonal response',
  legend: {position: 'bottom'},
  hAxis: {textStyle: {fontSize: 9}},
  vAxis: {title: 'Index', viewWindow: {min: -0.3, max: 0.8}},
  colors: ['#1b9e77', '#7570b3'],
  lineWidth: 2, pointSize: 4, height: 190
});

var note = ui.Label(
  'Management note: mapped field units are remote-sensing objects, not legal cadastral boundaries. Flood results are potential impact indicators, not confirmed crop-damage estimates; verify priority fields with radar review and field inspection.',
  {fontSize: '11px', color: '#6a4d16', backgroundColor: '#fff8e5', padding: '8px', margin: '12px 0 0 0', whiteSpace: 'normal'}
);

var sidePanel = ui.Panel([
  title, subtitle, intro, actionPanel, layerHeader, layerPanel, statsHeader, statsLabel, floodHeader, floodLabel,
  methodHeader, methodLabel, chartHeader, phenologyChart, note
], ui.Panel.Layout.flow('vertical'), {
  width: '360px', padding: '14px', backgroundColor: '#ffffff'
});

map.onClick(function(coords) {
  var point = ee.Geometry.Point([coords.lon, coords.lat]);
  var values = ee.Image(composites[3]).select(['NDVI', 'NDMI', 'NDWI'])
    .addBands(cropClass).addBands(cropConfidence).addBands(floodCandidate)
    .addBands(floodRiskScore.unmask(-1)).reduceRegion({
      reducer: ee.Reducer.first(), geometry: point, scale: scale, maxPixels: 1e6
    });
  values.evaluate(function(result) {
    var classNames = ['Non-crop', 'Paddy field', 'Banana field', 'Other crop zone'];
    var classValue = result && result.crop_class !== null ? result.crop_class : 0;
    var text = 'Clicked location\n' +
      'Class: ' + classNames[classValue] + '\n' +
      'NDVI: ' + (result && result.NDVI !== null ? result.NDVI.toFixed(3) : 'n/a') + '\n' +
      'NDMI: ' + (result && result.NDMI !== null ? result.NDMI.toFixed(3) : 'n/a') + '\n' +
      'Confidence: ' + (result && result.crop_confidence !== null ? result.crop_confidence.toFixed(1) : 'n/a') + '\n' +
      'Flood signal: ' + (result && result.potential_flood === 1 ? 'Potential inundation' : 'No signal') + '\n' +
      'Flood-risk score: ' + (result && result.flood_risk_score >= 0 ? result.flood_risk_score.toFixed(1) : 'n/a');
    statsLabel.setValue(text);
  });
});

ui.root.clear();
ui.root.add(ui.SplitPanel({
  firstPanel: sidePanel,
  secondPanel: map,
  orientation: 'horizontal',
  wipe: false,
  style: {stretch: 'both'}
}));
