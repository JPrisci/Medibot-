import 'package:flutter/material.dart';

import '../session_tracker.dart';
import 'search_by_map_page.dart';
import 'search_by_department_page.dart';

class MainLayoutPage extends StatefulWidget {
  const MainLayoutPage({super.key});

  @override
  State<MainLayoutPage> createState() => _MainLayoutPageState();
}

class _MainLayoutPageState extends State<MainLayoutPage> {
  static const _primaryBlue = Color(0xFF1565C0);
  static const _floorStatus = {
    'G-1': _FloorStatus(available: 3, inUse: 1),
    'G-2': _FloorStatus(available: 2, inUse: 2),
  };
  static const _retiredFloors = {'G-G', 'G-3'};

  String _selectedFloor = 'G-1';

  void _selectFloor(String floor) {
    if (_retiredFloors.contains(floor) || floor == _selectedFloor) return;
    SessionTracker.instance.recordClick('Home floor change: $floor');
    setState(() => _selectedFloor = floor);
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            Expanded(flex: 3, child: _buildStatusDashboard()),
            const SizedBox(height: 16),
            Expanded(
              flex: 2,
              child: Row(
                children: [
                  Expanded(
                    child: _buildActionCard(
                      icon: Icons.search_rounded,
                      title: 'Search by Department',
                      description: 'Find the service you need',
                      onPressed: () {
                        SessionTracker.instance.recordClick('Department');
                        Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => const SearchByDepartmentPage(),
                          ),
                        );
                      },
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: _buildActionCard(
                      icon: Icons.map_outlined,
                      title: 'Search by Map',
                      description: 'Browse all available floors',
                      onPressed: () {
                        SessionTracker.instance.recordClick('Map');
                        Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => const SearchByMapPage(),
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusDashboard() {
    final status = _floorStatus[_selectedFloor]!;
    return Card(
      elevation: 3,
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      child: Row(
        children: [
          Expanded(
            flex: 6,
            child: Container(
              color: const Color(0xFFF7FBFF),
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Icon(Icons.location_on_rounded, color: _primaryBlue),
                      SizedBox(width: 8),
                      Text(
                        'NaviBot locations',
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                          color: Color(0xFF0D47A1),
                        ),
                      ),
                    ],
                  ),
                    const SizedBox(height: 10),
                    Wrap(
                      spacing: 8,
                      children: ['G-G', 'G-1', 'G-2', 'G-3']
                          .map((floor) {
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
                          })
                          .toList(),
                    ),
                    const SizedBox(height: 8),
                    Expanded(child: _buildFloorMap()),
                ],
              ),
            ),
          ),
          Container(width: 1, color: const Color(0xFFE3F2FD)),
          Expanded(
            flex: 4,
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Floor availability',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Color(0xFF0D47A1)),
                  ),
                  const SizedBox(height: 4),
                  Text('$_selectedFloor - ${status.available + status.inUse} NaviBots', style: const TextStyle(color: Colors.black54)),
                  _buildAvailabilityCount(
                    value: status.available.toString(),
                    label: 'Available now',
                    color: Colors.green.shade700,
                    icon: Icons.check_circle_rounded,
                  ),
                  const SizedBox(height: 6),
                  _buildAvailabilityCount(
                    value: status.inUse.toString(),
                    label: 'Currently in use',
                    color: Colors.red.shade700,
                    icon: Icons.directions_walk_rounded,
                  ),
                  const SizedBox(height: 8),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: const Color(0xFFE8F5E9),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.schedule_rounded, color: Color(0xFF2E7D32)),
                        const SizedBox(width: 10),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('Next NaviBot available', style: TextStyle(fontWeight: FontWeight.w700)),
                            Text('About ${_estimatedWait()} min', style: const TextStyle(color: Color(0xFF2E7D32))),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    'Have a question?',
                    style: TextStyle(fontWeight: FontWeight.w600, color: Color(0xFF0D47A1)),
                  ),
                  const SizedBox(height: 6),
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton.icon(
                      onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Staff have been notified. (Demo only)')),
                      ),
                      icon: const Icon(Icons.support_agent_rounded),
                      label: const Text('Call staff'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: _primaryBlue,
                        minimumSize: const Size.fromHeight(36),
                        padding: EdgeInsets.zero,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFloorMap() {
    final isGroundOne = _selectedFloor == 'G-1';
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFBBDEFB)),
      ),
      child: Center(
        child: AspectRatio(
          aspectRatio: isGroundOne ? 633 / 733 : 646 / 753,
          child: Stack(
            fit: StackFit.expand,
            children: [
              Image.asset(
                'assets/images/${_selectedFloor}.png',
                fit: BoxFit.fill,
              ),
              ...isGroundOne
                  ? const [
                      _RobotDot(left: 0.32, top: 0.32, color: Colors.green, label: 'Available NaviBot'),
                      _RobotDot(left: 0.57, top: 0.30, color: Colors.red, label: 'NaviBot in use'),
                      _RobotDot(left: 0.65, top: 0.63, color: Colors.green, label: 'Available NaviBot'),
                      _RobotDot(left: 0.32, top: 0.74, color: Colors.green, label: 'Available NaviBot'),
                    ]
                  : const [
                      _RobotDot(left: 0.37, top: 0.27, color: Colors.green, label: 'Available NaviBot'),
                      _RobotDot(left: 0.67, top: 0.44, color: Colors.red, label: 'NaviBot in use'),
                      _RobotDot(left: 0.49, top: 0.72, color: Colors.green, label: 'Available NaviBot'),
                      _RobotDot(left: 0.74, top: 0.74, color: Colors.red, label: 'NaviBot in use'),
                    ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildAvailabilityCount({
    required String value,
    required String label,
    required Color color,
    required IconData icon,
  }) {
    return Row(
      children: [
        Icon(icon, size: 28, color: color),
        const SizedBox(width: 12),
        Text(value, style: TextStyle(fontSize: 32, fontWeight: FontWeight.w700, color: color)),
        const SizedBox(width: 10),
        Text(label, style: const TextStyle(fontSize: 15)),
      ],
    );
  }

  String _estimatedWait() => _selectedFloor == 'G-1' ? '3' : '5';

  Widget _buildActionCard({
    required IconData icon,
    required String title,
    required String description,
    required VoidCallback onPressed,
  }) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: onPressed,
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(14),
                decoration: const BoxDecoration(color: Color(0xFFE3F2FD), shape: BoxShape.circle),
                child: Icon(icon, color: _primaryBlue, size: 30),
              ),
              const SizedBox(width: 18),
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Color(0xFF0D47A1))),
                    const SizedBox(height: 5),
                    Text(description, style: const TextStyle(color: Colors.black54)),
                  ],
                ),
              ),
              const Icon(Icons.arrow_forward_rounded, color: _primaryBlue),
            ],
          ),
        ),
      ),
    );
  }
}

class _FloorStatus {
  const _FloorStatus({required this.available, required this.inUse});

  final int available;
  final int inUse;
}

class _RobotDot extends StatelessWidget {
  const _RobotDot({
    required this.left,
    required this.top,
    required this.color,
    required this.label,
  });

  final double left;
  final double top;
  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment(-1 + (left * 2), -1 + (top * 2)),
      child: Semantics(
        label: label,
        child: Container(
          width: 22,
          height: 22,
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
            border: Border.all(color: Colors.white, width: 3),
            boxShadow: const [BoxShadow(color: Colors.black26, blurRadius: 3)],
          ),
        ),
      ),
    );
  }
}
