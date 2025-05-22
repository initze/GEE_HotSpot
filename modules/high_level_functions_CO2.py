import sys

# Projekt-path, delete later on (as well as import sys)
sys.path.insert(1, '/isipd/projects/p_alex/ALEX-Development/2025-05_Praktikum-Sina/GEE_HotSpot')
import ee 

#from modules import configs
#from modules import utils_string
from modules import ms_indices_CO2 as indices
from modules import utils_Landsat_SR_CO2 as utils_LS

def makeLandsatSeriesSrFiltered(config):
    # 1. load Landsat data and calculate indices
    collection = utils_LS.makeLandsatSeriesSr(config['geom'], config['date_filter_yr'], config['date_filter_mth'], config['meta_filter_cld'])\
    .map(indices.ndvi) \
    .map(indices.ndmi) \
    .map(indices.ndwi) \
    .map(indices.tc) 

#------------------------------------------masking, not applied--------------------------------------------------------------------
#    # 2. Filter pixels off 3 std from mean
#    std_diff = utils_LS.calculate_std_diff(collection, 3)
#    lower = std_diff[0]
#    upper = std_diff[1]
#    def func_gsi(image):
#        return utils_LS.update_mask_by_std(image, lower, upper, configs.select_bands_visible)    
#    #collection = collection.map(func_gsi)
    
#    return collection

#def add_external_mask(external_mask): #????
#    def wrap(image):
#        image_mask = image.mask()
#        combined_mask = image_mask.And(external_mask)
#        return image.updateMask(combined_mask)
#    return wrap
#---------------------------------------------------------------------------------------------------------------------------------

def make_annual_mosaics(collection, startyear, endyear):
  """
  Creates an ImageCollection of annual median mosaics from the input collection.
  """
  def make_mosaic(year):
      year = ee.Number(year)
      yearly = collection.filter(ee.Filter.calendarRange(year, year, 'year'))

      size = yearly.size()

      return ee.Algorithms.If(
          size.gt(0),
          yearly.reduce(ee.Reducer.median())
              .addBands(ee.Image.constant(year).rename('Year').toFloat())
              .set('system:time_start', ee.Date.fromYMD(year, 7, 1).millis())
              .set('id', ee.String('Landsat Annual Mosaic ').cat(year.format()))
              .set('name', year.format()),
          None
      )

  years = ee.List.sequence(startyear, endyear - 1)
  mosaics = years.map(make_mosaic)

  # Entferne None-Einträge (Jahre ohne Bilder)
  annual_mosaics = mosaics.removeAll([None])

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

#------------------------------------------------------------------------------------------------------------------DELETE?
#  if 'mask' in config_trend.keys():
#      if isinstance(config_trend['mask'], ee.Image):
#        collection = collection.map(add_external_mask(config_trend['mask']))
#      else:
#
#      print('Mask Layer is not an ee.Image instance')
#-------------------------------------------------------------------------------------------------------------------------

  # 2. Filter pixels off 2 std from mean
  std_diff = utils_LS.calculate_std_diff(collection, 2)
  lower = std_diff[0]
  upper = std_diff[1]
  
  print(config_trend['select_bands_visible'])

  def mask_outliers(image):
      return utils_LS.update_mask_by_std(image, lower, upper, config_trend['select_bands_visible'])
  masked_collection = collection.map(mask_outliers)
  
  startyear = config_trend['STARTYEAR']
  endyear = config_trend['ENDYEAR']
  annual_collection = make_annual_mosaics(masked_collection, startyear, endyear+1)


  # 3. Calculate image pixel count
  image_observations = annual_collection.count().select([1], ['nObservations'])


  # 4. Calculate trend 
  trend_image = ee.Image()
  print(config_trend['select_indices'])
  for index in config_trend['select_indices']: 
    trend = ee.ImageCollection(annual_collection.select(['Year', index + '_median'])) \
      .reduce(ee.Reducer.linearFit().unweighted()) \
      .select(['scale', 'offset', 'scale', 'scale'], 
              [index + '_slope', index + '_offset', index + '_upper', index + '_lower'])
    trend_image = trend_image.addBands(trend).clip(config_trend['geom'])

  trend_image = trend_image.multiply(ee.Image.constant(10))
  trend_image = trend_image.set({
    'description': 'TCVIS trend image',
    'start_year': config_trend['STARTYEAR'],
    'end_year': config_trend['ENDYEAR'],
    'max_cloud_cover': config_trend['max_cloud_cover'],
})

  # setup timestamps for image date metadata
  date_start = ee.Date(f'{startyear}-07-01').millis()
  date_end = ee.Date(f'{endyear}-08-31').millis()

  # 6. Create visual output 
  trend_image_visual = trend_image.select(config_trend['select_TCtrend_bands']) \
                                  .unitScale(-0.12, 0.12)\
                                  .multiply(ee.Image.constant(255)).uint8()\
                                  .set({
                                    'description': 'TCVIS trend image',
                                    'start_year': config_trend['STARTYEAR'],
                                    'end_year': config_trend['ENDYEAR'],
                                    'max_cloud_cover': config_trend['max_cloud_cover'],
                                    'longitude': ','.join(map(str, config_trend['longitudes'])),
                                    'latitude': ','.join(map(str, config_trend['latitudes'])),
                                    'system:time_start': date_start,
                                    'system:time_end': date_end,
                                  })
     
  return {'visual': trend_image_visual,
          'data': trend_image,
          'image_collection': annual_collection,
          'n_observations': image_observations.uint16(),
          'image_collection_original': masked_collection 
  }


#def exportTCTrendImage(config):
#
#  assetname = utils_string.make_TCTrendAssetNameSR(config['leftLon'], config['lowLat'], config['STARTYEAR'], config['ENDYEAR'])
#  assetname_nObs = assetname + '_nObservations'

#  ee.batch.Export.image.toAsset({
#    'image': config['data_trend'],
#    'description': assetname,
#    'assetId': assetname,
#    'scale': config['SCALE'],
#    'region': config['geom'],
#    'maxPixels': 1e12
#  })

#  ee.batch.Export.image.toAsset({
#    'image': config['data_n_observations'],
#    'description': assetname_nObs,
#    'assetId': assetname_nObs,
#    'scale': config['SCALE'],
#    'region': config['geom'],
#    'maxPixels': 1e12
#  })

#def exportTCTrendImage2(config, assetname):
#  ee.batch.Export.image.toAsset(
#    image=config['data_trend'],
#    description= assetname,
#    assetId= assetname,
#    scale= config['SCALE'],
#    region= config['geom'],
#    maxPixels= 1e12
#  )


