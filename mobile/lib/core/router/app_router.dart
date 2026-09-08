import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../screens/admin/admin_shell.dart';
import '../../screens/auth/login_screen.dart';
import '../../screens/officer/officer_shell.dart';
import '../../screens/student/student_shell.dart';
import '../theme/app_theme.dart';

/// Decides which shell the app shows, from the session alone.
///
/// Role routing lives in one place so no screen has to check a role to know
/// whether it should be on screen: signing in, signing out and an expired
/// refresh all move the user automatically.
class AppRouter extends StatelessWidget {
  const AppRouter({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();

    switch (auth.status) {
      case AuthStatus.unknown:
        return const _SplashScreen();

      case AuthStatus.unauthenticated:
        return const LoginScreen();

      case AuthStatus.authenticated:
        final user = auth.user;
        if (user == null) return const _SplashScreen();

        if (user.isAdmin) return const AdminShell();
        if (user.isOfficer) return const OfficerShell();
        return const StudentShell();
    }
  }
}

/// Shown while the stored session is being restored.
class _SplashScreen extends StatelessWidget {
  const _SplashScreen();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 76,
              height: 76,
              decoration: BoxDecoration(
                color: AppColors.brand600,
                borderRadius: BorderRadius.circular(20),
              ),
              child: const Icon(Icons.gavel_rounded,
                  color: Colors.white, size: 38),
            ),
            const SizedBox(height: 20),
            const Text(
              'DSVV Grievance',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: AppColors.slate900,
              ),
            ),
            const SizedBox(height: 6),
            const Text(
              'Dev Sanskriti Vishwavidyalaya',
              style: TextStyle(fontSize: 13.5, color: AppColors.slate500),
            ),
            const SizedBox(height: 32),
            const SizedBox(
              width: 26,
              height: 26,
              child: CircularProgressIndicator(strokeWidth: 2.5),
            ),
          ],
        ),
      ),
    );
  }
}
