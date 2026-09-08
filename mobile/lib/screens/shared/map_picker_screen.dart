import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../../core/config/campus.dart';
import '../../core/theme/app_theme.dart';
import '../../models/complaint.dart';
import '../../services/location_service.dart';
import '../../widgets/common.dart';

/// Pick the complaint location on the DSVV campus map.
///
/// Two ways in, because either can fail the user: the GPS button for someone
/// standing at the problem, and dragging the map for someone reporting it
/// later or indoors where the fix is poor.
///
/// The campus outline is drawn from the same polygon the server validates
/// against, so "inside the shaded area" means exactly "the API will accept it".
class MapPickerScreen extends StatefulWidget {
  const MapPickerScreen({super.key, this.initial});

  /// Re-opening the picker keeps whatever was chosen last time.
  final ComplaintLocation? initial;

  @override
  State<MapPickerScreen> createState() => _MapPickerScreenState();
}

class _MapPickerScreenState extends State<MapPickerScreen> {
  final MapController _map = MapController();
  final TextEditingController _landmark = TextEditingController();
  final TextEditingController _building = TextEditingController();
  final TextEditingController _room = TextEditingController();

  late LatLng _pin;
  bool _locating = false;
  String? _locationMessage;
  String? _landmarkError;

  @override
  void initState() {
    super.initState();

    final initial = widget.initial;
    _pin = (initial != null && initial.hasCoordinates)
        ? LatLng(initial.latitude!, initial.longitude!)
        : Campus.center;

    _landmark.text = initial?.address ?? '';
    _building.text = initial?.building ?? '';
    _room.text = initial?.room ?? '';

    // Only auto-locate on a fresh pick; re-opening should not move the pin the
    // user already placed.
    if (initial == null || !initial.hasCoordinates) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _useCurrentLocation());
    }
  }

  @override
  void dispose() {
    _landmark.dispose();
    _building.dispose();
    _room.dispose();
    super.dispose();
  }

  bool get _pinOnCampus => Campus.inBounds(_pin.latitude, _pin.longitude);

  Future<void> _useCurrentLocation() async {
    setState(() {
      _locating = true;
      _locationMessage = null;
    });

    final result = await LocationService.instance.current();
    if (!mounted) return;

    setState(() => _locating = false);

    if (!result.isSuccess) {
      setState(() => _locationMessage = result.message);

      // "Blocked forever" is the one case the user cannot fix from here.
      if (result.failure == LocationFailure.deniedForever && mounted) {
        final open = await confirm(
          context,
          title: 'Location is blocked',
          message:
              'Location permission is turned off for this app. Open Settings to allow it, or place the pin on the map yourself.',
          confirmLabel: 'Open settings',
          cancelLabel: 'Place manually',
        );
        if (open) await LocationService.instance.openAppSettings();
      } else if (result.failure == LocationFailure.serviceDisabled && mounted) {
        final open = await confirm(
          context,
          title: 'Location is switched off',
          message:
              'Turn on GPS to use your current position, or place the pin on the map yourself.',
          confirmLabel: 'Turn on GPS',
          cancelLabel: 'Place manually',
        );
        if (open) await LocationService.instance.openLocationSettings();
      }
      return;
    }

    final fix = LatLng(result.latitude!, result.longitude!);
    setState(() {
      _pin = fix;
      _locationMessage = result.isOnCampus
          ? null
          : 'You appear to be outside the campus. Move the pin to the correct spot on campus.';
    });
    _map.move(fix, 17);
  }

  void _confirmSelection() {
    final landmark = _landmark.text.trim();

    // The server requires a landmark as well as coordinates, so it is checked
    // here rather than letting the submit fail two screens later.
    if (landmark.isEmpty) {
      setState(() => _landmarkError = 'Enter a landmark or building name');
      return;
    }

    if (!_pinOnCampus) {
      showSnack(
        context,
        'The pin must be inside the DSVV campus.',
        isError: true,
      );
      return;
    }

    Navigator.of(context).pop(
      ComplaintLocation(
        latitude: _pin.latitude,
        longitude: _pin.longitude,
        address: landmark,
        building: _building.text.trim(),
        room: _room.text.trim(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Complaint location'),
        actions: [
          TextButton(
            onPressed: _confirmSelection,
            child: const Text('Done'),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: Stack(
              children: [
                FlutterMap(
                  mapController: _map,
                  options: MapOptions(
                    initialCenter: _pin,
                    initialZoom: Campus.defaultZoom,
                    minZoom: Campus.minZoom,
                    maxZoom: Campus.maxZoom,
                    // Keep the user on campus: panning to another city would
                    // only produce a pin the server rejects.
                    cameraConstraint: CameraConstraint.contain(
                      bounds: LatLngBounds(Campus.southWest, Campus.northEast),
                    ),
                    onTap: (_, point) => setState(() => _pin = point),
                  ),
                  children: [
                    TileLayer(
                      urlTemplate: Campus.tileUrl,
                      userAgentPackageName: 'in.ac.dsvv.grievance',
                      maxZoom: Campus.maxZoom,
                    ),
                    PolygonLayer(
                      polygons: [
                        Polygon(
                          points: Campus.polygon,
                          color: AppColors.brand600.withValues(alpha: 0.10),
                          borderColor: AppColors.brand600,
                          borderStrokeWidth: 2,
                        ),
                      ],
                    ),
                    MarkerLayer(
                      markers: [
                        Marker(
                          point: _pin,
                          width: 44,
                          height: 44,
                          alignment: Alignment.topCenter,
                          child: Icon(
                            Icons.location_on,
                            size: 44,
                            color: _pinOnCampus
                                ? AppColors.brand600
                                : AppColors.red600,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),

                // Attribution is required by the OSM tile usage policy.
                Positioned(
                  left: 0,
                  bottom: 0,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 6, vertical: 2),
                    color: Colors.white70,
                    child: const Text(
                      Campus.tileAttribution,
                      style: TextStyle(fontSize: 10, color: AppColors.slate600),
                    ),
                  ),
                ),

                Positioned(
                  top: 12,
                  left: 12,
                  right: 12,
                  child: _hintBanner(),
                ),

                Positioned(
                  right: 12,
                  bottom: 20,
                  child: FloatingActionButton(
                    heroTag: 'locate',
                    onPressed: _locating ? null : _useCurrentLocation,
                    backgroundColor: Colors.white,
                    foregroundColor: AppColors.brand600,
                    tooltip: 'Use my current location',
                    child: _locating
                        ? const SizedBox(
                            width: 22,
                            height: 22,
                            child: CircularProgressIndicator(strokeWidth: 2.5),
                          )
                        : const Icon(Icons.my_location_rounded),
                  ),
                ),
              ],
            ),
          ),

          _detailsSheet(),
        ],
      ),
    );
  }

  Widget _hintBanner() {
    final message = _locationMessage ??
        (_pinOnCampus
            ? 'Tap the map to move the pin to the exact spot.'
            : 'The pin is outside the campus. Move it inside the shaded area.');
    final isProblem = _locationMessage != null || !_pinOnCampus;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: isProblem ? AppColors.red50 : Colors.white,
        borderRadius: BorderRadius.circular(10),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.12),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        children: [
          Icon(
            isProblem ? Icons.warning_amber_rounded : Icons.touch_app_outlined,
            size: 18,
            color: isProblem ? AppColors.red600 : AppColors.brand600,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: TextStyle(
                fontSize: 13,
                height: 1.35,
                color: isProblem ? AppColors.red600 : AppColors.slate700,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _detailsSheet() {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      padding: EdgeInsets.fromLTRB(
        16,
        16,
        16,
        16 + MediaQuery.of(context).viewInsets.bottom,
      ),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                const Icon(Icons.place_outlined,
                    size: 16, color: AppColors.slate400),
                const SizedBox(width: 6),
                Text(
                  '${_pin.latitude.toStringAsFixed(5)}, ${_pin.longitude.toStringAsFixed(5)}',
                  style: const TextStyle(
                    fontSize: 12.5,
                    color: AppColors.slate500,
                  ),
                ),
                const Spacer(),
                if (_pinOnCampus)
                  const Row(
                    children: [
                      Icon(Icons.check_circle,
                          size: 14, color: AppColors.green600),
                      SizedBox(width: 4),
                      Text(
                        'On campus',
                        style: TextStyle(
                          fontSize: 12.5,
                          fontWeight: FontWeight.w600,
                          color: AppColors.green600,
                        ),
                      ),
                    ],
                  ),
              ],
            ),
            const SizedBox(height: 14),

            AppTextField(
              controller: _landmark,
              label: 'Landmark or building name',
              hint: 'e.g. Annapurna Bhavan, near Gate 2',
              errorText: _landmarkError,
              onChanged: (_) {
                if (_landmarkError != null) {
                  setState(() => _landmarkError = null);
                }
              },
            ),
            const SizedBox(height: 12),

            Row(
              children: [
                Expanded(
                  child: AppTextField(
                    controller: _building,
                    label: 'Block (optional)',
                    hint: 'e.g. Block A',
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: AppTextField(
                    controller: _room,
                    label: 'Room (optional)',
                    hint: 'e.g. 204',
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            FilledButton.icon(
              onPressed: _confirmSelection,
              icon: const Icon(Icons.check_rounded),
              label: const Text('Confirm this location'),
            ),
          ],
        ),
      ),
    );
  }
}
