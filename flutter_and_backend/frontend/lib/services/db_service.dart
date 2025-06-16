import 'dart:convert';
import 'package:http/http.dart' as http;

class DBService {
  DBService._();
  static final DBService instance = DBService._();

  static const _apiBase = 'http://localhost:8888';

  /* ───────── tablas soportadas ───────── */
  static const List<String> _tables = [
    'versions',
    'champions',
    'leaguepedia_games',
  ];

  /* ───────── caché ───────── */
  final Map<String, List<Map<String, dynamic>>> _rowsCache = {};
  List<String>? _championNamesCache;

  /// cache en memoria para los game-states completos
  Map<String, dynamic>? _allGameStatesCache;

  /* ───────── tabla fija ───────── */
  Future<List<String>> getTableNames() async => _tables;

  /* ───────── Nombres de campeón ───────── */
  Future<List<String>> getChampionNames() async {
    if (_championNamesCache != null) return _championNamesCache!;
    final res = await http.get(
      Uri.parse('$_apiBase/api/riot/champions/names'),
    );
    if (res.statusCode != 200) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }
    final decoded = jsonDecode(res.body) as Map<String, dynamic>;
    _championNamesCache =
        (decoded['champion_names'] as List<dynamic>).cast<String>();
    return _championNamesCache!;
  }

  /* ───────── Filas por tabla ───────── */
  Future<List<Map<String, dynamic>>> getTableRows(String table) async {
    if (!_tables.contains(table)) {
      throw ArgumentError('Tabla no soportada: $table');
    }

    if (_rowsCache.containsKey(table)) return _rowsCache[table]!;

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

    final res = await http.get(uri);
    if (res.statusCode != 200) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }

    final decoded = jsonDecode(res.body) as Map<String, dynamic>;
    late List<Map<String, dynamic>> rows;

    switch (table) {
      case 'versions':
        final list = (decoded['versions'] as List).cast<String>();
        rows = [
          for (int i = 0; i < list.length; i++)
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

  /* ───────── NUEVOS END-POINTS ───────── */

  /// Devuelve **los roles** de un campeón concreto o `null` si no existen.
  Future<String?> getRolesOfChampion(String championName) async {
    final clean = championName.replaceAll("’", "").replaceAll("'", "").trim();
    final uri = Uri.parse('$_apiBase/api/riot/champions/$clean/roles');

    final res = await http.get(uri);
    if (res.statusCode == 404) return null;
    if (res.statusCode != 200) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }

    final decoded = jsonDecode(res.body) as Map<String, dynamic>;
    return decoded['roles'] as String;
  }

  /// Devuelve los campeones cuyo campo **roles** coincide exactamente
  /// con `roles`.
  Future<List<String>> getChampionsByRoles(String roles) async {
    final uri = Uri.parse(
      '$_apiBase/api/riot/champions/by_roles'
      '?roles=${Uri.encodeQueryComponent(roles)}',
    );

    final res = await http.get(uri);
    if (res.statusCode != 200) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }

    final decoded = jsonDecode(res.body) as Map<String, dynamic>;
    return (decoded['champions'] as List<dynamic>).cast<String>();
  }

  /// ──────── ⏩ NUEVO ⏩ ────────
  /// Recupera **todos** los `game_state.json` guardados en el backend
  /// (clave = _slug_ de la partida).
  ///
  /// El resultado queda cacheado en memoria; pasa `forceRefresh: true`
  /// para forzar una nueva descarga.
  Future<Map<String, dynamic>> getAllGameStates({bool forceRefresh = false}) async {
    if (!forceRefresh && _allGameStatesCache != null) {
      return _allGameStatesCache!;
    }

    final res = await http.get(Uri.parse('$_apiBase/api/game_state/all'));
    if (res.statusCode != 200) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }

    final decoded = jsonDecode(res.body) as Map<String, dynamic>;
    final states = decoded['matches'] as Map<String, dynamic>;
    _allGameStatesCache = states;
    return states;
  }

  /* ───────── ACTUALIZAR BBDD COMPLETA ───────── */
  Future<Map<String, dynamic>> updateFullDatabase() async {
    final res =
        await http.post(Uri.parse('$_apiBase/api/riot/database/update'));
    if (res.statusCode != 200) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }
    invalidateCache();
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  /* ───────── Limpiar caché ───────── */
  void invalidateCache() {
    _rowsCache.clear();
    _championNamesCache = null;
    _allGameStatesCache = null;
  }
}
