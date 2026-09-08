import 'package:flutter/material.dart';

import '../../core/config/constants.dart';
import '../../core/network/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../models/user.dart';
import '../../services/admin_service.dart';
import '../../widgets/common.dart';
import '../../widgets/state_views.dart';

/// Student and staff accounts, with activation control.
class AdminUsersScreen extends StatefulWidget {
  const AdminUsersScreen({super.key});

  @override
  State<AdminUsersScreen> createState() => _AdminUsersScreenState();
}

class _AdminUsersScreenState extends State<AdminUsersScreen> {
  final _search = TextEditingController();

  List<AppUser> _users = [];
  String? _role;
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
      final users = await AdminService.instance.users(
        search: _search.text.trim(),
        role: _role ?? '',
      );
      if (mounted) setState(() => _users = users);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Could not load users.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _toggleActive(AppUser user) async {
    final ok = await confirm(
      context,
      title: user.isActive ? 'Deactivate account?' : 'Activate account?',
      message: user.isActive
          ? '${user.name} will not be able to sign in. Their complaints stay on record.'
          : '${user.name} will be able to sign in again.',
      confirmLabel: user.isActive ? 'Deactivate' : 'Activate',
      destructive: user.isActive,
    );
    if (!ok) return;

    try {
      await AdminService.instance.toggleUserActive(user.id);
      if (!mounted) return;
      showSnack(context,
          user.isActive ? 'Account deactivated.' : 'Account activated.');
      _load();
    } on ApiException catch (e) {
      if (mounted) showSnack(context, e.message, isError: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Users')),
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
                    hintText: 'Search by name, email or ID',
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
                      _chip('All', null),
                      _chip('Students', Domain.roleStudent),
                      _chip('Officers', Domain.roleOfficer),
                      _chip('Admins', Domain.roleAdmin),
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

  Widget _chip(String label, String? value) {
    final selected = _role == value;
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: FilterChip(
        label: Text(label),
        selected: selected,
        showCheckmark: false,
        onSelected: (_) {
          setState(() => _role = value);
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
    if (_loading) return const LoadingView(message: 'Loading users...');

    if (_error != null) {
      return ErrorView(
        message: _error!,
        isNetwork: _error!.toLowerCase().contains('connection'),
        onRetry: _load,
      );
    }

    if (_users.isEmpty) {
      return const EmptyView(
        icon: Icons.people_outline_rounded,
        title: 'No users found',
        message: 'Try a different search or filter.',
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
        itemCount: _users.length,
        separatorBuilder: (_, __) => const SizedBox(height: 10),
        itemBuilder: (context, index) {
          final user = _users[index];
          return Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 21,
                    backgroundColor:
                        user.isActive ? AppColors.brand50 : AppColors.slate100,
                    child: Text(
                      user.initials,
                      style: TextStyle(
                        fontSize: 13.5,
                        fontWeight: FontWeight.w700,
                        color: user.isActive
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
                                user.name,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  fontSize: 15.5,
                                  fontWeight: FontWeight.w600,
                                  color: AppColors.slate900,
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: AppColors.slate100,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                user.role,
                                style: const TextStyle(
                                  fontSize: 10.5,
                                  fontWeight: FontWeight.w600,
                                  color: AppColors.slate600,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 3),
                        Text(
                          user.email,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 13,
                            color: AppColors.slate500,
                          ),
                        ),
                        if (user.department.isNotEmpty) ...[
                          const SizedBox(height: 2),
                          Text(
                            user.department,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontSize: 12.5,
                              color: AppColors.slate400,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                  IconButton(
                    icon: Icon(
                      user.isActive
                          ? Icons.toggle_on_rounded
                          : Icons.toggle_off_rounded,
                      size: 32,
                      color: user.isActive
                          ? AppColors.green600
                          : AppColors.slate400,
                    ),
                    onPressed: () => _toggleActive(user),
                    tooltip: user.isActive ? 'Deactivate' : 'Activate',
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
