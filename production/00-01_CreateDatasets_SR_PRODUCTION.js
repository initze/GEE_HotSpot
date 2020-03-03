// %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
 
// date: 2020-02-14
// author: Ingmar Nitze | ingmar.nitze@awi.de, ingmarnitze@gmail.com
//         
// website:  
// script: 2020-02-14 Ingmar Nitze
// This is a script automatically create and export Landsat Tasseled Cap trend images
// This is the production script

// %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

// --------------------------------------------------------------------------------------------------------------------
// SET PROCESSING LOCATION
var imageCollection = ee.ImageCollection('users/ingmarnitze/TCTrend_SR_2000-2019_TCVIS')
// Imports
var high_level_functions = require('users/ingmarnitze/HotSpots:modules/high_level_functions');

Map.setOptions('SATELLITE')

// PROPERTIES
//var longitudes = [-180, -170, -160, -150, -140, -130, -120, -110, -100]
var longitudes = [-90, -80, -70, -60, -50, -40, -30, -20, -10, 0]
//var longitudes = [90, 80, 70, 60, 50, 40, 30, 20, 10]
//var longitudes = [60, 50, 40, 30, 20, 10]
//var longitudes = [170, 160, 150, 140, 130, 120, 110, 100]
//var longitudes = [-180]
var latitudes = [35]
var sizeLon = 10
var sizeLat = 5


// SET METADATA PARAMETERS
var MAXCLOUD = 70;
var STARTYEAR = 2000;
var ENDYEAR = 2019;
var STARTMONTH = 7;
var ENDMONTH = 8;
var ZOOMLEVEL = 6;
var SCALE = 30;

// image metadata Filters
var date_filter_yr = ee.Filter.calendarRange(STARTYEAR, ENDYEAR, 'year');
var date_filter_mth = ee.Filter.calendarRange(STARTMONTH, ENDMONTH, 'month');
var meta_filter_cld = ee.Filter.lt('CLOUD_COVER', MAXCLOUD);

var select_bands_visible = ["B1", "B2","B3","B4"]
var select_indices = ["TCB", "TCG", "TCW"]
var select_TCtrend_bands = ["TCB_slope", "TCG_slope", "TCW_slope"]

var config_trend = {
  date_filter_yr : date_filter_yr,
  date_filter_mth : date_filter_mth,
  meta_filter_cld : meta_filter_cld,
  select_bands_visible : select_bands_visible,
  select_indices : select_indices,
  select_TCtrend_bands : select_TCtrend_bands,
  geom : null
}

var config_image_export = {
  STARTYEAR : STARTYEAR,
  ENDYEAR : ENDYEAR,
  leftLon : null,
  lowLat : null,
  geom : null,
  SCALE: SCALE,
  data_trend : null,
  data_n_observations : null
}

//------ RUN FULL PROCESS FOR ALL REGIONS IN LOOP ------------------------------
Map.addLayer(imageCollection, {}, 'TCVIS')

for (var i in longitudes) {
  for (var j in latitudes) {
    var leftLon = longitudes[i]
    var lowLat = latitudes[j]
    
    // create Bounding Box
    var geom = ee.Geometry.Polygon([leftLon,lowLat+sizeLat, leftLon, lowLat, leftLon+sizeLon, lowLat, leftLon+sizeLon, lowLat+sizeLat])
    config_trend.geom = geom
    
    // Calculate Trend
    var trend = high_level_functions.runTCTrend(config_trend);
    
    // Export Image
    
    // update export config
    config_image_export.leftLon = leftLon
    config_image_export.lowLat = lowLat
    config_image_export.geom = geom
    config_image_export.data_trend = trend.visual
    config_image_export.data_n_observations = trend.n_observations
    
    // run Export
    high_level_functions.exportTCTrendImage(config_image_export)
    
    // add Map Layers
    Map.addLayer(trend.visual, {}, 'TCVIS: '+ leftLon.toString() + '_' + lowLat.toString(), false, 1)
    Map.addLayer(geom, {}, 'Geometry : '+ leftLon.toString() + '_' + lowLat.toString(), true, 0.3)
  }
}