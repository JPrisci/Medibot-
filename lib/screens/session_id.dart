import 'package:shared_preferences/shared_preferences.dart';

/// Persists an incrementing session ID across app restarts.
class SessionIdProvider {
  static const _key = 'session_id_counter';

  /// Increments and returns the next session id (starts at 1).
  static Future<int> nextId() async {
    final prefs = await SharedPreferences.getInstance();
    final current = prefs.getInt(_key) ?? 0;
    final next = current + 1;
    await prefs.setInt(_key, next);
    return next;
  }

  static Future<void> reset() async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.remove(_key);
}
}