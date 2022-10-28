# -*- coding: utf-8 -*-
"""
Created on Wed Sep 29 13:28:50 2021

@author: initze
"""

import ee 

#rename bands of oli
def oli_renamebands(image):
    img = image.select(['B2', 'B3', 'B4', 'B5', 'B6', 'B7'], ['B1', 'B2', 'B3', 'B4', 'B5', 'B7'])
    return (img)


#tasseled cap

#tasseled cap for LS5
def tc5(image):
    tcb = image.expression(
    '(0.2043*a + 0.4158 * b + 0.5524 * c + 0.5741 * d + 0.3124 * e + 0.2303 * f) * 0.0001',
    {
        'a': image.select('B1'), 'b': image.select('B2'), 'c': image.select('B3'),
        'd': image.select('B4'), 'e': image.select('B5'), 'f': image.select('B7')
    }) \
    .rename('TCB')

    tcg = image.expression(
    '(-0.1603*a - 0.2819*b - 0.4934*c + 0.7940*d - 0.0002*e - 0.1446*f) * 0.0001',
    {
        'a': image.select('B1'), 'b': image.select('B2'), 'c': image.select('B3'),
        'd': image.select('B4'), 'e': image.select('B5'), 'f': image.select('B7')
    }) \
    .rename('TCG')
    tcw = image.expression(
    '(0.0315* + 0.2021*b + 0.3102*c + 0.1594*d -0.6806*e -0.6109*f) * 0.0001',
    {
        'a': image.select('B1'), 'b': image.select('B2'), 'c': image.select('B3'),
        'd': image.select('B4'), 'e': image.select('B5'), 'f': image.select('B7')
    }) \
    .rename('TCW')
    return (image.addBands(tcb).addBands(tcg).addBands(tcw)).toFloat()


def tc7(image):
    tcb = image.expression(
    '(0.3561 * a + 0.3972 * b + 0.3904 * c + 0.6966 * d + 0.2286 * e + 0.1596 * f) * 0.0001',
    {
        'a': image.select('B1'), 'b': image.select('B2'), 'c': image.select('B3'),
        'd': image.select('B4'), 'e': image.select('B5'), 'f': image.select('B7')
    }) \
    .rename('TCB')
    tcg = image.expression(
    '(-0.3344*a - 0.3544*b -0.4556*c + 0.6966*d - 0.0242*e - 0.2630*f) * 0.0001',
    {
        'a': image.select('B1'), 'b': image.select('B2'), 'c': image.select('B3'),
        'd': image.select('B4'), 'e': image.select('B5'), 'f': image.select('B7')
    }) \
    .rename('TCG')
    tcw = image.expression(
    '(0.2626*a + 0.2141*b + 0.0926*c + 0.0656*d - 0.7629*e - 0.5388*f) * 0.0001',
    {
        'a': image.select('B1'), 'b': image.select('B2'), 'c': image.select('B3'),
        'd': image.select('B4'), 'e': image.select('B5'), 'f': image.select('B7')
    }) \
    .rename('TCW')
    return (image.addBands(tcb).addBands(tcg).addBands(tcw)).toFloat()


def tc8(image):
    tcb = image.expression(
    '(0.3029 * a + 0.2786 * b + 0.4733 * c + 0.5599 * d + 0.508 * e + 0.1872 * f) * 0.0001',
    {
        'a': image.select('B2'), 'b': image.select('B3'), 'c': image.select('B4'),
        'd': image.select('B5'), 'e': image.select('B6'), 'f': image.select('B7')
    }) \
    .rename('TCB')
    tcg = image.expression(
    '(-0.2941*a - 0.243*b - 0.5424*c + 0.7276*d + 0.0713*e - 0.1608*f) * 0.0001',
    {
        'a': image.select('B1'), 'b': image.select('B2'), 'c': image.select('B3'),
        'd': image.select('B4'), 'e': image.select('B5'), 'f': image.select('B7')
    }) \
    .rename('TCG')
    tcw = image.expression(
    '(0.1511*a + 0.1973*b + 0.3283*c + 0.3407*d - 0.7117*e - 0.4559*f) * 0.0001',
    {
        'a': image.select('B1'), 'b': image.select('B2'), 'c': image.select('B3'),
        'd': image.select('B4'), 'e': image.select('B5'), 'f': image.select('B7')
    }) \
    .rename('TCW')
    return  (image.addBands(tcb).addBands(tcg).addBands(tcw)).toFloat()


#calculate NDVI
#Landsat 8
def ndvi8(image):
  ndvi = image.normalizedDifference(['B5', 'B4']).rename('NDVI')
  return image.addBands(ndvi)

#Landsat 5 and 7
def ndvi57(image):
  ndvi = image.normalizedDifference(['B4', 'B3']).rename('NDVI')
  return image.addBands(ndvi)


#calculate NDMI
#Landsat 8
def ndmi8(image):
  ndmi = image.normalizedDifference(['B5', 'B6']).rename('NDMI')
  return image.addBands(ndmi)

#Landsat 5 and 7
def ndmi57(image):
  ndmi = image.normalizedDifference(['B4', 'B5']).rename('NDMI')
  return image.addBands(ndmi)


def nbr(image):
  nbr = image.normalizedDifference(['B7', 'B4']).rename('NBR')
  return image.addBands(nbr)


def ndwi8(image):
  ndwi = image.normalizedDifference(['B3', 'B5']).rename('NDWI')
  return image.addBands(ndwi)

#Landsat 5 and 7
def ndwi57(image):
  ndwi = image.normalizedDifference(['B2', 'B4']).rename('NDWI')
  return image.addBands(ndwi)


def nbr_S2(image):
  nbr = image.normalizedDifference(['B8', 'B12']).rename('NBR')
  return image.addBands(nbr)



# Future Version
def tc_br_l5(image):
  return ee.Image(0).expression(
      '(f1 * b) + (f2 * g) + (f3 * r) + (f4 * nir) + (f5 * swir1) + (f6 * swir2)',
      {
        'b': image.select('B1'),
        'g': image.select('B2'),
        'r': image.select('B3'),
        'nir': image.select('B4'),
        'swir1': image.select('B5'),
        'swir2': image.select('B7'),
        'f1':0.2043,
        'f2':0.4158,
        'f3':0.5524,
        'f4':0.5741,
        'f5':0.3124,
        'f6':0.2303
      })

def tc_gr_l5(image):
  return ee.Image(0).expression(
      '(f1 * b) + (f2 * g) + (f3 * r) + (f4 * nir) + (f5 * swir1) + (f6 * swir2)',
      {
        'b': image.select('B1'),
        'g': image.select('B2'),
        'r': image.select('B3'),
        'nir': image.select('B4'),
        'swir1': image.select('B5'),
        'swir2': image.select('B7'),
        'f1':-0.1603,
        'f2':-0.2819,
        'f3':-0.4934,
        'f4':0.7940,
        'f5':-0.0002,
        'f6':-0.1446
      })

def tc_we_l5(image):
  return ee.Image(0).expression(
      '(f1 * b) + (f2 * g) + (f3 * r) + (f4 * nir) + (f5 * swir1) + (f6 * swir2)',
      {
        'b': image.select('B1'),
        'g': image.select('B2'),
        'r': image.select('B3'),
        'nir': image.select('B4'),
        'swir1': image.select('B5'),
        'swir2': image.select('B7'),
        'f1':0.0315,
        'f2':0.2021,
        'f3':0.3102,
        'f4':0.1594,
        'f5':-0.6806,
        'f6':-0.6109
      })


# tasseled cap for LS8
def tc_br_l8(image):
  return ee.Image(0).expression(
      '(f1 * b) + (f2 * g) + (f3 * r) + (f4 * nir) + (f5 * swir1) + (f6 * swir2)',
      {
        'b': image.select('B1'),
        'g': image.select('B2'),
        'r': image.select('B3'),
        'nir': image.select('B4'),
        'swir1': image.select('B5'),
        'swir2': image.select('B7'),
        'f1':0.3029,
        'f2':0.2786,
        'f3':0.4733,
        'f4':0.5599,
        'f5':0.508,
        'f6':0.1872
      })

def tc_gr_l8(image):
  return ee.Image(0).expression(
      '(f1 * b) + (f2 * g) + (f3 * r) + (f4 * nir) + (f5 * swir1) + (f6 * swir2)',
      {
        'b': image.select('B1'),
        'g': image.select('B2'),
        'r': image.select('B3'),
        'nir': image.select('B4'),
        'swir1': image.select('B5'),
        'swir2': image.select('B7'),
        'f1':-0.2941,
        'f2':-0.243,
        'f3':-0.5424,
        'f4':0.7276,
        'f5':0.0713,
        'f6':-0.1608
      })

def tc_we_l8(image):
  return ee.Image(0).expression(
      '(f1 * b) + (f2 * g) + (f3 * r) + (f4 * nir) + (f5 * swir1) + (f6 * swir2)',
      {
        'b': image.select('B1'),
        'g': image.select('B2'),
        'r': image.select('B3'),
        'nir': image.select('B4'),
        'swir1': image.select('B5'),
        'swir2': image.select('B7'),
        'f1':0.1511,
        'f2':0.1973,
        'f3':0.3283,
        'f4':0.3407,
        'f5':-0.7117,
        'f6':-0.4559
      })