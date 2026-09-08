import 'package:geolocator/geolocator.dart';

import '../core/config/campus.dart';

/// Why a location request could not be satisfied, so the UI can offer the
/// right next step rather than one generic error.
enum LocationFailure {
  serviceDisabled, // GPS is off at the OS level
  denied, // user said no this time
  deniedForever, // user said "don't ask again" - needs app settings
  timeout, // no fix in time, e.g. indoors
  unknown,
}

class LocationResult {
  const LocationResult.success(this.latitude, this.longitude, {this.accuracy})
      : failure = null;
  const LocationResult.failed(this.failure)
      : latitude = null,
        longitude = null,
        accuracy = null;

  final double? latitude;
  final double? longitude;
  final double? accuracy;
  final LocationFailure? failure;

  bool get isSuccess => failure == null && latitude != null;

  /// Whether this fix falls inside the fence the server enforces.
  bool get isOnCampus =>
      isSuccess && Campus.inBounds(latitude!, longitude!);

  String get message {
    switch (failure) {
      case LocationFailure.serviceDisabled:
        return 'Location is switched off. Turn on GPS to use your current position.';
      case LocationFailure.denied:
        return 'Location permission was declined. You can still drop the pin on the map.';
      case LocationFailure.deniedForever:
        return 'Location permission is blocked. Enable it in Settings, or place the pin manually.';
      case LocationFailure.timeout:
        return 'Could not get a GPS fix. Move near a window or place the pin manually.';
      case LocationFailure.unknown:
        return 'Could not read your location. Please place the pin on the map.';
      case null:
        return '';
    }
  }
}

/// GPS access, wrapped so screens never touch the permission plumbing.
///
/// Failure is always recoverable here: every screen that asks for a fix also
/// lets the user drag a pin, because a denied permission must not make it
/// impossible to file a complaint.
class LocationService {
  LocationService._();
  static final LocationService instance = LocationService._();

  Future<bool> isServiceEnabled() => Geolocator.isLocationServiceEnabled();

  /// Ask for permission, following the Android flow: check, then request only
  /// if not already decided.
  Future<LocationPermission> ensurePermission() async {
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    return permission;
  }

  Future<LocationResult> current({
    Duration timeout = const Duration(seconds: 15),
  }) async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      return const LocationResult.failed(LocationFailure.serviceDisabled);
    }

    final permission = await ensurePermission();
    if (permission == LocationPermission.deniedForever) {
      return const LocationResult.failed(LocationFailure.deniedForever);
    }
    if (permission == LocationPermission.denied) {
      return const LocationResult.failed(LocationFailure.denied);
    }

    try {
      // geolocator 12 takes these directly; it builds the platform-specific
      // LocationSettings internally.
      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: timeout,
      );
      return LocationResult.success(
        position.latitude,
        position.longitude,
        accuracy: position.accuracy,
      );
    } catch (_) {
      // Timeout indoors is the common case; fall back to the last known fix
      // rather than making the user wait again for nothing.
      try {
        final last = await Geolocator.getLastKnownPosition();
        if (last != null) {
          return LocationResult.success(last.latitude, last.longitude,
              accuracy: last.accuracy);
        }
      } catch (_) {
        // ignored: treated as a plain timeout below
      }
      return const LocationResult.failed(LocationFailure.timeout);
    }
  }

  /// Opens the OS settings page, for the "blocked forever" case.
  Future<void> openAppSettings() => Geolocator.openAppSettings();
  Future<void> openLocationSettings() => Geolocator.openLocationSettings();
}
