import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/complaint_provider.dart';
import '../../widgets/common.dart';
import '../../widgets/complaint_card.dart';
import '../../widgets/state_views.dart';
import '../shared/complaint_details_screen.dart';

/// The officer home screen.
///
/// Leads with what needs attention - overdue and urgent work - because an
/// officer opens the app to find the next job, not to browse.
class OfficerDashboard extends StatefulWidget {
  const OfficerDashboard({super.key, this.onSeeAll});

  final VoidCallback? onSeeAll;

  @override
  State<OfficerDashboard> createState() => _OfficerDashboardState();
}

class _OfficerDashboardState extends State<OfficerDashboard> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh());
  }

  Future<void> _refresh() => context.read<ComplaintProvider>().refreshAll();

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().user;
    final provider = context.watch<ComplaintProvider>();
    final stats = provider.stats;

    // Worth surfacing first: anything past its deadline, then anything urgent.
    final urgent = provider.items
        .where((c) => c.isActive && (c.isOverdue || c.priority == 'Urgent'))
        .take(5)
        .toList();

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
                        Text(
                          user?.department.isNotEmpty == true
                              ? user!.department
                              : 'Officer',
                          style: const TextStyle(
                            fontSize: 13.5,
                            color: AppColors.slate500,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          user?.name ?? 'Officer',
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
                childAspectRatio: 1.45,
                children: [
                  StatTile(
                    label: 'Assigned to me',
                    value: '${stats.total}',
                    icon: Icons.assignment_outlined,
                    color: AppColors.brand600,
                    onTap: widget.onSeeAll,
                  ),
                  StatTile(
                    label: 'In progress',
                    value: '${stats.inProgress}',
                    icon: Icons.build_outlined,
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
                    value: '${stats.resolved}',
                    icon: Icons.check_circle_outline,
                    color: AppColors.green600,
                    onTap: widget.onSeeAll,
                  ),
                ],
              ),
              const SizedBox(height: 28),

              SectionHeader(
                title: urgent.isEmpty ? 'Your queue' : 'Needs attention first',
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
                  icon: Icons.task_alt_rounded,
                  title: 'Nothing assigned',
                  message:
                      'Complaints routed to you will appear here as soon as they arrive.',
                )
              else
                ...(urgent.isNotEmpty ? urgent : provider.items.take(5)).map(
                  (complaint) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: ComplaintCard(
                      complaint: complaint,
                      showSubmitter: true,
                      onTap: () async {
                        final changed = await Navigator.of(context).push<bool>(
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
}
