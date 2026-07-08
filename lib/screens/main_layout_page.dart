// Main app layout combining a map preview and options to search by map or department.
import 'package:flutter/material.dart';

import '../session_tracker.dart';
import 'search_by_map_page.dart';
import 'search_by_ward_page.dart';

class MainLayoutPage extends StatelessWidget {
  const MainLayoutPage({super.key});

  @override
  Widget build(BuildContext context) {
    // Two-pane layout: map preview above, action cards below.
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            Expanded(
              flex: 1,
              child: _buildMapPane(),
            ),
            const SizedBox(height: 16),
            Expanded(
              flex: 1,
              child: Row(
                children: [
                  Expanded(
                    child: _buildOptionCard(
                      context: context,
                      title: 'Find a Department',
                      icon: Icons.search_rounded,
                      buttonLabel: 'Search by Department',
                      onPressed: () {
                        // Track click and navigate to department selection.
                        SessionTracker.instance.recordClick('Department');
                        Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => const SearchByWardPage(),
                          ),
                        );
                      },
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: _buildOptionCard(
                      context: context,
                      title: 'Explore the Mall',
                      icon: Icons.map_outlined,
                      buttonLabel: 'Search by Map',
                      onPressed: () {
                        // Track click and navigate to interactive map.
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

  Widget _buildMapPane() {
    // Small visual placeholder representing the mall map.
    return Card(
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(24),
          gradient: const LinearGradient(
            colors: [Color(0xFFE3F2FD), Color(0xFFBBDEFB)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Live Mall Map',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: Color(0xFF0D47A1),
                ),
              ),
              const SizedBox(height: 12),
              const Text(
                'Placeholder live map for mall navigation.',
                style: TextStyle(fontSize: 15, color: Colors.black87),
              ),
              const Spacer(),
              Container(
                height: 140,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.7),
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: Colors.indigo.shade200),
                ),
                child: Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.location_on,
                        size: 42,
                        color: Colors.indigo.shade700,
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'Map placeholder',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: Color(0xFF1565C0),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildOptionCard({
    required BuildContext context,
    required String title,
    required IconData icon,
    required String buttonLabel,
    required VoidCallback onPressed,
  }) {
    // Reusable card widget used for the two main actions on the home screen.
    return Card(
      elevation: 3,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 40, color: const Color(0xFF1565C0)),
            const SizedBox(height: 12),
            Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: Color(0xFF0D47A1),
              ),
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: onPressed,
              style: FilledButton.styleFrom(
                backgroundColor: const Color(0xFF1565C0),
                minimumSize: const Size(double.infinity, 48),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
              ),
              child: Text(buttonLabel),
            ),
          ],
        ),
      ),
    );
  }
}
