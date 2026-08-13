import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../session_tracker.dart';
import 'session_summary_page.dart';

/// Displays the floor plans used in the user-testing prototype.
class SearchByMapPage extends StatefulWidget {
  const SearchByMapPage({super.key, this.selectedWard});

  // Kept while the department-search flow remains in the prototype.
  final String? selectedWard;

  @override
  State<SearchByMapPage> createState() => _SearchByMapPageState();
}

class _SearchByMapPageState extends State<SearchByMapPage> {
  static const _primaryBlue = Color(0xFF1565C0);
  static const _floorPlans = ['G-G', 'G-1', 'G-2', 'G-3'];
  static const _retiredFloors = {'G-G', 'G-3'};
  static const _floorStatus = {
    'G-1': {'total': 3, 'available': 1, 'inUse': 2},
    'G-2': {'total': 3, 'available': 2, 'inUse': 1},
  };
  String _selectedFloor = 'G-1';
  bool _showRoute = false;

  @override
  void initState() {
    super.initState();
    // The enabled department option starts the same predefined route.
    _showRoute = widget.selectedWard != null;
  }

  void _selectFloor(String floor) {
    if (_retiredFloors.contains(floor)) return;

    SessionTracker.instance.recordClick('Floor change: $floor');
    setState(() {
      _selectedFloor = floor;
    });
  }

  void _cancelRoute() {
    SessionTracker.instance.recordClick('Cancel route');
    setState(() => _showRoute = false);
  }

  void _toggleDestinationRoute() {
    if (_showRoute) {
      _cancelRoute();
    } else {
      SessionTracker.instance.recordClick('Room 2.31 route');
      setState(() => _showRoute = true);
    }
  }

  Future<void> _confirmBooking() async {
    if (!_showRoute) return;
    final name = SessionTracker.instance.participantName ?? 'Guest';

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Confirm booking'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Booking for $name',
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 16),
            const Text('Route', style: TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            const Text('Start: Room 1.05, G-1'),
            const SizedBox(height: 4),
            const Text('Destination: Room 2.31, G-2'),
            const SizedBox(height: 16),
            const Text('Call NaviBot?'),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Confirm'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    SessionTracker.instance.recordClick('Booking confirmed');

    final started = await _startRobotRoute();

    if (!mounted) return;

    if (!started) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'NaviBot could not start the robot route. Please try again.',
          ),
        ),
      );
      return;
    }

    SessionTracker.instance.recordClick('Robot route started');
    _finishSession();
  }

  Future<bool> _startRobotRoute() async {
    try {
      final response = await http
          .post(
            Uri.parse('http://127.0.0.1:8082/route/start'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'destination': 'ELEVATOR_2'}),
          )
          .timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        return true;
      }

      debugPrint(
        'Route API rejected request: '
        '${response.statusCode} ${response.body}',
      );

      return false;
    } catch (error) {
      debugPrint('Route API error: $error');
      return false;
    }
  }

  void _finishSession() {
    SessionTracker.instance.recordClick('Session complete');
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const SessionSummaryPage()),
    );
  }

  String get _mapAsset => 'assets/images/$_selectedFloor.png';

  double get _mapAspectRatio => _selectedFloor == 'G-2' ? 646 / 753 : 633 / 733;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        title: const Text(
          'Search by Map',
          style: TextStyle(color: Colors.white),
        ),
        backgroundColor: _primaryBlue,
        leading: IconButton(
          color: Colors.white,
          icon: const Icon(Icons.arrow_back),
          onPressed: () {
            SessionTracker.instance.recordClick('Back');
            Navigator.of(context).pop();
          },
        ),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Expanded(
                flex: 4,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Hospital Map',
                      style: TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF0D47A1),
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Select a floor or tap the destination marker to toggle its route.',
                    ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 8,
                      children: _floorPlans.map(_buildFloorChip).toList(),
                    ),
                    const SizedBox(height: 16),
                    Expanded(
                      child: Card(
                        clipBehavior: Clip.antiAlias,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(24),
                        ),
                        child: Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            border: Border.all(
                              color: _primaryBlue.withValues(alpha: 0.25),
                              width: 2,
                            ),
                            borderRadius: BorderRadius.circular(24),
                          ),
                          child: _buildMap(),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 16),
              SizedBox(width: 260, child: _buildRoutePanel()),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildRoutePanel() {
    final floorStats = _floorStatus[_selectedFloor]!;

    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Route details',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: Color(0xFF0D47A1),
              ),
            ),
            const SizedBox(height: 12),
            Expanded(
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      _showRoute ? Icons.route_rounded : Icons.route_outlined,
                      color: _showRoute ? Colors.green.shade700 : Colors.grey,
                      size: 28,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _showRoute ? 'Route active' : 'No route selected',
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 20),
                    _buildInfoRow('Start', 'Room 1.05, G-1'),
                    const SizedBox(height: 12),
                    _buildInfoRow('Destination', 'Room 2.31, G-2'),
                    const SizedBox(height: 12),
                    _buildInfoRow('Estimated Travel Time', 'N/A'),
                    const SizedBox(height: 20),
                    const Text(
                      'Floor Status',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF0D47A1),
                      ),
                    ),
                    const SizedBox(height: 12),
                    _buildInfoRow(
                      'NaviBots on floor',
                      floorStats['total'].toString(),
                    ),
                    const SizedBox(height: 8),
                    _buildInfoRow(
                      'Available NaviBots',
                      floorStats['available'].toString(),
                    ),
                    const SizedBox(height: 8),
                    _buildInfoRow(
                      'NaviBots In Use',
                      floorStats['inUse'].toString(),
                    ),
                    const SizedBox(height: 20),
                    const Text(
                      'Key',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF0D47A1),
                      ),
                    ),
                    const SizedBox(height: 8),
                    _buildLegendRow(Icons.circle, 'Available', Colors.green),
                    const SizedBox(height: 6),
                    _buildLegendRow(Icons.circle, 'In Use', Colors.red),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: _showRoute ? _confirmBooking : null,
                icon: const Icon(Icons.calendar_month_rounded),
                label: const Text('Confirm booking'),
                style: FilledButton.styleFrom(
                  backgroundColor: _primaryBlue,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
              ),
            ),
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _showRoute ? _cancelRoute : null,
                icon: const Icon(Icons.cancel_outlined),
                label: const Text('Cancel route'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.red.shade700,
                  side: BorderSide(color: Colors.red.shade300),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontWeight: FontWeight.w600,
            color: _primaryBlue,
          ),
        ),
        const SizedBox(height: 6),
        Text(value, style: const TextStyle(fontSize: 15)),
      ],
    );
  }

  Widget _buildLegendRow(IconData icon, String label, Color color) {
    return Row(
      children: [
        Icon(icon, color: color, size: 16),
        const SizedBox(width: 8),
        Text(label, style: const TextStyle(fontSize: 14)),
      ],
    );
  }

  Widget _buildFloorChip(String floor) {
    final retired = _retiredFloors.contains(floor);
    final selected = floor == _selectedFloor;

    return ChoiceChip(
      label: Text(floor),
      selected: selected,
      onSelected: retired ? null : (_) => _selectFloor(floor),
      selectedColor: _primaryBlue,
      checkmarkColor: Colors.white,
      disabledColor: Colors.grey.shade300,
      labelStyle: TextStyle(
        color: retired
            ? Colors.grey.shade600
            : selected
            ? Colors.white
            : _primaryBlue,
        fontWeight: FontWeight.w600,
      ),
    );
  }

  Widget _buildMap() {
    return LayoutBuilder(
      builder: (context, constraints) {
        final availableWidth = constraints.maxWidth;
        final availableHeight = constraints.maxHeight;
        final mapWidth = math.min(
          availableWidth,
          availableHeight * _mapAspectRatio,
        );
        final mapHeight = mapWidth / _mapAspectRatio;
        final mapLeft = (availableWidth - mapWidth) / 2;
        final mapTop = (availableHeight - mapHeight) / 2;

        return Stack(
          children: [
            Positioned(
              left: mapLeft,
              top: mapTop,
              width: mapWidth,
              height: mapHeight,
              child: InteractiveViewer(
                boundaryMargin: const EdgeInsets.all(80),
                minScale: 0.5,
                maxScale: 4,
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    Image.asset(
                      _mapAsset,
                      key: ValueKey(_mapAsset),
                      fit: BoxFit.fill,
                    ),
                    if (_showRoute)
                      Positioned.fill(
                        child: IgnorePointer(
                          child: CustomPaint(
                            key: ValueKey('dynamic-route-$_selectedFloor'),
                            painter: _RoutePainter(floor: _selectedFloor),
                          ),
                        ),
                      ),
                    if (_selectedFloor == 'G-1')
                      Positioned(
                        // The route starts at room 1.05: (41.7%, 20%) of G-1.
                        left: (mapWidth * 0.417) - 12,
                        top: (mapHeight * 0.200) - 12,
                        child: Semantics(
                          label: 'Start: room 1.05',
                          child: const Tooltip(
                            message: 'Start: room 1.05',
                            child: Icon(
                              Icons.trip_origin_rounded,
                              color: _primaryBlue,
                              size: 24,
                            ),
                          ),
                        ),
                      ),
                    if (_selectedFloor == 'G-2')
                      Positioned(
                        // The route ends at room 2.31: (69%, 66.2%) of G-2.
                        left: (mapWidth * 0.69) - 16,
                        top: (mapHeight * 0.662) - 16,
                        child: Semantics(
                          button: true,
                          label: _showRoute
                              ? 'Cancel route at destination: room 2.31'
                              : 'Start route to destination: room 2.31',
                          child: Tooltip(
                            message: _showRoute
                                ? 'Cancel route at destination: room 2.31'
                                : 'Start route to destination: room 2.31',
                            child: IconButton.filled(
                              key: const ValueKey('room-2.31-destination'),
                              onPressed: _toggleDestinationRoute,
                              style: IconButton.styleFrom(
                                backgroundColor: _showRoute
                                    ? Colors.green.shade700
                                    : _primaryBlue,
                                minimumSize: const Size(32, 32),
                                maximumSize: const Size(32, 32),
                                padding: EdgeInsets.zero,
                              ),
                              icon: Icon(
                                _showRoute
                                    ? Icons.cancel_rounded
                                    : Icons.flag_rounded,
                                size: 16,
                              ),
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

/// Draws the fixed user-testing route in the floor plan's own coordinate space.
class _RoutePainter extends CustomPainter {
  const _RoutePainter({required this.floor});

  final String floor;

  @override
  void paint(Canvas canvas, Size size) {
    final points = floor == 'G-1'
        ? const [
            Offset(0.417, 0.200),
            Offset(0.227, 0.200),
            Offset(0.227, 0.659),
            Offset(0.452, 0.659),
            Offset(0.452, 0.930),
          ]
        : const [
            Offset(0.452, 0.924),
            Offset(0.452, 0.662),
            Offset(0.690, 0.662),
          ];
    final scaledPoints = points
        .map((point) => Offset(point.dx * size.width, point.dy * size.height))
        .toList();
    final paint = Paint()
      ..color = const Color(0xFFF21D2B)
      ..strokeWidth = 6
      ..strokeCap = StrokeCap.square
      ..strokeJoin = StrokeJoin.miter
      ..style = PaintingStyle.stroke;
    final path = Path()..moveTo(scaledPoints.first.dx, scaledPoints.first.dy);
    for (final point in scaledPoints.skip(1)) {
      path.lineTo(point.dx, point.dy);
    }
    canvas.drawPath(path, paint);

    final end = scaledPoints.last;
    final previous = scaledPoints[scaledPoints.length - 2];
    final direction = (end - previous) / (end - previous).distance;
    final perpendicular = Offset(-direction.dy, direction.dx);
    final arrowPaint = Paint()
      ..color = paint.color
      ..style = PaintingStyle.fill;
    final arrow = Path()
      ..moveTo(end.dx, end.dy)
      ..lineTo(
        end.dx - (direction.dx * 16) + (perpendicular.dx * 12),
        end.dy - (direction.dy * 16) + (perpendicular.dy * 12),
      )
      ..lineTo(
        end.dx - (direction.dx * 16) - (perpendicular.dx * 12),
        end.dy - (direction.dy * 16) - (perpendicular.dy * 12),
      )
      ..close();
    canvas.drawPath(arrow, arrowPaint);
  }

  @override
  bool shouldRepaint(covariant _RoutePainter oldDelegate) =>
      oldDelegate.floor != floor;
}
