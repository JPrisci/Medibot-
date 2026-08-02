// Basic widget test (smoke test).
// Note: this test was originally scaffolded for the starter template and
// asserts a counter increment. It may be updated later to better match NaviBot
// UI semantics (for now it verifies the app boots and a simple interaction).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:medibot/screens/search_by_map_page.dart';

void main() {
  testWidgets('map page switches between floor backgrounds', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: SearchByMapPage()));

    expect(find.text('G-G'), findsOneWidget);
    expect(find.text('G-1'), findsOneWidget);

    await tester.tap(find.widgetWithText(ChoiceChip, 'G-1'));
    await tester.pumpAndSettle();

    expect(find.widgetWithText(ChoiceChip, 'G-1'), findsOneWidget);
  });
}
