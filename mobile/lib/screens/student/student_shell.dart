import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/complaint_provider.dart';
import '../../providers/notification_provider.dart';
import '../shared/complaint_list_screen.dart';
import '../shared/notifications_screen.dart';
import '../shared/profile_screen.dart';
import 'new_complaint_screen.dart';
import 'student_dashboard.dart';

/// The student's tabbed home.
///
/// Tabs are kept alive in an IndexedStack so switching back to a list does not
/// refetch it, and the Android back button steps back to Home before leaving
/// the app - the behaviour Android users expect from a bottom-nav app.
class StudentShell extends StatefulWidget {
  const StudentShell({super.key});

  @override
  State<StudentShell> createState() => _StudentShellState();
}

class _StudentShellState extends State<StudentShell> {
  int _index = 0;

  /// One provider for the whole shell, so the dashboard and the list share
  /// their loaded pages instead of each fetching separately.
  late final ComplaintProvider _complaints =
      ComplaintProvider(ComplaintScope.mine);

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

  Future<void> _newComplaint() async {
    final created = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => const NewComplaintScreen()),
    );
    if (created == true && mounted) {
      _complaints.refreshAll();
      setState(() => _index = 1); // show the list the complaint landed in
    }
  }

  @override
  Widget build(BuildContext context) {
    final unread = context.watch<NotificationProvider>().unreadCount;

    return ChangeNotifierProvider<ComplaintProvider>.value(
      value: _complaints,
      child: PopScope(
        // Back from a sub-tab returns to Home rather than exiting.
        canPop: _index == 0,
        onPopInvokedWithResult: (didPop, _) {
          if (!didPop) setState(() => _index = 0);
        },
        child: Scaffold(
          body: IndexedStack(
            index: _index,
            children: [
              StudentDashboard(onSeeAll: () => setState(() => _index = 1)),
              ComplaintListScreen(
                scope: ComplaintScope.mine,
                title: 'My complaints',
                emptyTitle: 'No complaints yet',
                emptyMessage:
                    'Raise your first complaint and track it here.',
                emptyActionLabel: 'Raise a complaint',
                onEmptyAction: _newComplaint,
              ),
              const NotificationsScreen(),
              const ProfileScreen(),
            ],
          ),
          floatingActionButton: _index == 1
              ? FloatingActionButton.extended(
                  onPressed: _newComplaint,
                  icon: const Icon(Icons.add_rounded),
                  label: const Text('New'),
                )
              : null,
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
