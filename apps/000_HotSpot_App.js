// Imports
var utils_LS = require('users/ingmarnitze/HotSpots:modules/utils_Landsat_SR');
var indices = require('users/ingmarnitze/default:Modules/ms_indices');
var utils_plot = require('users/ingmarnitze/HotSpots:modules/utils_plot');
var configs = require('users/ingmarnitze/HotSpots:modules/configs');
var funcs = require('users/ingmarnitze/HotSpots:modules/high_level_functions');
var config_trend = configs.config_trend

var TCVIS_SR = ee.ImageCollection('users/ingmarnitze/TCTrend_SR_2000-2019_TCVIS')

Map.setOptions('SATELLITE')

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

var style_label = {
  fontWeight:'bold',
  fontSize: 'large',
  textAlign: 'center',
  backgroundColor:'#7174a5',
  color: '#ffffff',
  width:'95%',
  padding:'1px',
  height: '30px'
}

var style_exampleButton = {stretch: 'horizontal',
                      backgroundColor: '#bcbcbc',
                      border: '1px solid black'}
                      
var style_TSbutton = {stretch: 'horizontal',
                      color:'#67000d',
                      backgroundColor: '#bcbcbc',
                      border: '1px solid black'}

var style_button = {stretch: 'horizontal'}

// Panel for example Buttons
var panel_main = ui.Panel({
  layout: ui.Panel.Layout.flow('vertical'),
  style: {width: '15%', 
          backgroundColor:'#25277a' 
  }
});

// Panel for example Buttons
var panel_exampleButtons = ui.Panel({
  layout: ui.Panel.Layout.flow('vertical'),
  style: {width: '100%', 
          backgroundColor:'#bcbcbc' 
  }
});

// Buttons: Permafrost Examples
var button_DP = ui.Button({label: 'Drew Point Coastal Erosion',
                           style: style_exampleButton})
button_DP.onClick(function(){Map.centerObject(ee.Geometry.Point([-153.8, 70.88]), 11)})

var button_HI = ui.Button({label: 'Herschel Island Slumps',
                           style: style_exampleButton})
button_HI.onClick(function(){Map.centerObject(ee.Geometry.Point([-139, 69.56]), 12)})

var button_SP = ui.Button({label: 'Lake Drainage Seward Peninsula',
                           style: style_exampleButton})
button_SP.onClick(function(){Map.centerObject(ee.Geometry.Point([-164, 66.5]), 11)})

var button_BOV = ui.Button({label: 'Bovanenkovo Oil Fields', 
                           style: style_exampleButton})
button_BOV.onClick(function(){Map.centerObject(ee.Geometry.Point([68.45, 70.36]), 10)})

var button_BAT = ui.Button({label: 'Batagaika Crater', 
                           style: style_exampleButton})
button_BAT.onClick(function(){Map.centerObject(ee.Geometry.Point([134.77, 67.58]), 13)})

panel_exampleButtons.add(ui.Label('Examples', style_label))
panel_exampleButtons.add(button_DP)
panel_exampleButtons.add(button_HI)
panel_exampleButtons.add(button_SP)
panel_exampleButtons.add(button_BOV)
panel_exampleButtons.add(button_BAT)

// ########################################################################################### 



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
  Map.style().set('cursor', 'crosshair')
  button_plotTSon.setDisabled(true)
  button_plotTSoff.setDisabled(false)
})                              

var button_plotTSoff = ui.Button(
  {label: 'Off', style: style_TSbutton, disabled: true})
button_plotTSoff.onClick(function(){
  panel_timeSeries.style().set('shown', false)
  Map.style().set('cursor', 'hand')
  button_plotTSon.setDisabled(false)
  button_plotTSoff.setDisabled(true)
})

var panel_TStoggle = ui.Panel({
  layout: ui.Panel.Layout.flow('vertical'),
  style: {width: '100%', 
          backgroundColor:'#aaaaaa' 
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
panel_TStoggle.add(panel_TStoggle_buttons)

//panel_exampleButtons.add(panel_TStoggle)

panel_main.add(panel_exampleButtons)
panel_main.add(panel_TStoggle)

ui.root.add(panel_main);

Map.add(panel_timeSeries)
Map.onClick(function(coords) {
  panel_timeSeries.clear()
  point = ee.Geometry.Point(coords.lon, coords.lat);
  Map.addLayer(point, {}, 'Selected Location')
  var plots = make_plots(point)
  panel_timeSeries.add(plots.plot_NDXI)
  panel_timeSeries.add(plots.plot_TCX)

});
// ########################################################################################### 
//utils_plot.plot_NDXI_timeseries
//utils_plot.plot_TCX_timeseries
// ########################################################################################### 

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

Map.addLayer(dem, elevationVis2, 'Arctic DEM Elevation', false)
Map.addLayer(hillshade, VisHs, 'Arctic DEM Hillshade', false, 0.4)
// Add TCVIS data
Map.addLayer(TCVIS_SR, {}, 'HotSpot TCVIS Landsat Trends (SR) 2000-2019', true)
