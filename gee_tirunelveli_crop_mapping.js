// Tirunelveli paddy and banana screening in Google Earth Engine
// Study window: Ambasamudram-side and Cheranmahadevi-side landscape
// Paste this file into the Earth Engine Code Editor and click Run.

// -----------------------------------------------------------------------------
// 1. Study area and editable parameters
// -----------------------------------------------------------------------------
var aoi = ee.Geometry.Rectangle([77.42, 8.64, 77.60, 8.75], null, false);
var scale = 10;
var cloudProbabilityLimit = 40;

// These thresholds mirror the first screening model. They are deliberately
// exposed here so they can be tuned after checking local field observations.
var bananaMinMedianNdvi = 0.32;
var bananaMinNdvi = 0.20;
var bananaMaxAmplitude = 0.32;
var bananaMinMedianNdmi = 0.03;
var paddyMinPeakNdvi = 0.40;
var paddyMinAmplitude = 0.22;
var paddyMinMedianNdvi = 0.22;
var otherCropMinMedianNdvi = 0.28;

// Optional advanced modules. Keep these false until the basic map is working.
// To activate the Random Forest and accuracy modules, replace the empty
// referencePoints collection below with your labelled validation asset and set
// useReferenceSamples = true.
var useReferenceSamples = false;
var referencePoints = ee.FeatureCollection([]);
var chartPoint = ee.Geometry.Point([77.50, 8.69]);
var waterDistanceLimitM = 1000;
var radarWaterVvLimit = -16;
var radarChangeLimitDb = 3;

Map.centerObject(aoi, 12);
Map.addLayer(aoi, {color: 'yellow'}, 'Study window', false);

// Four seasonal windows. Earth Engine composites all available clear images
// in each window, so the script does not depend on one exact scene ID.
var periods = [
  {name: 'mar2026', start: '2026-03-01', end: '2026-04-01'},
  {name: 'apr2026', start: '2026-04-01', end: '2026-05-01'},
  {name: 'sep_early2026', start: '2026-09-01', end: '2026-09-16'},
  {name: 'sep_late2026', start: '2026-09-16', end: '2026-10-01'}
];

// -----------------------------------------------------------------------------
// 2. Sentinel-2 SR Harmonized + cloud probability mask
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
  var probability = ee.Image(image.get('cloud_probability'))
    .select('probability');
  var scl = image.select('SCL');

  // Remove cloud probability >= threshold, cloud shadow, cirrus, cloud and snow.
  var clear = probability.lt(cloudProbabilityLimit)
    .and(scl.neq(3))
    .and(scl.neq(8))
    .and(scl.neq(9))
    .and(scl.neq(10))
    .and(scl.neq(11));

  var reflectance = image
    .updateMask(clear)
    .select(['B2', 'B3', 'B4', 'B8', 'B11'])
    .divide(10000);

  var ndvi = reflectance.normalizedDifference(['B8', 'B4']).rename('NDVI');
  var ndwi = reflectance.normalizedDifference(['B3', 'B8']).rename('NDWI');
  var ndmi = reflectance.normalizedDifference(['B8', 'B11']).rename('NDMI');

  return reflectance
    .addBands([ndvi, ndwi, ndmi])
    .copyProperties(image, ['system:index', 'system:time_start', 'CLOUDY_PIXEL_PERCENTAGE']);
}

var s2 = ee.ImageCollection(joined).map(maskAndAddIndices);
print('Cloud-filtered Sentinel-2 image count', s2.size());

function seasonalComposite(period) {
  var subset = s2.filterDate(period.start, period.end);
  print(period.name + ' image count', subset.size());
  return subset.median().clip(aoi);
}

var composites = periods.map(seasonalComposite);

// Add a true-colour layer from the late-September composite.
var rgbVisualization = {
  bands: ['B4', 'B3', 'B2'],
  min: 0,
  max: 0.30,
  gamma: 1.15
};
Map.addLayer(composites[3], rgbVisualization,
  'Sentinel-2 RGB, late September', true, 1.0);

// -----------------------------------------------------------------------------
// 3. Multi-date phenology features
// -----------------------------------------------------------------------------
var ndviStack = ee.Image.cat(periods.map(function(period, index) {
  return ee.Image(composites[index]).select('NDVI').rename('NDVI_' + period.name);
}));

var ndmiStack = ee.Image.cat(periods.map(function(period, index) {
  return ee.Image(composites[index]).select('NDMI').rename('NDMI_' + period.name);
}));

var ndviMin = ndviStack.reduce(ee.Reducer.min()).rename('NDVI_min');
var ndviMax = ndviStack.reduce(ee.Reducer.max()).rename('NDVI_max');
var ndviMedian = ndviStack.reduce(ee.Reducer.median()).rename('NDVI_median');
var ndviAmplitude = ndviMax.subtract(ndviMin).rename('NDVI_amplitude');
var ndmiMedian = ndmiStack.reduce(ee.Reducer.median()).rename('NDMI_median');
var valid = ndviStack.reduce(ee.Reducer.count()).eq(periods.length);

Map.addLayer(ndviMedian, {min: 0, max: 0.70, palette: ['8c510a', 'f6e8c3', '01665e']},
  'Median NDVI', false);
Map.addLayer(ndviAmplitude, {min: 0, max: 0.60, palette: ['f7fbff', '6baed6', '08306b']},
  'Seasonal NDVI amplitude', false);

// -----------------------------------------------------------------------------
// 4. Rule-based crop candidates
// -----------------------------------------------------------------------------
var banana = valid
  .and(ndviMedian.gte(bananaMinMedianNdvi))
  .and(ndviMin.gte(bananaMinNdvi))
  .and(ndviAmplitude.lte(bananaMaxAmplitude))
  .and(ndmiMedian.gte(bananaMinMedianNdmi));

var paddy = valid
  .and(banana.not())
  .and(ndviMax.gte(paddyMinPeakNdvi))
  .and(ndviAmplitude.gte(paddyMinAmplitude))
  .and(ndviMedian.gte(paddyMinMedianNdvi));

var otherCropland = valid
  .and(banana.not())
  .and(paddy.not())
  .and(ndviMedian.gte(otherCropMinMedianNdvi))
  .and(ndviMax.gte(paddyMinPeakNdvi));

// 0 = non-crop, 1 = paddy candidate, 2 = banana candidate,
// 3 = other cropland candidate.
var cropClass = ee.Image(0).rename('crop_class')
  .where(paddy, 1)
  .where(banana, 2)
  .where(otherCropland, 3)
  .toInt8();

var classPalette = ['000000', '287dd2', 'dc4637', '5fb45a'];
Map.addLayer(cropClass.updateMask(cropClass.gt(0)),
  {min: 1, max: 3, palette: ['287dd2', 'dc4637', '5fb45a']},
  'Combined crop classification', false, 0.55);

// Separate layers so paddy and banana can be switched on/off independently.
// updateMask() keeps only the true pixels visible.
var paddyDisplay = paddy.updateMask(paddy).rename('paddy_candidates');
var bananaDisplay = banana.updateMask(banana).rename('banana_candidates');
var otherCroplandDisplay = otherCropland.updateMask(otherCropland)
  .rename('other_cropland_candidates');

Map.addLayer(paddyDisplay,
  {palette: ['287dd2']},
  'Paddy candidates - blue', true, 0.60);

Map.addLayer(bananaDisplay,
  {palette: ['dc4637']},
  'Banana candidates - red', true, 0.60);

Map.addLayer(otherCroplandDisplay,
  {palette: ['5fb45a']},
  'Other cropland - green', false, 0.50);

// -----------------------------------------------------------------------------
// 4A. Advanced novelty modules
// -----------------------------------------------------------------------------
// A. Confidence score: a transparent 0-100 score based on distance from the
// rule thresholds. This is a screening confidence, not a probability.
var bananaConfidence = ee.Image(0)
  .add(ndviMedian.subtract(bananaMinMedianNdvi).divide(0.30).clamp(0, 1))
  .add(ndviMin.subtract(bananaMinNdvi).divide(0.30).clamp(0, 1))
  .add(ee.Image(bananaMaxAmplitude).subtract(ndviAmplitude)
    .divide(bananaMaxAmplitude).clamp(0, 1))
  .add(ndmiMedian.subtract(bananaMinMedianNdmi).divide(0.30).clamp(0, 1))
  .divide(4).multiply(100).updateMask(banana)
  .rename('banana_confidence');

var paddyConfidence = ee.Image(0)
  .add(ndviMax.subtract(paddyMinPeakNdvi).divide(0.30).clamp(0, 1))
  .add(ndviAmplitude.subtract(paddyMinAmplitude).divide(0.40).clamp(0, 1))
  .add(ndviMedian.subtract(paddyMinMedianNdvi).divide(0.35).clamp(0, 1))
  .divide(3).multiply(100).updateMask(paddy)
  .rename('paddy_confidence');

var otherConfidence = ndviMedian.subtract(otherCropMinMedianNdvi)
  .divide(0.40).clamp(0, 1).multiply(100)
  .updateMask(otherCropland).rename('other_cropland_confidence');

var cropConfidence = paddyConfidence.unmask(0)
  .where(banana, bananaConfidence.unmask(0))
  .where(otherCropland, otherConfidence.unmask(0))
  .updateMask(cropClass.gt(0))
  .rename('crop_confidence');

Map.addLayer(cropConfidence,
  {min: 0, max: 100, palette: ['f7fbff', '9ecae1', '2171b5']},
  'Crop confidence 0-100', false, 0.75);

// B. Phenology chart for a demonstrator point. Move chartPoint to a known
// paddy or banana patch when presenting the project.
Map.addLayer(chartPoint, {color: 'yellow'}, 'Phenology chart point', false);
var seasonalStats = ee.FeatureCollection(periods.map(function(period, index) {
  var stats = ee.Image(composites[index]).select(['NDVI', 'NDMI', 'NDWI'])
    .reduceRegion({
      reducer: ee.Reducer.mean(),
      geometry: chartPoint,
      scale: scale,
      maxPixels: 1e7
    });
  return ee.Feature(null, stats).set({
    period: period.name,
    date: period.start,
    system_time_start: ee.Date(period.start).millis()
  });
}));
print('Phenology values at selected point', seasonalStats);
print('NDVI and NDMI phenology chart', ui.Chart.feature.byFeature({
  features: seasonalStats,
  xProperty: 'period',
  yProperties: ['NDVI', 'NDMI']
}).setChartType('LineChart').setOptions({
  title: 'Selected patch phenology',
  hAxis: {title: 'Seasonal composite'},
  vAxis: {title: 'Index value'},
  lineWidth: 3,
  pointSize: 6,
  colors: ['1b9e77', '7570b3']
}));

// C. Sentinel-1 radar fusion. Radar is useful when optical imagery is affected
// by clouds and gives an additional wetness/structure signal for paddy.
var s1 = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(aoi)
  .filterDate('2026-03-01', '2026-10-01')
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
  .select(['VV', 'VH']);

var s1Early = s1.filterDate('2026-03-01', '2026-05-01').median().clip(aoi);
var s1Late = s1.filterDate('2026-09-01', '2026-10-01').median().clip(aoi);
var s1VvChange = s1Late.select('VV').subtract(s1Early.select('VV')).abs();
var s1WaterSignal = s1Late.select('VV').lt(radarWaterVvLimit);
var s1PaddySupport = s1WaterSignal.or(s1VvChange.gte(radarChangeLimitDb));
var paddySentinelFusion = paddy.and(s1PaddySupport)
  .rename('paddy_sentinel1_sentinel2_fusion');

Map.addLayer(s1Late.select('VV'),
  {min: -25, max: 0, palette: ['081d58', '225ea8', '41b6c4', 'ffffcc']},
  'Sentinel-1 VV, late season', false, 0.75);
Map.addLayer(s1PaddySupport.updateMask(s1PaddySupport),
  {palette: ['fdae61']},
  'Sentinel-1 paddy radar support', false, 0.60);
Map.addLayer(paddySentinelFusion.updateMask(paddySentinelFusion),
  {palette: ['7b3294']},
  'Paddy after Sentinel-1 fusion', false, 0.75);
print('Sentinel-1 image count', s1.size());

// D. Change monitoring between the first and last seasonal composites.
var ndviChange = ee.Image(composites[3]).select('NDVI')
  .subtract(ee.Image(composites[0]).select('NDVI'))
  .rename('NDVI_change');
// 1 = greening, 2 = decline/harvest, 3 = stable.
var changeClass = ee.Image(0)
  .where(ndviChange.gte(0.20), 1)
  .where(ndviChange.lte(-0.20), 2)
  .where(ndviChange.abs().lt(0.20), 3)
  .updateMask(valid)
  .rename('change_class');
Map.addLayer(changeClass, {
  min: 1, max: 3, palette: ['31a354', 'd73027', 'bdbdbd']
}, 'Crop change: greening, decline, stable', false, 0.65);
Map.addLayer(ndviChange, {
  min: -0.50, max: 0.50, palette: ['b2182b', 'f7f7f7', '2166ac']
}, 'NDVI change, late minus early', false, 0.70);

// E. Water availability proxy using open Global Surface Water occurrence.
var waterOccurrence = ee.Image('JRC/GSW1_4/GlobalSurfaceWater')
  .select('occurrence').clip(aoi);
var surfaceWater = waterOccurrence.gte(50).rename('surface_water');
var distanceToWater = surfaceWater.fastDistanceTransform(128)
  .sqrt().multiply(30).rename('distance_to_surface_water_m');
var paddyNearWater = paddy.and(distanceToWater.lte(waterDistanceLimitM));
Map.addLayer(distanceToWater, {
  min: 0, max: 3000, palette: ['084081', '7bccc4', 'f7fcf0']
}, 'Distance to surface water (m)', false, 0.65);
Map.addLayer(paddyNearWater.updateMask(paddyNearWater),
  {palette: ['00bfc4']},
  'Paddy candidate within 1 km of surface water', false, 0.75);
var waterStats = ee.Image.pixelArea().updateMask(paddyNearWater).reduceRegion({
  reducer: ee.Reducer.sum(),
  geometry: aoi,
  scale: scale,
  maxPixels: 1e10,
  tileScale: 4
});
print('Paddy candidate area within 1 km of surface water, m2', waterStats);

// F. Optional supervised Random Forest comparison and accuracy assessment.
// Set useReferenceSamples = true after replacing referencePoints with an
// imported FeatureCollection containing property: reference (0/1/2/3).
var predictorImage = ee.Image.cat(periods.map(function(period, index) {
  var names = ['B2', 'B3', 'B4', 'B8', 'B11', 'NDVI', 'NDWI', 'NDMI'];
  var renamed = names.map(function(name) { return name + '_' + period.name; });
  return ee.Image(composites[index]).select(names).rename(renamed);
})).addBands([
  ndviMin, ndviMax, ndviMedian, ndviAmplitude, ndmiMedian,
  s1Late.select(['VV', 'VH']).rename(['S1_VV_late', 'S1_VH_late']),
  distanceToWater
]).clip(aoi);

if (useReferenceSamples) {
  var allSamples = predictorImage.sampleRegions({
    collection: referencePoints,
    properties: ['reference'],
    scale: scale,
    geometries: true,
    tileScale: 4
  }).filter(ee.Filter.notNull(['reference'])).randomColumn({
    columnName: 'random', seed: 42
  });
  var trainingSamples = allSamples.filter(ee.Filter.lt('random', 0.70));
  var validationSamples = allSamples.filter(ee.Filter.gte('random', 0.70));
  var rf = ee.Classifier.smileRandomForest({
    numberOfTrees: 100,
    seed: 42
  }).train({
    features: trainingSamples,
    classProperty: 'reference',
    inputProperties: predictorImage.bandNames()
  });
  var rfClass = predictorImage.classify(rf).rename('random_forest_class');
  Map.addLayer(rfClass.updateMask(rfClass.gt(0)), {
    min: 1, max: 3, palette: ['287dd2', 'dc4637', '5fb45a']
  }, 'Random Forest classification', false, 0.65);
  Map.addLayer(cropClass.neq(rfClass).selfMask(),
    {palette: ['ff00ff']},
    'Rule-based vs Random Forest disagreement', false, 0.70);

  var rfValidated = validationSamples.classify(rf);
  var rfMatrix = rfValidated.errorMatrix({
    actual: 'reference', predicted: 'classification', order: [0, 1, 2, 3]
  });
  print('Random Forest confusion matrix', rfMatrix);
  print('Random Forest overall accuracy', rfMatrix.accuracy());
  print('Random Forest producer accuracy', rfMatrix.producersAccuracy());
  print('Random Forest user accuracy', rfMatrix.consumersAccuracy());
  print('Random Forest Kappa', rfMatrix.kappa());
  print('Random Forest variable importance', ee.Dictionary(rf.explain()).get('importance'));

  var ruleValidated = cropClass.sampleRegions({
    collection: referencePoints,
    properties: ['reference'],
    scale: scale,
    tileScale: 4
  }).filter(ee.Filter.notNull(['reference', 'crop_class']));
  var ruleMatrix = ruleValidated.errorMatrix({
    actual: 'reference', predicted: 'crop_class', order: [0, 1, 2, 3]
  });
  print('Rule-based confusion matrix', ruleMatrix);
  print('Rule-based overall accuracy', ruleMatrix.accuracy());
  print('Rule-based producer accuracy', ruleMatrix.producersAccuracy());
  print('Rule-based user accuracy', ruleMatrix.consumersAccuracy());
  print('Rule-based Kappa', ruleMatrix.kappa());
}

// Quick area summary in hectares.
var areaSummary = ee.Image.pixelArea().addBands(cropClass).reduceRegion({
  reducer: ee.Reducer.sum().group({groupField: 1, groupName: 'crop_class'}),
  geometry: aoi,
  scale: scale,
  maxPixels: 1e10,
  tileScale: 4
});
print('Area summary by class, square metres', areaSummary);

// -----------------------------------------------------------------------------
// 5. Parcel-like image objects using SNIC superpixels
// -----------------------------------------------------------------------------
// SNIC groups nearby pixels with similar spectral/phenology values. The output
// is an image-object layer, not a cadastral boundary layer.
var segmentationInput = composites[3]
  .select(['B4', 'B3', 'B2', 'B8'])
  .addBands([ndviMedian, ndmiMedian])
  .clip(aoi);

var snic = ee.Algorithms.Image.Segmentation.SNIC({
  image: segmentationInput,
  size: 10,
  compactness: 2,
  connectivity: 8,
  neighborhoodSize: 40
});

var clusterIds = snic.select('clusters').rename('cluster_id');
var clusterPolygons = clusterIds.reduceToVectors({
  geometry: aoi,
  scale: scale,
  geometryType: 'polygon',
  eightConnected: true,
  labelProperty: 'cluster_id',
  reducer: ee.Reducer.countEvery(),
  maxPixels: 1e10,
  tileScale: 4
});

// Calculate the crop class and phenology statistics for each SNIC polygon.
var parcelsWithClass = cropClass.reduceRegions({
  collection: clusterPolygons,
  reducer: ee.Reducer.mode(),
  scale: scale,
  tileScale: 4
}).map(function(feature) {
  return feature.set('crop_class', ee.Number(feature.get('mode')).int());
});

var parcelsWithNdvi = ndviMedian.reduceRegions({
  collection: parcelsWithClass,
  reducer: ee.Reducer.mean(),
  scale: scale,
  tileScale: 4
}).map(function(feature) {
  return feature.set('mean_ndvi', feature.get('mean'));
});

var parcelsWithAmplitude = ndviAmplitude.reduceRegions({
  collection: parcelsWithNdvi,
  reducer: ee.Reducer.mean(),
  scale: scale,
  tileScale: 4
}).map(function(feature) {
  return feature.set('seasonal_ndvi_amplitude', feature.get('mean'));
});

var parcelsWithNdmi = ndmiMedian.reduceRegions({
  collection: parcelsWithAmplitude,
  reducer: ee.Reducer.mean(),
  scale: scale,
  tileScale: 4
}).map(function(feature) {
  return feature.set('mean_ndmi', feature.get('mean'));
});

var cropParcels = parcelsWithNdmi.map(function(feature) {
  var classNumber = ee.Number(feature.get('crop_class'));
  var className = ee.Algorithms.If(classNumber.eq(1), 'paddy',
    ee.Algorithms.If(classNumber.eq(2), 'banana', 'other_cropland'));
  var areaHa = feature.geometry().area(1).divide(10000);
  return feature.set({
    class_name: className,
    area_ha: areaHa,
    interpretation: 'remote-sensing patch; not cadastral boundary'
  });
}).filter(ee.Filter.inList('crop_class', [1, 2, 3]))
  .filter(ee.Filter.gte('area_ha', 0.10));

print('Crop patch count', cropParcels.size());
print('Example crop patches', cropParcels.limit(10));

Map.addLayer(cropParcels.style({color: 'ffffff', fillColor: '00000000', width: 1}),
  {}, 'Crop patch boundaries', false);

// -----------------------------------------------------------------------------
// 6. Export tasks
// -----------------------------------------------------------------------------
Export.image.toDrive({
  image: cropClass,
  description: 'tirunelveli_crop_class_10m',
  folder: 'GEE_Tirunelveli',
  fileNamePrefix: 'tirunelveli_crop_class_10m',
  region: aoi,
  scale: scale,
  maxPixels: 1e10
});

Export.image.toDrive({
  image: paddyDisplay,
  description: 'tirunelveli_paddy_candidates_10m',
  folder: 'GEE_Tirunelveli',
  fileNamePrefix: 'tirunelveli_paddy_candidates_10m',
  region: aoi,
  scale: scale,
  maxPixels: 1e10
});

Export.image.toDrive({
  image: bananaDisplay,
  description: 'tirunelveli_banana_candidates_10m',
  folder: 'GEE_Tirunelveli',
  fileNamePrefix: 'tirunelveli_banana_candidates_10m',
  region: aoi,
  scale: scale,
  maxPixels: 1e10
});

Export.image.toDrive({
  image: cropConfidence,
  description: 'tirunelveli_crop_confidence_10m',
  folder: 'GEE_Tirunelveli',
  fileNamePrefix: 'tirunelveli_crop_confidence_10m',
  region: aoi,
  scale: scale,
  maxPixels: 1e10
});

Export.image.toDrive({
  image: changeClass,
  description: 'tirunelveli_crop_change_early_late_10m',
  folder: 'GEE_Tirunelveli',
  fileNamePrefix: 'tirunelveli_crop_change_early_late_10m',
  region: aoi,
  scale: scale,
  maxPixels: 1e10
});

Export.image.toDrive({
  image: distanceToWater,
  description: 'tirunelveli_distance_to_surface_water_10m',
  folder: 'GEE_Tirunelveli',
  fileNamePrefix: 'tirunelveli_distance_to_surface_water_10m',
  region: aoi,
  scale: scale,
  maxPixels: 1e10
});

Export.image.toDrive({
  image: paddySentinelFusion,
  description: 'tirunelveli_paddy_sentinel1_sentinel2_fusion_10m',
  folder: 'GEE_Tirunelveli',
  fileNamePrefix: 'tirunelveli_paddy_sentinel1_sentinel2_fusion_10m',
  region: aoi,
  scale: scale,
  maxPixels: 1e10
});

Export.table.toDrive({
  collection: cropParcels.select([
    'cluster_id', 'crop_class', 'class_name', 'area_ha',
    'mean_ndvi', 'seasonal_ndvi_amplitude', 'mean_ndmi', 'interpretation'
  ]),
  description: 'tirunelveli_crop_patches_geojson',
  folder: 'GEE_Tirunelveli',
  fileNamePrefix: 'tirunelveli_crop_patches',
  fileFormat: 'GeoJSON',
  maxVertices: 1e5
});

Export.table.toDrive({
  collection: cropParcels.select([
    'cluster_id', 'crop_class', 'class_name', 'area_ha',
    'mean_ndvi', 'seasonal_ndvi_amplitude', 'mean_ndmi', 'interpretation'
  ]),
  description: 'tirunelveli_crop_patches_csv',
  folder: 'GEE_Tirunelveli',
  fileNamePrefix: 'tirunelveli_crop_patches',
  fileFormat: 'CSV'
});
