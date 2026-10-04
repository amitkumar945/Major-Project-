import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/complaint_provider.dart';
import '../../widgets/common.dart';
import '../../widgets/complaint_card.dart';
import '../../widgets/state_views.dart';
import '../shared/complaint_details_screen.dart';
import 'admin_analytics_screen.dart';
import 'admin_departments_screen.dart';
import 'admin_escalations_screen.dart';
import 'admin_officers_screen.dart';
import 'admin_settings_screen.dart';
import 'admin_users_screen.dart';

/// The admin home: system-wide counters, quick links to the management
/// screens, and the most recent complaints.
class AdminDashboard extends StatefulWidget {
  const AdminDashboard({super.key, this.onSeeAll});

  final VoidCallback? onSeeAll;

  @override
  State<AdminDashboard> createState() => _AdminDashboardState();
}

class _AdminDashboardState extends State<AdminDashboard> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh());
  }

  Future<void> _refresh() => context.read<ComplaintProvider>().refreshAll();

  void _open(Widget screen) {
    Navigator.of(context)
        .push(MaterialPageRoute(builder: (_) => screen))
        .then((_) {
      if (mounted) _refresh();
    });
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().user;
    final provider = context.watch<ComplaintProvider>();
    final stats = provider.stats;

    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _refresh,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Administrator',
                          style: TextStyle(
                            fontSize: 13.5,
                            color: AppColors.slate500,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          user?.name ?? 'Admin',
                          style: const TextStyle(
                            fontSize: 22,
                            fontWeight: FontWeight.w700,
                            color: AppColors.slate900,
                          ),
                        ),
                      ],
                    ),
                  ),
                  CircleAvatar(
                    radius: 22,
                    backgroundColor: AppColors.brand600,
                    child: Text(
                      user?.initials ?? '?',
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 22),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                mainAxisExtent: 140,
                children: [
                  StatTile(
                    label: 'Total complaints',
                    value: '${stats.total}',
                    icon: Icons.description_outlined,
                    color: AppColors.brand600,
                    onTap: widget.onSeeAll,
                  ),
                  StatTile(
                    label: 'Open',
                    value: '${stats.pending + stats.inProgress}',
                    icon: Icons.pending_actions_rounded,
                    color: AppColors.amber500,
                    onTap: widget.onSeeAll,
                  ),
                  StatTile(
                    label: 'Overdue',
                    value: '${stats.overdue}',
                    icon: Icons.warning_amber_rounded,
                    color: AppColors.red600,
                    onTap: widget.onSeeAll,
                  ),
                  StatTile(
                    label: 'Resolved',
                    value: '${stats.resolutionRate}%',
                    icon: Icons.check_circle_outline,
                    color: AppColors.green600,
                    onTap: () => _open(const AdminAnalyticsScreen()),
                  ),
                ],
              ),
              const SizedBox(height: 28),
              const SectionHeader(title: 'Manage'),
              _tile(
                  Icons.trending_up_rounded,
                  'Escalations',
                  'Complaints raised to a higher authority',
                  AppColors.red600,
                  () => _open(const AdminEscalationsScreen()),
                  badge: stats.escalated),
              _tile(
                  Icons.insights_outlined,
                  'Analytics',
                  'Trends, departments and SLA performance',
                  AppColors.violet600,
                  () => _open(const AdminAnalyticsScreen())),
              _tile(
                  Icons.engineering_outlined,
                  'Officers',
                  'Add officers and see their workload',
                  AppColors.brand600,
                  () => _open(const AdminOfficersScreen())),
              _tile(
                  Icons.people_outline_rounded,
                  'Users',
                  'Students and staff accounts',
                  AppColors.sky600,
                  () => _open(const AdminUsersScreen())),
              _tile(
                  Icons.apartment_outlined,
                  'Departments',
                  'The four campus departments',
                  AppColors.amber500,
                  () => _open(const AdminDepartmentsScreen())),
              _tile(
                  Icons.settings_outlined,
                  'Settings',
                  'System configuration and SLA checks',
                  AppColors.slate500,
                  () => _open(const AdminSettingsScreen())),
              const SizedBox(height: 24),
              SectionHeader(
                title: 'Recent complaints',
                actionLabel: provider.items.isEmpty ? null : 'See all',
                onAction: widget.onSeeAll,
              ),
              if (provider.isLoading && provider.items.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 40),
                  child: LoadingView(),
                )
              else if (provider.error != null && provider.items.isEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 20),
                  child: ErrorView(
                    message: provider.error!,
                    isNetwork:
                        provider.error!.toLowerCase().contains('connection'),
                    onRetry: _refresh,
                  ),
                )
              else if (provider.items.isEmpty)
                const EmptyView(
                  icon: Icons.inbox_outlined,
                  title: 'No complaints yet',
                  message:
                      'Complaints from across the campus will appear here.',
                )
              else
                ...provider.items.take(5).map(
                      (complaint) => Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: ComplaintCard(
                          complaint: complaint,
                          showSubmitter: true,
                          showOfficer: true,
                          onTap: () async {
                            final changed =
                                await Navigator.of(context).push<bool>(
                              MaterialPageRoute(
                                builder: (_) => ComplaintDetailsScreen(
                                  complaintId: complaint.id,
                                ),
                              ),
                            );
                            if (changed == true && mounted) _refresh();
                          },
                        ),
                      ),
                    ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _tile(
    IconData icon,
    String title,
    String subtitle,
    Color color,
    VoidCallback onTap, {
    int badge = 0,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Card(
        clipBehavior: Clip.antiAlias,
        child: ListTile(
          onTap: onTap,
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
          leading: Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(11),
            ),
            child: Icon(icon, size: 20, color: color),
          ),
          title: Text(
            title,
            style: const TextStyle(
              fontSize: 15.5,
              fontWeight: FontWeight.w600,
              color: AppColors.slate900,
            ),
          ),
          subtitle: Text(
            subtitle,
            style: const TextStyle(fontSize: 13, color: AppColors.slate500),
          ),
          trailing: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (badge > 0) ...[
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppColors.red50,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    '$badge',
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                      color: AppColors.red600,
                    ),
                  ),
                ),
                const SizedBox(width: 6),
              ],
              const Icon(Icons.chevron_right_rounded,
                  color: AppColors.slate400),
            ],
          ),
        ),
      ),
    );
  }
}
