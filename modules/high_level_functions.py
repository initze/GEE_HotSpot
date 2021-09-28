import ee 
from ee_plugin import Map 

# Imports
landTrendr = require('users/ingmarnitze/LandTrendr_fork:LandTrendr')

# Move indices function
indices = require('users/ingmarnitze/default:Modules/ms_indices')
utils_LS = require('users/ingmarnitze/HotSpots:modules/utils_Landsat_SR')
utils_plot = require('users/ingmarnitze/HotSpots:modules/utils_plot')
utils_string = require('users/ingmarnitze/HotSpots:modules/utils_string')

def makeLandsatSeriesSrFiltered (config):
  # 1. load Landsat data and calculate indices
  collection = utils_LS.makeLandsatSeriesSr(config.geom, config.date_filter_yr, config.date_filter_mth, config.meta_filter_cld) \
  .map(indices.ndvi57) \
  .map(indices.ndmi57) \
  .map(indices.tc5)

  # 2. Filter pixels off 3 std from mean
  std_diff = utils_LS.calculate_std_diff(collection, 3)
  lower = std_diff[0]
  upper = std_diff[1]

def func_gsi(image):
    return utils_LS.update_mask_by_std(image, lower, upper, config.select_bands_visible)

  collection = collection.map(func_gsi)



  return collection

exports.makeLandsatSeriesSrFiltered = makeLandsatSeriesSrFiltered


def runTCTrend(config):

  # 1. load Landsat data and calculate indices
  collection = utils_LS.makeLandsatSeriesSr(config.geom, config.date_filter_yr, config.date_filter_mth, config.meta_filter_cld) \
  .map(indices.ndvi57) \
  .map(indices.ndmi57) \
  .map(indices.tc5)

  # 2. Filter pixels off 3 std from mean
  std_diff = utils_LS.calculate_std_diff(collection, 3)
  lower = std_diff[0]
  upper = std_diff[1]

def func_tcb(image):
    return utils_LS.update_mask_by_std(image, lower, upper, config.select_bands_visible)

  collection = collection.map(func_tcb)




  # 3. Calculate image pixel count
  image_observations = collection.count().select([1], ['nObservations'])
  image_total_count = collection.count().select([0], ['imageCount'])

  # 4. Calculate trend
  trend_image = ee.Image()
  for i in config.select_indices:
    trend = ee.ImageCollection(collection.select(['Date', config.select_indices[i]])) \
      .reduce(ee.Reducer.linearFit().unweighted()) \
      .select(['scale'], [config.select_indices[i].toString()+'_slope'])
    trend_image = trend_image.addBands(trend)

  trend_image = trend_image.multiply(ee.Image.constant(3650))

  # 5. Calculate basic collection statistics
  #
  reduced_image = ee.Image() \
    .addBands(collection.select(config.select_indices).reduce(ee.Reducer.mean())) \
    .addBands(collection.select(config.select_indices).reduce(ee.Reducer.stdDev())) \
    .addBands(collection.select(config.select_indices).reduce(ee.Reducer.minMax())) \
    .addBands(collection.select(config.select_indices).reduce(ee.Reducer.percentile([10, 25, 50, 75, 90])))
  #

  # 6. Create visual output
  trend_image = trend_image
  trend_image_visual = trend_image.select(config.select_TCtrend_bands).unitScale(-1200, 1200) # Scale to values from -0.12 to 0.12 \
    .multiply(ee.Image.constant(255)).uint8(); 

  return {'visual': trend_image_visual,
          'data': trend_image,
          'image_collection': collection,
          'n_observations': image_observations.uint16()
  }

exports.runTCTrend = runTCTrend


def exportTCTrendImage(config):

  assetname = utils_string.make_TCTrendAssetNameSR(config.leftLon, config.lowLat, config.STARTYEAR, config.ENDYEAR)
  assetname_nObs = assetname + '_nObservations'

  Export.image.toAsset({
    'image': config.data_trend,
    'description': assetname,
    'assetId': assetname,
    'scale': config.SCALE,
    'region': config.geom,
    'maxPixels': 1e12
  })

  Export.image.toAsset({
    'image': config.data_n_observations,
    'description': assetname_nObs,
    'assetId': assetname_nObs,
    'scale': config.SCALE,
    'region': config.geom,
    'maxPixels': 1e12
  })

exports.exportTCTrendImage = exportTCTrendImage
