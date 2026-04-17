import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import '../config.dart';
import '../providers/auth_provider.dart';

/// Sequential capture of 3 CBCL pages with preview and retake.
class CameraScreen extends ConsumerStatefulWidget {
  const CameraScreen({super.key});

  @override
  ConsumerState<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends ConsumerState<CameraScreen> {
  final _picker = ImagePicker();
  final List<File?> _photos = [null, null, null];
  int _currentPage = 0;
  bool _uploading = false;
  double _uploadProgress = 0;

  Future<void> _takePhoto() async {
    final picked = await _picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 95,
      maxWidth: 3000,
    );
    if (picked != null) {
      setState(() {
        _photos[_currentPage] = File(picked.path);
        if (_currentPage < 2) _currentPage++;
      });
    }
  }

  Future<void> _pickFromGallery() async {
    final picked = await _picker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 95,
    );
    if (picked != null) {
      setState(() {
        _photos[_currentPage] = File(picked.path);
        if (_currentPage < 2) _currentPage++;
      });
    }
  }

  bool get _allCaptured => _photos.every((p) => p != null);

  Future<void> _upload() async {
    if (!_allCaptured) return;

    setState(() { _uploading = true; _uploadProgress = 0; });

    try {
      final api = ref.read(apiClientProvider);
      final jobId = await api.createJob(
        page4: _photos[0]!,
        page5: _photos[1]!,
        page6: _photos[2]!,
        onProgress: (sent, total) {
          if (total > 0) {
            setState(() { _uploadProgress = sent / total; });
          }
        },
      );
      if (mounted) context.go('/analysis/$jobId');
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Errore upload: $e')),
        );
      }
    } finally {
      if (mounted) setState(() { _uploading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Cattura Pagine'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: Column(
        children: [
          // Page selector
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: List.generate(3, (i) => _buildPageChip(i)),
            ),
          ),

          // Preview area
          Expanded(
            child: _photos[_currentPage] != null
                ? Stack(
                    fit: StackFit.expand,
                    children: [
                      Image.file(_photos[_currentPage]!, fit: BoxFit.contain),
                      Positioned(
                        bottom: 16,
                        right: 16,
                        child: FloatingActionButton.small(
                          onPressed: () => setState(() { _photos[_currentPage] = null; }),
                          child: const Icon(Icons.refresh),
                        ),
                      ),
                    ],
                  )
                : Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.photo_camera_outlined,
                            size: 80, color: Colors.grey[400]),
                        const SizedBox(height: 16),
                        Text(AppConfig.cbclPageLabels[_currentPage],
                            style: Theme.of(context).textTheme.titleLarge),
                        const SizedBox(height: 8),
                        const Text('Fotografa o seleziona dalla galleria'),
                      ],
                    ),
                  ),
          ),

          // Buttons
          Padding(
            padding: const EdgeInsets.all(16),
            child: _uploading
                ? Column(
                    children: [
                      LinearProgressIndicator(value: _uploadProgress),
                      const SizedBox(height: 8),
                      const Text('Caricamento in corso...'),
                    ],
                  )
                : Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          icon: const Icon(Icons.photo_library),
                          label: const Text('Galleria'),
                          onPressed: _pickFromGallery,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: FilledButton.icon(
                          icon: const Icon(Icons.camera_alt),
                          label: const Text('Scatta'),
                          onPressed: _takePhoto,
                        ),
                      ),
                      if (_allCaptured) ...[
                        const SizedBox(width: 12),
                        Expanded(
                          child: FilledButton.tonalIcon(
                            icon: const Icon(Icons.send),
                            label: const Text('Analizza'),
                            onPressed: _upload,
                          ),
                        ),
                      ],
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildPageChip(int index) {
    final captured = _photos[index] != null;
    final selected = _currentPage == index;

    return ChoiceChip(
      label: Text(AppConfig.cbclPageLabels[index]),
      selected: selected,
      avatar: Icon(captured ? Icons.check_circle : Icons.circle_outlined,
          size: 18),
      onSelected: (_) => setState(() { _currentPage = index; }),
    );
  }
}
