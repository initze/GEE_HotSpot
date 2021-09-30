import ee 

# Make time-Series plot
def plot_NDXI_timeseries(image_collection, point):
  chart_NDXI = ui.Chart.image.series(image_collection.select(['NDVI', 'NDMI']), point, {}, {}) \
    .setChartType('ScatterChart') \
    .setOptions({
      'title': "Plot time-series",
      'interpolateNulls': True,
      'series': {
          '0': {'pointSize': 3},
          '1': {'pointSize': 3},
          '2': {'pointSize': 3},
      },
      'hAxis': {
        'title': "Data"
      },
      'vAxis': {
        'title': "Reflectance/Index values"
      }
    })
  return chart_NDXI


def plot_TCX_timeseries(image_collection, point):
  chart_TC = ui.Chart.image.series(image_collection.select(['TCB', 'TCG', 'TCW']), point, {}, {}) \
    .setChartType('ScatterChart') \
    .setOptions({
      'title': "Plot time-series",
      'interpolateNulls': True,
      'series': {
          '0': {'pointSize': 3, 'color': '#d73027'},
          '1': {'pointSize': 3, 'color': '#1a9850'},
          '2': {'pointSize': 3, 'color': '#3288bd'},
      },
      'hAxis': {
        'title': "Data",
      },
      'vAxis': {
        'title': "Reflectance/Index values",
      }
    })
  return chart_TC