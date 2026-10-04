import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/complaint_provider.dart';
import '../../widgets/common.dart';
import '../../widgets/complaint_card.dart';
import '../../widgets/state_views.dart';
import '../shared/complaint_details_screen.dart';
import 'new_complaint_screen.dart';

/// The student home screen: a greeting, four counters, and recent complaints.
///
/// The primary action - raising a complaint - is a full-width button rather
/// than a small FAB, because it is the reason most students open the app.
class StudentDashboard extends StatefulWidget {
  const StudentDashboard({super.key, this.onSeeAll});

  /// Switches the shell to the complaints tab.
  final VoidCallback? onSeeAll;

  @override
  State<StudentDashboard> createState() => _StudentDashboardState();
}

class _StudentDashboardState extends State<StudentDashboard> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh());
  }

  Future<void> _refresh() => context.read<ComplaintProvider>().refreshAll();

  Future<void> _newComplaint() async {
    final created = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => const NewComplaintScreen()),
    );
    if (created == true && mounted) _refresh();
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
                        Text(
                          _greeting(),
                          style: const TextStyle(
                            fontSize: 14,
                            color: AppColors.slate500,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          user?.name ?? 'Student',
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
              const SizedBox(height: 20),
              FilledButton.icon(
                onPressed: _newComplaint,
                icon: const Icon(Icons.add_rounded, size: 22),
                label: const Text('Raise a new complaint'),
              ),
              const SizedBox(height: 24),
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
                    label: 'In progress',
                    value: '${stats.inProgress}',
                    icon: Icons.hourglass_bottom_rounded,
                    color: AppColors.amber500,
                    onTap: widget.onSeeAll,
                  ),
                  StatTile(
                    label: 'Resolved',
                    value: '${stats.resolved}',
                    icon: Icons.check_circle_outline,
                    color: AppColors.green600,
                    onTap: widget.onSeeAll,
                  ),
                  StatTile(
                    label: 'Awaiting action',
                    value: '${stats.pending}',
                    icon: Icons.schedule_rounded,
                    color: AppColors.sky600,
                    onTap: widget.onSeeAll,
                  ),
                ],
              ),
              const SizedBox(height: 28),
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
                EmptyView(
                  icon: Icons.assignment_outlined,
                  title: 'No complaints yet',
                  message:
                      'When you raise a complaint it will appear here so you can follow its progress.',
                  actionLabel: 'Raise a complaint',
                  onAction: _newComplaint,
                )
              else
                // Only the newest few; the full list lives on its own tab.
                ...provider.items.take(5).map(
                      (complaint) => Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: ComplaintCard(
                          complaint: complaint,
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

  String _greeting() {
    final hour = DateTime.now().hour;
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  }
}
