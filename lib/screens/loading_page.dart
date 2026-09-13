// Loading and intro screens shown before the main layout.
// Simplified: the initial loading animation was removed per request.
import 'package:flutter/material.dart';

import '../session_tracker.dart';
import 'main_layout_page.dart';

class LoadingPage extends StatefulWidget {
  const LoadingPage({super.key});

  @override
  State<LoadingPage> createState() => _LoadingPageState();
}

class _LoadingPageState extends State<LoadingPage> {
  // 1 = intro, 2 = main app
  int _screenStage = 1;
  final _nameController = TextEditingController();

  @override
  void initState() {
    super.initState();
    // Reset session state.
    SessionTracker.instance.reset();
  }

  void _startSession() {
    final name = _nameController.text.trim();
    if (name.isEmpty) return;

    // Starts session timer on start, moves to app.
    SessionTracker.instance.userId = name;
    SessionTracker.instance.recordClick('Start');
    SessionTracker.instance.start();
    setState(() {
      _screenStage = 2;
    });
  }

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final Widget currentPage = _screenStage == 2
        ? const MainLayoutPage(key: ValueKey('main'))
        : _buildIntroScreen(key: const ValueKey('manual'));

    return Scaffold(
      backgroundColor: const Color(0xFFF1FAF9),
      body: Column(
        children: [
          Expanded(child: currentPage),
        ],
      ),
    );
  }

  Widget _buildIntroScreen({Key? key}) {
    // Intro screen, has robot icon and start button with text.
    return Center(
      key: key,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.smart_toy,
              size: 88,
              color: Color(0xFF1565C0),
            ),
            const SizedBox(height: 24),
            Text(
              'NaviBot',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w700,
                    color: const Color(0xFF0D47A1),
                  ),
            ),
            const SizedBox(height: 12),
            const Text(
              'Scenario: you need to get to the Fashion department.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 16, color: Colors.black87),
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: 280,
              child: TextField(
                controller: _nameController,
                textCapitalization: TextCapitalization.words,
                textInputAction: TextInputAction.done,
                onChanged: (_) => setState(() {}),
                onSubmitted: (_) => _startSession(),
                decoration: const InputDecoration(
                  labelText: 'Your name',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.person_outline_rounded),
                ),
              ),
            ),
            const SizedBox(height: 28),
            FilledButton.icon(
              onPressed: _nameController.text.trim().isEmpty ? null : _startSession,
              icon: const Icon(Icons.play_arrow_rounded),
              label: const Padding(
                padding: EdgeInsets.symmetric(vertical: 12, horizontal: 8),
                child: Text('Start'),
              ),
              style: FilledButton.styleFrom(
                backgroundColor: const Color(0xFF1565C0),
                minimumSize: const Size(180, 56),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
