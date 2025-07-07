import 'package:flutter/material.dart';

class SideNav extends StatelessWidget {
  final int selectedIndex;

  const SideNav({
    super.key,
    required this.selectedIndex,
  });

  @override
  Widget build(BuildContext context) {
    final items = [
      {
        'icon': Icons.update,
        'label': 'Actualizar BBDD',
        'route': '/updateDB',
      },
      {
        'icon': Icons.search,
        'label': 'Consultar BBDD',
        'route': '/consultDB',
      },
      {
        'icon': Icons.image,
        'label': 'Galería de Imágenes',
        'route': '/gallery',
      },
      {
        'icon': Icons.group,
        'label': 'Team Builder',
        'route': '/teamBuilder',
      },
      {
        'icon': Icons.videogame_asset,
        'label': 'Analizar partida Live',
        'route': '/liveAnalysis',
      },
      {
        'icon': Icons.history,
        'label': 'Historial partidas',
        'route': '/history',
      },
      {
        'icon': Icons.download,
        'label': 'Descargar Video',
        'route': '/downloadVideo',
      },
    ];

    return NavigationRail(
      extended: true,
      selectedIndex: selectedIndex,
      onDestinationSelected: (index) {
        if (index == selectedIndex) return;
        Navigator.pushReplacementNamed(
          context,
          items[index]['route'] as String,
        );
      },
      labelType: NavigationRailLabelType.none,
      destinations: items.map((item) {
        return NavigationRailDestination(
          icon: Icon(item['icon'] as IconData),
          label: Text(item['label'] as String),
        );
      }).toList(),
    );
  }
}
