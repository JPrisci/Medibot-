// Simple singleton used to track session.
import 'dart:async';

import 'package:flutter/material.dart';

class SessionTracker {
  SessionTracker._();

  // Global singleton instance for easy access across widgets.
  static final SessionTracker instance = SessionTracker._();

  final ValueNotifier<int> clickCount = ValueNotifier<int>(0);
  final ValueNotifier<Duration> elapsed = ValueNotifier<Duration>(Duration.zero);
  Timer? _timer;
  bool _running = false;

  // Starts timer.
  void start() {
    if (_running) {
      return;
    }
    _running = true;
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      elapsed.value = elapsed.value + const Duration(seconds: 1);
    });
  }

  void stop() {
    // Stops timer and resets.
    _running = false;
    _timer?.cancel();
    _timer = null;
  }

  void reset() {
    // Goes back to initial values.
    stop();
    clickCount.value = 0;
    elapsed.value = Duration.zero;
  }

  void recordClick([String? source]) {
    // Add 1 to click counter.
    clickCount.value += 1;
  }

  String get elapsedText {
    // Formatting.
    final minutes = elapsed.value.inMinutes.toString().padLeft(2, '0');
    final seconds = (elapsed.value.inSeconds % 60).toString().padLeft(2, '0');
    return '$minutes:$seconds';
  }
}
