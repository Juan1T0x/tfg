// lib/services/pipeline_service.dart
//
// Cliente muy ligero para el **Pipeline API**:
//
//   POST /api/pipeline/startChampionSelect
//
// ─────────────────────────────────────────────────────────────────────────
// Ejemplo de uso:
//
//   final data = await PipelineService.instance.startChampionSelect(
//     matchTitle: 'Azure Drakes vs Crimson Foxes',
//     youtubeUrl : 'https://youtu.be/abc123DEF',
//     minute     : 12,
//     second     : 34,
//   );
//
//   print('Blue team -> ${data['champions']['blue']}');
//   print('Red team  -> ${data['champions']['red']}');
//
import 'dart:convert';
import 'package:http/http.dart' as http;

class PipelineService {
  PipelineService._();
  static final PipelineService instance = PipelineService._();

  static const String _apiBase = 'http://localhost:8888';

  /// Lanza el pipeline de *champ-select*.
  ///
  /// Devuelve el JSON completo (decoded) que envía el backend:
  /// ```json
  /// {
  ///   "status"      : "created",
  ///   "match_title" : "…",
  ///   "frame_file"  : "e7d4…c9.jpg",
  ///   "champions"   : { "blue": ["Gwen", …], "red": ["Camille", …] }
  /// }
  /// ```
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
      'minute'     : minute,
      'second'     : second,
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
}
