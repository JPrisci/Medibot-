import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

/// Accumulates session records on-device until an explicit export happens.
class SessionRecordStore {
  static const _key = 'session_records';

  /// Appends one session's metrics to persistent storage.
  static Future<void> addRecord(Map<String, dynamic> record) async {
    final prefs = await SharedPreferences.getInstance();
    final existing = prefs.getStringList(_key) ?? <String>[];
    existing.add(jsonEncode(record));
    await prefs.setStringList(_key, existing);
  }

  /// Returns all stored records, oldest first.
  static Future<List<Map<String, dynamic>>> getAllRecords() async {
    final prefs = await SharedPreferences.getInstance();
    final existing = prefs.getStringList(_key) ?? <String>[];
    return existing
        .map((e) => Map<String, dynamic>.from(jsonDecode(e) as Map))
        .toList();
  }

  /// Call after a successful export if you want to start fresh.
  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key);
  }
}