import 'dart:io';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:provider/provider.dart';

import '../../core/config/app_config.dart';
import '../../core/config/campus.dart';
import '../../core/config/constants.dart';
import '../../core/network/api_exception.dart';
import '../../core/storage/secure_store.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/formatters.dart';
import '../../models/complaint.dart';
import '../../models/stats.dart';
import '../../providers/auth_provider.dart';
import '../../services/admin_service.dart';
import '../../services/complaint_service.dart';
import '../../widgets/badges.dart';
import '../../widgets/common.dart';
import '../../widgets/image_picker_field.dart';
import '../../widgets/state_views.dart';

/// One complaint in full, with the actions the signed-in role may take.
///
/// The action set is derived from the role and the current status, and mirrors
/// what the backend permits - an officer only ever sees the statuses in
/// `OFFICER_STATUS_OPTIONS`, so the UI cannot offer a move the API refuses.
class ComplaintDetailsScreen extends StatefulWidget {
  const ComplaintDetailsScreen({super.key, required this.complaintId});

  final String complaintId;

  @override
  State<ComplaintDetailsScreen> createState() => _ComplaintDetailsScreenState();
}

class _ComplaintDetailsScreenState extends State<ComplaintDetailsScreen> {
  final ComplaintService _service = ComplaintService.instance;

  Complaint? _complaint;
  bool _loading = true;
  bool _busy = false;
  String? _error;

  /// Set when anything is changed, so the list behind can refresh on pop.
  bool _changed = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final complaint = await _service.byId(widget.complaintId);
      if (mounted) setState(() => _complaint = complaint);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Could not load this complaint.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  /// Run an action, showing progress and reporting the outcome consistently.
  Future<void> _run(
    Future<Complaint> Function() action, {
    required String successMessage,
  }) async {
    setState(() => _busy = true);
    try {
      final updated = await action();
      if (!mounted) return;
      setState(() {
        _complaint = updated;
        _changed = true;
      });
      showSnack(context, successMessage);
    } on ApiException catch (e) {
      if (mounted) showSnack(context, e.message, isError: true);
    } catch (_) {
      if (mounted) {
        showSnack(context, 'That did not work. Please try again.',
            isError: true);
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    // The Android back gesture must carry the "something changed" result back,
    // not just dismiss the screen.
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) Navigator.of(context).pop(_changed);
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(_complaint?.id ?? 'Complaint'),
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_rounded),
            onPressed: () => Navigator.of(context).pop(_changed),
          ),
        ),
        body: _body(),
        bottomNavigationBar: _complaint == null ? null : _actionBar(),
      ),
    );
  }

  Widget _body() {
    if (_loading) return const LoadingView(message: 'Loading complaint...');

    if (_error != null) {
      return ErrorView(
        message: _error!,
        isNetwork: _error!.toLowerCase().contains('connection'),
        onRetry: _load,
      );
    }

    final complaint = _complaint;
    if (complaint == null) {
      return const EmptyView(
        title: 'Complaint not found',
        message: 'It may have been removed.',
      );
    }

    return BusyOverlay(
      busy: _busy,
      message: 'Saving...',
      child: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
          children: [
            _headerCard(complaint),
            const SizedBox(height: 16),
            _detailsCard(complaint),
            if (complaint.location.hasCoordinates) ...[
              const SizedBox(height: 16),
              _locationCard(complaint),
            ],
            if (complaint.evidence.isNotEmpty) ...[
              const SizedBox(height: 16),
              _evidenceCard('Photos and attachments', complaint.evidence),
            ],
            if (complaint.resolutionNotes.isNotEmpty) ...[
              const SizedBox(height: 16),
              _resolutionCard(complaint),
            ],
            if (complaint.hasFeedback) ...[
              const SizedBox(height: 16),
              _feedbackCard(complaint),
            ],
            if (complaint.remarks.isNotEmpty) ...[
              const SizedBox(height: 16),
              _remarksCard(complaint),
            ],
            if (complaint.timeline.isNotEmpty) ...[
              const SizedBox(height: 16),
              _timelineCard(complaint),
            ],
          ],
        ),
      ),
    );
  }

  // ----------------------------------------------------------------- cards

  Widget _headerCard(Complaint complaint) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              complaint.title,
              style: const TextStyle(
                fontSize: 19,
                fontWeight: FontWeight.w700,
                color: AppColors.slate900,
                height: 1.35,
              ),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                StatusBadge(complaint.status),
                PriorityBadge(complaint.priority),
                if (complaint.isOverdue)
                  OverdueBadge(daysOverdue: complaint.daysOverdue),
                if (complaint.escalationLevel > 0)
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppColors.red50,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      'Escalated - level ${complaint.escalationLevel}',
                      style: const TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: AppColors.red600,
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 14),
            Text(
              complaint.description,
              style: const TextStyle(
                fontSize: 15,
                color: AppColors.slate700,
                height: 1.6,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _detailsCard(Complaint complaint) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Details',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: AppColors.slate900,
              ),
            ),
            const SizedBox(height: 14),
            _row('Reference', complaint.id),
            _row('Category', complaint.category),
            _row('Department', complaint.department),
            _row(
              'Submitted by',
              complaint.submittedByName.isEmpty
                  ? 'Not available'
                  : complaint.submittedByName,
            ),
            _row(
              'Assigned to',
              complaint.assignedOfficerName.isEmpty
                  ? 'Not assigned yet'
                  : complaint.assignedOfficerName,
            ),
            _row('Submitted', Format.dateTime(complaint.submittedAt)),
            _row('Target date', Format.deadline(complaint.deadline)),
            if (complaint.resolvedAt != null)
              _row('Resolved', Format.dateTime(complaint.resolvedAt)),
          ],
        ),
      ),
    );
  }

  Widget _row(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 116,
            child: Text(
              label,
              style: const TextStyle(fontSize: 13.5, color: AppColors.slate500),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(
                fontSize: 14.5,
                fontWeight: FontWeight.w500,
                color: AppColors.slate900,
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// A small non-interactive map, so the handler can see where to go.
  Widget _locationCard(Complaint complaint) {
    final point = LatLng(
      complaint.location.latitude!,
      complaint.location.longitude!,
    );

    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            height: 170,
            child: FlutterMap(
              options: MapOptions(
                initialCenter: point,
                initialZoom: 17,
                interactionOptions: const InteractionOptions(
                  flags: InteractiveFlag.none,
                ),
              ),
              children: [
                TileLayer(
                  urlTemplate: Campus.tileUrl,
                  userAgentPackageName: 'in.ac.dsvv.grievance',
                ),
                MarkerLayer(
                  markers: [
                    Marker(
                      point: point,
                      width: 40,
                      height: 40,
                      alignment: Alignment.topCenter,
                      child: const Icon(Icons.location_on,
                          size: 40, color: AppColors.brand600),
                    ),
                  ],
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              children: [
                const Icon(Icons.place_outlined,
                    size: 18, color: AppColors.slate400),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    complaint.location.summary,
                    style: const TextStyle(
                      fontSize: 14.5,
                      color: AppColors.slate700,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _evidenceCard(String title, List<Evidence> files) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: AppColors.slate900,
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              height: 100,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: files.length,
                separatorBuilder: (_, __) => const SizedBox(width: 10),
                itemBuilder: (context, index) => _evidenceThumb(files[index]),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Files are behind `@jwt_required`, so the thumbnail has to carry the
  /// bearer token; a plain Image.network would get a 401.
  Widget _evidenceThumb(Evidence file) {
    if (!file.isImage) {
      return Container(
        width: 100,
        height: 100,
        decoration: BoxDecoration(
          color: AppColors.slate100,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              file.kind == 'pdf'
                  ? Icons.picture_as_pdf_outlined
                  : Icons.description_outlined,
              size: 28,
              color: AppColors.slate500,
            ),
            const SizedBox(height: 6),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 6),
              child: Text(
                file.name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 11, color: AppColors.slate500),
              ),
            ),
          ],
        ),
      );
    }

    return FutureBuilder<String?>(
      future: SecureStore.instance.readAccessToken(),
      builder: (context, snapshot) {
        final token = snapshot.data;
        if (token == null) {
          return _thumbPlaceholder();
        }
        return GestureDetector(
          onTap: () => _openFullImage(file, token),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: CachedNetworkImage(
              imageUrl: '${AppConfig.apiBaseUrl}${file.url}',
              httpHeaders: {'Authorization': 'Bearer $token'},
              width: 100,
              height: 100,
              fit: BoxFit.cover,
              placeholder: (_, __) => _thumbPlaceholder(),
              errorWidget: (_, __, ___) => Container(
                width: 100,
                height: 100,
                color: AppColors.slate100,
                child: const Icon(Icons.broken_image_outlined,
                    color: AppColors.slate400),
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _thumbPlaceholder() => Container(
        width: 100,
        height: 100,
        decoration: BoxDecoration(
          color: AppColors.slate100,
          borderRadius: BorderRadius.circular(10),
        ),
        child: const Center(
          child: SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
        ),
      );

  void _openFullImage(Evidence file, String token) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => Scaffold(
          backgroundColor: Colors.black,
          appBar: AppBar(
            backgroundColor: Colors.black,
            foregroundColor: Colors.white,
            title: Text(file.name, style: const TextStyle(fontSize: 15)),
          ),
          body: Center(
            child: InteractiveViewer(
              maxScale: 4,
              child: CachedNetworkImage(
                imageUrl: '${AppConfig.apiBaseUrl}${file.url}',
                httpHeaders: {'Authorization': 'Bearer $token'},
                fit: BoxFit.contain,
                placeholder: (_, __) => const CircularProgressIndicator(),
                errorWidget: (_, __, ___) => const Icon(
                  Icons.broken_image_outlined,
                  color: Colors.white54,
                  size: 48,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _resolutionCard(Complaint complaint) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.check_circle_outline,
                    size: 18, color: AppColors.green600),
                SizedBox(width: 8),
                Text(
                  'Resolution',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: AppColors.slate900,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              complaint.resolutionNotes,
              style: const TextStyle(
                fontSize: 14.5,
                color: AppColors.slate700,
                height: 1.6,
              ),
            ),
            if (complaint.resolutionProof.isNotEmpty) ...[
              const SizedBox(height: 14),
              SizedBox(
                height: 100,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: complaint.resolutionProof.length,
                  separatorBuilder: (_, __) => const SizedBox(width: 10),
                  itemBuilder: (context, index) =>
                      _evidenceThumb(complaint.resolutionProof[index]),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _feedbackCard(Complaint complaint) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Your feedback',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: AppColors.slate900,
              ),
            ),
            const SizedBox(height: 10),
            Row(
              children: List.generate(
                5,
                (index) => Icon(
                  index < (complaint.feedbackRating ?? 0)
                      ? Icons.star_rounded
                      : Icons.star_outline_rounded,
                  size: 22,
                  color: AppColors.amber500,
                ),
              ),
            ),
            if (complaint.feedbackComment.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(
                complaint.feedbackComment,
                style: const TextStyle(
                  fontSize: 14.5,
                  color: AppColors.slate700,
                  height: 1.5,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _remarksCard(Complaint complaint) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Remarks (${complaint.remarks.length})',
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: AppColors.slate900,
              ),
            ),
            const SizedBox(height: 12),
            ...complaint.remarks.map(
              (remark) => Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          remark.byName.isEmpty ? 'Staff' : remark.byName,
                          style: const TextStyle(
                            fontSize: 13.5,
                            fontWeight: FontWeight.w600,
                            color: AppColors.slate900,
                          ),
                        ),
                        const Spacer(),
                        Text(
                          Format.relative(remark.at),
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppColors.slate400,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      remark.message,
                      style: const TextStyle(
                        fontSize: 14,
                        color: AppColors.slate600,
                        height: 1.5,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _timelineCard(Complaint complaint) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Progress',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: AppColors.slate900,
              ),
            ),
            const SizedBox(height: 14),
            ...complaint.timeline.asMap().entries.map((entry) {
              final isLast = entry.key == complaint.timeline.length - 1;
              final item = entry.value;
              final color = AppColors.forStatus(item.status);

              return IntrinsicHeight(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Column(
                      children: [
                        Container(
                          width: 12,
                          height: 12,
                          margin: const EdgeInsets.only(top: 3),
                          decoration: BoxDecoration(
                            color: color,
                            shape: BoxShape.circle,
                          ),
                        ),
                        if (!isLast)
                          Expanded(
                            child: Container(
                              width: 2,
                              color: AppColors.slate200,
                              margin: const EdgeInsets.symmetric(vertical: 4),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Padding(
                        padding: EdgeInsets.only(bottom: isLast ? 0 : 18),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              item.status,
                              style: TextStyle(
                                fontSize: 14.5,
                                fontWeight: FontWeight.w600,
                                color: color,
                              ),
                            ),
                            if (item.note.isNotEmpty) ...[
                              const SizedBox(height: 3),
                              Text(
                                item.note,
                                style: const TextStyle(
                                  fontSize: 13.5,
                                  color: AppColors.slate600,
                                  height: 1.45,
                                ),
                              ),
                            ],
                            const SizedBox(height: 3),
                            Text(
                              [
                                Format.dateTime(item.at),
                                if (item.byName.isNotEmpty) item.byName,
                              ].join('  -  '),
                              style: const TextStyle(
                                fontSize: 12,
                                color: AppColors.slate400,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }

  // --------------------------------------------------------------- actions

  Widget? _actionBar() {
    final user = context.read<AuthProvider>().user;
    final complaint = _complaint;
    if (user == null || complaint == null) return null;

    final actions = <Widget>[];

    if (user.isStudent) {
      if (complaint.canGiveFeedback) {
        actions.add(_primary('Give feedback', Icons.star_outline_rounded,
            _showFeedbackSheet));
      }
      if (complaint.canReopen) {
        actions.add(_secondary('Reopen', Icons.refresh_rounded, _showReopenSheet));
      }
    }

    if (user.isOfficer) {
      if (complaint.isActive) {
        actions.add(_primary(
            'Update status', Icons.published_with_changes_rounded,
            _showStatusSheet));
        if (complaint.status != Domain.statusResolved) {
          actions.add(_secondary(
              'Resolve', Icons.check_circle_outline, _showResolveSheet));
        }
      }
      actions.add(_secondary(
          'Add remark', Icons.chat_bubble_outline_rounded, _showRemarkSheet));
    }

    if (user.isAdmin) {
      actions.add(_primary('Manage', Icons.settings_outlined, _showAdminSheet));
      actions.add(_secondary(
          'Add remark', Icons.chat_bubble_outline_rounded, _showRemarkSheet));
    }

    if (actions.isEmpty) return null;

    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(top: BorderSide(color: AppColors.slate200)),
      ),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
          child: Row(
            children: [
              for (var i = 0; i < actions.length; i++) ...[
                if (i > 0) const SizedBox(width: 12),
                Expanded(child: actions[i]),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _primary(String label, IconData icon, VoidCallback onTap) =>
      FilledButton.icon(
        onPressed: _busy ? null : onTap,
        icon: Icon(icon, size: 19),
        label: Text(label, overflow: TextOverflow.ellipsis),
      );

  Widget _secondary(String label, IconData icon, VoidCallback onTap) =>
      OutlinedButton.icon(
        onPressed: _busy ? null : onTap,
        icon: Icon(icon, size: 19),
        label: Text(label, overflow: TextOverflow.ellipsis),
      );

  // --------------------------------------------------------- action sheets

  void _showStatusSheet() {
    showModalBottomSheet<void>(
      context: context,
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 8, 16, 12),
              child: Text(
                'Update status',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
              ),
            ),
            // Exactly the statuses the backend allows an officer to set.
            ...Domain.officerStatusOptions.map(
              (status) => ListTile(
                leading: Container(
                  width: 10,
                  height: 10,
                  decoration: BoxDecoration(
                    color: AppColors.forStatus(status),
                    shape: BoxShape.circle,
                  ),
                ),
                title: Text(status, style: const TextStyle(fontSize: 16)),
                trailing: _complaint?.status == status
                    ? const Icon(Icons.check_rounded,
                        color: AppColors.brand600)
                    : null,
                onTap: () {
                  Navigator.of(sheetContext).pop();
                  if (_complaint?.status == status) return;

                  // Resolving needs notes, so it routes to the fuller flow.
                  if (status == Domain.statusResolved) {
                    _showResolveSheet();
                    return;
                  }
                  _run(
                    () => _service.updateStatus(widget.complaintId, status),
                    successMessage: 'Status updated to $status.',
                  );
                },
              ),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  void _showRemarkSheet() {
    final controller = TextEditingController();
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => Padding(
        padding: EdgeInsets.fromLTRB(
          16,
          8,
          16,
          16 + MediaQuery.of(sheetContext).viewInsets.bottom,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Add a remark',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 16),
            AppTextField(
              controller: controller,
              label: 'Remark',
              hint: 'Share an update on this complaint',
              maxLines: 4,
              autofocus: true,
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: () {
                final message = controller.text.trim();
                if (message.isEmpty) return;
                Navigator.of(sheetContext).pop();
                _run(
                  () => _service.addRemark(widget.complaintId, message),
                  successMessage: 'Remark added.',
                );
              },
              child: const Text('Add remark'),
            ),
          ],
        ),
      ),
    );
  }

  void _showResolveSheet() {
    final controller = TextEditingController();
    var files = <File>[];

    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (context, setSheetState) => Padding(
          padding: EdgeInsets.fromLTRB(
            16,
            8,
            16,
            16 + MediaQuery.of(context).viewInsets.bottom,
          ),
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'Submit resolution',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 6),
                const Text(
                  'Describe what was done. The complaint will be marked Resolved.',
                  style: TextStyle(fontSize: 14, color: AppColors.slate500),
                ),
                const SizedBox(height: 16),
                AppTextField(
                  controller: controller,
                  label: 'What did you do?',
                  hint: 'e.g. Replaced the leaking pipe and tested the flow.',
                  maxLines: 4,
                ),
                const SizedBox(height: 18),
                ImagePickerField(
                  files: files,
                  onChanged: (next) => setSheetState(() => files = next),
                  label: 'Proof photos (optional)',
                  helper: 'Photos of the completed work.',
                ),
                const SizedBox(height: 20),
                FilledButton(
                  onPressed: () {
                    final notes = controller.text.trim();
                    if (notes.isEmpty) {
                      showSnack(context, 'Please describe what was done.',
                          isError: true);
                      return;
                    }
                    Navigator.of(sheetContext).pop();
                    _run(
                      () => _service.resolve(widget.complaintId,
                          notes: notes, files: files),
                      successMessage: 'Resolution submitted.',
                    );
                  },
                  child: const Text('Submit resolution'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _showFeedbackSheet() {
    var rating = 0;
    final controller = TextEditingController();

    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (context, setSheetState) => Padding(
          padding: EdgeInsets.fromLTRB(
            16,
            8,
            16,
            16 + MediaQuery.of(context).viewInsets.bottom,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'How did we do?',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 6),
              const Text(
                'Your rating helps the departments improve.',
                style: TextStyle(fontSize: 14, color: AppColors.slate500),
              ),
              const SizedBox(height: 18),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(5, (index) {
                  final value = index + 1;
                  return IconButton(
                    iconSize: 40,
                    onPressed: () => setSheetState(() => rating = value),
                    icon: Icon(
                      value <= rating
                          ? Icons.star_rounded
                          : Icons.star_outline_rounded,
                      color: AppColors.amber500,
                    ),
                  );
                }),
              ),
              const SizedBox(height: 12),
              AppTextField(
                controller: controller,
                label: 'Comment (optional)',
                hint: 'Anything you would like to add?',
                maxLines: 3,
              ),
              const SizedBox(height: 20),
              FilledButton(
                onPressed: () {
                  if (rating == 0) {
                    showSnack(context, 'Please select a star rating.',
                        isError: true);
                    return;
                  }
                  Navigator.of(sheetContext).pop();
                  _run(
                    () => _service.submitFeedback(
                      widget.complaintId,
                      rating: rating,
                      comment: controller.text.trim(),
                    ),
                    successMessage: 'Thank you for your feedback.',
                  );
                },
                child: const Text('Submit feedback'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showReopenSheet() {
    final controller = TextEditingController();
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => Padding(
        padding: EdgeInsets.fromLTRB(
          16,
          8,
          16,
          16 + MediaQuery.of(sheetContext).viewInsets.bottom,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Reopen this complaint',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 6),
            const Text(
              'Tell us what is still wrong, so the team knows what to look at.',
              style: TextStyle(fontSize: 14, color: AppColors.slate500),
            ),
            const SizedBox(height: 16),
            AppTextField(
              controller: controller,
              label: 'Why are you reopening it?',
              hint: 'e.g. The leak has started again.',
              maxLines: 3,
              autofocus: true,
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: () {
                final reason = controller.text.trim();
                if (reason.isEmpty) {
                  showSnack(context, 'Please tell us why.', isError: true);
                  return;
                }
                Navigator.of(sheetContext).pop();
                _run(
                  () => _service.reopen(widget.complaintId, reason),
                  successMessage: 'Your complaint has been reopened.',
                );
              },
              child: const Text('Reopen complaint'),
            ),
          ],
        ),
      ),
    );
  }

  /// Admin-only controls: assignment, priority, escalation, closing.
  void _showAdminSheet() {
    final complaint = _complaint!;
    showModalBottomSheet<void>(
      context: context,
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 8, 16, 12),
              child: Text(
                'Manage complaint',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
              ),
            ),
            ListTile(
              leading: const Icon(Icons.person_add_alt_outlined),
              title: Text(
                complaint.assignedOfficerName.isEmpty
                    ? 'Assign an officer'
                    : 'Reassign officer',
                style: const TextStyle(fontSize: 16),
              ),
              onTap: () {
                Navigator.of(sheetContext).pop();
                _showAssignSheet(complaint);
              },
            ),
            ListTile(
              leading: const Icon(Icons.flag_outlined),
              title: const Text('Change priority',
                  style: TextStyle(fontSize: 16)),
              onTap: () {
                Navigator.of(sheetContext).pop();
                _showPrioritySheet();
              },
            ),
            if (complaint.isActive)
              ListTile(
                leading: const Icon(Icons.trending_up_rounded,
                    color: AppColors.red600),
                title: const Text('Escalate', style: TextStyle(fontSize: 16)),
                onTap: () async {
                  Navigator.of(sheetContext).pop();
                  final ok = await confirm(
                    context,
                    title: 'Escalate this complaint?',
                    message:
                        'It will be raised to the next authority level and everyone involved will be notified.',
                    confirmLabel: 'Escalate',
                  );
                  if (ok) {
                    _run(
                      () => _service.escalate(widget.complaintId),
                      successMessage: 'Complaint escalated.',
                    );
                  }
                },
              ),
            if (!complaint.isClosed)
              ListTile(
                leading: const Icon(Icons.lock_outline_rounded),
                title: const Text('Close complaint',
                    style: TextStyle(fontSize: 16)),
                onTap: () async {
                  Navigator.of(sheetContext).pop();
                  final ok = await confirm(
                    context,
                    title: 'Close this complaint?',
                    message:
                        'Closing marks it finished. The student can still reopen it if the problem returns.',
                    confirmLabel: 'Close',
                    destructive: true,
                  );
                  if (ok) {
                    _run(
                      () => _service.close(widget.complaintId),
                      successMessage: 'Complaint closed.',
                    );
                  }
                },
              ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  void _showPrioritySheet() {
    showModalBottomSheet<void>(
      context: context,
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 8, 16, 12),
              child: Text(
                'Change priority',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
              ),
            ),
            ...Domain.priorityList.map(
              (priority) => ListTile(
                leading: Icon(Icons.flag_rounded,
                    color: AppColors.forPriority(priority)),
                title: Text(priority, style: const TextStyle(fontSize: 16)),
                trailing: _complaint?.priority == priority
                    ? const Icon(Icons.check_rounded, color: AppColors.brand600)
                    : null,
                onTap: () {
                  Navigator.of(sheetContext).pop();
                  if (_complaint?.priority == priority) return;
                  _run(
                    () => _service.changePriority(widget.complaintId, priority),
                    successMessage: 'Priority changed to $priority.',
                  );
                },
              ),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  /// Officers are fetched for the complaint's own department, which is where
  /// an assignment realistically goes.
  void _showAssignSheet(Complaint complaint) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => _OfficerPicker(
        department: complaint.department,
        currentOfficerId: complaint.assignedOfficerId,
        onPicked: (officer) {
          Navigator.of(sheetContext).pop();
          _run(
            () => complaint.assignedOfficerId.isEmpty
                ? _service.assign(widget.complaintId, officer.id)
                : _service.reassign(widget.complaintId, officer.id),
            successMessage: 'Assigned to ${officer.name}.',
          );
        },
      ),
    );
  }
}

/// The officer list inside the assign sheet.
///
/// A StatefulWidget rather than a bare FutureBuilder: the future is created
/// once in initState, so a rebuild (a keyboard opening, the sheet being
/// dragged) does not refire the request, and Retry re-runs the fetch against
/// this widget's own state instead of the screen behind it.
class _OfficerPicker extends StatefulWidget {
  const _OfficerPicker({
    required this.department,
    required this.currentOfficerId,
    required this.onPicked,
  });

  final String department;
  final String currentOfficerId;
  final void Function(Officer officer) onPicked;

  @override
  State<_OfficerPicker> createState() => _OfficerPickerState();
}

class _OfficerPickerState extends State<_OfficerPicker> {
  List<Officer> _officers = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final officers =
          await AdminService.instance.officers(department: widget.department);
      if (mounted) setState(() => _officers = officers);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Could not load officers.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.6,
      maxChildSize: 0.9,
      builder: (context, scrollController) => Column(
        children: [
          const Padding(
            padding: EdgeInsets.fromLTRB(16, 8, 16, 12),
            child: Text(
              'Choose an officer',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
            ),
          ),
          Expanded(child: _body(scrollController)),
        ],
      ),
    );
  }

  Widget _body(ScrollController scrollController) {
    if (_loading) return const LoadingView();

    if (_error != null) {
      return ErrorView(
        message: _error!,
        isNetwork: _error!.toLowerCase().contains('connection'),
        onRetry: _load,
      );
    }

    if (_officers.isEmpty) {
      return const EmptyView(
        icon: Icons.engineering_outlined,
        title: 'No officers available',
        message: 'There are no active officers in this department yet.',
      );
    }

    return ListView.builder(
      controller: scrollController,
      itemCount: _officers.length,
      itemBuilder: (context, index) {
        final officer = _officers[index];
        final isCurrent = officer.id == widget.currentOfficerId;

        return ListTile(
          leading: CircleAvatar(
            backgroundColor: AppColors.brand50,
            child: Text(
              officer.initials,
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppColors.brand700,
              ),
            ),
          ),
          title: Text(officer.name, style: const TextStyle(fontSize: 15.5)),
          subtitle: Text(
            '${officer.activeCount} active - ${officer.resolvedCount} resolved',
            style: const TextStyle(fontSize: 13),
          ),
          trailing: isCurrent
              ? const Icon(Icons.check_rounded, color: AppColors.brand600)
              : null,
          // Re-picking the current officer would be a no-op round trip.
          onTap: isCurrent ? null : () => widget.onPicked(officer),
        );
      },
    );
  }
}
