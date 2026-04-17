/// App-wide configuration constants.
class AppConfig {
  /// Default server URL (can be changed in settings).
  static const String defaultServerUrl = 'http://192.168.1.100:8000';

  /// API base path.
  static const String apiBasePath = '/api/v1';

  /// Job polling interval (initial).
  static const Duration pollInterval = Duration(seconds: 2);

  /// Job polling interval (after 30s).
  static const Duration pollIntervalSlow = Duration(seconds: 5);

  /// JWT token key in secure storage.
  static const String tokenKey = 'jwt_access_token';
  static const String serverUrlKey = 'server_url';

  /// CBCL pages.
  static const List<String> cbclPages = ['page_4', 'page_5', 'page_6'];
  static const List<String> cbclPageLabels = ['Pagina 4', 'Pagina 5', 'Pagina 6'];
}
