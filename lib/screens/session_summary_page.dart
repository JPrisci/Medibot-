import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../session_tracker.dart';
import 'admin_page.dart';
import 'loading_page.dart';
import 'session_id.dart';
import 'session_record_store.dart';

class SessionSummaryPage extends StatefulWidget {
  const SessionSummaryPage({super.key});

  @override
  State<SessionSummaryPage> createState() => _SessionSummaryPageState();
}

class _SessionSummaryPageState extends State<SessionSummaryPage> {
  static const _routeApiUrl = String.fromEnvironment(
    'ROUTE_API_URL',
    defaultValue: 'http://localhost:8000/route-requests',
  );

  bool _exporting = false;
  bool _taskComplete = false;
  bool _showBusyMessage = false;
  bool _resetting = false;
  String? _exportError;
  String? _resetError;
  Timer? _taskStateTimer;
  Timer? _busyMessageTimer;
  late final Future<void> _recordSessionFuture;
  int? _sessionId;
  int _sessionClickCount = 0;
  String _sessionElapsedText = '00:00';

  Uri get _uxStateUrl => Uri.parse(
    _routeApiUrl,
  ).replace(path: '/ux-state/latest', query: null);

  Uri get _taskResetUrl => Uri.parse(
    _routeApiUrl,
  ).replace(path: '/task-reset', query: null);

  @override
  void initState() {
    super.initState();
    final tracker = SessionTracker.instance;
    _sessionClickCount = tracker.clickCount.value;
    _sessionElapsedText = tracker.elapsedText;
    _recordSessionFuture = _recordSession();
    _checkTaskState();
    _taskStateTimer = Timer.periodic(
      const Duration(seconds: 2),
      (_) => _checkTaskState(),
    );
    _busyMessageTimer = Timer(const Duration(seconds: 10), () {
      if (mounted && !_taskComplete) {
        setState(() => _showBusyMessage = true);
      }
    });
  }

  @override
  void dispose() {
    _taskStateTimer?.cancel();
    _busyMessageTimer?.cancel();
    super.dispose();
  }

  Future<void> _checkTaskState() async {
    if (_taskComplete) return;

    try {
      final response = await http
          .get(_uxStateUrl)
          .timeout(const Duration(seconds: 10));
      if (response.statusCode != 200) return;

      final state = jsonDecode(response.body);
      if (state is! Map<String, dynamic>) return;

      final taskFinished = state['state'] == 'task_complete' ||
          state['current_stage'] == 'task_complete';
      if (!taskFinished || !mounted) return;

      _taskStateTimer?.cancel();
      _busyMessageTimer?.cancel();
      SessionTracker.instance.stop();
      _sessionClickCount = SessionTracker.instance.clickCount.value;
      _sessionElapsedText = SessionTracker.instance.elapsedText;
      setState(() => _taskComplete = true);
      unawaited(_completeSessionRecord());
    } on http.ClientException {
      // Keep the button disabled until the Coordinator is available again.
    } on TimeoutException {
      // Keep the button disabled until the Coordinator is available again.
    } on FormatException {
      // Ignore an invalid response and try again on the next poll.
    }
  }

  Future<void> _recordSession() async {
    if (_exporting) return;

    setState(() => _exporting = true);
    try {
      final sessionId = await SessionIdProvider.nextId();
      _sessionId = sessionId;
      await SessionRecordStore.addRecord({
        'session_id': sessionId,
        'click_count': _sessionClickCount,
        'elapsed_time': _sessionElapsedText,
        'booking_time_seconds': SessionTracker.instance.bookingTimeSeconds,
        'booking_retries': SessionTracker.instance.bookingRetries,
        'cancel_count': SessionTracker.instance.routeCancellations,
        'route_selected': 'Fashion',
        'completion_status': 'in_progress',
      });
    } catch (error) {
      _exportError = error.toString();
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  Future<void> _completeSessionRecord() async {
    await _recordSessionFuture;
    final sessionId = _sessionId;
    if (sessionId == null) return;

    try {
      await SessionRecordStore.updateRecord(sessionId, {
        'click_count': _sessionClickCount,
        'elapsed_time': _sessionElapsedText,
        'booking_time_seconds': SessionTracker.instance.bookingTimeSeconds,
        'booking_retries': SessionTracker.instance.bookingRetries,
        'cancel_count': SessionTracker.instance.routeCancellations,
        'route_selected': 'Fashion',
        'completion_status': 'completed',
      });
    } catch (error) {
      if (mounted) setState(() => _exportError = error.toString());
    }
  }

  Future<void> _startAgain() async {
    if (!_taskComplete || _resetting) return;

    setState(() {
      _resetting = true;
      _resetError = null;
    });

    try {
      final response = await http
          .post(_taskResetUrl)
          .timeout(const Duration(seconds: 10));
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw _TaskResetException('API returned HTTP ${response.statusCode}');
      }

      SessionTracker.instance.reset();
      if (!mounted) return;
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => const LoadingPage()),
        (route) => false,
      );
    } on http.ClientException {
      _showResetError('Could not connect to the Coordinator. Please try again.');
    } on TimeoutException {
      _showResetError('The reset request timed out. Please try again.');
    } on _TaskResetException catch (error) {
      _showResetError('Could not reset task: ${error.message}');
    }
  }

  void _showResetError(String message) {
    if (!mounted) return;
    setState(() {
      _resetting = false;
      _resetError = message;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF1FAF9),
      appBar: AppBar(
        title: const Text('Session Summary'),
        automaticallyImplyLeading: false,
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Center(
            child: Card(
              elevation: 4,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(24),
              ),
              child: Padding(
                padding: const EdgeInsets.all(28),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      _taskComplete
                          ? Icons.emoji_events_rounded
                          : Icons.smart_toy_rounded,
                      size: 72,
                      color: const Color(0xFF1565C0),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      _taskComplete
                          ? 'You have arrived at the Fashion department'
                          : _showBusyMessage
                              ? 'NaviBot is currently in use'
                              : 'NaviBot is on its way',
                      style: const TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF0D47A1),
                      ),
                    ),
                    const SizedBox(height: 16),
                    if (_taskComplete) ...[
                      Text(
                        'Total clicks: $_sessionClickCount',
                        style: const TextStyle(fontSize: 20),
                      ),
                      const SizedBox(height: 10),
                      Text(
                        'Time taken: $_sessionElapsedText',
                        style: const TextStyle(fontSize: 20),
                      ),
                    ] else
                      Text(
                        _showBusyMessage
                            ? 'NaviBot is currently guiding a visitor. Please wait for the next available NaviBot.'
                            : 'Please wait for NaviBot. When it arrives, follow it to the Fashion department.',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontSize: 16),
                      ),
                    const SizedBox(height: 12),
                    if (_taskComplete && _exporting)
                      const Text(
                        'Saving CSV...',
                        style: TextStyle(fontSize: 14, color: Colors.grey),
                      )
                    else if (_taskComplete && _exportError != null)
                      Text(
                        'CSV export failed: $_exportError',
                        style: const TextStyle(fontSize: 13, color: Colors.red),
                      )
                    else if (_taskComplete)
                      const Text(
                        'CSV saved',
                        style: TextStyle(fontSize: 14, color: Colors.green),
                      ),
                    const SizedBox(height: 24),
                    FilledButton.icon(
                      onPressed: _taskComplete && !_resetting ? _startAgain : null,
                      icon: const Icon(Icons.restart_alt_rounded),
                      label: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        child: Text(_resetting ? 'Resetting...' : 'Start Again'),
                      ),
                      style: FilledButton.styleFrom(
                        backgroundColor: const Color(0xFF1565C0),
                        disabledBackgroundColor: Colors.grey.shade400,
                        minimumSize: const Size(220, 52),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                      ),
                    ),
                    if (_resetError != null) ...[
                      const SizedBox(height: 12),
                      Text(
                        _resetError!,
                        textAlign: TextAlign.center,
                        style: const TextStyle(fontSize: 13, color: Colors.red),
                      ),
                    ],
                    const SizedBox(height: 12),
                    TextButton.icon(
                      onPressed: () {
                        Navigator.of(context).push(
                          MaterialPageRoute(builder: (_) => const AdminPage()),
                        );
                      },
                      icon: const Icon(Icons.admin_panel_settings_outlined),
                      label: const Text('Admin'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _TaskResetException implements Exception {
  const _TaskResetException(this.message);

  final String message;
}
