import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';

import '../../core/config/constants.dart';
import '../../core/network/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../models/complaint.dart';
import '../../services/complaint_service.dart';
import '../../widgets/badges.dart';
import '../../widgets/common.dart';
import '../../widgets/state_views.dart';
import '../../widgets/image_picker_field.dart';
import '../shared/map_picker_screen.dart';

/// File a complaint.
///
/// One scrolling form rather than a wizard: the fields fit on a phone, and a
/// multi-step flow would hide from the user how much is left. The server does
/// the classification and the routing, so the form asks only for what a person
/// actually knows - what is wrong, what kind of thing it is, and where.
class NewComplaintScreen extends StatefulWidget {
  const NewComplaintScreen({super.key});

  @override
  State<NewComplaintScreen> createState() => _NewComplaintScreenState();
}

class _NewComplaintScreenState extends State<NewComplaintScreen> {
  final _title = TextEditingController();
  final _description = TextEditingController();
  final _scroll = ScrollController();

  String? _category;
  ComplaintLocation? _location;
  List<File> _files = [];

  AiAnalysis? _analysis;
  bool _analysing = false;
  Timer? _debounce;

  bool _submitting = false;
  Map<String, String> _fieldErrors = {};
  String? _formError;

  @override
  void dispose() {
    _debounce?.cancel();
    _title.dispose();
    _description.dispose();
    _scroll.dispose();
    super.dispose();
  }

  /// Ask the server to classify while the user types.
  ///
  /// Advisory only: the server re-runs the analysis on submit and its result
  /// is what gets stored, so a failure here is swallowed silently.
  void _scheduleAnalysis() {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 900), () async {
      final title = _title.text.trim();
      final description = _description.text.trim();

      // The backend refuses to analyse text this short, so do not ask.
      if (title.length < 8 || description.length < 25 || _category == null) {
        if (mounted && _analysis != null) setState(() => _analysis = null);
        return;
      }

      setState(() => _analysing = true);
      try {
        final result = await ComplaintService.instance.classify(
          title: title,
          description: description,
          category: _category!,
        );
        if (mounted) setState(() => _analysis = result);
      } catch (_) {
        // Classification is a convenience; its absence changes nothing.
      } finally {
        if (mounted) setState(() => _analysing = false);
      }
    });
  }

  /// The same rules `validate_complaint` applies, so problems surface here.
  Map<String, String> _validate() {
    final errors = <String, String>{};

    final title = _title.text.trim();
    if (title.isEmpty) {
      errors['title'] = 'Complaint title is required';
    } else if (title.length < 8) {
      errors['title'] = 'Title should be at least 8 characters';
    } else if (title.length > 200) {
      errors['title'] = 'Title must be 200 characters or fewer';
    }

    final description = _description.text.trim();
    if (description.isEmpty) {
      errors['description'] = 'Please describe the problem';
    } else if (description.length < 25) {
      errors['description'] =
          'Please add a little more detail (at least 25 characters)';
    } else if (description.length > 5000) {
      errors['description'] = 'Description must be 5000 characters or fewer';
    }

    if (_category == null || _category!.isEmpty) {
      errors['category'] = 'Select a category';
    }

    if (_location == null || !_location!.hasCoordinates) {
      errors['location'] = 'Choose the complaint location on the map';
    } else if (_location!.address.trim().isEmpty) {
      errors['address'] = 'Enter a landmark or building name';
    }

    return errors;
  }

  Future<void> _pickLocation() async {
    final result = await Navigator.of(context).push<ComplaintLocation>(
      MaterialPageRoute(
        builder: (_) => MapPickerScreen(initial: _location),
      ),
    );
    if (result != null) {
      setState(() {
        _location = result;
        _fieldErrors.remove('location');
        _fieldErrors.remove('address');
      });
    }
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();

    final errors = _validate();
    if (errors.isNotEmpty) {
      setState(() {
        _fieldErrors = errors;
        _formError = null;
      });
      _scroll.animateTo(
        0,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
      return;
    }

    setState(() {
      _submitting = true;
      _formError = null;
      _fieldErrors = {};
    });

    try {
      final complaint = await ComplaintService.instance.create(
        title: _title.text,
        description: _description.text,
        category: _category!,
        location: _location!,
        files: _files,
      );

      if (!mounted) return;
      await _showSuccess(complaint);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _formError = e.message;
        _fieldErrors = e.fieldErrors;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() =>
          _formError = 'Could not submit your complaint. Please try again.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  /// Confirm with the reference id, which is what the user needs to quote later.
  Future<void> _showSuccess(Complaint complaint) async {
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        icon: Container(
          width: 56,
          height: 56,
          decoration: const BoxDecoration(
            color: AppColors.green50,
            shape: BoxShape.circle,
          ),
          child: const Icon(Icons.check_rounded,
              size: 30, color: AppColors.green600),
        ),
        title: const Text(
          'Complaint registered',
          style: TextStyle(fontSize: 19, fontWeight: FontWeight.w700),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Your complaint has been sent to the right department. Keep this reference number:',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 15, height: 1.5),
            ),
            const SizedBox(height: 14),
            Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: BoxDecoration(
                color: AppColors.slate100,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                complaint.id,
                style: const TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w700,
                  color: AppColors.slate900,
                  letterSpacing: 0.5,
                ),
              ),
            ),
            const SizedBox(height: 14),
            Wrap(
              spacing: 8,
              alignment: WrapAlignment.center,
              children: [
                StatusBadge(complaint.status),
                PriorityBadge(complaint.priority),
              ],
            ),
          ],
        ),
        actions: [
          FilledButton(
            onPressed: () {
              Navigator.of(dialogContext).pop();
              // true tells the list to refresh itself.
              Navigator.of(context).pop(true);
            },
            child: const Text('Done'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('New complaint')),
      body: BusyOverlay(
        busy: _submitting,
        message: _files.isEmpty
            ? 'Submitting your complaint...'
            : 'Uploading photos and submitting...',
        child: SingleChildScrollView(
          controller: _scroll,
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (_formError != null) ...[
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: AppColors.red50,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                        color: AppColors.red500.withValues(alpha: 0.3)),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.error_outline_rounded,
                          size: 20, color: AppColors.red600),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          _formError!,
                          style: const TextStyle(
                            fontSize: 14,
                            color: AppColors.red600,
                            height: 1.4,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
              ],

              AppTextField(
                controller: _title,
                label: 'What is the problem?',
                hint: 'e.g. Water leaking in hostel bathroom',
                maxLength: 200,
                textInputAction: TextInputAction.next,
                errorText: _fieldErrors['title'],
                enabled: !_submitting,
                onChanged: (_) {
                  if (_fieldErrors.containsKey('title')) {
                    setState(() => _fieldErrors.remove('title'));
                  }
                  _scheduleAnalysis();
                },
              ),
              const SizedBox(height: 20),

              AppTextField(
                controller: _description,
                label: 'Describe it in detail',
                hint:
                    'Tell us what is wrong, since when, and anything that helps the team find it.',
                maxLines: 5,
                maxLength: 5000,
                errorText: _fieldErrors['description'],
                enabled: !_submitting,
                helperText: 'At least 25 characters.',
                onChanged: (_) {
                  if (_fieldErrors.containsKey('description')) {
                    setState(() => _fieldErrors.remove('description'));
                  }
                  _scheduleAnalysis();
                },
              ),
              const SizedBox(height: 20),

              AppDropdown<String>(
                label: 'Category',
                value: _category,
                hint: 'What kind of problem is it?',
                items: Domain.categories,
                errorText: _fieldErrors['category'],
                onChanged: _submitting
                    ? (_) {}
                    : (value) {
                        setState(() {
                          _category = value;
                          _fieldErrors.remove('category');
                        });
                        _scheduleAnalysis();
                      },
              ),

              if (_analysing || _analysis != null) ...[
                const SizedBox(height: 16),
                _analysisCard(),
              ],

              const SizedBox(height: 24),
              _locationField(),

              const SizedBox(height: 24),
              ImagePickerField(
                files: _files,
                onChanged: (files) => setState(() => _files = files),
                helper:
                    'A photo helps the team understand the problem quickly.',
              ),

              const SizedBox(height: 32),
              FilledButton(
                onPressed: _submitting ? null : _submit,
                child: const Text('Submit complaint'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// What the server thinks this complaint is, shown as information rather
  /// than as an editable field - the user cannot pick their own priority.
  Widget _analysisCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: AppColors.violet50,
                borderRadius: BorderRadius.circular(9),
              ),
              child: const Icon(Icons.auto_awesome_outlined,
                  size: 18, color: AppColors.violet600),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _analysing
                  ? const Padding(
                      padding: EdgeInsets.symmetric(vertical: 6),
                      child: Text(
                        'Checking which department should handle this...',
                        style: TextStyle(
                            fontSize: 14, color: AppColors.slate500),
                      ),
                    )
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Suggested routing',
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: AppColors.slate700,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            if (_analysis!.department.isNotEmpty)
                              DepartmentBadge(_analysis!.department),
                            if (_analysis!.priority.isNotEmpty)
                              PriorityBadge(_analysis!.priority, compact: true),
                          ],
                        ),
                        if (_analysis!.reason.isNotEmpty) ...[
                          const SizedBox(height: 8),
                          Text(
                            _analysis!.reason,
                            style: const TextStyle(
                              fontSize: 12.5,
                              color: AppColors.slate500,
                              height: 1.4,
                            ),
                          ),
                        ],
                        const SizedBox(height: 6),
                        const Text(
                          'The department confirms this after you submit.',
                          style: TextStyle(
                            fontSize: 12,
                            color: AppColors.slate400,
                          ),
                        ),
                      ],
                    ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _locationField() {
    final location = _location;
    final error = _fieldErrors['location'] ?? _fieldErrors['address'];
    final hasLocation = location != null && location.hasCoordinates;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Where is it?',
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            color: AppColors.slate700,
          ),
        ),
        const SizedBox(height: 6),
        const Text(
          'Pick the spot on the campus map so the team can find it.',
          style: TextStyle(fontSize: 13, color: AppColors.slate500),
        ),
        const SizedBox(height: 10),

        InkWell(
          onTap: _submitting ? null : _pickLocation,
          borderRadius: BorderRadius.circular(AppTheme.fieldRadius),
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(AppTheme.fieldRadius),
              border: Border.all(
                color: error != null ? AppColors.red600 : AppColors.slate200,
                width: error != null ? 2 : 1,
              ),
            ),
            child: Row(
              children: [
                Icon(
                  hasLocation
                      ? Icons.place_rounded
                      : Icons.add_location_alt_outlined,
                  size: 22,
                  color: hasLocation ? AppColors.brand600 : AppColors.slate400,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: hasLocation
                      ? Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              location.summary,
                              style: const TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w500,
                                color: AppColors.slate900,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              '${location.latitude!.toStringAsFixed(5)}, ${location.longitude!.toStringAsFixed(5)}',
                              style: const TextStyle(
                                fontSize: 12,
                                color: AppColors.slate400,
                              ),
                            ),
                          ],
                        )
                      : const Text(
                          'Choose location on map',
                          style: TextStyle(
                            fontSize: 15,
                            color: AppColors.slate400,
                          ),
                        ),
                ),
                const Icon(Icons.chevron_right_rounded,
                    color: AppColors.slate400),
              ],
            ),
          ),
        ),

        if (error != null) ...[
          const SizedBox(height: 6),
          Text(
            error,
            style: const TextStyle(fontSize: 12.5, color: AppColors.red600),
          ),
        ],
      ],
    );
  }
}
