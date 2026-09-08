import 'package:flutter/foundation.dart';

import '../core/network/api_exception.dart';
import '../models/complaint.dart';
import '../models/stats.dart';
import '../services/complaint_service.dart';

/// Which list a screen is showing. The scope decides the endpoint, which is
/// what keeps a student from ever requesting the full complaint table.
enum ComplaintScope { mine, assigned, all }

/// Paged complaint list plus dashboard counters, shared by all three roles.
///
/// One provider instance per screen (created with ChangeNotifierProvider), so
/// the student list and the admin list never share state.
class ComplaintProvider extends ChangeNotifier {
  ComplaintProvider(this.scope);

  final ComplaintScope scope;
  final ComplaintService _service = ComplaintService.instance;

  final List<Complaint> _items = [];
  ComplaintStats _stats = const ComplaintStats();

  bool _loading = false;
  bool _loadingMore = false;
  String? _error;
  int _page = 1;
  int _totalPages = 0;
  int _total = 0;

  Map<String, dynamic> _filters = {};

  List<Complaint> get items => List.unmodifiable(_items);
  ComplaintStats get stats => _stats;
  bool get isLoading => _loading;
  bool get isLoadingMore => _loadingMore;
  String? get error => _error;
  bool get isEmpty => !_loading && _error == null && _items.isEmpty;
  bool get hasMore => _page < _totalPages;
  int get total => _total;
  Map<String, dynamic> get filters => Map.unmodifiable(_filters);

  /// True when any filter beyond the defaults is active, so the UI can offer
  /// a "clear filters" action on an empty result.
  bool get hasActiveFilters =>
      _filters.values.any((v) => v != null && '$v'.isNotEmpty);

  Future<void> load({bool refresh = false}) async {
    if (refresh) _page = 1;
    _loading = true;
    _error = null;
    notifyListeners();

    try {
      final result = await _fetch(_page);
      _items
        ..clear()
        ..addAll(result.items);
      _totalPages = result.totalPages;
      _total = result.total;
    } on ApiException catch (e) {
      _error = e.message;
    } catch (_) {
      _error = 'Something went wrong while loading complaints.';
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  /// Append the next page for infinite scroll.
  Future<void> loadMore() async {
    if (_loadingMore || _loading || !hasMore) return;
    _loadingMore = true;
    notifyListeners();

    try {
      final result = await _fetch(_page + 1);
      _page += 1;
      _items.addAll(result.items);
      _totalPages = result.totalPages;
      _total = result.total;
    } on ApiException catch (e) {
      _error = e.message; // the already-loaded pages stay on screen
    } finally {
      _loadingMore = false;
      notifyListeners();
    }
  }

  Future<Paginated<Complaint>> _fetch(int page) {
    switch (scope) {
      case ComplaintScope.mine:
        return _service.myComplaints(page: page, filters: _filters);
      case ComplaintScope.assigned:
        return _service.assignedComplaints(page: page, filters: _filters);
      case ComplaintScope.all:
        return _service.allComplaints(page: page, filters: _filters);
    }
  }

  Future<void> applyFilters(Map<String, dynamic> filters) async {
    _filters = {...filters}..removeWhere((_, v) => v == null || '$v'.isEmpty);
    await load(refresh: true);
  }

  Future<void> clearFilters() async {
    _filters = {};
    await load(refresh: true);
  }

  Future<void> loadStats({String? department}) async {
    try {
      _stats = await _service.statistics(department: department);
      notifyListeners();
    } catch (_) {
      // Counters are decoration on a list that still works without them.
    }
  }

  /// Refresh both the list and the counters, for pull-to-refresh.
  Future<void> refreshAll({String? department}) async {
    await Future.wait([
      load(refresh: true),
      loadStats(department: department),
    ]);
  }

  /// Swap in an updated complaint after a status change or remark, so the list
  /// reflects the change without a full reload.
  void replace(Complaint updated) {
    final index = _items.indexWhere((c) => c.id == updated.id);
    if (index == -1) return;
    _items[index] = updated;
    notifyListeners();
  }

  /// Drop a complaint that no longer belongs in this list.
  void remove(String complaintId) {
    _items.removeWhere((c) => c.id == complaintId);
    notifyListeners();
  }
}
