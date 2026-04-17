import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../models/job.dart';
import '../providers/auth_provider.dart';
import '../config.dart';

/// Shows job progress while the backend processes the questionnaire.
class AnalysisScreen extends ConsumerStatefulWidget {
  final String jobId;
  const AnalysisScreen({super.key, required this.jobId});

  @override
  ConsumerState<AnalysisScreen> createState() => _AnalysisScreenState();
}

class _AnalysisScreenState extends ConsumerState<AnalysisScreen> {
  Timer? _timer;
  Job? _job;
  String? _error;

  @override
  void initState() {
    super.initState();
    _startPolling();
  }

  void _startPolling() {
    _poll(); // immediate first poll
    _timer = Timer.periodic(AppConfig.pollInterval, (_) => _poll());
  }

  Future<void> _poll() async {
    try {
      final api = ref.read(apiClientProvider);
      final data = await api.getJobStatus(widget.jobId);
      final job = Job.fromJson(data);

      if (mounted) setState(() { _job = job; _error = null; });

      if (job.isTerminal) {
        _timer?.cancel();
        if (job.status == 'completed' && mounted) {
          // Small delay for UX (show 100% briefly)
          await Future.delayed(const Duration(milliseconds: 500));
          if (mounted) context.go('/results/${widget.jobId}');
        }
      }
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); });
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final job = _job;

    return Scaffold(
      appBar: AppBar(title: const Text('Analisi in corso')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              SizedBox(
                width: 120,
                height: 120,
                child: CircularProgressIndicator(
                  value: job?.progress,
                  strokeWidth: 8,
                ),
              ),
              const SizedBox(height: 32),
              Text(
                job?.currentStep ?? 'Avvio analisi...',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              if (job != null)
                Text('${(job.progress * 100).toInt()}%',
                    style: Theme.of(context).textTheme.headlineMedium),
              if (job?.status == 'failed') ...[
                const SizedBox(height: 16),
                Text(
                  job?.errorMessage ?? 'Errore sconosciuto',
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: () => context.go('/home'),
                  child: const Text('Torna alla home'),
                ),
              ],
              if (_error != null) ...[
                const SizedBox(height: 16),
                Text('Errore connessione: $_error',
                    style: const TextStyle(color: Colors.orange)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
