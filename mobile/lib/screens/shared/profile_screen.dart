import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/network/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/notification_provider.dart';
import '../../services/auth_service.dart';
import '../../widgets/common.dart';

/// Profile, password change and sign-out, shared by every role.
class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key, this.showAppBar = true});

  final bool showAppBar;

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final user = auth.user;

    if (user == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    return Scaffold(
      appBar: showAppBar ? AppBar(title: const Text('Profile')) : null,
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                children: [
                  CircleAvatar(
                    radius: 36,
                    backgroundColor: AppColors.brand600,
                    child: Text(
                      user.initials,
                      style: const TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  Text(
                    user.name,
                    style: const TextStyle(
                      fontSize: 19,
                      fontWeight: FontWeight.w700,
                      color: AppColors.slate900,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    user.email,
                    style: const TextStyle(
                      fontSize: 14,
                      color: AppColors.slate500,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 5),
                    decoration: BoxDecoration(
                      color: AppColors.brand50,
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Text(
                      // "student" reads better capitalised in a badge.
                      user.role.isEmpty
                          ? 'User'
                          : user.role[0].toUpperCase() +
                              user.role.substring(1),
                      style: const TextStyle(
                        fontSize: 12.5,
                        fontWeight: FontWeight.w600,
                        color: AppColors.brand700,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Account details',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: AppColors.slate900,
                    ),
                  ),
                  const SizedBox(height: 14),
                  if (user.userId.isNotEmpty) _row('User ID', user.userId),
                  if (user.department.isNotEmpty)
                    _row('Department', user.department),
                  if (user.userType.isNotEmpty) _row('Type', user.userType),
                  if (user.phone.isNotEmpty) _row('Mobile', user.phone),
                  if (user.designation.isNotEmpty)
                    _row('Designation', user.designation),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          Card(
            clipBehavior: Clip.antiAlias,
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.edit_outlined),
                  title: const Text('Edit profile',
                      style: TextStyle(fontSize: 15.5)),
                  trailing: const Icon(Icons.chevron_right_rounded),
                  onTap: () => _editProfile(context, auth),
                ),
                const Divider(height: 1),
                ListTile(
                  leading: const Icon(Icons.lock_outline_rounded),
                  title: const Text('Change password',
                      style: TextStyle(fontSize: 15.5)),
                  trailing: const Icon(Icons.chevron_right_rounded),
                  onTap: () => _changePassword(context),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          Card(
            clipBehavior: Clip.antiAlias,
            child: ListTile(
              leading: const Icon(Icons.logout_rounded, color: AppColors.red600),
              title: const Text(
                'Sign out',
                style: TextStyle(
                  fontSize: 15.5,
                  fontWeight: FontWeight.w600,
                  color: AppColors.red600,
                ),
              ),
              onTap: () => _signOut(context, auth),
            ),
          ),

          const SizedBox(height: 24),
          const Center(
            child: Text(
              'DSVV Grievance Management\nVersion 1.0.0',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 12.5,
                color: AppColors.slate400,
                height: 1.5,
              ),
            ),
          ),
        ],
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
            width: 110,
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

  Future<void> _signOut(BuildContext context, AuthProvider auth) async {
    final ok = await confirm(
      context,
      title: 'Sign out?',
      message: 'You will need to sign in again to raise or track complaints.',
      confirmLabel: 'Sign out',
      destructive: true,
    );
    if (!ok || !context.mounted) return;

    context.read<NotificationProvider>().reset();
    await auth.signOut();
  }

  void _editProfile(BuildContext context, AuthProvider auth) {
    final user = auth.user!;
    final name = TextEditingController(text: user.name);
    final phone = TextEditingController(text: user.phone);
    var saving = false;

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
                'Edit profile',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 16),
              AppTextField(
                controller: name,
                label: 'Full name',
                enabled: !saving,
              ),
              const SizedBox(height: 16),
              AppTextField(
                controller: phone,
                label: 'Mobile number',
                hint: '10-digit number',
                keyboardType: TextInputType.phone,
                maxLength: 10,
                enabled: !saving,
              ),
              const SizedBox(height: 20),
              FilledButton(
                onPressed: saving
                    ? null
                    : () async {
                        setSheetState(() => saving = true);
                        try {
                          await auth.updateProfile({
                            'name': name.text.trim(),
                            'phone': phone.text.trim(),
                          });
                          if (!sheetContext.mounted) return;
                          Navigator.of(sheetContext).pop();
                          showSnack(context, 'Profile updated.');
                        } on ApiException catch (e) {
                          setSheetState(() => saving = false);
                          if (context.mounted) {
                            showSnack(context, e.message, isError: true);
                          }
                        }
                      },
                child: Text(saving ? 'Saving...' : 'Save changes'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _changePassword(BuildContext context) {
    final current = TextEditingController();
    final next = TextEditingController();
    final confirmField = TextEditingController();
    var saving = false;
    String? error;

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
                  'Change password',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 16),
                AppTextField(
                  controller: current,
                  label: 'Current password',
                  obscureText: true,
                  enabled: !saving,
                ),
                const SizedBox(height: 16),
                AppTextField(
                  controller: next,
                  label: 'New password',
                  hint: 'At least 8 characters',
                  obscureText: true,
                  errorText: error,
                  enabled: !saving,
                ),
                const SizedBox(height: 16),
                AppTextField(
                  controller: confirmField,
                  label: 'Confirm new password',
                  obscureText: true,
                  enabled: !saving,
                ),
                const SizedBox(height: 20),
                FilledButton(
                  onPressed: saving
                      ? null
                      : () async {
                          if (next.text.length < 8) {
                            setSheetState(() =>
                                error = 'Password must be at least 8 characters');
                            return;
                          }
                          if (next.text != confirmField.text) {
                            setSheetState(
                                () => error = 'Passwords do not match');
                            return;
                          }

                          setSheetState(() {
                            saving = true;
                            error = null;
                          });
                          try {
                            await AuthService.instance.changePassword(
                              currentPassword: current.text,
                              newPassword: next.text,
                            );
                            if (!sheetContext.mounted) return;
                            Navigator.of(sheetContext).pop();
                            showSnack(context, 'Password changed.');
                          } on ApiException catch (e) {
                            setSheetState(() {
                              saving = false;
                              error = e.message;
                            });
                          }
                        },
                  child: Text(saving ? 'Saving...' : 'Change password'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
