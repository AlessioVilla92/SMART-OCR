import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../config.dart';

/// HTTP client for the Smart OCR backend API.
///
/// Handles JWT injection, token refresh/logout on 401, and multipart uploads.
class ApiClient {
  late final Dio _dio;
  final FlutterSecureStorage _storage = const FlutterSecureStorage();

  String _baseUrl;

  ApiClient({String? baseUrl}) : _baseUrl = baseUrl ?? AppConfig.defaultServerUrl {
    _dio = Dio(BaseOptions(
      baseUrl: '$_baseUrl${AppConfig.apiBasePath}',
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 120),
    ));

    // JWT interceptor
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await _storage.read(key: AppConfig.tokenKey);
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onError: (error, handler) async {
        if (error.response?.statusCode == 401) {
          await _storage.delete(key: AppConfig.tokenKey);
          // The UI layer should detect this and redirect to login
        }
        handler.next(error);
      },
    ));
  }

  /// Update server URL at runtime (from settings screen).
  Future<void> updateBaseUrl(String newUrl) async {
    _baseUrl = newUrl;
    _dio.options.baseUrl = '$newUrl${AppConfig.apiBasePath}';
    await _storage.write(key: AppConfig.serverUrlKey, value: newUrl);
  }

  /// Load saved server URL from secure storage.
  Future<String> loadBaseUrl() async {
    final saved = await _storage.read(key: AppConfig.serverUrlKey);
    if (saved != null) {
      _baseUrl = saved;
      _dio.options.baseUrl = '$saved${AppConfig.apiBasePath}';
    }
    return _baseUrl;
  }

  // ── Auth ───────────────────────────────────────────────

  /// Login and store JWT token.
  Future<String> login(String username, String password) async {
    final resp = await _dio.post(
      '/auth/login',
      data: FormData.fromMap({
        'username': username,
        'password': password,
      }),
    );
    final token = resp.data['access_token'] as String;
    await _storage.write(key: AppConfig.tokenKey, value: token);
    return token;
  }

  /// Logout — delete stored token.
  Future<void> logout() async {
    await _storage.delete(key: AppConfig.tokenKey);
  }

  /// Check if we have a stored token.
  Future<bool> hasToken() async {
    final token = await _storage.read(key: AppConfig.tokenKey);
    return token != null && token.isNotEmpty;
  }

  // ── Health ─────────────────────────────────────────────

  Future<Map<String, dynamic>> healthCheck() async {
    final resp = await _dio.get('/health');
    return resp.data as Map<String, dynamic>;
  }

  // ── Jobs ───────────────────────────────────────────────

  /// Upload 3 page photos and create an analysis job.
  Future<String> createJob({
    required File page4,
    required File page5,
    required File page6,
    String mode = 'ensemble',
    void Function(int sent, int total)? onProgress,
  }) async {
    final formData = FormData.fromMap({
      'page_4': await MultipartFile.fromFile(page4.path, filename: 'page_4.jpg'),
      'page_5': await MultipartFile.fromFile(page5.path, filename: 'page_5.jpg'),
      'page_6': await MultipartFile.fromFile(page6.path, filename: 'page_6.jpg'),
      'mode': mode,
    });

    final resp = await _dio.post(
      '/jobs',
      data: formData,
      onSendProgress: onProgress,
    );
    return resp.data['job_id'] as String;
  }

  /// Poll job status.
  Future<Map<String, dynamic>> getJobStatus(String jobId) async {
    final resp = await _dio.get('/jobs/$jobId');
    return resp.data as Map<String, dynamic>;
  }

  /// Fetch completed job results.
  Future<Map<String, dynamic>> getJobResults(String jobId) async {
    final resp = await _dio.get('/jobs/$jobId/results');
    return resp.data as Map<String, dynamic>;
  }

  /// Delete a job.
  Future<void> deleteJob(String jobId) async {
    await _dio.delete('/jobs/$jobId');
  }

  // ── Scoring ────────────────────────────────────────────

  /// Recompute scores from edited item values.
  Future<Map<String, dynamic>> recomputeScores({
    required Map<String, int> items,
    int? age,
    String? gender,
    String compilatore = 'MD',
  }) async {
    final resp = await _dio.post('/score/recompute', data: {
      'items': items,
      'age': age,
      'gender': gender,
      'compilatore': compilatore,
    });
    return resp.data as Map<String, dynamic>;
  }
}
