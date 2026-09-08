import 'package:flutter/material.dart';

import '../../core/config/constants.dart';
import '../../core/network/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../models/stats.dart';
import '../../services/admin_service.dart';
import '../../widgets/common.dart';
import '../../widgets/state_views.dart';

/// Officer directory with live workload, plus creation and activation.
class AdminOfficersScreen extends StatefulWidget {
  const AdminOfficersScreen({super.key});

  @override
  State<AdminOfficersScreen> createState() => _AdminOfficersScreenState();
}

class _AdminOfficersScreenState extends State<AdminOfficersScreen> {
  final _search = TextEditingController();

  List<Officer> _officers = [];
  String? _department;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final officers = await AdminService.instance.officers(
        department: _department ?? '',
        search: _search.text.trim(),
      );
      if (mounted) setState(() => _officers = officers);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Could not load officers.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _toggleActive(Officer officer) async {
    final ok = await confirm(
      context,
      title: officer.isActive ? 'Deactivate officer?' : 'Activate officer?',
      message: officer.isActive
          ? '${officer.name} will stop receiving new complaint assignments. Their existing work stays with them.'
          : '${officer.name} will start receiving new complaint assignments again.',
      confirmLabel: officer.isActive ? 'Deactivate' : 'Activate',
      destructive: officer.isActive,
    );
    if (!ok) return;

    try {
      await AdminService.instance.toggleOfficerActive(officer.id);
      if (!mounted) return;
      showSnack(context,
          officer.isActive ? 'Officer deactivated.' : 'Officer activated.');
      _load();
    } on ApiException catch (e) {
      if (mounted) showSnack(context, e.message, isError: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Officers')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showCreateSheet,
        icon: const Icon(Icons.add_rounded),
        label: const Text('Add officer'),
      ),
      body: Column(
        children: [
          Container(
            color: Colors.white,
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
            child: Column(
              children: [
                TextField(
                  controller: _search,
                  textInputAction: TextInputAction.search,
                  onSubmitted: (_) => _load(),
                  decoration: InputDecoration(
                    hintText: 'Search officers',
                    prefixIcon: const Icon(Icons.search_rounded,
                        size: 20, color: AppColors.slate400),
                    contentPadding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 12),
                    suffixIcon: _search.text.isEmpty
                        ? null
                        : IconButton(
                            icon: const Icon(Icons.close_rounded, size: 18),
                            onPressed: () {
                              _search.clear();
                              _load();
                            },
                          ),
                  ),
                ),
                const SizedBox(height: 10),
                SizedBox(
                  height: 36,
                  child: ListView(
                    scrollDirection: Axis.horizontal,
                    children: [
                      _filterChip('All', null),
                      ...Domain.departmentNames
                          .map((name) => _filterChip(name, name)),
                    ],
                  ),
                ),
              ],
            ),
          ),
          Expanded(child: _body()),
        ],
      ),
    );
  }

  Widget _filterChip(String label, String? value) {
    final selected = _department == value;
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: FilterChip(
        label: Text(label),
        selected: selected,
        showCheckmark: false,
        onSelected: (_) {
          setState(() => _department = value);
          _load();
        },
        selectedColor: AppColors.brand50,
        labelStyle: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: selected ? AppColors.brand700 : AppColors.slate600,
        ),
      ),
    );
  }

  Widget _body() {
    if (_loading) return const LoadingView(message: 'Loading officers...');

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
        title: 'No officers found',
        message: 'Add an officer, or clear the filters to see everyone.',
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 90),
        itemCount: _officers.length,
        separatorBuilder: (_, __) => const SizedBox(height: 12),
        itemBuilder: (context, index) => _officerCard(_officers[index]),
      ),
    );
  }

  Widget _officerCard(Officer officer) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 22,
                  backgroundColor: officer.isActive
                      ? AppColors.brand50
                      : AppColors.slate100,
                  child: Text(
                    officer.initials,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: officer.isActive
                          ? AppColors.brand700
                          : AppColors.slate400,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              officer.name,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                fontSize: 15.5,
                                fontWeight: FontWeight.w600,
                                color: AppColors.slate900,
                              ),
                            ),
                          ),
                          if (!officer.isActive) ...[
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: AppColors.slate100,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: const Text(
                                'Inactive',
                                style: TextStyle(
                                  fontSize: 10.5,
                                  fontWeight: FontWeight.w600,
                                  color: AppColors.slate500,
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                      const SizedBox(height: 2),
                      Text(
                        officer.department,
                        style: const TextStyle(
                          fontSize: 13,
                          color: AppColors.slate500,
                        ),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  icon: Icon(
                    officer.isActive
                        ? Icons.toggle_on_rounded
                        : Icons.toggle_off_rounded,
                    size: 32,
                    color: officer.isActive
                        ? AppColors.green600
                        : AppColors.slate400,
                  ),
                  onPressed: () => _toggleActive(officer),
                  tooltip: officer.isActive ? 'Deactivate' : 'Activate',
                ),
              ],
            ),
            const SizedBox(height: 12),
            const Divider(height: 1),
            const SizedBox(height: 12),
            Row(
              children: [
                _workload('Active', officer.activeCount, AppColors.amber500),
                _workload('Resolved', officer.resolvedCount, AppColors.green600),
                _workload('Total', officer.totalCount, AppColors.slate500),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _workload(String label, int value, Color color) {
    return Expanded(
      child: Column(
        children: [
          Text(
            '$value',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: color,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: const TextStyle(fontSize: 12, color: AppColors.slate500),
          ),
        ],
      ),
    );
  }

  /// Create an officer. The backend assigns the officer role itself, so the
  /// form only collects identity, department and the starting password.
  void _showCreateSheet() {
    final name = TextEditingController();
    final email = TextEditingController();
    final userId = TextEditingController();
    final phone = TextEditingController();
    final designation = TextEditingController();
    final password = TextEditingController();
    String? department;
    var saving = false;
    Map<String, String> errors = {};

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
                  'Add an officer',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 16),
                AppTextField(
                  controller: name,
                  label: 'Full name',
                  errorText: errors['name'] ?? errors['fullName'],
                  enabled: !saving,
                ),
                const SizedBox(height: 14),
                AppTextField(
                  controller: email,
                  label: 'Email address',
                  keyboardType: TextInputType.emailAddress,
                  errorText: errors['email'],
                  enabled: !saving,
                ),
                const SizedBox(height: 14),
                AppTextField(
                  controller: userId,
                  label: 'Employee ID',
                  errorText: errors['userId'],
                  enabled: !saving,
                ),
                const SizedBox(height: 14),
                AppDropdown<String>(
                  label: 'Department',
                  value: department,
                  hint: 'Select a department',
                  items: Domain.departmentNames,
                  errorText: errors['department'],
                  onChanged: saving
                      ? (_) {}
                      : (value) => setSheetState(() => department = value),
                ),
                const SizedBox(height: 14),
                AppTextField(
                  controller: designation,
                  label: 'Designation (optional)',
                  hint: 'e.g. Junior Engineer',
                  enabled: !saving,
                ),
                const SizedBox(height: 14),
                AppTextField(
                  controller: phone,
                  label: 'Mobile (optional)',
                  keyboardType: TextInputType.phone,
                  maxLength: 10,
                  errorText: errors['mobile'] ?? errors['phone'],
                  enabled: !saving,
                ),
                const SizedBox(height: 14),
                AppTextField(
                  controller: password,
                  label: 'Temporary password',
                  hint: 'At least 8 characters',
                  obscureText: true,
                  errorText: errors['password'],
                  enabled: !saving,
                  helperText: 'Share it with the officer so they can sign in.',
                ),
                const SizedBox(height: 20),
                FilledButton(
                  onPressed: saving
                      ? null
                      : () async {
                          setSheetState(() {
                            saving = true;
                            errors = {};
                          });
                          try {
                            await AdminService.instance.createOfficer({
                              'name': name.text.trim(),
                              'fullName': name.text.trim(),
                              'email': email.text.trim(),
                              'userId': userId.text.trim(),
                              'department': department,
                              'password': password.text,
                              if (designation.text.trim().isNotEmpty)
                                'designation': designation.text.trim(),
                              if (phone.text.trim().isNotEmpty)
                                'mobile': phone.text.trim(),
                            });
                            if (!sheetContext.mounted) return;
                            Navigator.of(sheetContext).pop();
                            showSnack(context, 'Officer added.');
                            _load();
                          } on ApiException catch (e) {
                            setSheetState(() {
                              saving = false;
                              errors = e.fieldErrors;
                            });
                            if (e.fieldErrors.isEmpty && context.mounted) {
                              showSnack(context, e.message, isError: true);
                            }
                          }
                        },
                  child: Text(saving ? 'Adding...' : 'Add officer'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
