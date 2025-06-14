import 'package:flutter/material.dart';
import '../layouts/main_layout.dart';
import '../widgets/side_nav.dart';
import '../theme/app_colors.dart';

class TeamBuilderScreen extends StatefulWidget {
  const TeamBuilderScreen({super.key});

  @override
  State<TeamBuilderScreen> createState() => _TeamBuilderScreen();
}

class _TeamBuilderScreen extends State<TeamBuilderScreen> {
  // Clave para poder abrir el Drawer desde el icono de menú del MainLayout
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();

  // Índice que debe quedar resaltado en el SideNav
  static const int _navIndex = 3; // 0=Actualizar, 1=Consultar, 2=Gallery, 3=Team, 4=Live, 5=Historial, 6=Descargar

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
            'Aquí irá el formulario para crear un equipo',
            style: TextStyle(color: Colors.white),
          ),
        ),

        center: const Center(
          child: Text(
            'Crear equipo',
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
