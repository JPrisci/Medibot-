import 'package:flutter/material.dart';

import 'csv.dart';
import 'session_record_store.dart';
import 'session_id.dart';

class AdminPage extends StatefulWidget {
  const AdminPage({super.key});

  @override
  State<AdminPage> createState() => _AdminPageState();
}

class _AdminPageState extends State<AdminPage> {
  static const _adminPassword = '6767';

  final _passwordController = TextEditingController();
  bool _unlocked = false;
  String? _passwordError;
  bool _exporting = false;
  String? _statusMessage;

  @override
  void dispose() {
    _passwordController.dispose();
    super.dispose();
  }

  void _checkPassword() {
    if (_passwordController.text == _adminPassword) {
      setState(() {
        _unlocked = true;
        _passwordError = null;
      });
    } else {
      setState(() => _passwordError = 'Incorrect password');
    }
  }

  Future<void> _exportAllSessions() async {
    setState(() {
      _exporting = true;
      _statusMessage = null;
    });
    try {
      final records = await SessionRecordStore.getAllRecords();
      if (records.isEmpty) {
        setState(() => _statusMessage = 'No sessions recorded yet.');
        return;
      }
      await Csv.exportRecords(
        records: records,
        fileName: 'all_sessions_${DateTime.now().millisecondsSinceEpoch}',
      );
      setState(() => _statusMessage = 'Exported ${records.length} session(s).');
    } catch (e) {
      setState(() => _statusMessage = 'Export failed: $e');
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF1FAF9),
      appBar: AppBar(title: const Text('Admin')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Center(
            child: _unlocked ? _buildAdminPanel() : _buildPasswordGate(),
          ),
        ),
      ),
    );
  }

  Widget _buildPasswordGate() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.lock_outline_rounded, size: 56, color: Color(0xFF1565C0)),
        const SizedBox(height: 16),
        const Text('Enter admin password', style: TextStyle(fontSize: 18)),
        const SizedBox(height: 16),
        SizedBox(
          width: 220,
          child: TextField(
            controller: _passwordController,
            obscureText: true,
            keyboardType: TextInputType.number,
            textAlign: TextAlign.center,
            onSubmitted: (_) => _checkPassword(),
            decoration: InputDecoration(
              border: const OutlineInputBorder(),
              errorText: _passwordError,
            ),
          ),
        ),
        const SizedBox(height: 16),
        FilledButton(
          onPressed: _checkPassword,
          child: const Text('Unlock'),
        ),
      ],
    );
  }

  Future<void> _resetAllData() async {
    // Confirm first — this is destructive and can't be undone.
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reset all data?'),
        content: const Text(
          'This will permanently delete all recorded sessions and reset the data, continue?'
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Reset'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    setState(() {
      _exporting = true;
      _statusMessage = null;
    });
    try {
      await SessionRecordStore.clear();
      await SessionIdProvider.reset();
      setState(() => _statusMessage = 'All data reset. Next session will be #1.');
    } catch (e) {
      setState(() => _statusMessage = 'Reset failed: $e');
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }


  Widget _buildAdminPanel() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.admin_panel_settings_rounded, size: 56, color: Color(0xFF1565C0)),
        const SizedBox(height: 16),
        const Text('Session Data Export', style: TextStyle(fontSize: 18)),
        const SizedBox(height: 20),
        FilledButton.icon(
          onPressed: _exporting ? null : _exportAllSessions,
          icon: const Icon(Icons.download_rounded),
          label: Text(_exporting ? 'Exporting…' : 'Export All Sessions (CSV)'),
        ),
        if (_statusMessage != null) ...[
          const SizedBox(height: 16),
          Text(_statusMessage!, textAlign: TextAlign.center),
        ],
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: _exporting ? null : _resetAllData,
          icon: const Icon(Icons.delete_forever_rounded, color: Colors.red),
          label: const Text('Reset All Data', style: TextStyle(color: Colors.red)),
          style: OutlinedButton.styleFrom(
            side: const BorderSide(color: Colors.red),
          ),
        ),
      ],
    );
  }
}