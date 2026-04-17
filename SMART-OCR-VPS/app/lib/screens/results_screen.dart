import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../models/cbcl_result.dart';
import '../providers/auth_provider.dart';

/// Shows CBCL analysis results with editable item values.
class ResultsScreen extends ConsumerStatefulWidget {
  final String jobId;
  const ResultsScreen({super.key, required this.jobId});

  @override
  ConsumerState<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends ConsumerState<ResultsScreen> {
  CbclResult? _result;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadResults();
  }

  Future<void> _loadResults() async {
    try {
      final api = ref.read(apiClientProvider);
      final data = await api.getJobResults(widget.jobId);
      if (mounted) {
        setState(() {
          _result = CbclResult.fromJson(data);
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(
        appBar: AppBar(title: const Text('Risultati')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    if (_error != null || _result == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Risultati')),
        body: Center(child: Text(_error ?? 'Nessun risultato')),
      );
    }

    final result = _result!;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Risultati CBCL'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/home'),
        ),
      ),
      body: Column(
        children: [
          // Summary cards
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                _buildMetricCard(context, 'Totale',
                    '${result.totalScore}', Colors.blue),
                const SizedBox(width: 8),
                _buildMetricCard(context, 'Rilevati',
                    '${result.statistics['items_scored'] ?? 0}', Colors.green),
                const SizedBox(width: 8),
                _buildMetricCard(context, 'Mancanti',
                    '${result.statistics['items_missing'] ?? 0}', Colors.orange),
              ],
            ),
          ),

          // Item list
          Expanded(
            child: ListView.builder(
              itemCount: result.items.length,
              itemBuilder: (context, index) {
                final entry = result.items.entries.elementAt(index);
                return _buildItemTile(entry.key, entry.value);
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMetricCard(BuildContext ctx, String label, String value, Color color) {
    return Expanded(
      child: Card(
        color: color.withValues(alpha: 0.1),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
          child: Column(
            children: [
              Text(value, style: TextStyle(
                  fontSize: 24, fontWeight: FontWeight.bold, color: color)),
              Text(label, style: Theme.of(ctx).textTheme.bodySmall),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildItemTile(String itemId, CbclItem item) {
    final hasValue = item.value != null;
    final color = item.flag == null
        ? Colors.green
        : item.flag == 'missing'
            ? Colors.grey
            : Colors.orange;

    return ListTile(
      leading: CircleAvatar(
        backgroundColor: color.withValues(alpha: 0.2),
        child: Text(
          hasValue ? '${item.value}' : '-',
          style: TextStyle(color: color, fontWeight: FontWeight.bold),
        ),
      ),
      title: Text('Item $itemId'),
      subtitle: item.flag != null ? Text(item.flag!) : null,
      trailing: Text(
        hasValue ? '${(item.confidence * 100).toInt()}%' : '',
        style: TextStyle(color: Colors.grey[600], fontSize: 12),
      ),
      onTap: () => _editItem(itemId, item),
    );
  }

  Future<void> _editItem(String itemId, CbclItem item) async {
    final newValue = await showDialog<int>(
      context: context,
      builder: (ctx) => SimpleDialog(
        title: Text('Item $itemId'),
        children: [0, 1, 2].map((v) =>
          SimpleDialogOption(
            onPressed: () => Navigator.pop(ctx, v),
            child: ListTile(
              leading: Radio<int>(value: v, groupValue: item.value, onChanged: (_) {}),
              title: Text('$v'),
              selected: item.value == v,
            ),
          ),
        ).toList(),
      ),
    );

    if (newValue != null && newValue != item.value) {
      // Update locally and recompute
      setState(() {
        _result = CbclResult(
          items: Map.from(_result!.items)
            ..[itemId] = CbclItem(value: newValue, confidence: 1.0),
          scoring: _result!.scoring,
          reportFinale: _result!.reportFinale,
          subscaleScores: _result!.subscaleScores,
          totalScore: _result!.totalScore,
          statistics: _result!.statistics,
          method: _result!.method,
          processingTimeMs: _result!.processingTimeMs,
        );
      });

      // Recompute scores on server
      try {
        final items = <String, int>{};
        for (final e in _result!.items.entries) {
          if (e.value.value != null) items[e.key] = e.value.value!;
        }

        final api = ref.read(apiClientProvider);
        final recomputed = await api.recomputeScores(items: items);

        if (mounted) {
          setState(() {
            _result = CbclResult(
              items: _result!.items,
              scoring: recomputed['scoring'] as Map<String, dynamic>? ?? {},
              reportFinale: recomputed['report_finale'] as Map<String, dynamic>? ?? {},
              subscaleScores: recomputed['subscale_scores'] as Map<String, dynamic>? ?? {},
              totalScore: recomputed['total_score'] as int? ?? 0,
              statistics: recomputed['statistics'] as Map<String, dynamic>? ?? {},
              method: _result!.method,
              processingTimeMs: _result!.processingTimeMs,
            );
          });
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Errore re-scoring: $e')),
          );
        }
      }
    }
  }
}
