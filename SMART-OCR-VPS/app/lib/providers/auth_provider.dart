import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/user.dart';
import '../services/api_client.dart';

/// Global API client instance.
final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());

/// Auth state: null = not logged in, AppUser = logged in.
final authProvider = StateNotifierProvider<AuthNotifier, AppUser?>((ref) {
  return AuthNotifier(ref.read(apiClientProvider));
});

class AuthNotifier extends StateNotifier<AppUser?> {
  final ApiClient _api;

  AuthNotifier(this._api) : super(null);

  /// Check if there's a stored token on app start.
  Future<void> checkAuth() async {
    final hasToken = await _api.hasToken();
    if (hasToken) {
      try {
        // Verify token by calling health (lightweight)
        await _api.healthCheck();
        state = const AppUser(username: 'user', token: 'stored');
      } catch (_) {
        await _api.logout();
        state = null;
      }
    }
  }

  /// Login with username and password.
  Future<void> login(String username, String password) async {
    final token = await _api.login(username, password);
    state = AppUser(username: username, token: token);
  }

  /// Logout.
  Future<void> logout() async {
    await _api.logout();
    state = null;
  }
}
