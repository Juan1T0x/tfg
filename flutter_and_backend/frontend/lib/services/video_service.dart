// lib/services/video_service.dart
//
// Cliente REST unificado para todas las operaciones de vídeo:
//   • Cola “processVideoSignal”            →  extracción diferida (worker)
//   • “extractFrameNow”                    →  extracción inmediata
//   • “downloadVideo”                      →  descarga del vídeo completo
//
// NOTA:  Todos los endpoints viven ahora bajo el prefijo /api/video
//        según la reorganización del backend.
//

import 'dart:convert';
import 'package:http/http.dart' as http;

/// Encapsula todas las llamadas al API de vídeo del backend.
class VideoService {
  /// Crea una instancia “ligera”; no mantiene estado interno.
  const VideoService();

  /// Cambia esto si tu backend no corre en localhost:8888
  static const _apiBase = 'http://localhost:8888';

  // ────────────────────────────────────────────────────────────────
  // 1)  Descargar vídeo completo
  // ────────────────────────────────────────────────────────────────
  ///
  /// Devuelve el cuerpo JSON como `Map<String, dynamic>` cuando la
  /// respuesta es un código 2xx.  Lanza [Exception] para cualquier
  /// otro status code.
  ///
  Future<Map<String, dynamic>> downloadVideo(String youtubeUrl) async {
    final res = await http.post(
      Uri.parse('$_apiBase/api/video/downloadVideo'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'url': youtubeUrl}),
    );

    if (res.statusCode ~/ 100 != 2) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  // ────────────────────────────────────────────────────────────────
  // 2)  Enviar señal para extraer un frame (cola + worker)
  // ────────────────────────────────────────────────────────────────
  ///
  /// Encola la extracción del frame que corresponde a [seconds] en
  /// el vídeo [url].  Si se proporciona [onLog], escribe trazas de
  /// depuración antes/después de la petición.
  ///
  Future<void> queueFrameExtraction(
    String url,
    double seconds, {
    void Function(String line)? onLog,
  }) async {
    onLog?.call('⏩ encolando  ${_short(url)} @ ${seconds.toStringAsFixed(2)}');

    final res = await http.post(
      Uri.parse('$_apiBase/api/video/processVideoSignal'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'url': url, 'time': seconds}),
    );

    if (res.statusCode ~/ 100 != 2) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }
  }

  // ────────────────────────────────────────────────────────────────
  // 3)  Extraer frame *ya mismo* (sin pasar por la cola)
  // ────────────────────────────────────────────────────────────────
  ///
  /// Devuelve el JSON decodificado con los metadatos del frame
  /// generado (nombre de archivo, ruta absoluta,…).
  ///
  Future<Map<String, dynamic>> extractFrameNow(
    String url,
    double seconds,
  ) async {
    final res = await http.post(
      Uri.parse('$_apiBase/api/video/extractFrameNow'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'url': url, 'time': seconds}),
    );

    if (res.statusCode ~/ 100 != 2) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  // ────────────────────────────────────────────────────────────────
  //  Helper: acorta la URL para logs
  // ────────────────────────────────────────────────────────────────
  String _short(String url) =>
      url.replaceAll(RegExp(r'https?://(www\.)?'), '');
}
