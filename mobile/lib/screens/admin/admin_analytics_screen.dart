import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../../core/network/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../models/stats.dart';
import '../../services/admin_service.dart';
import '../../widgets/common.dart';
import '../../widgets/state_views.dart';

/// System analytics: status mix, department load, priority split and the
/// twelve-month registered-vs-resolved trend.
///
/// Charts are sized for a phone: few categories, direct labels, and a legend
/// only where the chart cannot label itself.
class AdminAnalyticsScreen extends StatefulWidget {
  const AdminAnalyticsScreen({super.key});

  @override
  State<AdminAnalyticsScreen> createState() => _AdminAnalyticsScreenState();
}

class _AdminAnalyticsScreenState extends State<AdminAnalyticsScreen> {
  Map<String, dynamic> _summary = {};
  List<ChartPoint> _status = [];
  List<ChartPoint> _departments = [];
  List<ChartPoint> _priority = [];
  List<TrendPoint> _trend = [];

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
      final service = AdminService.instance;
      // Fired together: four independent reads should not queue up.
      final results = await Future.wait([
        service.analyticsSummary(),
        service.analyticsStatus(),
        service.analyticsDepartments(),
        service.analyticsPriority(),
        service.analyticsTrend(),
      ]);

      if (!mounted) return;
      setState(() {
        _summary = results[0] as Map<String, dynamic>;
        _status = results[1] as List<ChartPoint>;
        _departments = results[2] as List<ChartPoint>;
        _priority = results[3] as List<ChartPoint>;
        _trend = results[4] as List<TrendPoint>;
      });
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Could not load analytics.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Analytics')),
      body: _body(),
    );
  }

  Widget _body() {
    if (_loading) return const LoadingView(message: 'Crunching the numbers...');

    if (_error != null) {
      return ErrorView(
        message: _error!,
        isNetwork: _error!.toLowerCase().contains('connection'),
        onRetry: _load,
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        children: [
          _summaryTiles(),
          const SizedBox(height: 24),
          if (_status.isNotEmpty) ...[
            _chartCard('Complaints by status', _statusChart()),
            const SizedBox(height: 16),
          ],
          if (_departments.isNotEmpty) ...[
            _chartCard('Complaints by department', _departmentChart()),
            const SizedBox(height: 16),
          ],
          if (_priority.isNotEmpty) ...[
            _chartCard('Complaints by priority', _priorityChart()),
            const SizedBox(height: 16),
          ],
          if (_trend.isNotEmpty)
            _chartCard('Registered vs resolved', _trendChart(), legend: true),
        ],
      ),
    );
  }

  int _metric(String key) => (_summary[key] as num?)?.toInt() ?? 0;

  Widget _summaryTiles() {
    final total = _metric('total');
    final resolved = _metric('resolved');
    final rate = total == 0 ? 0 : ((resolved / total) * 100).round();

    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 12,
      crossAxisSpacing: 12,
      childAspectRatio: 1.45,
      children: [
        StatTile(
          label: 'Total complaints',
          value: '$total',
          icon: Icons.description_outlined,
          color: AppColors.brand600,
        ),
        StatTile(
          label: 'Resolved',
          value: '$resolved',
          icon: Icons.check_circle_outline,
          color: AppColors.green600,
        ),
        StatTile(
          label: 'Resolution rate',
          value: '$rate%',
          icon: Icons.trending_up_rounded,
          color: AppColors.violet600,
        ),
        StatTile(
          label: 'Filed today',
          value: '${_metric('today')}',
          icon: Icons.today_outlined,
          color: AppColors.amber500,
        ),
      ],
    );
  }

  Widget _chartCard(String title, Widget chart, {bool legend = false}) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: AppColors.slate900,
              ),
            ),
            const SizedBox(height: 18),
            SizedBox(height: 200, child: chart),
            if (legend) ...[
              const SizedBox(height: 14),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _legendDot(AppColors.brand600, 'Registered'),
                  const SizedBox(width: 20),
                  _legendDot(AppColors.green600, 'Resolved'),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _legendDot(Color color, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 6),
        Text(
          label,
          style: const TextStyle(fontSize: 12.5, color: AppColors.slate600),
        ),
      ],
    );
  }

  /// Horizontal bars: status names are too long to sit under vertical bars on
  /// a phone.
  Widget _statusChart() {
    final points = _status.where((p) => p.value > 0).toList();
    if (points.isEmpty) return const Center(child: Text('No data yet'));

    final maxValue =
        points.map((p) => p.value).reduce((a, b) => a > b ? a : b).toDouble();

    return ListView.separated(
      itemCount: points.length,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (context, index) {
        final point = points[index];
        final color = AppColors.forStatus(point.name);
        return Row(
          children: [
            SizedBox(
              width: 92,
              child: Text(
                point.name,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 12.5,
                  color: AppColors.slate600,
                ),
              ),
            ),
            Expanded(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: maxValue == 0 ? 0 : point.value / maxValue,
                  minHeight: 18,
                  backgroundColor: AppColors.slate100,
                  valueColor: AlwaysStoppedAnimation(color),
                ),
              ),
            ),
            SizedBox(
              width: 34,
              child: Text(
                '${point.value}',
                textAlign: TextAlign.right,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: AppColors.slate900,
                ),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _departmentChart() {
    final points = _departments;
    final maxValue = points.isEmpty
        ? 1.0
        : points.map((p) => p.value).reduce((a, b) => a > b ? a : b).toDouble();

    return BarChart(
      BarChartData(
        alignment: BarChartAlignment.spaceAround,
        maxY: (maxValue * 1.2).ceilToDouble(),
        borderData: FlBorderData(show: false),
        gridData: FlGridData(
          show: true,
          drawVerticalLine: false,
          getDrawingHorizontalLine: (_) =>
              const FlLine(color: AppColors.slate100, strokeWidth: 1),
        ),
        titlesData: FlTitlesData(
          topTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          rightTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          leftTitles: const AxisTitles(
            sideTitles: SideTitles(showTitles: true, reservedSize: 30),
          ),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 46,
              getTitlesWidget: (value, meta) {
                final index = value.toInt();
                if (index < 0 || index >= points.length) {
                  return const SizedBox.shrink();
                }
                // Department names are long; the first word identifies each.
                final label = points[index].name.split(' ').first;
                return Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(
                    label,
                    style: const TextStyle(
                      fontSize: 11,
                      color: AppColors.slate500,
                    ),
                  ),
                );
              },
            ),
          ),
        ),
        barGroups: points.asMap().entries.map((entry) {
          return BarChartGroupData(
            x: entry.key,
            barRods: [
              BarChartRodData(
                toY: entry.value.value.toDouble(),
                color: AppColors.forDepartment(entry.value.name),
                width: 24,
                borderRadius: const BorderRadius.vertical(
                  top: Radius.circular(6),
                ),
              ),
            ],
          );
        }).toList(),
      ),
    );
  }

  Widget _priorityChart() {
    final points = _priority.where((p) => p.value > 0).toList();
    if (points.isEmpty) return const Center(child: Text('No data yet'));

    final total = points.fold<int>(0, (sum, p) => sum + p.value);

    return Row(
      children: [
        SizedBox(
          width: 150,
          child: PieChart(
            PieChartData(
              sectionsSpace: 2,
              centerSpaceRadius: 38,
              sections: points.map((point) {
                final share = total == 0 ? 0 : (point.value / total) * 100;
                return PieChartSectionData(
                  value: point.value.toDouble(),
                  color: AppColors.forPriority(point.name),
                  radius: 48,
                  title: share < 8 ? '' : '${share.round()}%',
                  titleStyle: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                );
              }).toList(),
            ),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: points
                .map((point) => Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Row(
                        children: [
                          Container(
                            width: 10,
                            height: 10,
                            decoration: BoxDecoration(
                              color: AppColors.forPriority(point.name),
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              point.name,
                              style: const TextStyle(
                                fontSize: 13,
                                color: AppColors.slate600,
                              ),
                            ),
                          ),
                          Text(
                            '${point.value}',
                            style: const TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                              color: AppColors.slate900,
                            ),
                          ),
                        ],
                      ),
                    ))
                .toList(),
          ),
        ),
      ],
    );
  }

  Widget _trendChart() {
    if (_trend.isEmpty) return const Center(child: Text('No data yet'));

    final maxValue = _trend
        .expand((p) => [p.registered, p.resolved])
        .fold<int>(0, (a, b) => a > b ? a : b)
        .toDouble();

    return LineChart(
      LineChartData(
        minY: 0,
        maxY: maxValue == 0 ? 5 : (maxValue * 1.2).ceilToDouble(),
        borderData: FlBorderData(show: false),
        gridData: FlGridData(
          show: true,
          drawVerticalLine: false,
          getDrawingHorizontalLine: (_) =>
              const FlLine(color: AppColors.slate100, strokeWidth: 1),
        ),
        titlesData: FlTitlesData(
          topTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          rightTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          leftTitles: const AxisTitles(
            sideTitles: SideTitles(showTitles: true, reservedSize: 30),
          ),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 28,
              interval: 2, // twelve month labels will not fit side by side
              getTitlesWidget: (value, meta) {
                final index = value.toInt();
                if (index < 0 || index >= _trend.length) {
                  return const SizedBox.shrink();
                }
                return Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(
                    _trend[index].month,
                    style: const TextStyle(
                      fontSize: 10.5,
                      color: AppColors.slate500,
                    ),
                  ),
                );
              },
            ),
          ),
        ),
        lineBarsData: [
          _line(
            _trend
                .asMap()
                .entries
                .map((e) =>
                    FlSpot(e.key.toDouble(), e.value.registered.toDouble()))
                .toList(),
            AppColors.brand600,
          ),
          _line(
            _trend
                .asMap()
                .entries
                .map((e) =>
                    FlSpot(e.key.toDouble(), e.value.resolved.toDouble()))
                .toList(),
            AppColors.green600,
          ),
        ],
      ),
    );
  }

  LineChartBarData _line(List<FlSpot> spots, Color color) {
    return LineChartBarData(
      spots: spots,
      isCurved: true,
      curveSmoothness: 0.25,
      color: color,
      barWidth: 2.5,
      dotData: const FlDotData(show: false),
      belowBarData: BarAreaData(
        show: true,
        color: color.withValues(alpha: 0.10),
      ),
    );
  }
}
