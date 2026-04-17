/// Job status from the backend API.
class Job {
  final String jobId;
  final String status;
  final double progress;
  final String? currentStep;
  final DateTime createdAt;
  final DateTime? completedAt;
  final double? durationSeconds;
  final String? errorMessage;

  const Job({
    required this.jobId,
    required this.status,
    this.progress = 0.0,
    this.currentStep,
    required this.createdAt,
    this.completedAt,
    this.durationSeconds,
    this.errorMessage,
  });

  bool get isTerminal =>
      status == 'completed' || status == 'failed' || status == 'cancelled';

  factory Job.fromJson(Map<String, dynamic> json) => Job(
        jobId: json['job_id'] as String,
        status: json['status'] as String,
        progress: (json['progress'] as num?)?.toDouble() ?? 0.0,
        currentStep: json['current_step'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
        completedAt: json['completed_at'] != null
            ? DateTime.parse(json['completed_at'] as String)
            : null,
        durationSeconds: (json['duration_seconds'] as num?)?.toDouble(),
        errorMessage: json['error_message'] as String?,
      );
}
