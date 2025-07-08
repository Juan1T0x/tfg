import 'dart:convert';
import 'package:http/http.dart' as http;

class DBService {
  DBService._();
  static final DBService instance = DBService._();

  static const _apiBase = 'http://localhost:8888';

  static const List<String> _tables = [
    'versions',
    'champions',
    'leaguepedia_games',
  ];

  final Map<String, List<Map<String, dynamic>>> _rowsCache = {};
  List<String>? _championNamesCache;
  Map<String, dynamic>? _allGameStatesCache;

  /* ─────────── tablas auxiliares ─────────── */
  Future<List<String>> getTableNames() async => _tables;

  Future<List<String>> getChampionNames() async {
    if (_championNamesCache != null) return _championNamesCache!;
    final res = await http.get(Uri.parse('$_apiBase/api/riot/champions/names'));
    if (res.statusCode != 200) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }
    final decoded = jsonDecode(res.body) as Map<String, dynamic>;
    _championNamesCache =
        (decoded['champion_names'] as List<dynamic>).cast<String>();
    return _championNamesCache!;
  }

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

  /* ─────────── endpoints Riot extra ─────────── */
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

  Future<List<String>> getChampionsByRoles(String roles) async {
    final uri = Uri.parse(
      '$_apiBase/api/riot/champions/by_roles?roles=${Uri.encodeQueryComponent(roles)}',
    );
    final res = await http.get(uri);
    if (res.statusCode != 200) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }
    final decoded = jsonDecode(res.body) as Map<String, dynamic>;
    return (decoded['champions'] as List<dynamic>).cast<String>();
  }

  /* ─────────── game-state helpers ─────────── */
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

  /* ─────────── análisis completo ─────────── */
  Future<Map<String, dynamic>> generateAllVisuals(String matchSlug) async {
    final uri = Uri.parse('$_apiBase/api/game_state/$matchSlug/analysis');
    final res = await http.post(uri);
    if (res.statusCode != 202) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  /* ─────────── actualizar BBDD Riot ─────────── */
  Future<Map<String, dynamic>> updateFullDatabase() async {
    final res =
        await http.post(Uri.parse('$_apiBase/api/riot/database/update'));
    if (res.statusCode != 200) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }
    invalidateCache();
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  /* ─────────── utilidades varias ─────────── */
  void invalidateCache() {
    _rowsCache.clear();
    _championNamesCache = null;
    _allGameStatesCache = null;
  }

  /* ─────────── visualización (PNG) ─────────── */
  Future<List<String>> _getVisuals(
    String matchSlug,
    String endpointSuffix,
    String jsonKey,
  ) async {
    final uri = Uri.parse('$_apiBase/api/game_state/$matchSlug/visuals$endpointSuffix');
    final res = await http.get(uri);
    if (res.statusCode != 200) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }
    final decoded = jsonDecode(res.body) as Map<String, dynamic>;
    return (decoded[jsonKey] as List<dynamic>).cast<String>();
  }

  Future<List<String>> getVisualsCsDiff(String matchSlug) =>
      _getVisuals(matchSlug, '/cs_diff', 'cs_diff');

  Future<List<String>> getVisualsCsTotal(String matchSlug) =>
      _getVisuals(matchSlug, '/cs_total', 'cs_total');

  Future<List<String>> getVisualsGoldDiff(String matchSlug) =>
      _getVisuals(matchSlug, '/gold_diff', 'gold_diff');

  Future<List<String>> getVisualsHeatMaps(String matchSlug) =>
      _getVisuals(matchSlug, '/heat_maps', 'heat_maps');

  Future<Map<String, List<String>>> getVisualsAll(String matchSlug) async {
    final uri = Uri.parse('$_apiBase/api/game_state/$matchSlug/visuals');
    final res = await http.get(uri);
    if (res.statusCode != 200) {
      throw Exception('Backend ${res.statusCode}: ${res.body}');
    }
    final decoded = jsonDecode(res.body) as Map<String, dynamic>;
    final vis = decoded['visuals'] as Map<String, dynamic>;
    return {
      'cs_diff':   (vis['cs_diff']   as List).cast<String>(),
      'cs_total':  (vis['cs_total']  as List).cast<String>(),
      'gold_diff': (vis['gold_diff'] as List).cast<String>(),
      'heat_maps': (vis['heat_maps'] as List).cast<String>(),
    };
  }
}
