// lib/services/backend_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class BackendService {
  // singleton
  static final BackendService _singleton = BackendService._internal();
  factory BackendService() => _singleton;
  BackendService._internal();

  static const _apiBase = 'http://localhost:8888';

  /// Envía (URL, segundo) al backend.
  Future<void> sendProcessSignal(
    String url,
    double seconds, {
    void Function(String line)? onLog,
  }) async {
    onLog?.call('⏩ enviando  ${_short(url)} @ ${seconds.toStringAsFixed(2)}');

    final res = await http.post(
      Uri.parse('$_apiBase/api/processvideosignal'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'url': url, 'time': seconds}),
    );

    if (res.statusCode != 200) {
      throw Exception(
          'Backend ${res.statusCode}: ${res.body.isNotEmpty ? res.body : 'sin cuerpo'}');
    }
  }

  /// No hay WebSocket que cerrar, pero por simetría…
  void dispose() {}

  String _short(String url) =>
      url.replaceAll(RegExp(r'https?://(www\.)?'), '');
}
