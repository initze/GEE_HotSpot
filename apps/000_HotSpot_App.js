// Create header

// Imports
var utils_plot = require('users/ingmarnitze/HotSpots:modules/utils_plot');
var configs = require('users/ingmarnitze/HotSpots:modules/configs');
var funcs = require('users/ingmarnitze/HotSpots:modules/high_level_functions');
var config_trend = configs.config_trend

var TCVIS_SR = ee.ImageCollection('users/ingmarnitze/TCTrend_SR_2000-2019_TCVIS')

// #############################################################################
// ### GET URL PARAMS ###
// #############################################################################
// check if full path exists and set defaults if not
// perhaps possible to simplify


if (typeof ui.url.get('lon') == 'undefined')
{
  //print(ui.url)

  var initLon = 0;
  var lonUrl = ui.url.get('lon', initLon);
  ui.url.set('lon', lonUrl);
  
  var initLat = 50;
  var latUrl = ui.url.get('lat', initLat);
  //print(latUrl)
  ui.url.set('lat', latUrl);
  
  // add zoom level
  var initZoom = 5;
  var zoomUrl = ui.url.get('zoom', initZoom);
  ui.url.set('zoom', zoomUrl);
}
else
{
 var lonUrl = ui.url.get('lon');
 var latUrl = ui.url.get('lat');
 var zoomUrl = ui.url.get('zoom');
 
}

// #############################################################################
// ### MAP CALLBACKS ###
// #############################################################################

function handleMapChange(coords) {
  ui.url.set('lon', coords.lon);
  ui.url.set('lat', coords.lat);
}

function handleMapZoom(zoomlevel) {
  ui.url.set('zoom', zoomlevel);
}

//################
var mapData = ui.Map()

// Add left map object
var leftMap = ui.Map();
leftMap.setOptions('SATELLITE')

var rightMap = ui.Map()

rightMap.onChangeCenter(handleMapChange)
rightMap.onChangeZoom(handleMapZoom)


rightMap.setOptions('SATELLITE')
var point = ee.Geometry.Point([0, 0])


// Create time-series Plots
var make_plots = function(geom){
  var config_trend = configs.config_trend
  config_trend.geom = geom.buffer(10)
  config_trend.date_filter_yr = ee.Filter.calendarRange(2000, 2019, 'year')
  config_trend.date_filter_mth = ee.Filter.calendarRange(7, 8, 'month')
  var collection = funcs.makeLandsatSeriesSrFiltered(config_trend)
  var plot_NDXI = utils_plot.plot_NDXI_timeseries(collection, geom)
  var plot_TCX = utils_plot.plot_TCX_timeseries(collection, geom)
  return {plot_NDXI:plot_NDXI, plot_TCX:plot_TCX};
};
// Create a panel with vertical flow layout.

// Text Styles
var style_label = {
  fontWeight:'bold',
  fontSize: 'medium',
  textAlign: 'center',
  backgroundColor:'#eeeeee',
  width:'95%',
  padding:'1px',
  margin: '2px',
  height: '30px'
}
var style_label2 = {
  fontWeight:'bold',
  fontSize: 'medium',
  textAlign: 'center',
  backgroundColor:'#ffffff',
  width:'95%',
  padding:'2px',
  height: '30px',
  margin: '2px',
}

var style_text = {
  textAlign: 'center',
  backgroundColor:'#eeeeee',
  width:'95%',
  padding: '1px',
  margin: '1px',
}

// Button Styles
var style_exampleButton = {stretch: 'horizontal',
                      backgroundColor: '#bcbcbc',
                      color: '#555555',
                      border: '1px solid black',
                      margin:'2px',
                      }
                      
var style_TSbutton = {stretch: 'horizontal',
                      color:'#67000d',
                      backgroundColor: '#bcbcbc',
                      border: '1px solid black'
                      }
                      


var style_button = {stretch: 'horizontal'}

// Main Panel
var panel_main = ui.Panel({
  layout: ui.Panel.Layout.flow('vertical'),
  style: {width: '18%', 
          backgroundColor:'#eeeeee' 
  }
});

// Panel for example Buttons
var panel_exampleButtons = ui.Panel({
  layout: ui.Panel.Layout.flow('vertical'),
  style: {width: '100%', 
          backgroundColor:'#eeeeee' 
  }
});

// Buttons: Permafrost Examples
var button_DP = ui.Button({label: 'Drew Point Coastal Erosion',
                           style: style_exampleButton})
button_DP.onClick(function(){rightMap.centerObject(ee.Geometry.Point([-153.8, 70.88]), 11)})

var button_HI = ui.Button({label: 'Herschel Island Slumps',
                           style: style_exampleButton})
button_HI.onClick(function(){rightMap.centerObject(ee.Geometry.Point([-139, 69.56]), 12)})

var button_SP = ui.Button({label: 'Lake Drainage Seward Peninsula',
                           style: style_exampleButton})
button_SP.onClick(function(){rightMap.centerObject(ee.Geometry.Point([-164, 66.5]), 11)})

var button_BOV = ui.Button({label: 'Bovanenkovo Gas Fields', 
                           style: style_exampleButton})
button_BOV.onClick(function(){rightMap.centerObject(ee.Geometry.Point([68.45, 70.36]), 10)})

var button_BAT = ui.Button({label: 'Batagaika Crater', 
                           style: style_exampleButton})
button_BAT.onClick(function(){rightMap.centerObject(ee.Geometry.Point([134.77, 67.58]), 13)})

var button_ANF = ui.Button({label: 'Anaktuvuk Fire', 
                           style: style_exampleButton})
button_ANF.onClick(function(){rightMap.centerObject(ee.Geometry.Point([-151.01, 69.11]), 8)})


panel_exampleButtons.add(ui.Label('Erosion permafrost', style_label2))
panel_exampleButtons.add(button_DP)
panel_exampleButtons.add(button_HI)
panel_exampleButtons.add(button_BAT)
panel_exampleButtons.add(ui.Label('Lake change permafrost', style_label2))
panel_exampleButtons.add(button_SP)
panel_exampleButtons.add(ui.Label('Infrastructure permafrost', style_label2))
panel_exampleButtons.add(button_BOV)
panel_exampleButtons.add(ui.Label('Wildfire', style_label2))
panel_exampleButtons.add(button_ANF)


// ########################################################################################### 
var panel_timeSeries = ui.Panel({
  layout: ui.Panel.Layout.flow('vertical'),
  style: {width: '30%', 
          backgroundColor:'#eeeeee',
          position:'bottom-right',
          shown:false
  }
});

// TS Toggle Button definitions
var button_plotTSon = ui.Button(
  {label: 'On', style: style_TSbutton, disabled: false})
button_plotTSon.onClick(function(){
  panel_timeSeries.style().set('shown', true)
  rightMap.style().set('cursor', 'crosshair')
  button_plotTSon.setDisabled(true)
  button_plotTSoff.setDisabled(false)
})                              

var button_plotTSoff = ui.Button(
  {label: 'Off', style: style_TSbutton, disabled: true})
button_plotTSoff.onClick(function(){
  panel_timeSeries.style().set('shown', false)
  rightMap.style().set('cursor', 'hand')
  button_plotTSon.setDisabled(false)
  button_plotTSoff.setDisabled(true)
})
// Get Linker Button
var button_linkLandsatViewer = ui.Button(
  {label: 'Select RGB Viewer', style: style_TSbutton, disabled: false})
button_plotTSoff.onClick(function(){
  rightMap.style().set('cursor', 'crosshair')
})


var panel_TStoggle = ui.Panel({
  layout: ui.Panel.Layout.flow('vertical'),
  style: {width: '100%', 
          backgroundColor:'#eeeeee' 
  }
});

var panel_TStoggle_buttons = ui.Panel({
  layout: ui.Panel.Layout.flow('horizontal'),
  style: {width: '100%', 
          backgroundColor:'#bcbcbc',
          shown:true
  }
});


panel_TStoggle.add(ui.Label('Plot Time-Series', style_label))
panel_TStoggle_buttons.add(button_plotTSon)
panel_TStoggle_buttons.add(button_plotTSoff)
panel_TStoggle_buttons.add(button_linkLandsatViewer)
panel_TStoggle.add(panel_TStoggle_buttons)

// Description Panel
var panel_description = ui.Panel({
  layout: ui.Panel.Layout.flow('vertical'),
  style: {width: '100%', 
          backgroundColor:'#ffffff',
          position:'bottom-center',
          shown:true
  }
});
var label_Github = ui.Label('Github Repository', style_text)
  .setUrl('https://github.com/initze/GEE_HotSpot');

//panel_description.add(ui.Label('Additional Information', style_label))
panel_description.add(ui.Label('Author: I.Nitze', style_text))
panel_description.add(ui.Label('Version: 0.4dev', style_text))
panel_description.add(label_Github)
panel_description.add(ui.Label('Data Period: 2000-2019', style_text))


panel_main.add(panel_exampleButtons)
panel_main.add(panel_TStoggle)
panel_main.add(panel_description)

ui.root.add(panel_main);

rightMap.add(panel_timeSeries)
rightMap.onClick(function(coords) {
  panel_timeSeries.clear()
  point = ee.Geometry.Point(coords.lon, coords.lat);
  
  var url_link = 'https://ingmarnitze.users.earthengine.app/view/landsat-timeseries-explorer-initze#run=true;lon='+coords.lon+';lat='+coords.lat+';from=07-01;to=08-31;index=TCB;rgb=SWIR1%2FNIR%2FGREEN;chipwidth=2'
  panel_timeSeries.add(ui.Label('Link')
  .setUrl(url_link))
  // make if statement to check which buttons are activated
  if (button_plotTSon.enabled === true){
    rightMap.addLayer(point, {}, 'Selected Location')
    var plots = make_plots(point)
    panel_timeSeries.add(plots.plot_NDXI)
    panel_timeSeries.add(plots.plot_TCX)
  }
});

// DEM visualization
var elevationVis2 = {
  min: -10.0,
  max: 700.0,
  palette: ['#709959', '#F0E990', '#F0CB86', '#C9957F', '#CC9E89', '#EED7BC', '#F9ECD7', '#FBF5EA', '#FCFAF5', '#FCFBF9', '#FCFCFC'],
};

var VisHs = {
  min: 150,
  max: 200,
};

// ########################################################################################### 
// Load Arctic DEM and make Hillshade
var dem = ee.Image("UMN/PGC/ArcticDEM/V3/2m_mosaic").select('elevation');
var hillshade = ee.Terrain.hillshade(dem, 270, 45).select('hillshade');

rightMap.addLayer(dem, elevationVis2, 'Arctic DEM Elevation', false)
rightMap.addLayer(hillshade, VisHs, 'Arctic DEM Hillshade', false, 0.4)
// Add TCVIS data
rightMap.addLayer(TCVIS_SR, {}, 'HotSpot TCVIS Landsat Trends (SR) 2000-2019', true)
rightMap.setCenter(lonUrl, latUrl, zoomUrl)


// ########################################################################################### 

// Add left map object
var leftMap = ui.Map();
leftMap.setOptions('SATELLITE')

leftMap.addLayer(dem, elevationVis2, 'Arctic DEM Elevation', true)
leftMap.addLayer(hillshade, VisHs, 'Arctic DEM Hillshade', true, 0.4)
// Add TCVIS data
leftMap.addLayer(TCVIS_SR, {}, 'HotSpot TCVIS Landsat Trends (SR) 2000-2019', false)
leftMap.setCenter(lonUrl, latUrl, zoomUrl)


// Create linker, necessary to link both windows
var linker = ui.Map.Linker([leftMap, rightMap]);


var splitPanel = ui.SplitPanel({
  firstPanel: linker.get(0),
  secondPanel: linker.get(1),
  orientation: 'horizontal',
  wipe: true,
  style: {stretch: 'both'}
});

// add new swipe map
ui.root.widgets().reset([splitPanel, panel_main]);