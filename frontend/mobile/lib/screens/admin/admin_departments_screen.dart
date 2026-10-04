import 'package:flutter/material.dart';

import '../../core/network/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../models/stats.dart';
import '../../services/admin_service.dart';
import '../../widgets/common.dart';
import '../../widgets/state_views.dart';

/// The four campus departments, their heads, and their complaint load.
class AdminDepartmentsScreen extends StatefulWidget {
  const AdminDepartmentsScreen({super.key});

  @override
  State<AdminDepartmentsScreen> createState() => _AdminDepartmentsScreenState();
}

class _AdminDepartmentsScreenState extends State<AdminDepartmentsScreen> {
  List<Department> _departments = [];
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
      final departments = await AdminService.instance.departments();
      if (mounted) setState(() => _departments = departments);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Could not load departments.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _toggleActive(Department department) async {
    final ok = await confirm(
      context,
      title: department.isActive
          ? 'Deactivate ${department.name}?'
          : 'Activate ${department.name}?',
      message: department.isActive
          ? 'New complaints will no longer be routed to this department.'
          : 'This department will start receiving complaints again.',
      confirmLabel: department.isActive ? 'Deactivate' : 'Activate',
      destructive: department.isActive,
    );
    if (!ok) return;

    try {
      await AdminService.instance.toggleDepartmentActive(department.code);
      if (!mounted) return;
      showSnack(context, 'Department updated.');
      _load();
    } on ApiException catch (e) {
      if (mounted) showSnack(context, e.message, isError: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Departments')),
      body: _body(),
    );
  }

  Widget _body() {
    if (_loading) return const LoadingView(message: 'Loading departments...');

    if (_error != null) {
      return ErrorView(
        message: _error!,
        isNetwork: _error!.toLowerCase().contains('connection'),
        onRetry: _load,
      );
    }

    if (_departments.isEmpty) {
      return const EmptyView(
        icon: Icons.apartment_outlined,
        title: 'No departments',
        message: 'No departments are configured on the server.',
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
        itemCount: _departments.length,
        separatorBuilder: (_, __) => const SizedBox(height: 12),
        itemBuilder: (context, index) => _card(_departments[index]),
      ),
    );
  }

  Widget _card(Department department) {
    final color = AppColors.forDepartment(department.name);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(11),
                  ),
                  child: Icon(Icons.apartment_rounded, size: 21, color: color),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        department.name,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          color: AppColors.slate900,
                        ),
                      ),
                      if (department.english.isNotEmpty) ...[
                        const SizedBox(height: 2),
                        Text(
                          department.english,
                          style: const TextStyle(
                            fontSize: 13,
                            color: AppColors.slate500,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                IconButton(
                  icon: Icon(
                    department.isActive
                        ? Icons.toggle_on_rounded
                        : Icons.toggle_off_rounded,
                    size: 32,
                    color: department.isActive
                        ? AppColors.green600
                        : AppColors.slate400,
                  ),
                  onPressed: () => _toggleActive(department),
                  tooltip: department.isActive ? 'Deactivate' : 'Activate',
                ),
              ],
            ),

            if (department.description.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text(
                department.description,
                style: const TextStyle(
                  fontSize: 13.5,
                  color: AppColors.slate600,
                  height: 1.5,
                ),
              ),
            ],

            const SizedBox(height: 14),
            const Divider(height: 1),
            const SizedBox(height: 12),

            if (department.head.isNotEmpty)
              _row(Icons.person_outline_rounded, department.head),
            if (department.email.isNotEmpty)
              _row(Icons.mail_outline_rounded, department.email),
            if (department.office.isNotEmpty)
              _row(Icons.location_on_outlined, department.office),

            const SizedBox(height: 10),
            Row(
              children: [
                _metric('Complaints', department.complaintCount, color),
                _metric('Officers', department.officerCount, AppColors.slate500),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _row(IconData icon, String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 15, color: AppColors.slate400),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(
                fontSize: 13.5,
                color: AppColors.slate600,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _metric(String label, int value, Color color) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '$value',
            style: TextStyle(
              fontSize: 19,
              fontWeight: FontWeight.w700,
              color: color,
            ),
          ),
          Text(
            label,
            style: const TextStyle(fontSize: 12, color: AppColors.slate500),
          ),
        ],
      ),
    );
  }
}
