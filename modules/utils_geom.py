import ee

def create_buffered_rectangle(leftLon, lowLat, sizeLon=1.0, sizeLat=1.0, buffer_size=0.001, geodesic=False):
    """
    Creates a rectangular ee.Geometry.Polygon with optional buffer and geodesic control.

    Args:
        leftLon (float): Left (western) longitude of the base rectangle.
        lowLat (float): Lower (southern) latitude of the base rectangle.
        sizeLon (float): Width of the rectangle in degrees. Default = 1.0.
        sizeLat (float): Height of the rectangle in degrees. Default = 1.0.
        buffer_size (float): Buffer around the rectangle in degrees. Default = 0.001.
        geodesic (bool): Whether to use geodesic (curved) edges. Default = True.

    Returns:
        ee.Geometry.Polygon: The resulting rectangular polygon.
    """
    # Expand bounds by buffer
    expanded_left = leftLon - buffer_size
    expanded_right = leftLon + sizeLon + buffer_size
    expanded_bottom = lowLat - buffer_size
    expanded_top = lowLat + sizeLat + buffer_size

    # Define the polygon coordinates
    coords = [
        [expanded_left, expanded_top],
        [expanded_left, expanded_bottom],
        [expanded_right, expanded_bottom],
        [expanded_right, expanded_top],
        [expanded_left, expanded_top]  # Close the loop
    ]

    # Return the Earth Engine Polygon
    return ee.Geometry.Polygon([coords], geodesic=geodesic)