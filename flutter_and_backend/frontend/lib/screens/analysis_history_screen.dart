import 'package:flutter/material.dart';
import '../layouts/main_layout.dart';
import '../widgets/side_nav.dart';
import '../theme/app_colors.dart';

class AnalysisHistoryScreen extends StatefulWidget {
  const AnalysisHistoryScreen({super.key});

  @override
  State<AnalysisHistoryScreen> createState() => _AnalysisHistoryScreenState();
}

class _AnalysisHistoryScreenState extends State<AnalysisHistoryScreen> {
  // Clave para poder abrir el Drawer desde el icono de menú del MainLayout
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();

  // Índice que debe quedar resaltado en el SideNav
  static const int _navIndex = 5; // 0=Actualizar, 1=Consultar, 2=Gallery, 3=Team, 4=Live, 5=Historial, 6=Descargar

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: _scaffoldKey,

      // Drawer lateral con el SideNav
      drawer: Drawer(
        width: 250,
        child: Align(
          alignment: Alignment.topLeft,
          child: SideNav(selectedIndex: _navIndex),
        ),
      ),

      // Cuerpo principal usando MainLayout
      body: MainLayout(
        onMenuPressed: () => _scaffoldKey.currentState?.openDrawer(),

        left: Container(
          color: AppColors.leftRighDebug,
          padding: const EdgeInsets.all(16),
          child: const Text(
            'Aquí irá el formulario para consultar el historial de partidas',
            style: TextStyle(color: Colors.white),
          ),
        ),

        center: const Center(
          child: Text(
            'Historial de partidas analizadas',
            style: TextStyle(fontSize: 24),
          ),
        ),

        right: Container(
          color: AppColors.leftRighDebug,
        ),
      ),
    );
  }
}
