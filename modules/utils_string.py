import ee 
#from ee_plugin import Map 

# Create automated eastern western hemisphere detection
def make_TCTrendAssetNameSR(leftLon, lowLat, startyear, endyear):
  denom_lon = ''
  denom_lat = ''
  lon = 0
  lat = 0

  # Longitudes
  # Western hemisphere
  if leftLon < 0:
    lon = leftLon * -1
    denom_lon = 'W'
  # Eastern hemisphere
  else:
    lon = leftLon
    denom_lon = 'E'

  # Latitudes
  # Southern hemisphere
  if lowLat < 0:
    lat = lowLat * -1
    denom_lat = 'S'
  # Northern hemisphere
  else:
    lat = lowLat
    denom_lat = 'N'


  # add leading 0 for 2-digit values for name length consistency
  if lon < 100:
      lon = '0' + str(lon)
  else:
      lon = lon

  assetname = 'TCTrend_SR_'+ denom_lon + str(lon) + denom_lat + str(lat) +'_'+str(startyear)+'-'+str(endyear)+'_TCVIS'
  return assetname