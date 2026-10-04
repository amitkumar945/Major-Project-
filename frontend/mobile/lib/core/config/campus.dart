import 'package:latlong2/latlong.dart';

/// The real DSVV campus geometry, copied verbatim from `backend/constants.py`
/// (OpenStreetMap way/1152422760). These are NOT invented coordinates, and
/// they must stay identical to the server's copy: `validators.validate_location`
/// rejects any complaint tagged outside this fence, so a drifted client-side
/// polygon would let the app accept a pin the API then refuses.
class Campus {
  const Campus._();

  static const LatLng center = LatLng(29.99965, 78.1946);

  /// Vertices as (latitude, longitude), matching the Python tuple order.
  static const List<LatLng> polygon = [
    LatLng(30.0018344, 78.1905549),
    LatLng(29.9997622, 78.1906804),
    LatLng(29.9997529, 78.1909221),
    LatLng(29.9990507, 78.1909547),
    LatLng(29.9990560, 78.1906994),
    LatLng(29.9982475, 78.1907323),
    LatLng(29.9979564, 78.1912310),
    LatLng(29.9973232, 78.1919827),
    LatLng(29.9963837, 78.1931417),
    LatLng(29.9960528, 78.1935266),
    LatLng(29.9976137, 78.1954428),
    LatLng(29.9975361, 78.1955205),
    LatLng(29.9969588, 78.1960770),
    LatLng(29.9967062, 78.1963394),
    LatLng(29.9977739, 78.1974088),
    LatLng(29.9972499, 78.1979616),
    LatLng(29.9979125, 78.1986453),
    LatLng(29.9983217, 78.1980056),
    LatLng(29.9986674, 78.1974636),
    LatLng(29.9990781, 78.1969717),
    LatLng(29.9997395, 78.1959467),
    LatLng(30.0004379, 78.1950392),
    LatLng(30.0010698, 78.1940502),
    LatLng(30.0018910, 78.1929093),
    LatLng(30.0032553, 78.1910827),
    LatLng(30.0029709, 78.1908111),
    LatLng(30.0018757, 78.1909007),
    LatLng(30.0018344, 78.1905549),
  ];

  /// The padded bounding box the server actually enforces (~150 m beyond the
  /// polygon), so a GPS fix at the gate or a wall-side hostel is still valid.
  /// The app checks against THIS, exactly like `in_campus_bounds` does.
  static const double minLatitude = 29.9946;
  static const double maxLatitude = 30.0047;
  static const double minLongitude = 78.1890;
  static const double maxLongitude = 78.2002;

  static const LatLng southWest = LatLng(minLatitude, minLongitude);
  static const LatLng northEast = LatLng(maxLatitude, maxLongitude);

  /// Mirrors `validators.in_campus_bounds` — the check the API applies.
  static bool inBounds(double latitude, double longitude) {
    return latitude >= minLatitude &&
        latitude <= maxLatitude &&
        longitude >= minLongitude &&
        longitude <= maxLongitude;
  }

  /// Ray-casting test against the true outline. Used only to tell the user
  /// "that pin looks outside the campus" while they drag; submission is gated
  /// by [inBounds], which is what the server enforces.
  static bool inPolygon(double latitude, double longitude) {
    var inside = false;
    for (var i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      final lat1 = polygon[i].latitude, lng1 = polygon[i].longitude;
      final lat2 = polygon[j].latitude, lng2 = polygon[j].longitude;
      final intersects = (lng1 > longitude) != (lng2 > longitude) &&
          latitude < (lat2 - lat1) * (longitude - lng1) / (lng2 - lng1) + lat1;
      if (intersects) inside = !inside;
    }
    return inside;
  }

  static const double defaultZoom = 16.0;
  static const double minZoom = 14.0;
  static const double maxZoom = 19.0;

  /// CARTO Voyager raster tiles with OSM/CARTO attribution rendered on the map.
  static const String tileUrl =
      'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png';
  static const String tileAttribution =
      '© OpenStreetMap contributors · © CARTO';
}
