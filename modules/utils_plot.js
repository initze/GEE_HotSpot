// Make time-Series plot
var plot_NDXI_timeseries = function(image_collection, point){
  var chart_NDXI = ui.Chart.image.series(image_collection.select(['NDVI', 'NDMI']), point, null, null)
    .setChartType('ScatterChart')
    .setOptions({
      title: "Plot time-series", 
      interpolateNulls: true,
      series: {
          0: { pointSize: 3},
          1: { pointSize: 3},
          2: { pointSize: 3},
      },
      hAxis: {
        title: "Data"
      },
      vAxis: {
        title: "Reflectance/Index values"
      }
    });
  return chart_NDXI;
}
exports.plot_NDXI_timeseries = plot_NDXI_timeseries

var plot_TCX_timeseries = function(image_collection, point){
  var chart_TC = ui.Chart.image.series(image_collection.select(['TCB', 'TCG', 'TCW']), point, null, null)
    .setChartType('ScatterChart')
    .setOptions({
      title: "Plot time-series", 
      interpolateNulls: true,
      series: {
          0: { pointSize: 3, color: '#d73027'},
          1: { pointSize: 3, color: '#1a9850'},
          2: { pointSize: 3, color: '#3288bd'},
      },
      hAxis: {
        title: "Data",
      },
      vAxis: {
        title: "Reflectance/Index values",
      }
    });
  return chart_TC;
}
exports.plot_TCX_timeseries = plot_TCX_timeseries
