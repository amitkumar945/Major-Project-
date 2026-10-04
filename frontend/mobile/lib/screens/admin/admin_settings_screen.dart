import 'package:flutter/material.dart';

import '../../core/config/app_config.dart';
import '../../core/network/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../services/admin_service.dart';
import '../../widgets/common.dart';
import '../../widgets/state_views.dart';

/// System configuration, read-only, plus the on-demand SLA sweep.
///
/// The backend also exposes `POST /admin/reset-data`, which deletes every
/// complaint, notification and rating. It is deliberately NOT surfaced here:
/// an irreversible wipe of live data does not belong one tap away on a phone
/// that lives in someone's pocket. It stays available on the web admin.
class AdminSettingsScreen extends StatefulWidget {
  const AdminSettingsScreen({super.key});

  @override
  State<AdminSettingsScreen> createState() => _AdminSettingsScreenState();
}

class _AdminSettingsScreenState extends State<AdminSettingsScreen> {
  Map<String, dynamic> _settings = {};
  bool _loading = true;
  bool _runningSla = false;
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
      final settings = await AdminService.instance.settings();
      if (mounted) setState(() => _settings = settings);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Could not load settings.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _runSlaCheck() async {
    final ok = await confirm(
      context,
      title: 'Run the SLA check?',
      message:
          'Complaints past their deadline will be escalated and the people involved notified.',
      confirmLabel: 'Run check',
    );
    if (!ok) return;

    setState(() => _runningSla = true);
    try {
      final result = await AdminService.instance.runSlaCheck();
      if (!mounted) return;
      final escalated = (result['escalated'] as num?)?.toInt() ?? 0;
      final warned = (result['warned'] as num?)?.toInt() ?? 0;
      showSnack(
        context,
        'SLA check complete: $escalated escalated, $warned warned.',
      );
    } on ApiException catch (e) {
      if (mounted) showSnack(context, e.message, isError: true);
    } finally {
      if (mounted) setState(() => _runningSla = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: _body(),
    );
  }

  Widget _body() {
    if (_loading) return const LoadingView(message: 'Loading settings...');

    if (_error != null) {
      return ErrorView(
        message: _error!,
        isNetwork: _error!.toLowerCase().contains('connection'),
        onRetry: _load,
      );
    }

    final sla = _settings['slaDays'];
    final upload = _settings['upload'];
    final levels = _settings['escalationLevels'];

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        children: [
          Card(
            clipBehavior: Clip.antiAlias,
            child: ListTile(
              leading: Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: AppColors.amber500.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(11),
                ),
                child: _runningSla
                    ? const Padding(
                        padding: EdgeInsets.all(10),
                        child: CircularProgressIndicator(strokeWidth: 2.5),
                      )
                    : const Icon(Icons.rule_rounded,
                        size: 20, color: AppColors.amber500),
              ),
              title: const Text(
                'Run SLA check',
                style: TextStyle(
                  fontSize: 15.5,
                  fontWeight: FontWeight.w600,
                  color: AppColors.slate900,
                ),
              ),
              subtitle: const Text(
                'Escalate overdue complaints and warn on due-soon',
                style: TextStyle(fontSize: 13, color: AppColors.slate500),
              ),
              trailing: const Icon(Icons.chevron_right_rounded,
                  color: AppColors.slate400),
              onTap: _runningSla ? null : _runSlaCheck,
            ),
          ),
          const SizedBox(height: 20),

          if (sla is Map) ...[
            _section('Resolution deadlines', [
              for (final entry in sla.entries)
                _row(
                  entry.key.toString(),
                  '${entry.value} ${entry.value == 1 ? 'day' : 'days'}',
                  color: AppColors.forPriority(entry.key.toString()),
                ),
            ]),
            const SizedBox(height: 16),
          ],

          if (levels is List && levels.isNotEmpty) ...[
            _section('Escalation levels', [
              for (final level in levels.whereType<Map>())
                _row(
                  'Level ${level['level']} - ${level['authority']}',
                  (level['afterDays'] as num?)?.toInt() == 0
                      ? 'Immediately'
                      : 'After ${level['afterDays']} days',
                ),
            ]),
            const SizedBox(height: 16),
          ],

          if (upload is Map) ...[
            _section('File uploads', [
              _row('Maximum file size', '${upload['maxFileSizeMB']} MB'),
              _row('Files per complaint', '${upload['maxFiles']}'),
            ]),
            const SizedBox(height: 16),
          ],

          _section('This app', [
            _row('Backend', AppConfig.apiBaseUrl),
            _row('App version', '1.0.0'),
          ]),

          const SizedBox(height: 20),
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppColors.slate100,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.info_outline_rounded,
                    size: 18, color: AppColors.slate500),
                SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Destructive operations such as resetting all complaint data are available only on the web admin panel.',
                    style: TextStyle(
                      fontSize: 13,
                      color: AppColors.slate600,
                      height: 1.45,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _section(String title, List<Widget> rows) {
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
            const SizedBox(height: 14),
            ...rows,
          ],
        ),
      ),
    );
  }

  Widget _row(String label, String value, {Color? color}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (color != null) ...[
            Container(
              width: 8,
              height: 8,
              margin: const EdgeInsets.only(top: 6, right: 8),
              decoration: BoxDecoration(color: color, shape: BoxShape.circle),
            ),
          ],
          Expanded(
            child: Text(
              label,
              style: const TextStyle(fontSize: 14, color: AppColors.slate600),
            ),
          ),
          const SizedBox(width: 12),
          Text(
            value,
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: AppColors.slate900,
            ),
          ),
        ],
      ),
    );
  }
}
