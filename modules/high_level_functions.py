import ee 


from . import configs
from . import utils_string
from . import ms_indices as indices
from . import utils_Landsat_SR as utils_LS


def makeLandsatSeriesSrFiltered(config):
    # 1. load Landsat data and calculate indices
    collection = utils_LS.makeLandsatSeriesSr(config['geom'], config['date_filter_yr'], config['date_filter_mth'], config['meta_filter_cld'])\
    .map(indices.ndvi57) \
    .map(indices.ndmi57) \
    .map(indices.ndwi57) \
    .map(indices.tc5)

    # 2. Filter pixels off 3 std from mean
    std_diff = utils_LS.calculate_std_diff(collection, 3)
    lower = std_diff[0]
    upper = std_diff[1]
    def func_gsi(image):
        return utils_LS.update_mask_by_std(image, lower, upper, config.select_bands_visible)    
    collection = collection.map(func_gsi)
    
    return collection


def runTCTrend(config_trend):
  # 1. load Landsat data and calculate indices
  collection = utils_LS.makeLandsatSeriesSr(config_trend['geom'], 
                                            config_trend['date_filter_yr'], 
                                            config_trend['date_filter_mth'], 
                                            config_trend['meta_filter_cld']) \
  .map(indices.ndvi57) \
  .map(indices.ndmi57) \
  .map(indices.ndwi57) \
  .map(indices.tc5)

  # 2. Filter pixels off 3 std from mean
  std_diff = utils_LS.calculate_std_diff(collection, 3)
  lower = std_diff[0]
  upper = std_diff[1]
  
  print(config_trend['select_bands_visible'])
  def mask_outliers(image):
      return utils_LS.update_mask_by_std(image, lower, upper, config_trend['select_bands_visible'])
  collection = collection.map(mask_outliers)

  # 3. Calculate image pixel count
  image_observations = collection.count().select([1], ['nObservations'])
  #image_total_count = collection.count().select([0], ['imageCount'])

  # 4. Calculate trend
  trend_image = ee.Image()
  print(config_trend['select_indices'])
  for index in config_trend['select_indices']:
    trend = ee.ImageCollection(collection.select(['Date', index])) \
      .reduce(ee.Reducer.linearFit().unweighted()) \
      .select(['scale', 'offset', 'scale', 'scale'], 
              [index + '_slope', index + '_offset', index + '_upper', index + '_lower'])
    trend_image = trend_image.addBands(trend)

  trend_image = trend_image.multiply(ee.Image.constant(3650))

  # 5. Calculate basic collection statistics
  #
  
  # 6. Create visual output
  #trend_image = trend_image
  trend_image_visual = trend_image.select(config_trend['select_TCtrend_bands']) \
                                  .unitScale(-1200, 1200)\
                                  .multiply(ee.Image.constant(255)).uint8() # Scale to values from -0.12 to 0.12 \
     

  return {'visual': trend_image_visual,
          'data': trend_image,
          'image_collection': collection,
          'n_observations': image_observations.uint16()
  }



def exportTCTrendImage(config):

  assetname = utils_string.make_TCTrendAssetNameSR(config['leftLon'], config['lowLat'], config['STARTYEAR'], config['ENDYEAR'])
  assetname_nObs = assetname + '_nObservations'

  ee.batch.Export.image.toAsset({
    'image': config['data_trend'],
    'description': assetname,
    'assetId': assetname,
    'scale': config['SCALE'],
    'region': config['geom'],
    'maxPixels': 1e12
  })

  ee.batch.Export.image.toAsset({
    'image': config['data_n_observations'],
    'description': assetname_nObs,
    'assetId': assetname_nObs,
    'scale': config['SCALE'],
    'region': config['geom'],
    'maxPixels': 1e12
  })

def exportTCTrendImage2(config, assetname):
  ee.batch.Export.image.toAsset(
    image=config['data_trend'],
    description= assetname,
    assetId= assetname,
    scale= config['SCALE'],
    region= config['geom'],
    maxPixels= 1e12
  )


