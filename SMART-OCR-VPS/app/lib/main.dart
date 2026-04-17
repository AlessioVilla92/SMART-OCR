import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'providers/auth_provider.dart';
import 'screens/login_screen.dart';
import 'screens/home_screen.dart';
import 'screens/camera_screen.dart';
import 'screens/analysis_screen.dart';
import 'screens/results_screen.dart';
import 'screens/settings_screen.dart';

void main() {
  runApp(const ProviderScope(child: SmartOcrApp()));
}

class SmartOcrApp extends ConsumerWidget {
  const SmartOcrApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(authProvider);

    final router = GoRouter(
      initialLocation: user == null ? '/login' : '/home',
      routes: [
        GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
        GoRoute(path: '/home', builder: (_, __) => const HomeScreen()),
        GoRoute(path: '/camera', builder: (_, __) => const CameraScreen()),
        GoRoute(
          path: '/analysis/:jobId',
          builder: (_, state) => AnalysisScreen(
            jobId: state.pathParameters['jobId']!,
          ),
        ),
        GoRoute(
          path: '/results/:jobId',
          builder: (_, state) => ResultsScreen(
            jobId: state.pathParameters['jobId']!,
          ),
        ),
        GoRoute(path: '/settings', builder: (_, __) => const SettingsScreen()),
      ],
      redirect: (context, state) {
        final isLoggedIn = user != null;
        final isOnLogin = state.matchedLocation == '/login';

        if (!isLoggedIn && !isOnLogin) return '/login';
        if (isLoggedIn && isOnLogin) return '/home';
        return null;
      },
    );

    return MaterialApp.router(
      title: 'Smart OCR',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFF3D85C6),
        useMaterial3: true,
        brightness: Brightness.light,
      ),
      darkTheme: ThemeData(
        colorSchemeSeed: const Color(0xFF3D85C6),
        useMaterial3: true,
        brightness: Brightness.dark,
      ),
      themeMode: ThemeMode.system,
      routerConfig: router,
    );
  }
}
