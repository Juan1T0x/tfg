// lib/services/db_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;

/// Wrapper centralizado para todas las lecturas “simples” que hace
/// el front-end sobre la base de datos expuesta por el backend.
///
/// *  /api/riot/versions              → lista de versiones
/// *  /api/riot/champions             → tabla completa de campeones
/// *  /api/riot/champions/names       → solo nombres de campeones
/// *  /api/database/leaguepedia_games → tabla leaguepedia
class DBService {
  DBService._();
  static final DBService instance = DBService._();

  static const _apiBase = 'http://localhost:8888';

  /*────────────────── tablas soportadas ──────────────────*/
  static const List<String> _tables = [
    'versions',
    'champions',
    'leaguepedia_games',
  ];

  /*────────────────── caché en memoria ──────────────────*/
  final Map<String, List<Map<String, dynamic>>> _rowsCache = {};
  List<String>? _championNamesCache;            // ← NUEVO

  /*────────────────── tablas disponibles ─────────────────*/
  Future<List<String>> getTableNames() async => _tables;

  /*────────────────── nombres de campeón ─────────────────*/
  Future<List<String>> getChampionNames() async {
    if (_championNamesCache != null) return _championNamesCache!;

    final res = await http
        .get(Uri.parse('$_apiBase/api/riot/champions/names'));

    if (res.statusCode != 200) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }

    final decoded = jsonDecode(res.body) as Map<String, dynamic>;
    _championNamesCache =
        (decoded['champion_names'] as List<dynamic>).cast<String>();

    return _championNamesCache!;
  }

  /*────────────────── filas por tabla ───────────────────*/
  Future<List<Map<String, dynamic>>> getTableRows(String table) async {
    if (!_tables.contains(table)) {
      throw ArgumentError('Tabla no soportada: $table');
    }

    // caché rápida
    if (_rowsCache.containsKey(table)) return _rowsCache[table]!;

    // ----------- Selección de endpoint ----------
    late Uri uri;
    switch (table) {
      case 'versions':
        uri = Uri.parse('$_apiBase/api/riot/versions');
        break;
      case 'champions':
        uri = Uri.parse('$_apiBase/api/riot/champions');
        break;
      case 'leaguepedia_games':
        uri = Uri.parse('$_apiBase/api/database/leaguepedia_games');
        break;
    }

    // ------------ Petición ------------
    final res = await http.get(uri);
    if (res.statusCode != 200) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }

    final decoded = jsonDecode(res.body) as Map<String, dynamic>;
    late List<Map<String, dynamic>> rows;

    // ------------ Adaptación a formato uniforme ------------
    switch (table) {
      case 'versions':
        final list = (decoded['versions'] as List).cast<String>();
        rows = [
          for (var i = 0; i < list.length; i++)
            {'version_id': i, 'version': list[i]}
        ];
        break;

      case 'champions':
        rows = (decoded['champions'] as List).cast<Map<String, dynamic>>();
        break;

      case 'leaguepedia_games':
        rows = (decoded['leaguepedia_games'] as List)
            .cast<Map<String, dynamic>>();
        break;
    }

    _rowsCache[table] = rows;
    return rows;
  }

  /*────────────────── limpiar caché ───────────────────*/
  void invalidateCache() {
    _rowsCache.clear();
    _championNamesCache = null;
  }
}
