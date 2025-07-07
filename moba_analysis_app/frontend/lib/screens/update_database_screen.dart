import 'package:flutter/material.dart';
import '../layouts/main_layout.dart';
import '../widgets/side_nav.dart';
import '../theme/app_colors.dart';
import '../services/db_service.dart';

class UpdateDatabaseScreen extends StatefulWidget {
  const UpdateDatabaseScreen({super.key});

  @override
  State<UpdateDatabaseScreen> createState() => _UpdateDatabaseScreenState();
}

class _UpdateDatabaseScreenState extends State<UpdateDatabaseScreen> {
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  static const int _navIndex = 0; // 0=Actualizar, 1=Consultar, 2=Gallery, 3=Team, 4=Live, 5=Historial, 6=Descargar

  bool _updating = false;
  Map<String, dynamic>? _lastResult;
  final DBService _db = DBService.instance;

  Future<void> _handleUpdate() async {
    setState(() {
      _updating = true;
      _lastResult = null;
    });

    try {
      final result = await _db.updateFullDatabase();
      setState(() => _lastResult = result);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('✔ Base de datos actualizada')),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('❌ Error: $e')),
      );
    } finally {
      if (mounted) setState(() => _updating = false);
    }
  }

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
      body: MainLayout(
        onMenuPressed: () => _scaffoldKey.currentState?.openDrawer(),

        /* ───────── Panel izquierdo (vacío) ───────── */
        left: Container(color: AppColors.leftRighDebug),

        /* ───────── Panel central ───────── */
        center: Center(
          child: _updating
              ? Column(
                  mainAxisSize: MainAxisSize.min,
                  children: const [
                    CircularProgressIndicator(),
                    SizedBox(height: 12),
                    Text('Actualizando base de datos…'),
                  ],
                )
              : Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    ElevatedButton.icon(
                      icon: const Icon(Icons.sync),
                      label: const Text('Actualizar base de datos'),
                      onPressed: _handleUpdate,
                    ),
                    if (_lastResult != null) ...[
                      const SizedBox(height: 16),
                      Text(
                        'Base de datos actualizada:',
                        style: const TextStyle(fontWeight: FontWeight.bold),
                      ),
                      Text(_lastResult.toString()),
                    ],
                  ],
                ),
        ),

        right: Container(color: AppColors.leftRighDebug),
      ),
    );
  }
}
