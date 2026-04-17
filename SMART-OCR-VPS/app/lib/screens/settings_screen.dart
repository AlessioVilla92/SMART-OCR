import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../providers/settings_provider.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  late TextEditingController _urlCtrl;
  bool _testing = false;
  String? _testResult;

  @override
  void initState() {
    super.initState();
    _urlCtrl = TextEditingController(text: ref.read(serverUrlProvider));
  }

  Future<void> _testConnection() async {
    setState(() { _testing = true; _testResult = null; });
    try {
      final api = ref.read(apiClientProvider);
      await api.updateBaseUrl(_urlCtrl.text.trim());
      final health = await api.healthCheck();
      final svm = health['models']?['svm'] == true;
      final yolo = health['models']?['yolo_onnx'] == true;
      setState(() {
        _testResult = 'Connesso! SVM: ${svm ? "OK" : "NO"}, '
            'YOLO: ${yolo ? "OK" : "NO"}';
      });
      ref.read(serverUrlProvider.notifier).state = _urlCtrl.text.trim();
    } catch (e) {
      setState(() { _testResult = 'Errore: $e'; });
    } finally {
      setState(() { _testing = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Impostazioni'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Text('Server URL', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          TextField(
            controller: _urlCtrl,
            decoration: const InputDecoration(
              hintText: 'http://192.168.1.100:8000',
              prefixIcon: Icon(Icons.dns),
              border: OutlineInputBorder(),
            ),
            keyboardType: TextInputType.url,
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            icon: _testing
                ? const SizedBox(width: 18, height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.wifi_find),
            label: const Text('Test Connessione'),
            onPressed: _testing ? null : _testConnection,
          ),
          if (_testResult != null) ...[
            const SizedBox(height: 12),
            Text(_testResult!,
                style: TextStyle(
                  color: _testResult!.startsWith('Connesso')
                      ? Colors.green
                      : Colors.red,
                )),
          ],
          const Divider(height: 48),
          Text('Info', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          const ListTile(
            leading: Icon(Icons.info_outline),
            title: Text('Smart OCR v6.0.0'),
            subtitle: Text('CBCL 6-18 Questionnaire Scanner'),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _urlCtrl.dispose();
    super.dispose();
  }
}
