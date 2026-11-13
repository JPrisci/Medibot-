import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

/// Accumulates session records on-device until an explicit export happens.
class SessionRecordStore {
  static const _key = 'session_records';

  /// Appends metrics.
  static Future<void> addRecord(Map<String, dynamic> record) async {
    final prefs = await SharedPreferences.getInstance();
    final existing = prefs.getStringList(_key) ?? <String>[];
    existing.add(jsonEncode(record));
    await prefs.setStringList(_key, existing);
  }

  /// Updates and adds record.
  static Future<void> updateRecord(
    int sessionId,
    Map<String, dynamic> updates,
  ) async {
    final prefs = await SharedPreferences.getInstance();
    final existing = prefs.getStringList(_key) ?? <String>[];
    for (var index = 0; index < existing.length; index += 1) {
      final record = Map<String, dynamic>.from(jsonDecode(existing[index]) as Map);
      if (record['session_id'] != sessionId) continue;
      record.addAll(updates);
      existing[index] = jsonEncode(record);
      await prefs.setStringList(_key, existing);
      return;
    }
  }

  /// Returns all stored records in order (date)
  static Future<List<Map<String, dynamic>>> getAllRecords() async {
    final prefs = await SharedPreferences.getInstance();
    final existing = prefs.getStringList(_key) ?? <String>[];
    return existing
        .map((e) => Map<String, dynamic>.from(jsonDecode(e) as Map))
        .toList();
  }


  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key);
  }
}
