import 'package:flutter/material.dart';

import '../core/config/constants.dart';
import '../core/theme/app_theme.dart';

/// A status pill. Colour carries the meaning at a glance, but the label is
/// always present too - colour alone would fail anyone who cannot distinguish
/// amber from green.
class StatusBadge extends StatelessWidget {
  const StatusBadge(this.status, {super.key, this.compact = false});

  final String status;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final color = AppColors.forStatus(status);
    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 8 : 10,
        vertical: compact ? 3 : 5,
      ),
      decoration: BoxDecoration(
        color: AppColors.forStatusBackground(status),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Text(
            status,
            style: TextStyle(
              fontSize: compact ? 11 : 12,
              fontWeight: FontWeight.w600,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}

/// A priority pill. Urgent gets a filled treatment so it stands out in a list
/// of otherwise similar cards.
class PriorityBadge extends StatelessWidget {
  const PriorityBadge(this.priority, {super.key, this.compact = false});

  final String priority;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final color = AppColors.forPriority(priority);
    final isUrgent = priority == Domain.priorityUrgent;

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 8 : 10,
        vertical: compact ? 3 : 5,
      ),
      decoration: BoxDecoration(
        color: isUrgent ? color : color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            isUrgent
                ? Icons.priority_high_rounded
                : Icons.flag_outlined,
            size: compact ? 12 : 13,
            color: isUrgent ? Colors.white : color,
          ),
          const SizedBox(width: 4),
          Text(
            priority,
            style: TextStyle(
              fontSize: compact ? 11 : 12,
              fontWeight: FontWeight.w600,
              color: isUrgent ? Colors.white : color,
            ),
          ),
        ],
      ),
    );
  }
}

/// A department tag, colour-matched to the web app's department colours.
class DepartmentBadge extends StatelessWidget {
  const DepartmentBadge(this.department, {super.key});

  final String department;

  @override
  Widget build(BuildContext context) {
    final color = AppColors.forDepartment(department);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        department,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: color,
        ),
      ),
    );
  }
}

/// A small count bubble for the navigation bar.
class CountBadge extends StatelessWidget {
  const CountBadge(this.count, {super.key});

  final int count;

  @override
  Widget build(BuildContext context) {
    if (count <= 0) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      constraints: const BoxConstraints(minWidth: 18),
      decoration: BoxDecoration(
        color: AppColors.red600,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        count > 99 ? '99+' : '$count',
        textAlign: TextAlign.center,
        style: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          color: Colors.white,
        ),
      ),
    );
  }
}

/// "3 days overdue" / "Due today" - the SLA state in words.
class OverdueBadge extends StatelessWidget {
  const OverdueBadge({super.key, required this.daysOverdue});

  final int daysOverdue;

  @override
  Widget build(BuildContext context) {
    if (daysOverdue <= 0) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.red50,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.schedule_rounded,
              size: 12, color: AppColors.red600),
          const SizedBox(width: 4),
          Text(
            daysOverdue == 1 ? '1 day overdue' : '$daysOverdue days overdue',
            style: const TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: AppColors.red600,
            ),
          ),
        ],
      ),
    );
  }
}
