# -*- coding: utf-8 -*-
"""
Created on Wed Sep 29 13:57:56 2021

@author: initze
"""

import ee

# Function to mask Sentinel-2 clouds and shadows using QA60 and SCL
#def maskS2Sr(image):
#    band_names = image.bandNames()
    
    # Check if both QA60 and SCL exist
#    def apply_mask():
#        qa60 = image.select('QA60')
#        cloud_mask = qa60.bitwiseAnd(1 << 10).eq(0).And(qa60.bitwiseAnd(1 << 11).eq(0))#

#        scl = image.select('SCL')
#        scl_mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11))
#        mask = cloud_mask.And(scl_mask)

#        return image.updateMask(mask)

#    return ee.Algorithms.If(
#        band_names.contains('QA60').And(band_names.contains('SCL')),
#        apply_mask(),
#        image  # Return unmasked image if bands missing
#    )


def mask_s2_clouds(s2_sr_image):
    """
    Cloud masking with Cloud Probability Collection.

    """
    # Cloud Probability Collection (COPERNICUS/S2_CLOUD_PROBABILITY)
    cloud_prob_col = ee.ImageCollection('COPERNICUS/S2_CLOUD_PROBABILITY')
    
    # Hole das entsprechende Cloud-Probability-Bild per 'system:index'
    cloud_mask = cloud_prob_col.filter(ee.Filter.eq('system:index', s2_sr_image.get('system:index'))).first()
    
    # Setze Schwelle (z.B. < 60% Wolkenwahrscheinlichkeit)
    cloud_prob_thresh = 60
    cloud_mask = cloud_mask.select('probability').lt(cloud_prob_thresh)
    
    # Maske anwenden
    return s2_sr_image.updateMask(cloud_mask).copyProperties(s2_sr_image, s2_sr_image.propertyNames())

def mask_snow_probability_and_scl(image):
    scl = image.select('SCL')
    snow_prob = image.select('MSK_SNWPRB')
    
    # Keep pixels where SCL ≠ 11 (not snow/ice) and snow_prob ≤ 20%
    combined_mask = scl.neq(11).And(snow_prob.lte(20))
    
    return image.updateMask(combined_mask)

# gets patchy fast, not applied
def mask_snow_ice_ndsi(image):
    ndsi = image.normalizedDifference(['B3', 'B11']).rename('NDSI')
    snow_mask = ndsi.lt(0.9)  # mask out pixels with NDSI >= 0.4 (likely snow/ice)
    return image.updateMask(snow_mask)

def mask_cloudshadow_SCL(image):
    scl = image.select("SCL")
    return image.updateMask(scl.neq(3))

def mask_defect_SCL(image):
    scl = image.select("SCL")
    return image.updateMask(scl.neq(1))

def mask_cirrus_SCL(image):
    scl = image.select("SCL")
    return image.updateMask(scl.neq(10))

def rename_s2_bands(image):
    return image.select(
        ['B2', 'B3', 'B4', 'B8', 'B11', 'B12'],
        ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7']
    )

# Sentinel-2 SR scaling
def scale_offset_sentinel(image):
    optical_bands = image.select(['SR_B.*']).multiply(0.0001)  # Scale factor only
    return image.addBands(optical_bands, None, True)


# Resamples SWIR bands (SR_B5, SR_B7) to 10m resolution
def resample_swir_to_10m(image):
    # 10m projection (based on B2 for example)
    proj_10m = image.select('SR_B1').projection()
    
    # Resample and reproject
    swir_resampled = image.select(['SR_B5', 'SR_B7'])\
        .resample('bilinear')\
        .reproject(crs=proj_10m.crs(), scale=10)

    other_bands = image.select(['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'Date'])

    return other_bands.addBands(swir_resampled)

# Adds decimal date band
#def make_dateband(image):
#    factor = ee.Number(864000000000)
#    time = ee.Number(image.get("system:time_start"))
#    date_band = ee.Image.constant(time.toDouble().divide(factor)).toFloat().rename('Date')
#    return image.addBands(date_band)

def make_dateband(image):
    ms_to_days = ee.Number(1000 * 60 * 60 * 24)  # 86,400,000
    time = ee.Number(image.get("system:time_start"))
    date_band = ee.Image.constant(time.divide(ms_to_days)).toFloat().rename('Date')
    return image.addBands(date_band)

# Function to compute std range
def calculate_std_diff(imageCollection, n_std):
    band_names = imageCollection.first().bandNames()
    mean = imageCollection.reduce(ee.Reducer.mean()).rename(band_names)
    std = imageCollection.reduce(ee.Reducer.stdDev()).rename(band_names).multiply(n_std)
    return [mean.subtract(std), mean.add(std)]

# Function to mask by std thresholds
def update_mask_by_std(image, lower_limits, upper_limits, band_selection):
    updated_mask = image.lt(upper_limits).And(image.gt(lower_limits)).select(band_selection).reduce(ee.Reducer.min())
    return image.updateMask(image.mask().And(updated_mask))

# Main preprocessing pipeline for Sentinel-2 SR
#def preprocessed_S2_collection(bbox, date_filter_yr, date_filter_mth, meta_filter_cld):
#    collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
#        .filterBounds(bbox)\
#        .filter(date_filter_yr)\
#        .filter(date_filter_mth)\
#        .filter(meta_filter_cld)\
#        .map(rename_s2_bands)\
#        .map(scale_offset_sentinel)\
#        .map(make_dateband)\
#        .map(resample_swir_to_10m)\
#        .select(['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7', 'Date'])
#    
#    return collection

def preprocessed_S2_collection(bbox, date_filter_yr, date_filter_mth, meta_filter_cld):
    # Lade SR und Cloud-Probability Collections
    s2_sr = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
        .filterBounds(bbox)\
        .filter(date_filter_yr)\
        .filter(date_filter_mth)\
        .filter(meta_filter_cld)
    
    s2_clouds = ee.ImageCollection('COPERNICUS/S2_CLOUD_PROBABILITY')\
        .filterBounds(bbox)\
        .filter(date_filter_yr)\
        .filter(date_filter_mth)
    
    # Verbinde SR und Cloud-Probability Collection per system:index
    join = ee.Join.inner()
    filter_time_eq = ee.Filter.equals(leftField='system:index', rightField='system:index')
    joined = join.apply(s2_sr, s2_clouds, filter_time_eq)
    
    # Funktion, die SR-Bild + Cloud-Maske zusammenführt
    def merge_and_mask(join_result):
        img = ee.Image(join_result.get('primary'))
        cloud_mask = ee.Image(join_result.get('secondary'))
        img = img.set('cloud_mask', cloud_mask)
        return mask_s2_clouds(img)
    
    # Maskierte Collection erzeugen
    masked_collection = ee.ImageCollection(joined.map(merge_and_mask))
    
    # Restliche Preprocessing-Schritte
    return masked_collection \
        .map(mask_snow_probability_and_scl) \
        .map(mask_cloudshadow_SCL) \
        .map(mask_defect_SCL) \
        .map(mask_cirrus_SCL) \
        .map(rename_s2_bands) \
        .map(scale_offset_sentinel) \
        .map(make_dateband) \
        .map(resample_swir_to_10m) \
        .select(['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7', 'Date'])

#---------------------------------------------------------------------------------------------------------------------------
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
#----------------------------------------------------------------------------------------------------------------------------