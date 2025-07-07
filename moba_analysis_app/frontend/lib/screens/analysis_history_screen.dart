import 'dart:convert';
import 'package:flutter/material.dart';
import '../layouts/main_layout.dart';
import '../widgets/side_nav.dart';
import '../theme/app_colors.dart';
import '../services/db_service.dart';

class AnalysisHistoryScreen extends StatefulWidget {
  const AnalysisHistoryScreen({super.key});

  @override
  State<AnalysisHistoryScreen> createState() => _AnalysisHistoryScreenState();
}

class _AnalysisHistoryScreenState extends State<AnalysisHistoryScreen> {
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  static const int _navIndex = 5;

  late Future<Map<String, dynamic>> _matchesF;
  String? _selectedSlug;

  String? _selectedCategory;              // ‘game_state’, ‘heat_maps’, …
  List<String> _urls = [];                // urls devueltas por endpoint
  List<String> _lvl1 = [];                // primer nivel
  List<String> _lvl2 = [];                // segundo nivel
  List<String> _lvl3 = [];                // png finales
  String? _pickedImage;                   // png seleccionado

  String? _currentL1;                     // elemento lvl-1 activo
  String? _currentL2;                     // elemento lvl-2 activo

  @override
  void initState() {
    super.initState();
    _matchesF = DBService.instance.getAllGameStates();
  }

  /* ─────────────────── cargar categoría ─────────────────── */

  Future<void> _loadCategory(String cat) async {
    if (_selectedSlug == null) return;

    _selectedCategory = cat;
    _pickedImage = null;
    _urls = [];
    _lvl1 = [];
    _lvl2 = [];
    _lvl3 = [];
    _currentL1 = null;
    _currentL2 = null;

    switch (cat) {
      case 'heat_maps':
        _urls = await DBService.instance.getVisualsHeatMaps(_selectedSlug!);
        break;
      case 'cs_diff':
        _urls = await DBService.instance.getVisualsCsDiff(_selectedSlug!);
        break;
      case 'cs_total':
        _urls = await DBService.instance.getVisualsCsTotal(_selectedSlug!);
        break;
      case 'gold_diff':
        _urls = await DBService.instance.getVisualsGoldDiff(_selectedSlug!);
        break;
      default:
        _urls = [];
    }

    if (_urls.isNotEmpty) {
      _lvl1 = _urls
          .map((u) => Uri.parse(u).pathSegments)
          .map((s) => s[s.indexOf(_selectedCategory!) + 1])
          .toSet()
          .toList()
        ..sort();
    }
    setState(() {});
  }

  /* ─────────────────── selección niveles ─────────────────── */

  void _selectLvl1(String l1) {
    _currentL1 = l1;
    _currentL2 = null;
    _pickedImage = null;

    _lvl2 = _urls
        .where((u) => u.contains('/$l1/'))
        .map((u) {
          final segs = Uri.parse(u).pathSegments;
          final idx = segs.indexOf(l1) + 1;
          return idx < segs.length - 1 ? segs[idx] : null;
        })
        .whereType<String>()
        .toSet()
        .toList()
      ..sort();

    // si no existe segundo nivel vamos directos a los png
    _lvl3 = _lvl2.isEmpty
        ? (_urls.where((u) => u.contains('/$l1/')).toList()..sort())
        : [];

    setState(() {});
  }

  void _selectLvl2(String l2) {
    if (_currentL1 == null) return;

    _currentL2 = l2;
    _pickedImage = null;

    _lvl3 = _urls
        .where((u) => u.contains('/$_currentL1/') && u.contains('/$l2/'))
        .toList()
      ..sort();
    setState(() {});
  }

  /* ─────────────────── UI central ─────────────────── */

  Widget _buildCenter(Map<String, dynamic> matches) {
    if (_selectedSlug == null) {
      return const Center(
        child: Text(
          'Selecciona una partida a la izquierda',
          style: TextStyle(fontSize: 18, fontStyle: FontStyle.italic),
        ),
      );
    }

    if (_selectedCategory == null || _selectedCategory == 'game_state') {
      final jsonPretty =
          const JsonEncoder.withIndent('  ').convert(matches[_selectedSlug]);
      return Padding(
        padding: const EdgeInsets.all(16),
        child: Scrollbar(
          thumbVisibility: true,
          child: SingleChildScrollView(
            child: SelectableText(
              jsonPretty,
              style: const TextStyle(fontFamily: 'RobotoMono', fontSize: 13),
            ),
          ),
        ),
      );
    }

    if (_pickedImage != null) {
      return InteractiveViewer(child: Image.network(_pickedImage!));
    }

    if (_lvl3.isNotEmpty) {
      return GridView.count(
        crossAxisCount: 3,
        children: _lvl3
            .map((u) => InkWell(
                  onTap: () => setState(() => _pickedImage = u),
                  child: Card(
                    clipBehavior: Clip.hardEdge,
                    child: Image.network(u, fit: BoxFit.cover),
                  ),
                ))
            .toList(),
      );
    }

    if (_lvl2.isNotEmpty) {
      return ListView(
        children: _lvl2
            .map((l2) => ListTile(
                  title: Text(l2),
                  onTap: () => _selectLvl2(l2),
                ))
            .toList(),
      );
    }

    if (_lvl1.isNotEmpty) {
      return ListView(
        children: _lvl1
            .map((l1) => ListTile(
                  title: Text(l1),
                  onTap: () => _selectLvl1(l1),
                ))
            .toList(),
      );
    }

    return const Center(child: Text('Sin datos'));
  }

  /* ═════════════ MAIN BUILD ═════════════ */

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: _scaffoldKey,
      drawer: Drawer(
        width: 250,
        child: Align(
          alignment: Alignment.topLeft,
          child: SideNav(selectedIndex: _navIndex),
        ),
      ),
      body: FutureBuilder<Map<String, dynamic>>(
        future: _matchesF,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(child: Text('❌ ${snap.error}'));
          }

          final matches = snap.data!;
          final slugs = matches.keys.toList()..sort();

          return MainLayout(
            onMenuPressed: () => _scaffoldKey.currentState?.openDrawer(),
            left: Container(
              width: 260,
              color: AppColors.leftRighDebug,
              child: ListView.separated(
                padding: const EdgeInsets.all(8),
                itemCount: slugs.length,
                separatorBuilder: (_, __) => const SizedBox(height: 6),
                itemBuilder: (_, i) {
                  final slug = slugs[i];
                  final selected = slug == _selectedSlug;
                  return ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor:
                          selected ? Colors.teal : Theme.of(context).primaryColor,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                    onPressed: () => setState(() {
                      _selectedSlug = slug;
                      _selectedCategory = null;
                      _urls = [];
                      _lvl1 = [];
                      _lvl2 = [];
                      _lvl3 = [];
                      _currentL1 = null;
                      _currentL2 = null;
                      _pickedImage = null;
                    }),
                    child: Text(
                      slug,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.center,
                    ),
                  );
                },
              ),
            ),
            center: _buildCenter(matches),
            right: Container(
              width: 180,
              color: AppColors.leftRighDebug,
              child: Column(
                children: [
                  ElevatedButton(
                    onPressed: _selectedSlug == null
                        ? null
                        : () => setState(() {
                              _selectedCategory = 'game_state';
                              _pickedImage = null;
                            }),
                    child: const Text('mostrar game state'),
                  ),
                  ElevatedButton(
                    onPressed:
                        _selectedSlug == null ? null : () => _loadCategory('heat_maps'),
                    child: const Text('mostrar heatmaps'),
                  ),
                  ElevatedButton(
                    onPressed:
                        _selectedSlug == null ? null : () => _loadCategory('cs_diff'),
                    child: const Text('mostrar cs diffs'),
                  ),
                  ElevatedButton(
                    onPressed:
                        _selectedSlug == null ? null : () => _loadCategory('cs_total'),
                    child: const Text('mostrar cs total'),
                  ),
                  ElevatedButton(
                    onPressed:
                        _selectedSlug == null ? null : () => _loadCategory('gold_diff'),
                    child: const Text('mostrar gold diff'),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
