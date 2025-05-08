import ee 

#from . import configs
from modules import utils_string
from modules import ms_indices_C02 as indices
from modules import utils_Landsat_SR_C02 as utils_LS


def makeLandsatSeriesSrFiltered(config):
    # 1. load Landsat data and calculate indices
    collection = utils_LS.makeLandsatSeriesSr(config['geom'], config['date_filter_yr'], config['date_filter_mth'], config['meta_filter_cld'])\
    .map(indices.ndvi) \
    .map(indices.ndmi) \
    .map(indices.ndwi) \
    .map(indices.tc) 

    # 2. Filter pixels off 3 std from mean
    std_diff = utils_LS.calculate_std_diff(collection, 3)
    lower = std_diff[0]
    upper = std_diff[1]
    def func_gsi(image):
        return utils_LS.update_mask_by_std(image, lower, upper, config.select_bands_visible)    
    collection = collection.map(func_gsi)
    
    return collection

def add_external_mask(external_mask):
    def wrap(image):
        image_mask = image.mask()
        combined_mask = image_mask.And(external_mask)
        return image.updateMask(combined_mask)
    return wrap

  #Create yearly median date function
def make_annual_mosaics(collection, startyear, endyear):
  """
  Creates an ImageCollection of annual median mosaics from the input collection.
  """
  annual_mosaics = ee.List([])
  for year in range(startyear, endyear, 1):
      yearly = collection.filter(ee.Filter.calendarRange(year, year, 'year'))
      mosaic = yearly.reduce(ee.Reducer.median())
      mosaic = mosaic.set('system:time_start', ee.Date.fromYMD(year, 7, 1).millis())
      mosaic = mosaic.addBands(ee.Image.constant(year).rename('Year').toFloat())
      annual_mosaics = annual_mosaics.add(mosaic)
  return ee.ImageCollection.fromImages(annual_mosaics)


def runTCTrend(config_trend):
  # 1. load Landsat data and calculate indices
  collection = utils_LS.makeLandsatSeriesSr(config_trend['geom'], 
                                            config_trend['date_filter_yr'], 
                                            config_trend['date_filter_mth'], 
                                            config_trend['meta_filter_cld']) \
  .map(indices.ndvi) \
  .map(indices.ndmi) \
  .map(indices.ndwi) \
  .map(indices.tc)

  if 'mask' in config_trend.keys():
      if isinstance(config_trend['mask'], ee.Image):
        collection = collection.map(add_external_mask(config_trend['mask']))
      else:
          print('Mask Layer is not an ee.Image instance')

  # 2. Filter pixels off 3 std from mean
  std_diff = utils_LS.calculate_std_diff(collection, 3)
  lower = std_diff[0]
  upper = std_diff[1]
  
  print(config_trend['select_bands_visible'])
  def mask_outliers(image):
      return utils_LS.update_mask_by_std(image, lower, upper, config_trend['select_bands_visible'])
  #annual_collection = collection.map(mask_outliers)
  
  startyear = config_trend['STARTYEAR']
  endyear = config_trend['ENDYEAR']
  annual_collection = make_annual_mosaics(collection, startyear, endyear+1) # end year must be one later trhan REAL endyear (python loop syntax)

  # TODO: This part here breaks the Collection

  # 3. Calculate image pixel count
  image_observations = annual_collection.count().select([1], ['nObservations'])
  #image_observations = collection.count().select([1], ['nObservations'])
  #image_total_count = collection.count().select([0], ['imageCount'])

  # 4. Calculate trend 
  trend_image = ee.Image()
  print(config_trend['select_indices'])
  for index in config_trend['select_indices']:
    trend = ee.ImageCollection(annual_collection.select(['Year', index + '_median'])) \
      .reduce(ee.Reducer.linearFit().unweighted()) \
      .select(['scale', 'offset', 'scale', 'scale'], 
              [index + '_slope', index + '_offset', index + '_upper', index + '_lower'])
    trend_image = trend_image.addBands(trend).clip(config_trend['geom'])

  # TODO: change factor to 10
  trend_image = trend_image.multiply(ee.Image.constant(10))

  # 6. Create visual output 
  trend_image_visual = trend_image.select(config_trend['select_TCtrend_bands']) \
                                  .unitScale(-0.12, 0.12)\
                                  .multiply(ee.Image.constant(255)).uint8() # Scale to values from -0.12 to 0.12 \
     
  return {'visual': trend_image_visual,
          'data': trend_image,
          'image_collection': annual_collection,
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


