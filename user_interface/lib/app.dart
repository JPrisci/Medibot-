// Application root widget.
// Configures the global MaterialApp theme and initial route.
import 'package:flutter/material.dart';

import 'screens/loading_page.dart';

class NaviBotApp extends StatelessWidget {
  const NaviBotApp({super.key});

  @override
  Widget build(BuildContext context) {
    // MaterialApp encapsulation makes it easy to swap themes or add routes.
    return MaterialApp(
      title: 'NaviBot',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo),
        useMaterial3: true,
      ),
      home: const LoadingPage(),
    );
  }
}
