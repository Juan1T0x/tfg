// lib/services/image_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;

/// Cliente muy ligero para las imágenes de campeones
/// expuestas por los end-points de `/api/riot/images/…`.
class ImageService {
  // Cambia host/puerto si tu backend escucha en otro sitio
  static const String _apiBase = 'http://localhost:8888';

  /*────────────────── LISTAS POR TIPO ──────────────────*/

  Future<List<String>> fetchIcons() async =>
      _fetchList('$_apiBase/api/riot/images/icons', 'icons');

  Future<List<String>> fetchSplashArts() async =>
      _fetchList('$_apiBase/api/riot/images/splash_arts', 'splash_arts');

  Future<List<String>> fetchLoadingScreens() async =>
      _fetchList('$_apiBase/api/riot/images/loading_screens',
          'loading_screens');

  /*────────────────── 3 IMÁGENES DE UN CAMPEÓN ──────────────────*/

  /// Devuelve un `Map` con las tres URLs
  /// (`icon`, `splash_art`, `loading_screen`) para `championKey`
  /// (Aatrox, DrMundo, KhaZix, …).
  ///
  /// Lanza una excepción si el backend responde con error.
  Future<Map<String, String>> fetchImagesForChampion(
      String championKey) async {
    final uri = Uri.parse('$_apiBase/api/riot/images/$championKey');
    final res = await http.get(uri);

    if (res.statusCode != 200) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }

    final decoded = jsonDecode(res.body) as Map<String, dynamic>;
    return <String, String>{
      'icon': decoded['icon'] as String,
      'splash_art': decoded['splash_art'] as String,
      'loading_screen': decoded['loading_screen'] as String,
    };
  }

  /*────────────────── helper interno ──────────────────*/
  Future<List<String>> _fetchList(String url, String key) async {
    final res = await http.get(Uri.parse(url));

    if (res.statusCode != 200) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }

    final decoded = jsonDecode(res.body) as Map<String, dynamic>;
    return (decoded[key] as List<dynamic>).cast<String>();
  }
}
