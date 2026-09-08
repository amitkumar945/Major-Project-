import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/config/constants.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/complaint_provider.dart';
import '../../widgets/common.dart';
import '../../widgets/complaint_card.dart';
import '../../widgets/state_views.dart';
import 'complaint_details_screen.dart';

/// The complaint list, reused by all three roles.
///
/// The scope decides the endpoint and therefore what the list contains, so the
/// same widget serves "my complaints", "my queue" and "all complaints" without
/// a role check of its own.
class ComplaintListScreen extends StatefulWidget {
  const ComplaintListScreen({
    super.key,
    required this.scope,
    this.title = 'Complaints',
    this.showAppBar = true,
    this.emptyTitle,
    this.emptyMessage,
    this.onEmptyAction,
    this.emptyActionLabel,
  });

  final ComplaintScope scope;
  final String title;
  final bool showAppBar;
  final String? emptyTitle;
  final String? emptyMessage;
  final VoidCallback? onEmptyAction;
  final String? emptyActionLabel;

  @override
  State<ComplaintListScreen> createState() => _ComplaintListScreenState();
}

class _ComplaintListScreenState extends State<ComplaintListScreen> {
  final _scroll = ScrollController();
  final _search = TextEditingController();

  String? _status;
  String? _priority;
  String? _department;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ComplaintProvider>().load();
    });
  }

  @override
  void dispose() {
    _scroll.removeListener(_onScroll);
    _scroll.dispose();
    _search.dispose();
    super.dispose();
  }

  /// Load the next page slightly before the user reaches the bottom, so the
  /// scroll does not visibly stall.
  void _onScroll() {
    if (_scroll.position.pixels >=
        _scroll.position.maxScrollExtent - 400) {
      context.read<ComplaintProvider>().loadMore();
    }
  }

  Future<void> _applyFilters() async {
    await context.read<ComplaintProvider>().applyFilters({
      'search': _search.text.trim(),
      'status': _status ?? '',
      'priority': _priority ?? '',
      'department': _department ?? '',
    });
  }

  void _openFilterSheet() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (context, setSheetState) => Padding(
          padding: EdgeInsets.fromLTRB(
            16,
            8,
            16,
            16 + MediaQuery.of(context).viewInsets.bottom,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Filter complaints',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 20),

              AppDropdown<String>(
                label: 'Status',
                value: _status,
                hint: 'Any status',
                items: Domain.statusList,
                onChanged: (value) => setSheetState(() => _status = value),
              ),
              const SizedBox(height: 16),

              AppDropdown<String>(
                label: 'Priority',
                value: _priority,
                hint: 'Any priority',
                items: Domain.priorityList,
                onChanged: (value) => setSheetState(() => _priority = value),
              ),

              // A student's complaints span departments; an officer's do not,
              // so the filter is only useful on the wider lists.
              if (widget.scope != ComplaintScope.assigned) ...[
                const SizedBox(height: 16),
                AppDropdown<String>(
                  label: 'Department',
                  value: _department,
                  hint: 'Any department',
                  items: Domain.departmentNames,
                  onChanged: (value) =>
                      setSheetState(() => _department = value),
                ),
              ],

              const SizedBox(height: 24),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () {
                        setSheetState(() {
                          _status = null;
                          _priority = null;
                          _department = null;
                        });
                        setState(() {});
                        Navigator.of(sheetContext).pop();
                        context.read<ComplaintProvider>().clearFilters();
                      },
                      child: const Text('Clear'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton(
                      onPressed: () {
                        setState(() {});
                        Navigator.of(sheetContext).pop();
                        _applyFilters();
                      },
                      child: const Text('Apply'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  int get _activeFilterCount =>
      [_status, _priority, _department].where((f) => f != null).length;

  Future<void> _openDetails(String complaintId) async {
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => ComplaintDetailsScreen(complaintId: complaintId),
      ),
    );
    if (changed == true && mounted) {
      context.read<ComplaintProvider>().load(refresh: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<ComplaintProvider>();

    return Scaffold(
      appBar: widget.showAppBar
          ? AppBar(title: Text(widget.title))
          : null,
      body: Column(
        children: [
          _searchBar(),
          Expanded(child: _body(provider)),
        ],
      ),
    );
  }

  Widget _searchBar() {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _search,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _applyFilters(),
              style: const TextStyle(fontSize: 15),
              decoration: InputDecoration(
                hintText: 'Search complaints',
                prefixIcon: const Icon(Icons.search_rounded,
                    size: 20, color: AppColors.slate400),
                contentPadding: const EdgeInsets.symmetric(
                    horizontal: 12, vertical: 12),
                suffixIcon: _search.text.isEmpty
                    ? null
                    : IconButton(
                        icon: const Icon(Icons.close_rounded, size: 18),
                        onPressed: () {
                          _search.clear();
                          _applyFilters();
                        },
                      ),
              ),
            ),
          ),
          const SizedBox(width: 10),
          Badge(
            isLabelVisible: _activeFilterCount > 0,
            label: Text('$_activeFilterCount'),
            child: SizedBox(
              width: 48,
              height: 48,
              child: OutlinedButton(
                onPressed: _openFilterSheet,
                style: OutlinedButton.styleFrom(
                  padding: EdgeInsets.zero,
                  minimumSize: const Size(48, 48),
                ),
                child: const Icon(Icons.tune_rounded, size: 20),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _body(ComplaintProvider provider) {
    if (provider.isLoading && provider.items.isEmpty) {
      return const LoadingView(message: 'Loading complaints...');
    }

    if (provider.error != null && provider.items.isEmpty) {
      return ErrorView(
        message: provider.error!,
        isNetwork: provider.error!.toLowerCase().contains('connection'),
        onRetry: () => provider.load(refresh: true),
      );
    }

    if (provider.isEmpty) {
      // An empty result caused by a filter needs a different way out than a
      // genuinely empty list.
      if (provider.hasActiveFilters) {
        return EmptyView(
          icon: Icons.filter_alt_off_outlined,
          title: 'No matching complaints',
          message: 'Try removing some filters to see more.',
          actionLabel: 'Clear filters',
          onAction: () {
            setState(() {
              _status = null;
              _priority = null;
              _department = null;
              _search.clear();
            });
            provider.clearFilters();
          },
        );
      }
      return EmptyView(
        icon: Icons.inbox_outlined,
        title: widget.emptyTitle ?? 'No complaints yet',
        message: widget.emptyMessage,
        actionLabel: widget.emptyActionLabel,
        onAction: widget.onEmptyAction,
      );
    }

    return RefreshIndicator(
      onRefresh: () => provider.load(refresh: true),
      child: ListView.separated(
        controller: _scroll,
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
        itemCount: provider.items.length + (provider.hasMore ? 1 : 0),
        separatorBuilder: (_, __) => const SizedBox(height: 12),
        itemBuilder: (context, index) {
          if (index >= provider.items.length) {
            return const Padding(
              padding: EdgeInsets.symmetric(vertical: 20),
              child: Center(
                child: SizedBox(
                  width: 24,
                  height: 24,
                  child: CircularProgressIndicator(strokeWidth: 2.5),
                ),
              ),
            );
          }

          final complaint = provider.items[index];
          return ComplaintCard(
            complaint: complaint,
            showSubmitter: widget.scope != ComplaintScope.mine,
            showOfficer: widget.scope != ComplaintScope.assigned,
            onTap: () => _openDetails(complaint.id),
          );
        },
      ),
    );
  }
}
