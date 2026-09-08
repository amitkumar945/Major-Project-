import 'package:flutter/material.dart';

import '../../core/network/api_exception.dart';
import '../../models/complaint.dart';
import '../../services/admin_service.dart';
import '../../widgets/complaint_card.dart';
import '../../widgets/state_views.dart';
import '../shared/complaint_details_screen.dart';

/// Complaints that have been escalated past their department.
class AdminEscalationsScreen extends StatefulWidget {
  const AdminEscalationsScreen({super.key});

  @override
  State<AdminEscalationsScreen> createState() => _AdminEscalationsScreenState();
}

class _AdminEscalationsScreenState extends State<AdminEscalationsScreen> {
  List<Complaint> _items = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final items = await AdminService.instance.escalations();
      if (mounted) setState(() => _items = items);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Could not load escalations.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Escalations')),
      body: _body(),
    );
  }

  Widget _body() {
    if (_loading) return const LoadingView(message: 'Loading escalations...');

    if (_error != null) {
      return ErrorView(
        message: _error!,
        isNetwork: _error!.toLowerCase().contains('connection'),
        onRetry: _load,
      );
    }

    if (_items.isEmpty) {
      return const EmptyView(
        icon: Icons.verified_outlined,
        title: 'No escalations',
        message:
            'Nothing has been escalated. Complaints appear here when they pass their deadline or are raised manually.',
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
        itemCount: _items.length,
        separatorBuilder: (_, __) => const SizedBox(height: 12),
        itemBuilder: (context, index) => ComplaintCard(
          complaint: _items[index],
          showSubmitter: true,
          showOfficer: true,
          onTap: () async {
            final changed = await Navigator.of(context).push<bool>(
              MaterialPageRoute(
                builder: (_) =>
                    ComplaintDetailsScreen(complaintId: _items[index].id),
              ),
            );
            if (changed == true && mounted) _load();
          },
        ),
      ),
    );
  }
}
