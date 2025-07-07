// lib/screens/team_builder_screen.dart
//
// Cartas más anchas y con wrap: el texto ya no se desborda.

import 'package:flutter/material.dart';

import '../layouts/main_layout.dart';
import '../widgets/side_nav.dart';
import '../theme/app_colors.dart';
import '../services/db_service.dart';
import '../services/image_service.dart';

/*────────────────── Constantes ──────────────────*/

const List<String> kPositions = ['TOP', 'JUNGLE', 'MID', 'BOT', 'SUPPORT'];
const Color kBlueTeamColor = Color(0xff1e88e5);
const Color kRedTeamColor  = Color(0xffe53935);

/*────────────────── Pantalla ──────────────────*/

class TeamBuilderScreen extends StatefulWidget {
  const TeamBuilderScreen({super.key});
  @override
  State<TeamBuilderScreen> createState() => _TeamBuilderScreenState();
}

class _TeamBuilderScreenState extends State<TeamBuilderScreen> {
  /*─ navegación ─*/
  final _scaffoldKey = GlobalKey<ScaffoldState>();
  static const int _navIndex = 3;

  /*─ servicios ─*/
  final _db  = DBService.instance;
  final _img = ImageService();

  /*─ datos iniciales ─*/
  late Future<void> _initFuture;
  late Map<String, String> _nameToRoles;   // nombre → roles
  late List<String> _champNames;           // A-Z

  /*─ selección ─*/
  final Map<String, String?> _blue = {for (var p in kPositions) p: null};
  final Map<String, String?> _red  = {for (var p in kPositions) p: null};

  @override
  void initState() {
    super.initState();
    _initFuture = () async {
      final rows = await _db.getTableRows('champions');
      _nameToRoles = {
        for (final r in rows) r['champion_name'] as String: r['roles'] as String
      };
      _champNames = _nameToRoles.keys.toList()..sort();
    }();
  }

  /*────────────────── helpers ──────────────────*/

  String _keyForImage(String n) => n.replaceAll(RegExp(r'[^A-Za-z0-9]'), '');

  Future<Map<String, String>> _iconAndRoles(String n) async {
    final icon = (await _img.fetchImagesForChampion(_keyForImage(n)))['icon']!;
    return {'icon': icon, 'roles': _nameToRoles[n] ?? ''};
  }

  Future<void> _pick(
    Map<String, String?> team,
    String pos,
  ) async {
    final chosen = await showDialog<String>(
      context: context,
      builder: (_) => SimpleDialog(
        title: Text('Seleccionar campeón – $pos'),
        children: [
          SizedBox(
            width: 300,
            height: 400,
            child: ListView.builder(
              itemCount: _champNames.length,
              itemBuilder: (_, i) {
                final name = _champNames[i];
                return ListTile(
                  title: Text(name),
                  subtitle: Text(_nameToRoles[name]!),
                  onTap: () => Navigator.pop(context, name),
                );
              },
            ),
          ),
        ],
      ),
    );
    if (chosen != null) setState(() => team[pos] = chosen);
  }

  /*───────── Widget de cada slot ─────────*/
  Widget _slot(
    Map<String, String?> team,
    String pos,
    Color col,
  ) {
    final name = team[pos];

    /*─ vacío ─*/
    if (name == null) {
      return GestureDetector(
        onTap: () => _pick(team, pos),
        child: _shell(
          col,
          child: Center(
            child: Text(
              pos,
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ),
      );
    }

    /*─ con campeón ─*/
    return FutureBuilder<Map<String, String>>(
      future: _iconAndRoles(name),
      builder: (c, s) {
        if (!s.hasData) {
          return _shell(
            col,
            child: const Center(
              child: SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ),
          );
        }

        final icon = s.data!['icon']!;
        final roles = s.data!['roles']!;

        return GestureDetector(
          onTap: () => _pick(team, pos),
          child: _shell(
            col,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 56,
                  height: 56,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(4),
                    image: icon.isNotEmpty
                        ? DecorationImage(image: NetworkImage(icon))
                        : null,
                    color: col.withOpacity(.25),
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  name,
                  textAlign: TextAlign.center,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                  ),
                ),
                if (roles.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(
                    roles,
                    textAlign: TextAlign.center,
                    maxLines: 2,
                    softWrap: true,
                    style: const TextStyle(
                      fontSize: 12,
                      color: Colors.white70,
                    ),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  /*─ contenedor de cada carta ─*/
  Widget _shell(Color c, {required Widget child}) => Container(
        width: 130,
        height: 130,
        padding: const EdgeInsets.all(6),
        decoration: BoxDecoration(
          color: c.withOpacity(.25),
          borderRadius: BorderRadius.circular(10),
        ),
        child: child,
      );

  /*────────────────── UI ──────────────────*/

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
      body: FutureBuilder(
        future: _initFuture,
        builder: (_, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(child: Text('Error: ${snap.error}'));
          }

          return MainLayout(
            onMenuPressed: () => _scaffoldKey.currentState?.openDrawer(),
            left: Container(color: AppColors.leftRighDebug),

            /* centro */
            center: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
              child: Column(
                children: [
                  const _TitlesRow(),
                  const SizedBox(height: 14),
                  Expanded(
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        _teamColumn(_blue, kBlueTeamColor),
                        const SizedBox(width: 24),
                        _teamColumn(_red, kRedTeamColor),
                      ],
                    ),
                  ),
                ],
              ),
            ),

            right: Container(color: AppColors.leftRighDebug),
          );
        },
      ),
    );
  }

  /*─ columna de un equipo ─*/
  Widget _teamColumn(Map<String, String?> t, Color col) => Expanded(
        child: ListView.separated(
          padding: const EdgeInsets.symmetric(vertical: 8),
          itemCount: kPositions.length,
          separatorBuilder: (_, __) => const SizedBox(height: 16),
          itemBuilder: (_, i) => Align(
            alignment: Alignment.topCenter,
            child: _slot(t, kPositions[i], col),
          ),
        ),
      );
}

/*───────── título azul / rojo ─────────*/
class _TitlesRow extends StatelessWidget {
  const _TitlesRow();

  @override
  Widget build(BuildContext context) => Row(
        children: const [
          Expanded(
            child: Text(
              'Equipo azul',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
          ),
          Expanded(
            child: Text(
              'Equipo rojo',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
          ),
        ],
      );
}
