import sys

# Projekt-Hauptverzeichnis zum Importpfad hinzufügen
sys.path.insert(1, '/isipd/projects/p_alex/ALEX-Development/2025-05_Praktikum-Sina/GEE_HotSpot')
import ee 

from modules import configs
from modules import utils_string
from modules import ms_indices_C02 as indices
from modules import nutils_Landsat_SR_C02_mask as nutils_LS

def makeLandsatSeriesSrFiltered(config):
    # 1. load Landsat data and calculate indices
    collection = nutils_LS.makeLandsatSeriesSr(config['geom'], config['date_filter_yr'], config['date_filter_mth'], config['meta_filter_cld'])\
    .map(indices.ndvi) \
    .map(indices.ndmi) \
    .map(indices.ndwi) \
    .map(indices.tc) 

#----------------------------------------------------------------------------------------------------------------------mask- both unnessecary?
    # 2. Filter pixels off 3 std from mean
    std_diff = nutils_LS.calculate_std_diff(collection, 3)
    lower = std_diff[0]
    upper = std_diff[1]
    def func_gsi(image):
        return nutils_LS.update_mask_by_std(image, lower, upper, configs.select_bands_visible)    
    #collection = collection.map(func_gsi)
    
    return collection

def add_external_mask(external_mask): #????
    def wrap(image):
        image_mask = image.mask()
        combined_mask = image_mask.And(external_mask)
        return image.updateMask(combined_mask)
    return wrap
#---------------------------------------------------------------------------------------------------------------------------------

#Old Annual Mosaic function without filtering empty mosaics
#def make_annual_mosaics(collection, startyear, endyear):
#  """
#  Creates an ImageCollection of annual median mosaics from the input collection.
#  """
#  annual_mosaics = ee.List([])
#  for year in range(startyear, endyear, 1):
#      # filter collection down to specific year
#      start_date = f'{year}-01-01'
#      end_date = f'{year}-12-31'
#      yearly = collection.filterDate(start_date, end_date)

#      yearly = collection.filter(ee.Filter.calendarRange(year, year, 'year'))
#      # calculate median and add to new mosaic image
#      mosaic = yearly.reduce(ee.Reducer.median())
#      mosaic = mosaic.addBands(ee.Image.constant(year).rename('Year').toFloat())
#      # add metadata
#      mosaic = mosaic.set('system:time_start', ee.Date.fromYMD(year, 7, 1).millis())
#      mosaic = mosaic.set('id', f'Landsat Annual Mosaic {year}')
#      mosaic = mosaic.set('name', f'{year}')
#      annual_mosaics = annual_mosaics.add(mosaic)
#  return ee.ImageCollection.fromImages(annual_mosaics)

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



def nrunTCTrend(config_trend):
  # 1. load Landsat data and calculate indices
  collection = nutils_LS.makeLandsatSeriesSr(config_trend['geom'], 
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
  std_diff = nutils_LS.calculate_std_diff(collection, 2)
  lower = std_diff[0]
  upper = std_diff[1]
  
  print(config_trend['select_bands_visible'])
  def mask_outliers(image):
      return nutils_LS.update_mask_by_std(image, lower, upper, config_trend['select_bands_visible'])
  masked_collection = collection.map(mask_outliers)
  #annual_collection = collection.map(mask_outliers)
  
  startyear = config_trend['STARTYEAR']
  endyear = config_trend['ENDYEAR']
  annual_collection = make_annual_mosaics(masked_collection, startyear, endyear+1)
  #annual_collection = make_annual_mosaics(collection, startyear, endyear+1) # end year must be one later trhan REAL endyear (python loop syntax)


  # 3. Calculate image pixel count
  image_observations = annual_collection.count().select([1], ['nObservations'])
  #image_observations = collection.count().select([1], ['nObservations'])
  #image_total_count = collection.count().select([0], ['imageCount'])

#---------------------------------------------------------------------------------------------Filter empty mosaics version 1, may be fast with years as properties---
  #def filter_empty_years(image):
  #    year = image.select('Year').reduceRegion(
  #        reducer=ee.Reducer.first(),
  #        geometry=config_trend['geom'].centroid(1000),
  #        scale=1000,
  #        maxPixels=1e6
  #    ).get('Year')

  #    year = ee.Number(year)
  #    start = ee.Date.fromYMD(year, 7, 1)
  #    end = ee.Date.fromYMD(year, 8, 31)

    # Zähle, wie viele Bilder im Ursprungsdatensatz für dieses Jahr existieren
  #    count = masked_collection \
  #        .filterDate(start, end) \
  #        .size()

    # Setze die Anzahl als Property, sodass man danach filtern kann
  #    return image.set('n_images', count)

    #Annotiere alle Bilder mit der Bildanzahl
  #annual_collection_imcount = annual_collection.map(filter_empty_years)

    #Filtere Bilder mit count == 0 raus
  #annual_collection_filtered = annual_collection_imcount.filter(ee.Filter.gt('n_images', 0))
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------


  # 4. Calculate trend 
  trend_image = ee.Image()
  print(config_trend['select_indices'])
  for index in config_trend['select_indices']: 
    trend = ee.ImageCollection(annual_collection.select(['Year', index + '_median'])) \
      .reduce(ee.Reducer.linearFit().unweighted()) \
      .select(['scale', 'offset', 'scale', 'scale'], 
              [index + '_slope', index + '_offset', index + '_upper', index + '_lower'])
    trend_image = trend_image.addBands(trend).clip(config_trend['geom'])
#(annual_collection_filtered.select(['Year', index + '_median'])) \

  trend_image = trend_image.multiply(ee.Image.constant(10))

  # 6. Create visual output 
  trend_image_visual = trend_image.select(config_trend['select_TCtrend_bands']) \
                                  .unitScale(-0.12, 0.12)\
                                  .multiply(ee.Image.constant(255)).uint8() 
     
  return {'visual': trend_image_visual,
          'data': trend_image,
          'image_collection': annual_collection,
          'n_observations': image_observations.uint16(),
          'nimage_collection_original': masked_collection #collection
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


