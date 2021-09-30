# -*- coding: utf-8 -*-
"""
Created on Wed Sep 29 13:57:56 2021

@author: initze
"""

import ee


def harmonizationRoy(oli):
  slopes = ee.Image.constant([0.9785, 0.9542, 0.9825, 1.0073, 1.0171, 0.9949]);        # RMA - create an image of slopes per band for L8 TO L7 regression line - David Roy
  itcp = ee.Image.constant([-0.0095, -0.0016, -0.0022, -0.0021, -0.0030, 0.0029]);     # RMA - create an image of y-intercepts per band for L8 TO L7 regression line - David Roy
  y = oli.select(['B2','B3','B4','B5','B6','B7'],['B1', 'B2', 'B3', 'B4', 'B5', 'B7']) \
  .resample('bicubic') \
  .subtract(itcp.multiply(10000)).divide(slopes) \
  .set('system:time_start', oli.get('system:time_start'))                      
  return y.toShort().addBands(oli.select(['pixel_qa']))

def maskLsSr(image):
  # Bits 3 and 5 are cloud shadow and cloud, respectively.
  cloudShadowBitMask = (1 << 3)
  snowBitMask = (1 << 4)
  cloudsBitMask = (1 << 5)
  terrainBitMask = (1 << 10)
  # Get the pixel QA band.
  qa = image.select('pixel_qa')
  # Both flags should be set to zero, indicating clear conditions.
  mask = qa.bitwiseAnd(cloudShadowBitMask).eq(0) \
                 .And(qa.bitwiseAnd(snowBitMask).eq(0)) \
                 .And(qa.bitwiseAnd(cloudsBitMask).eq(0)) \
                 .And(qa.bitwiseAnd(terrainBitMask).eq(0))
  return image.updateMask(mask)

# -------------- TESTING REQUIRED --------------
#Create yearly median date function
def yearly_median(image_collection, startyear, endyear):
  #get image years of full collection
  reduced_image_collection = ee.List([])
  #iterate over each year - Needs testing
  for year in range(startyear, endyear, 1):
      im = image_collection.filter(ee.Filter.calendarRange(year, year, 'year')) \
      .reduce(ee.Reducer.median()) \
      .set({'id': year})
      # make band for each year, needs explicit variable, otherwise error
      year_band = ee.Image.constant(year).toFloat().rename('Year')
      im = im.addBands(year_band)
    
      reduced_image_collection = reduced_image_collection.add(im)
  #print (year)

  return ee.ImageCollection.fromImages(reduced_image_collection)


# function calculates mean +- standard deviation bvalues for each band and pixel
def calculate_std_diff(imageCollection, n_std):
  band_names = imageCollection.first().bandNames()
  collection_mean = imageCollection \
  .reduce(ee.Reducer.mean()) \
  .rename(band_names)
  collection_std = imageCollection \
  .reduce(ee.Reducer.stdDev()) \
  .rename(band_names) \
  .multiply(ee.Image.constant(3)) 

  lower = collection_mean.subtract(collection_std)
  upper = collection_mean.add(collection_std)
  return [lower, upper]


# function calculates mean +- standard deviation bvalues for each band and pixel - more efficient version?
def calculate_std_diff_2(imageCollection, n_std):
  reducer = ee.Reducer.mean().combine({
    'reducer2': ee.Reducer.stdDev(),
    'sharedInputs': True
  })

  band_names = imageCollection.first().bandNames()
  stats = imageCollection.reduce(reducer)

  # Extract means and SDs to images.
  collection_mean = stats \
                      .select('.*_mean') \
                      .rename(band_names)
  collection_std = stats \
                    .select('.*_stdDev') \
                    .rename(band_names) \
                    .multiply(ee.Image.constant(n_std))

  lower = collection_mean.subtract(collection_std)
  upper = collection_mean.add(collection_std)
  return [lower, upper]


# function masks all pixels outside the lower and upper boundary limits
def update_mask_by_std(image, lower_limits, upper_limits, band_selection):
  updated_mask = image.lt(upper_limits) \
  .And(image.gt(lower_limits)) \
  .select(band_selection) \
  .reduce(ee.Reducer.min())
  final_mask = image.mask().multiply(updated_mask)
  return image.updateMask(final_mask)


# function takes acquisition time and converts to decadal values
def make_dateband(image):
  factor = ee.Number(864000000000)
  time = ee.Number(image.get("system:time_start"))
  time2 = time.toDouble().divide(factor)
  date_image = ee.Image.constant(time2).toFloat().select([0], ['Date'])
  #TODO: rename to 'Date'
  return image.addBands(date_image)

def preprocessed_L8_collection(dataset_name, bbox, date_filter_yr, date_filter_mth, meta_filter_cld):
  collection = ee.ImageCollection(dataset_name)\
  .filterBounds(bbox)\
  .filter(date_filter_yr)\
  .filter(date_filter_mth)\
  .filter(meta_filter_cld)\
  .map(harmonizationRoy)\
  .map(maskLsSr)\
  .map(make_dateband)\
  .select('B1', 'B2', 'B3', 'B4', 'B5', 'B7', 'pixel_qa', 'Date')
  return collection


def preprocessed_L57_collection(dataset_name, bbox, date_filter_yr, date_filter_mth, meta_filter_cld):
  collection = ee.ImageCollection(dataset_name)\
  .filterBounds(bbox)\
  .filter(date_filter_yr)\
  .filter(date_filter_mth)\
  .filter(meta_filter_cld)\
  .map(maskLsSr)\
  .map(make_dateband)\
  .select('B1', 'B2', 'B3', 'B4', 'B5', 'B7', 'pixel_qa', 'Date')
  return collection


def makeLandsatSeriesSr(bbox, date_filter_yr, date_filter_mth, meta_filter_cld):
  l5 = preprocessed_L57_collection('LANDSAT/LT05/C01/T1_SR', bbox, date_filter_yr, date_filter_mth, meta_filter_cld)
  l7 = preprocessed_L57_collection('LANDSAT/LE07/C01/T1_SR', bbox, date_filter_yr, date_filter_mth, meta_filter_cld)
  l8 = preprocessed_L8_collection('LANDSAT/LC08/C01/T1_SR', bbox, date_filter_yr, date_filter_mth, meta_filter_cld)
  return l5.merge(l7).merge(l8)


# create geometries from lists of longitude and latitute coordinates
# returns list
def geoms_from_coordlists(longitudes, latitudes, sizeLon, sizeLat):
  geoms = ee.List([])
  for i in longitudes:
    for j in latitudes:
      #code create geometry
      print(longitudes[i], latitudes[j])
      geom = ee.Geometry.Rectangle([longitudes[i], latitudes[j], longitudes[i]+ sizeLon, latitudes[j]+sizeLat])
      geoms = geoms.add(geom)
  return geoms

# remove bands by regex
def remove_bands(image, band_name):
  return image.select(image.bandNames().filter(ee.Filter.stringContains('item', band_name).Not()))