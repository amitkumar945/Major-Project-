import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/complaint_provider.dart';
import '../../providers/notification_provider.dart';
import '../shared/complaint_list_screen.dart';
import '../shared/notifications_screen.dart';
import '../shared/profile_screen.dart';
import 'officer_dashboard.dart';

/// The officer's tabbed home: queue, alerts, profile.
class OfficerShell extends StatefulWidget {
  const OfficerShell({super.key});

  @override
  State<OfficerShell> createState() => _OfficerShellState();
}

class _OfficerShellState extends State<OfficerShell> {
  int _index = 0;

  /// `assigned` scope, so the officer only ever loads their own queue.
  late final ComplaintProvider _complaints =
      ComplaintProvider(ComplaintScope.assigned);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<NotificationProvider>().refreshBadge();
    });
  }

  @override
  void dispose() {
    _complaints.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final unread = context.watch<NotificationProvider>().unreadCount;

    return ChangeNotifierProvider<ComplaintProvider>.value(
      value: _complaints,
      child: PopScope(
        canPop: _index == 0,
        onPopInvokedWithResult: (didPop, _) {
          if (!didPop) setState(() => _index = 0);
        },
        child: Scaffold(
          body: IndexedStack(
            index: _index,
            children: [
              OfficerDashboard(onSeeAll: () => setState(() => _index = 1)),
              const ComplaintListScreen(
                scope: ComplaintScope.assigned,
                title: 'My queue',
                emptyTitle: 'Nothing assigned',
                emptyMessage:
                    'Complaints routed to you will appear here as soon as they arrive.',
              ),
              const NotificationsScreen(),
              const ProfileScreen(),
            ],
          ),
          bottomNavigationBar: NavigationBar(
            selectedIndex: _index,
            onDestinationSelected: (index) => setState(() => _index = index),
            destinations: [
              const NavigationDestination(
                icon: Icon(Icons.home_outlined),
                selectedIcon: Icon(Icons.home_rounded),
                label: 'Home',
              ),
              const NavigationDestination(
                icon: Icon(Icons.assignment_outlined),
                selectedIcon: Icon(Icons.assignment_rounded),
                label: 'Queue',
              ),
              NavigationDestination(
                icon: Badge(
                  isLabelVisible: unread > 0,
                  label: Text(unread > 99 ? '99+' : '$unread'),
                  child: const Icon(Icons.notifications_outlined),
                ),
                selectedIcon: Badge(
                  isLabelVisible: unread > 0,
                  label: Text(unread > 99 ? '99+' : '$unread'),
                  child: const Icon(Icons.notifications_rounded),
                ),
                label: 'Alerts',
              ),
              const NavigationDestination(
                icon: Icon(Icons.person_outline_rounded),
                selectedIcon: Icon(Icons.person_rounded),
                label: 'Profile',
              ),
            ],
          ),
        ),
      ),
    );
  }
}
