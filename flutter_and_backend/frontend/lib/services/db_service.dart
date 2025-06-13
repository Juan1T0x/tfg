// lib/services/db_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class DBService {
  DBService._();
  static final DBService instance = DBService._();

  static const _apiBase = 'http://localhost:8888';

  // Guarda en memoria los nombres de tabla y la caché de filas para evitar peticiones redundantes
  List? _tableNamesCache;
  final Map<String, List<Map<String, dynamic>>> _rowsCache = {};

  /// Devuelve la lista de tablas disponibles en el backend
  Future<List> getTableNames() async {
    if (_tableNamesCache != null) return _tableNamesCache!;
    final res = await http.get(Uri.parse('$_apiBase/api/database'));
    if (res.statusCode != 200) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }

    final Map<String, dynamic> decoded = jsonDecode(res.body);
    _tableNamesCache = decoded.keys.toList();
    return _tableNamesCache!;
  }

  /// Devuelve todas las filas de una tabla concreta
  Future<List<Map<String, dynamic>>> getTableRows(String table) async {
    if (_rowsCache.containsKey(table)) return _rowsCache[table]!;
    final res = await http.get(Uri.parse('$_apiBase/api/database/$table'));
    if (res.statusCode != 200) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }

    final Map<String, dynamic> decoded = jsonDecode(res.body);
    final List<dynamic> rawRows = decoded[table] as List<dynamic>;
    final rows = rawRows.cast<Map<String, dynamic>>();

    _rowsCache[table] = rows;
    return rows;
  }

  /// Limpia las cachés (por ejemplo, si la BBDD se actualiza)
  void invalidateCache() {
    _tableNamesCache = null;
    _rowsCache.clear();
  }
}
