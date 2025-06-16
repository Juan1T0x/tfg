import 'dart:convert';

import 'package:flutter/material.dart';

import '../layouts/main_layout.dart';
import '../widgets/side_nav.dart';
import '../theme/app_colors.dart';
import '../services/db_service.dart'; // ← nuevo uso

class AnalysisHistoryScreen extends StatefulWidget {
  const AnalysisHistoryScreen({super.key});

  @override
  State<AnalysisHistoryScreen> createState() => _AnalysisHistoryScreenState();
}

class _AnalysisHistoryScreenState extends State<AnalysisHistoryScreen> {
  /* ───── navegación ───── */
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  static const int _navIndex = 5; // “Historial”

  /* ───── datos backend ───── */
  late Future<Map<String, dynamic>> _matchesF;
  String? _selectedSlug; // slug / key elegido

  @override
  void initState() {
    super.initState();
    _matchesF = DBService.instance.getAllGameStates();
  }

  /* ═════════════ UI ═════════════ */
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

          final matches = snap.data!; // slug → full json
          final slugs = matches.keys.toList()..sort();

          // contenido central cuando hay selección
          Widget _buildCenter() {
            if (_selectedSlug == null) {
              return const Center(
                child: Text(
                  'Selecciona una partida a la izquierda',
                  style: TextStyle(fontSize: 18, fontStyle: FontStyle.italic),
                ),
              );
            }

            final jsonPretty = const JsonEncoder.withIndent(
              '  ',
            ).convert(matches[_selectedSlug]);

            return Padding(
              padding: const EdgeInsets.all(16),
              child: Scrollbar(
                thumbVisibility: true,
                child: SingleChildScrollView(
                  child: SelectableText(
                    jsonPretty,
                    style: const TextStyle(
                      fontFamily: 'RobotoMono',
                      fontSize: 13,
                    ),
                  ),
                ),
              ),
            );
          }

          return MainLayout(
            onMenuPressed: () => _scaffoldKey.currentState?.openDrawer(),

            /* ───── Columna izquierda (lista de partidas) ───── */
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
                      backgroundColor: selected
                          ? Colors.teal
                          : Theme.of(context).primaryColor,
                      foregroundColor: Colors.white, // ← texto/icono en blanco
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                    onPressed: () => setState(() => _selectedSlug = slug),
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

            /* ───── Panel central ───── */
            center: _buildCenter(),

            /* ───── Columna derecha vacía ───── */
            right: Container(color: AppColors.leftRighDebug),
          );
        },
      ),
    );
  }
}
