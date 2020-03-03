// Create automated eastern western hemisphere detection
var make_TCTrendAssetNameSR = function(leftLon, lowLat, startyear, endyear){
  var denom_lon = '';
  var denom_lat = '';
  var lon = 0;
  var lat = 0;
  
  // Longitudes
  // Western hemisphere
  if (leftLon < 0){
    lon = leftLon * -1;
    denom_lon = 'W';
  }
  // Eastern hemisphere
  else {
    lon = leftLon;
    denom_lon = 'E';
  }

  // Latitudes
  // Southern hemisphere
  if (lowLat < 0){
    lat = lowLat * -1;
    denom_lat = 'S';
  }
  // Northern hemisphere
  else {
    lat = lowLat;
    denom_lat = 'N';
  }
  
  
  // add leading 0 for 2-digit values for name length consistency
  if (lon < 100){
    lon = '0' + lon.toString()} else {lon = lon.toString()
  }
  
  var assetname = 'TCTrend_SR_'+ denom_lon + lon + denom_lat + lat +'_'+startyear.toString()+'-'+endyear.toString()+'_TCVIS';
  return assetname;
};

exports.make_TCTrendAssetNameSR = make_TCTrendAssetNameSR;