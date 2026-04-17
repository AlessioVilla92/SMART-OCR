/// Complete analysis result from the backend.
class CbclResult {
  final Map<String, CbclItem> items;
  final Map<String, dynamic> scoring;
  final Map<String, dynamic> reportFinale;
  final Map<String, dynamic> subscaleScores;
  final int totalScore;
  final Map<String, dynamic> statistics;
  final String? method;
  final int? processingTimeMs;

  const CbclResult({
    required this.items,
    required this.scoring,
    required this.reportFinale,
    required this.subscaleScores,
    required this.totalScore,
    required this.statistics,
    this.method,
    this.processingTimeMs,
  });

  factory CbclResult.fromJson(Map<String, dynamic> json) {
    final itemsMap = <String, CbclItem>{};
    final rawItems = json['items'] as Map<String, dynamic>? ?? {};
    for (final entry in rawItems.entries) {
      itemsMap[entry.key] = CbclItem.fromJson(entry.value as Map<String, dynamic>);
    }

    return CbclResult(
      items: itemsMap,
      scoring: json['scoring'] as Map<String, dynamic>? ?? {},
      reportFinale: json['report_finale'] as Map<String, dynamic>? ?? {},
      subscaleScores: json['subscale_scores'] as Map<String, dynamic>? ?? {},
      totalScore: json['total_score'] as int? ?? 0,
      statistics: json['statistics'] as Map<String, dynamic>? ?? {},
      method: json['method'] as String?,
      processingTimeMs: json['processing_time_ms'] as int?,
    );
  }
}

/// Single CBCL item (question) result.
class CbclItem {
  final int? value;
  final String? flag;
  final double confidence;

  const CbclItem({this.value, this.flag, this.confidence = 0.0});

  factory CbclItem.fromJson(Map<String, dynamic> json) => CbclItem(
        value: json['value'] as int?,
        flag: json['flag'] as String?,
        confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      );

  Map<String, dynamic> toJson() => {
        'value': value,
        'flag': flag,
        'confidence': confidence,
      };
}
