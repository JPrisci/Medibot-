// Summary shown at the end of a session with basic metrics.
import 'package:flutter/material.dart';

import '../session_tracker.dart';
import 'loading_page.dart';

class SessionSummaryPage extends StatelessWidget {
  const SessionSummaryPage({super.key});

  @override
  Widget build(BuildContext context) {
    // Gets metrics.
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
                    Text(
                      'Total clicks: $clickCount',
                      style: const TextStyle(fontSize: 20),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      'Time taken: $elapsedText',
                      style: const TextStyle(fontSize: 20),
                    ),
                    const SizedBox(height: 24),
                    FilledButton.icon(
                      onPressed: () {
                        // Reset button to navigate back to screen.
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
