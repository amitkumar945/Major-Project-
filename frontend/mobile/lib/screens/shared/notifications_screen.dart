import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../core/utils/formatters.dart';
import '../../models/notification.dart';
import '../../providers/notification_provider.dart';
import '../../widgets/state_views.dart';
import 'complaint_details_screen.dart';

/// The in-app notification feed, shared by every role.
class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key, this.showAppBar = true});

  final bool showAppBar;

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<NotificationProvider>().load();
    });
  }

  Future<void> _open(AppNotification item) async {
    context.read<NotificationProvider>().markRead(item.id);

    final complaintId = item.complaintId;
    if (complaintId == null || complaintId.isEmpty) return;

    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ComplaintDetailsScreen(complaintId: complaintId),
      ),
    );
  }

  /// An icon per notification type, so the feed is scannable.
  IconData _iconFor(String type) {
    switch (type) {
      case 'submitted':
        return Icons.send_outlined;
      case 'assigned':
      case 'officer_assigned':
        return Icons.person_add_alt_outlined;
      case 'status_changed':
        return Icons.published_with_changes_rounded;
      case 'resolution_submitted':
      case 'resolved':
        return Icons.check_circle_outline;
      case 'deadline_approaching':
        return Icons.schedule_rounded;
      case 'escalated':
        return Icons.trending_up_rounded;
      case 'feedback_requested':
        return Icons.star_outline_rounded;
      default:
        return Icons.notifications_outlined;
    }
  }

  Color _colorFor(String type) {
    switch (type) {
      case 'resolved':
      case 'resolution_submitted':
        return AppColors.green600;
      case 'escalated':
      case 'deadline_approaching':
        return AppColors.red600;
      case 'assigned':
      case 'officer_assigned':
        return AppColors.brand600;
      default:
        return AppColors.slate500;
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<NotificationProvider>();

    return Scaffold(
      appBar: widget.showAppBar
          ? AppBar(
              title: const Text('Notifications'),
              actions: [
                if (provider.unreadCount > 0)
                  TextButton(
                    onPressed: provider.markAllRead,
                    child: const Text('Mark all read'),
                  ),
              ],
            )
          : null,
      body: _body(provider),
    );
  }

  Widget _body(NotificationProvider provider) {
    if (provider.isLoading && provider.items.isEmpty) {
      return const LoadingView(message: 'Loading notifications...');
    }

    if (provider.error != null && provider.items.isEmpty) {
      return ErrorView(
        message: provider.error!,
        isNetwork: provider.error!.toLowerCase().contains('connection'),
        onRetry: provider.load,
      );
    }

    if (provider.isEmpty) {
      return const EmptyView(
        icon: Icons.notifications_none_rounded,
        title: 'No notifications',
        message: 'Updates about your complaints will appear here.',
      );
    }

    return RefreshIndicator(
      onRefresh: provider.load,
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(vertical: 8),
        itemCount: provider.items.length,
        separatorBuilder: (_, __) => const Divider(height: 1, indent: 68),
        itemBuilder: (context, index) {
          final item = provider.items[index];
          final color = _colorFor(item.type);

          return Dismissible(
            key: ValueKey(item.id),
            direction: DismissDirection.endToStart,
            background: Container(
              alignment: Alignment.centerRight,
              padding: const EdgeInsets.only(right: 20),
              color: AppColors.red50,
              child: const Icon(Icons.delete_outline_rounded,
                  color: AppColors.red600),
            ),
            onDismissed: (_) => provider.remove(item.id),
            child: ListTile(
              onTap: () => _open(item),
              // Unread rows get a tint, so the badge count is visible in place.
              tileColor: item.read ? null : AppColors.brand50.withValues(alpha: 0.4),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              leading: Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(11),
                ),
                child: Icon(_iconFor(item.type), size: 20, color: color),
              ),
              title: Text(
                item.title,
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: item.read ? FontWeight.w500 : FontWeight.w700,
                  color: AppColors.slate900,
                ),
              ),
              subtitle: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SizedBox(height: 3),
                  Text(
                    item.message,
                    style: const TextStyle(
                      fontSize: 13.5,
                      color: AppColors.slate600,
                      height: 1.4,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    Format.relative(item.createdAt),
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppColors.slate400,
                    ),
                  ),
                ],
              ),
              trailing: item.read
                  ? null
                  : Container(
                      width: 8,
                      height: 8,
                      decoration: const BoxDecoration(
                        color: AppColors.brand600,
                        shape: BoxShape.circle,
                      ),
                    ),
            ),
          );
        },
      ),
    );
  }
}
