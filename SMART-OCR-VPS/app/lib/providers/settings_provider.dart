import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/api_client.dart';
import 'auth_provider.dart';

/// Server URL state.
final serverUrlProvider = StateProvider<String>((ref) => 'http://192.168.1.100:8000');

/// Load saved server URL on app start.
Future<void> loadSettings(ProviderContainer container) async {
  final api = container.read(apiClientProvider);
  final url = await api.loadBaseUrl();
  container.read(serverUrlProvider.notifier).state = url;
}
