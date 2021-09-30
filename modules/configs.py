import ee 

date_filter_yr = ee.Filter.calendarRange(2000, 2019, 'year')
date_filter_mth = ee.Filter.calendarRange(7, 8, 'month')
meta_filter_cld = ee.Filter.lt('CLOUD_COVER', 70)
select_bands_visible = ["B1", "B2","B3","B4"]
select_indices = ["TCB", "TCG", "TCW", "NDVI", "NDMI"]
select_TCtrend_bands = ["TCB_slope", "TCG_slope", "TCW_slope"]

config_trend = {
  'date_filter_yr' : date_filter_yr,
  'date_filter_mth' : date_filter_mth,
  'meta_filter_cld' : meta_filter_cld,
  'select_bands_visible' : select_bands_visible,
  'select_indices' : select_indices,
  'select_TCtrend_bands' : select_TCtrend_bands,
  'geom' : {}
}