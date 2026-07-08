// Department selection grid.
import 'package:flutter/material.dart';

import '../session_tracker.dart';
import 'search_by_map_page.dart';

class SearchByWardPage extends StatelessWidget {
  const SearchByWardPage({super.key});

  @override
  Widget build(BuildContext context) {
    final departments = [
      'Fashion',
      'Electronics',
      'Food Court',
      'Books & Media',
      'Home Goods',
      'Sports',
      'Beauty',
      "Children's",
    ];

    return Scaffold(
      backgroundColor: const Color(0xFF0D47A1),
      appBar: AppBar(
        title: const Text(
          'Search by Department',
          style: TextStyle(color: Colors.white),
        ),
        backgroundColor: const Color(0xFF1565C0),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () {
            // Record click and navigate back to main
            SessionTracker.instance.recordClick('Back');
            Navigator.of(context).pop();
          },
        ),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Choose a department',
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w700,
                  color: Color(0xFF0D47A1),
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Select a common mall department to continue.',
                style: TextStyle(fontSize: 15, color: Colors.black87),
              ),
              const SizedBox(height: 20),
              Expanded(
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    final crossAxisCount = constraints.maxWidth > 900 ? 4 : 2;
                    return GridView.count(
                      crossAxisCount: crossAxisCount,
                      mainAxisSpacing: 16,
                      crossAxisSpacing: 16,
                      childAspectRatio: 1.3,
                      physics: const NeverScrollableScrollPhysics(),
                      children: departments.map((department) {
                        return FilledButton(
                          onPressed: () {
                            // Track selection and push map screen with the department pre-selected.
                            SessionTracker.instance.recordClick(department);
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) => SearchByMapPage(selectedWard: department),
                              ),
                            );
                          },
                          style: FilledButton.styleFrom(
                            backgroundColor: const Color(0xFF1565C0),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                          ),
                          child: Text(department, textAlign: TextAlign.center),
                        );
                      }).toList(),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
