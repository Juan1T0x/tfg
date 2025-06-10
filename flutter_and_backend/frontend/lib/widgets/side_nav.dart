import 'package:flutter/material.dart';

class SideNav extends StatelessWidget {
  final int selectedIndex;
  final Function(int) onDestinationSelected;

  const SideNav({
    super.key,
    required this.selectedIndex,
    required this.onDestinationSelected,
  });

  @override
  Widget build(BuildContext context) {
    return NavigationRail(
      extended: true,
      selectedIndex: selectedIndex,
      onDestinationSelected: onDestinationSelected,
      labelType: NavigationRailLabelType.none,
      destinations: const [
        NavigationRailDestination(
          icon: Icon(Icons.dashboard),
          label: Text('Dashboard'),
        ),
        NavigationRailDestination(
          icon: Icon(Icons.analytics),
          label: Text('Análisis'),
        ),
        NavigationRailDestination(
          icon: Icon(Icons.settings),
          label: Text('Ajustes'),
        ),
        NavigationRailDestination(
          icon: Icon(Icons.info),
          label: Text('Acerca de'),
        ),
      ],
    );
  }
}
