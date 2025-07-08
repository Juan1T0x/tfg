// lib/services/pipeline_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class PipelineService {
  PipelineService._();
  static final PipelineService instance = PipelineService._();

  static const String _apiBase = 'http://localhost:8888';

  Future<Map<String, dynamic>> startChampionSelect({
    required String matchTitle,
    required String youtubeUrl,
    required int minute,
    required int second,
  }) async {
    final uri  = Uri.parse('$_apiBase/api/pipeline/startChampionSelect');
    final body = jsonEncode({
      'match_title': matchTitle,
      'youtube_url': youtubeUrl,
      'minute': minute,
      'second': second,
    });

    final res = await http.post(
      uri,
      headers: const {'Content-Type': 'application/json'},
      body: body,
    );

    if (res.statusCode != 201) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  /// Encola el procesamiento de un fotograma de **mid-game**.
  ///
  /// Devuelve el JSON que envía el backend:
  /// ```json
  /// {
  ///   "status"      : "queued",
  ///   "match_title" : "…",
  ///   "frame_file"  : "e7d4…c9.jpg"
  /// }
  /// ```
  Future<Map<String, dynamic>> processMainGame({
    required String matchTitle,
    required String youtubeUrl,
    required int minute,
    required int second,
  }) async {
    final uri  = Uri.parse('$_apiBase/api/pipeline/processMainGame');
    final body = jsonEncode({
      'match_title': matchTitle,
      'youtube_url': youtubeUrl,
      'minute': minute,
      'second': second,
    });

    final res = await http.post(
      uri,
      headers: const {'Content-Type': 'application/json'},
      body: body,
    );

    if (res.statusCode != 202) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }
}
