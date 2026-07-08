import 'package:flutter/material.dart';

import '../session_tracker.dart';
import 'session_summary_page.dart';

// Interactive map placeholder consisting of two floors.
class SearchByMapPage extends StatefulWidget {
  const SearchByMapPage({super.key, this.selectedWard});
  final String? selectedWard;

  @override
  State<SearchByMapPage> createState() => _SearchByMapPageState();
}

// Default settings for floor 1, before any selection is made, this is later updated upon click.
class _SearchByMapPageState extends State<SearchByMapPage> {
  final String _currentLocation = 'Main Entrance';
  late String _chosenLocation;
  late String _travelTime;
  String _selectedFloor = 'Floor 1';
  bool _routeSelected = false;
  bool _routeConfirmed = false;
  bool _confirmPromptVisible = false;

  // Placeholder values
  final Map<String, Map<String, int>> _floorStatus = {
    'Floor 1': {'total': 3, 'available': 2, 'inUse': 1},
    'Floor 2': {'total': 3, 'available': 1, 'inUse': 2},
  };

// Placeholder values - 'department store'.
  final Map<String, Map<String, dynamic>> _departmentDetails = {
    'Fashion': {
      'floor': 'Floor 1',
      'travelTime': '5 min',
      'color': Colors.purple.shade400,
      'icon': Icons.checkroom_rounded,
      'pos': const Offset(0.08, 0.08)
    },
    'Electronics': {
      'floor': 'Floor 1',
      'travelTime': '8 min',
      'color': Colors.teal.shade600,
      'icon': Icons.devices_rounded,
      'pos': const Offset(0.92, 0.08)
    },
    'Food Court': {
      'floor': 'Floor 1',
      'travelTime': '12 min',
      'color': Colors.orange.shade600,
      'icon': Icons.restaurant_rounded,
      'pos': const Offset(0.08, 0.92)
    },
    'Beauty': {
      'floor': 'Floor 1',
      'travelTime': '4 min',
      'color': Colors.pink.shade400,
      'icon': Icons.face_rounded,
      'pos': const Offset(0.92, 0.92)
    },
    'Books & Media': {
      'floor': 'Floor 2',
      'travelTime': '7 min',
      'color': Colors.blue.shade500,
      'icon': Icons.menu_book_rounded,
      'pos': const Offset(0.08, 0.08)
    },
    'Home Goods': {
      'floor': 'Floor 2',
      'travelTime': '6 min',
      'color': Colors.green.shade600,
      'icon': Icons.home_rounded,
      'pos': const Offset(0.92, 0.08)
    },
    'Sports': {
      'floor': 'Floor 2',
      'travelTime': '9 min',
      // Use app primary blue for consistency with ward_page
      'color': const Color(0xFF1565C0),
      'icon': Icons.sports_basketball_rounded,
      'pos': const Offset(0.08, 0.92)
    },
    "Children's": {
      'floor': 'Floor 2',
      'travelTime': '3 min',
      'color': Colors.cyan.shade600,
      'icon': Icons.child_care_rounded,
      'pos': const Offset(0.92, 0.92)
    },
  };

  @override
  void initState() {
    super.initState();
    if (widget.selectedWard != null) {
      _applyDepartmentSelection(widget.selectedWard!);
    } else {
      _chosenLocation = 'Waiting for selection';
      _travelTime = 'N/A';
      _routeSelected = false;
      _selectedFloor = 'Floor 1';
    }
  }

  // Click counter.
  void _recordInteraction(String label) {
    SessionTracker.instance.recordClick(label);
  }
  // Updates department info upon click
  void _applyDepartmentSelection(String department) {
    final details = _departmentDetails[department];
    if (details == null) {
      return;
    }
    // If values arent null, insert the values.
    _chosenLocation = department;
    _travelTime = details['travelTime'] as String;
    _selectedFloor = details['floor'] as String;
    _routeSelected = true;
    _routeConfirmed = false;
  }
  // Updates department info on click.
  void _selectDepartment(String department) {
    _recordInteraction(department);
    _applyDepartmentSelection(department);
    setState(() {});
  }
  // Method to confirm route, essentially greyed out until a department is selected, in which then a route can be confirmed.
  void _confirmRoute() {
    if (!_routeSelected) {
      return;
    }
    setState(() {
      _confirmPromptVisible = true;
      _routeConfirmed = false;
    });
  }
  // Accepting confirmation and closing prompt.
  void _acceptConfirmation() {
    setState(() {
      _confirmPromptVisible = false;
      _routeConfirmed = true;
    });
  }
  // If user doesnt confirm, kill prompt.
  void _dismissConfirmation() {
    setState(() {
      _confirmPromptVisible = false;
      _routeConfirmed = false;
    });
  }
  // When session is done, go to summary page recording clicks and time taken (for stats).
  void _finishSession() {
    SessionTracker.instance.recordClick('Session complete');
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const SessionSummaryPage()),
    );
  }

  Widget _buildFloorMarker({
    required String label,
    required IconData icon,
    required Color color,
    required bool selected,
    required VoidCallback onTap,
  }) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          width: 108,
          height: 86,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            gradient: LinearGradient(
              colors: selected
                  ? [color.withValues(alpha: 0.82), color.withValues(alpha: 0.5)]
                  : [color.withValues(alpha: 0.18), color.withValues(alpha: 0.08)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            border: Border.all(
              color: selected ? Colors.white : color.withValues(alpha: 0.7),
              width: selected ? 3 : 2,
            ),
            boxShadow: selected
                ? [
                    BoxShadow(
                      color: color.withValues(alpha: 0.28),
                      blurRadius: 10,
                      offset: const Offset(0, 5),
                    ),
                  ]
                : null,
          ),
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, color: selected ? Colors.white : color, size: 22),
              const SizedBox(height: 4),
              Text(
                label,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: selected ? Colors.white : color,
                  fontWeight: FontWeight.w700,
                  fontSize: 11,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final floorStats = _floorStatus[_selectedFloor]!;
    return Scaffold(
      backgroundColor: const Color.fromARGB(255, 255, 255, 255),
      appBar: AppBar(
        title: const Text(
          'Search by Map',
          style: TextStyle(color: Colors.white),
        ),
        backgroundColor: const Color(0xFF1565C0),
        leading: IconButton(
          color: Colors.white,
          icon: const Icon(Icons.arrow_back),
          onPressed: () {
            _recordInteraction('Back');
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
                child: Card(
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
                  child: Container(
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(24),
                      color: Colors.white.withValues(alpha: 0.35),
                    ),
                    child: Stack(
                      children: [
                        Positioned.fill(
                          child: Padding(
                            padding: const EdgeInsets.all(20),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const SizedBox(height: 16),
                                const Text(
                                  'Mall Map',
                                 style: TextStyle(
                                   fontSize: 24,
                                   fontWeight: FontWeight.w700,
                                   color: Color(0xFF0D47A1),
                                 ),
                                ),
                                const SizedBox(height: 8),
                                Wrap(
                                  spacing: 8,
                                  children: ['Floor 1', 'Floor 2'].map((floor) {
                                    final isSelected = floor == _selectedFloor;
                                    return ChoiceChip(
                                      label: Text(floor),
                                      selected: isSelected,
                                      onSelected: (_) {
                                        _recordInteraction('Floor change');
                                        setState(() {
                                          _selectedFloor = floor;
                                        });
                                      },
                                      selectedColor: const Color(0xFF1565C0),
                                      checkmarkColor: Colors.white,
                                      labelStyle: TextStyle(
                                        color: isSelected ? Colors.white : const Color(0xFF1565C0),
                                      ),
                                    );
                                  }).toList(),
                                ),
                                const SizedBox(height: 16),
                                Expanded(
                                  child: Container(
                                    decoration: BoxDecoration(
                                      color: Colors.white,
                                      borderRadius: BorderRadius.circular(24),
                                      border: Border.all(color: const Color(0xFF1565C0).withValues(alpha: 0.25), width: 2),
                                    ),
                                    child: Padding(
                                      padding: const EdgeInsets.all(20),
                                      child: Column(
                                        children: [
                                          Expanded(
                                            child: Container(
                                              decoration: BoxDecoration(
                                                borderRadius: BorderRadius.circular(20),
                                                border: Border.all(color: const Color.fromARGB(255, 255, 255, 255).withValues(alpha: 0.25), width: 2),
                                              ),
                                              child: LayoutBuilder(
                                                builder: (context, inner) {
                                                  return Stack(
                                                    children: [
                                                      // decorative inner area
                                                      Positioned.fill(
                                                        child: Padding(
                                                          padding: const EdgeInsets.all(24),
                                                          child: Container(
                                                            decoration: BoxDecoration(
                                                              borderRadius: BorderRadius.circular(18),
                                                              border: Border.all(color: const Color.fromARGB(255, 255, 255, 255).withValues(alpha: 0.15), width: 2),
                                                            ),
                                                            child: Center(
                                                              child: Column(
                                                                mainAxisSize: MainAxisSize.min,
                                                                children: [
                                                                  Icon(Icons.stairs_rounded, color: const Color(0xFF1565C0), size: 30),
                                                                  const SizedBox(height: 8),
                                                                  Text(
                                                                    _selectedFloor == 'Floor 1' ? 'Main level' : 'Upper level',
                                                                    style: const TextStyle(fontWeight: FontWeight.w700, color: Color(0xFF0D47A1)),
                                                                  ),
                                                                ],
                                                              ),
                                                            ),
                                                          ),
                                                        ),
                                                      ),
                                                      // Floor 1 markers
                                                      if (_selectedFloor == 'Floor 1') ...[
                                                        Align(
                                                          alignment: Alignment(-0.9, -0.9),
                                                          child: Padding(
                                                            padding: const EdgeInsets.all(8.0),
                                                            child: _buildFloorMarker(
                                                              label: 'Fashion',
                                                              icon: Icons.checkroom_rounded,
                                                              color: Colors.purple.shade400,
                                                              selected: _chosenLocation == 'Fashion',
                                                              onTap: () => _selectDepartment('Fashion'),
                                                            ),
                                                          ),
                                                        ),
                                                        Align(
                                                          alignment: Alignment(0.9, -0.9),
                                                          child: Padding(
                                                            padding: const EdgeInsets.all(8.0),
                                                            child: _buildFloorMarker(
                                                              label: 'Electronics',
                                                              icon: Icons.devices_rounded,
                                                              color: Colors.teal.shade600,
                                                              selected: _chosenLocation == 'Electronics',
                                                              onTap: () => _selectDepartment('Electronics'),
                                                            ),
                                                          ),
                                                        ),
                                                        Align(
                                                          alignment: Alignment(-0.9, 0.9),
                                                          child: Padding(
                                                            padding: const EdgeInsets.all(8.0),
                                                            child: _buildFloorMarker(
                                                              label: 'Food Court',
                                                              icon: Icons.restaurant_rounded,
                                                              color: Colors.orange.shade600,
                                                              selected: _chosenLocation == 'Food Court',
                                                              onTap: () => _selectDepartment('Food Court'),
                                                            ),
                                                          ),
                                                        ),
                                                        Align(
                                                          alignment: Alignment(0.9, 0.9),
                                                          child: Padding(
                                                            padding: const EdgeInsets.all(8.0),
                                                            child: _buildFloorMarker(
                                                              label: 'Beauty',
                                                              icon: Icons.face_rounded,
                                                              color: Colors.pink.shade400,
                                                              selected: _chosenLocation == 'Beauty',
                                                              onTap: () => _selectDepartment('Beauty'),
                                                            ),
                                                          ),
                                                        ),

                                                        // Entrance
                                                        Align(
                                                          alignment: Alignment(0, -0.84),
                                                          child: Padding(
                                                            padding: const EdgeInsets.only(top: 8.0),
                                                            child: _buildFloorMarker(
                                                              label: 'Main Entrance',
                                                              icon: Icons.door_front_door_rounded,
                                                              color: const Color(0xFF1565C0),
                                                              selected: _chosenLocation == 'Main Entrance',
                                                              onTap: () => _selectDepartment('Main Entrance'),
                                                            ),
                                                          ),
                                                        ),

                                                        // Lift 
                                                        Align(
                                                          alignment: Alignment(0, 0.84),
                                                          child: Padding(
                                                            padding: const EdgeInsets.only(bottom: 8.0),
                                                            child: _buildFloorMarker(
                                                              label: 'Lift',
                                                              icon: Icons.elevator,
                                                              color: Colors.grey.shade700,
                                                              selected: false,
                                                              onTap: () {},
                                                            ),
                                                          ),
                                                        ),
                                                      ] else ...[
                                                        // Floor 2 markers.
                                                        // Books & Medi.
                                                        Align(
                                                          alignment: Alignment(-0.9, -0.9),
                                                          child: Padding(
                                                            padding: const EdgeInsets.all(8.0),
                                                            child: _buildFloorMarker(
                                                              label: 'Books & Media',
                                                              icon: Icons.menu_book_rounded,
                                                              color: Colors.blue.shade500,
                                                              selected: _chosenLocation == 'Books & Media',
                                                              onTap: () => _selectDepartment('Books & Media'),
                                                            ),
                                                          ),
                                                        ),
                                                        // Home Goods Section
                                                        Align(
                                                          alignment: Alignment(0.9, -0.9),
                                                          child: Padding(
                                                            padding: const EdgeInsets.all(8.0),
                                                            child: _buildFloorMarker(
                                                              label: 'Home Goods',
                                                              icon: Icons.home_rounded,
                                                              color: Colors.green.shade600,
                                                              selected: _chosenLocation == 'Home Goods',
                                                              onTap: () => _selectDepartment('Home Goods'),
                                                            ),
                                                          ),
                                                        ),
                                                        // Sports Section.
                                                        Align(
                                                          alignment: Alignment(-0.9, 0.9),
                                                          child: Padding(
                                                            padding: const EdgeInsets.all(8.0),
                                                            child: _buildFloorMarker(
                                                              label: 'Sports',
                                                              icon: Icons.sports_basketball_rounded,
                                                              color: Colors.indigo.shade500,
                                                              selected: _chosenLocation == 'Sports',
                                                              onTap: () => _selectDepartment('Sports'),
                                                            ),
                                                          ),
                                                        ),
                                                        // Children's section.
                                                        Align(
                                                          alignment: Alignment(0.9, 0.9),
                                                          child: Padding(
                                                            padding: const EdgeInsets.all(8.0),
                                                            child: _buildFloorMarker(
                                                              label: "Children's",
                                                              icon: Icons.child_care_rounded,
                                                              color: Colors.cyan.shade600,
                                                              selected: _chosenLocation == "Children's",
                                                              onTap: () => _selectDepartment("Children's"),
                                                            ),
                                                          ),
                                                        ),

                                                        // Lift
                                                        Align(
                                                          alignment: Alignment(0, 0.84),
                                                          child: _buildFloorMarker(
                                                            label: 'Lift',
                                                            icon: Icons.elevator,
                                                            color: Colors.grey.shade700,
                                                            selected: false,
                                                            onTap: () {},
                                                          ),
                                                        ),
                                                      ],
                                                    ],
                                                  );
                                                },
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                        if (_confirmPromptVisible || _routeConfirmed)
                          Positioned.fill(
                            child: Center(
                              child: Container(
                                width: MediaQuery.of(context).size.width * 0.32,
                                height: MediaQuery.of(context).size.height * 0.32,
                                padding: const EdgeInsets.all(16),
                                decoration: BoxDecoration(
                                  color: Colors.white.withValues(alpha: 0.97),
                                  borderRadius: BorderRadius.circular(20),
                                  boxShadow: const [
                                    BoxShadow(
                                      color: Colors.black26,
                                      blurRadius: 12,
                                      offset: Offset(0, 6),
                                    ),
                                  ],
                                ),
                                child: _routeConfirmed
                                    ? Column(
                                        mainAxisAlignment: MainAxisAlignment.center,
                                        children: [
                                          const Icon(
                                            Icons.check_circle_rounded,
                                            color: Colors.green,
                                            size: 36,
                                          ),
                                          const SizedBox(height: 10),
                                          const Text(
                                            'NaviBot is on the way',
                                            textAlign: TextAlign.center,
                                            style: TextStyle(
                                              fontSize: 16,
                                              fontWeight: FontWeight.w700,
                                              color: Color(0xFF1B5E20),
                                            ),
                                          ),
                                          const SizedBox(height: 6),
                                          const Text(
                                            'ETA: 2 minutes',
                                            style: TextStyle(fontSize: 14),
                                          ),
                                          const SizedBox(height: 10),
                                          TextButton.icon(
                                            onPressed: _finishSession,
                                            icon: const Icon(Icons.close),
                                            label: const Text('Exit'),
                                          ),
                                        ],
                                      )
                                    : Column(
                                        mainAxisAlignment: MainAxisAlignment.center,
                                        children: [
                                          const Text(
                                            'Confirm route',
                                            style: TextStyle(
                                              fontSize: 18,
                                              fontWeight: FontWeight.w700,
                                            ),
                                          ),
                                          const SizedBox(height: 8),
                                          const Text(
                                            'Send NaviBot to this route now?',
                                            textAlign: TextAlign.center,
                                          ),
                                          const SizedBox(height: 12),
                                          Row(
                                            mainAxisAlignment: MainAxisAlignment.center,
                                            children: [
                                              TextButton(
                                                onPressed: _dismissConfirmation,
                                                child: const Text('Cancel'),
                                              ),
                                              const SizedBox(width: 8),
                                              FilledButton(
                                                onPressed: _acceptConfirmation,
                                                child: const Text('Yes'),
                                              ),
                                            ],
                                          ),
                                        ],
                                      ),
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                flex: 2,
                child: Card(
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      children: [
                        Expanded(
                          child: SingleChildScrollView(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Container(
                                  padding: const EdgeInsets.all(12),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFF1565C0),
                                    borderRadius: BorderRadius.circular(14),
                                  ),
                                  child: Row(
                                    children: const [
                                      Icon(Icons.info_outline_rounded, color: Colors.white),
                                      SizedBox(width: 8),
                                      Expanded(
                                        child: Text(
                                          'Choose a destination, then press Confirm Route.',
                                          style: TextStyle(
                                            fontSize: 14,
                                            fontWeight: FontWeight.w600,
                                            color: Colors.white,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(height: 16),
                                const Text(
                                  'Route Details',
                                  style: TextStyle(
                                    fontSize: 18,
                                    fontWeight: FontWeight.w700,
                                    color: Color(0xFF0D47A1),
                                  ),
                                ),
                                const SizedBox(height: 16),
                                _buildInfoRow('Current Location', _currentLocation),
                                const SizedBox(height: 12),
                                _buildInfoRow('Chosen Department', _chosenLocation),
                                const SizedBox(height: 12),
                                _buildInfoRow('Estimated Travel Time', _travelTime),
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
                                _buildInfoRow('NaviBots on floor', floorStats['total'].toString()),
                                const SizedBox(height: 8),
                                _buildInfoRow('Available NaviBots', floorStats['available'].toString()),
                                const SizedBox(height: 8),
                                _buildInfoRow('NaviBots In Use', floorStats['inUse'].toString()),
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
                        FilledButton.icon(
                          onPressed: _routeSelected ? _confirmRoute : null,
                          icon: const Icon(Icons.route_rounded),
                          label: const Padding(
                            padding: EdgeInsets.symmetric(vertical: 12),
                            child: Text(
                              'Confirm Route',
                              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                            ),
                          ),
                          style: FilledButton.styleFrom(
                            backgroundColor: _routeSelected ? const Color(0xFF0D47A1) : Colors.grey.shade400,
                            disabledBackgroundColor: Colors.grey.shade300,
                            minimumSize: const Size(double.infinity, 56),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(14),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
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
          style: const TextStyle(fontWeight: FontWeight.w600, color: Color(0xFF1565C0)),
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

}

 
