import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/complaint_provider.dart';
import '../../providers/notification_provider.dart';
import '../shared/complaint_list_screen.dart';
import '../shared/notifications_screen.dart';
import '../shared/profile_screen.dart';
import 'admin_dashboard.dart';

/// The admin's tabbed home. The management screens are reached from the
/// dashboard rather than the tab bar - five tabs would crowd a phone, and
/// they are visited far less often than the complaint list.
class AdminShell extends StatefulWidget {
  const AdminShell({super.key});

  @override
  State<AdminShell> createState() => _AdminShellState();
}

class _AdminShellState extends State<AdminShell> {
  int _index = 0;

  /// `all` scope: the admin sees every complaint the server permits.
  late final ComplaintProvider _complaints =
      ComplaintProvider(ComplaintScope.all);

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
              AdminDashboard(onSeeAll: () => setState(() => _index = 1)),
              const ComplaintListScreen(
                scope: ComplaintScope.all,
                title: 'All complaints',
                emptyTitle: 'No complaints yet',
                emptyMessage:
                    'Complaints from across the campus will appear here.',
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
                icon: Icon(Icons.dashboard_outlined),
                selectedIcon: Icon(Icons.dashboard_rounded),
                label: 'Dashboard',
              ),
              const NavigationDestination(
                icon: Icon(Icons.description_outlined),
                selectedIcon: Icon(Icons.description_rounded),
                label: 'Complaints',
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
