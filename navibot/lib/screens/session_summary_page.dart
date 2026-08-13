import 'package:flutter/material.dart';

import '../session_tracker.dart';
import 'csv.dart';
import 'loading_page.dart';
import 'session_id.dart';
import 'session_record_store.dart';
import 'admin_page.dart';

class SessionSummaryPage extends StatefulWidget {
  const SessionSummaryPage({super.key});

  @override
  State<SessionSummaryPage> createState() => _SessionSummaryPageState();
}

class _SessionSummaryPageState extends State<SessionSummaryPage> {
  bool _exporting = false;
  String? _exportError;

  @override
  void initState() {
    super.initState();
    // Session just ended -> export as soon as this screen mounts.
    WidgetsBinding.instance.addPostFrameCallback((_) => _recordSession());
  }

  Future<void> _recordSession() async {
  setState(() => _exporting = true);
  try {
    final tracker = SessionTracker.instance;
    final sessionId = await SessionIdProvider.nextId();

    await SessionRecordStore.addRecord({
      'session_id': sessionId,
      'click_count': tracker.clickCount.value,
      'elapsed_time': tracker.elapsedText,
    });
  } catch (e) {
    _exportError = e.toString();
  } finally {
    if (mounted) setState(() => _exporting = false);
  }
}

  @override
  Widget build(BuildContext context) {
    final clickCount = SessionTracker.instance.clickCount.value;
    final elapsedText = SessionTracker.instance.elapsedText;

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
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
              child: Padding(
                padding: const EdgeInsets.all(28),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.emoji_events_rounded, size: 72, color: Color(0xFF1565C0)),
                    const SizedBox(height: 16),
                    const Text(
                      'Session Complete',
                      style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: Color(0xFF0D47A1)),
                    ),
                    const SizedBox(height: 16),
                    Text('Total clicks: $clickCount', style: const TextStyle(fontSize: 20)),
                    const SizedBox(height: 10),
                    Text('Time taken: $elapsedText', style: const TextStyle(fontSize: 20)),
                    const SizedBox(height: 12),
                    if (_exporting)
                      const Text('Saving CSV…', style: TextStyle(fontSize: 14, color: Colors.grey))
                    else if (_exportError != null)
                      Text('CSV export failed: $_exportError',
                          style: const TextStyle(fontSize: 13, color: Colors.red))
                    else
                      const Text('CSV saved ✓', style: TextStyle(fontSize: 14, color: Colors.green)),
                    const SizedBox(height: 24),
                    FilledButton.icon(
                      onPressed: () {
                        SessionTracker.instance.reset();
                        Navigator.of(context).pushAndRemoveUntil(
                          MaterialPageRoute(builder: (_) => const LoadingPage()),
                          (route) => false,
                        );
                      },
                      icon: const Icon(Icons.restart_alt_rounded),
                      label: const Padding(
                        padding: EdgeInsets.symmetric(vertical: 12),
                        child: Text('Start Again'),
                      ),
                      style: FilledButton.styleFrom(
                        backgroundColor: const Color(0xFF1565C0),
                        minimumSize: const Size(220, 52),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      ),
                    ),
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

