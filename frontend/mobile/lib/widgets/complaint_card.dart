import 'package:flutter/material.dart';

import '../core/theme/app_theme.dart';
import '../core/utils/formatters.dart';
import '../models/complaint.dart';
import 'badges.dart';

/// One complaint as a tappable card.
///
/// This is the mobile answer to the website's table: a phone cannot show ten
/// columns, so the card leads with the two things that decide whether the user
/// taps - what the complaint is, and where it has got to.
class ComplaintCard extends StatelessWidget {
  const ComplaintCard({
    super.key,
    required this.complaint,
    required this.onTap,
    this.showSubmitter = false,
    this.showOfficer = false,
  });

  final Complaint complaint;
  final VoidCallback onTap;

  /// Officers and admins need to know who filed it; a student already knows.
  final bool showSubmitter;

  /// Students and admins care who is handling it; an officer is the handler.
  final bool showOfficer;

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Reference id and the time, so the user can quote the id on the
              // phone to an office without opening the complaint.
              Row(
                children: [
                  Expanded(
                    child: Text(
                      complaint.id,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: AppColors.slate500,
                        letterSpacing: 0.3,
                      ),
                    ),
                  ),
                  Text(
                    Format.relative(complaint.submittedAt),
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppColors.slate400,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),

              Text(
                complaint.title,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: AppColors.slate900,
                  height: 1.3,
                ),
              ),
              const SizedBox(height: 10),

              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  StatusBadge(complaint.status),
                  PriorityBadge(complaint.priority),
                  if (complaint.isOverdue)
                    OverdueBadge(daysOverdue: complaint.daysOverdue),
                ],
              ),

              const SizedBox(height: 12),
              const Divider(height: 1),
              const SizedBox(height: 12),

              // The supporting detail row: department always, then whichever
              // person this role needs to see.
              Row(
                children: [
                  Expanded(child: DepartmentBadge(complaint.department)),
                  if (complaint.evidence.isNotEmpty) ...[
                    const Icon(Icons.attach_file_rounded,
                        size: 14, color: AppColors.slate400),
                    const SizedBox(width: 2),
                    Text(
                      '${complaint.evidence.length}',
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppColors.slate400,
                      ),
                    ),
                  ],
                ],
              ),

              if (showSubmitter && complaint.submittedByName.isNotEmpty)
                _detailRow(
                  Icons.person_outline_rounded,
                  'By ${complaint.submittedByName}',
                ),

              if (showOfficer)
                _detailRow(
                  Icons.engineering_outlined,
                  complaint.assignedOfficerName.isEmpty
                      ? 'Not assigned yet'
                      : complaint.assignedOfficerName,
                ),

              if (complaint.location.address.isNotEmpty)
                _detailRow(
                  Icons.place_outlined,
                  complaint.location.address,
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _detailRow(IconData icon, String text) {
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        children: [
          Icon(icon, size: 14, color: AppColors.slate400),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              text,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 13, color: AppColors.slate600),
            ),
          ),
        ],
      ),
    );
  }
}
