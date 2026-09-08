import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import 'core/config/constants.dart';
import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';
import 'providers/auth_provider.dart';
import 'providers/notification_provider.dart';
import 'screens/shared/complaint_details_screen.dart';
import 'services/push_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Portrait only: every screen is a single column, and a rotated map picker
  // leaves no room for the address fields.
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.dark,
  ));

  // Push is optional - see PushService. It never throws, so a project without
  // Firebase configured still starts normally.
  await PushService.instance.initialise();

  runApp(const GrievanceApp());
}

class GrievanceApp extends StatelessWidget {
  const GrievanceApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        // `restoreSession` runs at construction, so the splash is only shown
        // for as long as the stored token takes to check.
        ChangeNotifierProvider(
          create: (_) => AuthProvider()..restoreSession(),
        ),
        ChangeNotifierProvider(create: (_) => NotificationProvider()),
      ],
      child: MaterialApp(
        title: Domain.appName,
        debugShowCheckedModeBanner: false,
        theme: AppTheme.light(),
        navigatorKey: _navigatorKey,
        home: const _PushTapListener(child: AppRouter()),
      ),
    );
  }
}

final GlobalKey<NavigatorState> _navigatorKey = GlobalKey<NavigatorState>();

/// Opens the relevant complaint when a push notification is tapped.
///
/// Wrapped around the router rather than living inside it, so the subscription
/// survives the shell being swapped when a session changes.
class _PushTapListener extends StatefulWidget {
  const _PushTapListener({required this.child});

  final Widget child;

  @override
  State<_PushTapListener> createState() => _PushTapListenerState();
}

class _PushTapListenerState extends State<_PushTapListener> {
  StreamSubscription<String>? _tapSubscription;

  @override
  void initState() {
    super.initState();

    _tapSubscription =
        PushService.instance.onNotificationTap.listen((complaintId) {
      if (complaintId.isEmpty) return;

      // The tap arrives long after initState, so the widget may be gone by
      // now - reading an inherited widget through a dead context would throw.
      if (!mounted) return;

      // Only meaningful once signed in; a tap while signed out lands on login.
      final auth = context.read<AuthProvider>();
      if (!auth.isSignedIn) return;

      final notifications = context.read<NotificationProvider>();

      _navigatorKey.currentState?.push(
        MaterialPageRoute(
          builder: (_) => ComplaintDetailsScreen(complaintId: complaintId),
        ),
      );

      // A push almost always means the feed changed too.
      notifications.refreshBadge();
    });
  }

  @override
  void dispose() {
    _tapSubscription?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
