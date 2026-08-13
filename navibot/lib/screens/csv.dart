import 'dart:convert';
import 'dart:typed_data';

import 'package:file_saver/file_saver.dart';

class Csv {
  /// Builds a CSV from multiple session records and saves it to the device.
  static Future<void> exportRecords({
    required List<Map<String, dynamic>> records,
    String fileName = 'session_summary',
  }) async {
    if (records.isEmpty) return;

    final headers = records.first.keys.toList();
    final buffer = StringBuffer();
    buffer.writeln(headers.map(_escape).join(','));
    for (final record in records) {
      buffer.writeln(headers.map((h) => _escape(record[h])).join(','));
    }

    final bytes = Uint8List.fromList(utf8.encode(buffer.toString()));

    await FileSaver.instance.saveAs(
      name: fileName,
      bytes: bytes,
      ext: 'csv',
      mimeType: MimeType.csv,
    );
  }

  static String _escape(dynamic value) {
    final str = value.toString();
    if (str.contains(',') || str.contains('"') || str.contains('\n')) {
      return '"${str.replaceAll('"', '""')}"';
    }
    return str;
  }
}