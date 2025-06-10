import 'package:flutter/material.dart';
import '../widgets/side_nav.dart';
import '../theme/app_colors.dart';
import '../constants/layout_constants.dart'; // importa la constante

class MainLayout extends StatefulWidget {
  final Widget? left;
  final Widget? right;
  final Widget? center;

  final double topHeight;
  final double bottomHeight;

  const MainLayout({
    super.key,
    this.left,
    this.right,
    this.center,
    this.topHeight = 80,
    this.bottomHeight = 80,
  });

  @override
  State<MainLayout> createState() => _MainLayoutState();
}

class _MainLayoutState extends State<MainLayout> {
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  int _selectedIndex = 0;

  void _onNavDestinationSelected(int index) {
    setState(() {
      _selectedIndex = index;
    });
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: _scaffoldKey,
      drawer: Drawer(
        width: 250,
        child: Align(
          alignment: Alignment.topLeft,
          child: SideNav(
            selectedIndex: _selectedIndex,
            onDestinationSelected: _onNavDestinationSelected,
          ),
        ),
      ),
      body: LayoutBuilder(
        builder: (_, constraints) {
          final totalWidth = constraints.maxWidth;
          final sidePanelWidth = totalWidth * kPanelSideRatio;

          return Stack(
            children: [
              // Top
              Positioned(
                top: 0,
                left: 0,
                right: 0,
                height: widget.topHeight,
                child: Container(
                  color: AppColors.headerFooter,
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Row(
                    children: [
                      IconButton(
                        icon: const Icon(Icons.menu, color: Colors.white),
                        onPressed: () {
                          _scaffoldKey.currentState?.openDrawer();
                        },
                      ),
                      const SizedBox(width: 8),
                      const Text(
                        'TFG - MOBA ANALYSIS',
                        style: TextStyle(color: Colors.white, fontSize: 18),
                      ),
                    ],
                  ),
                ),
              ),

              // Bottom
              Positioned(
                bottom: 0,
                left: 0,
                right: 0,
                height: widget.bottomHeight,
                child: Container(
                  color: AppColors.headerFooter,
                  alignment: Alignment.center,
                  child: const Text(
                    '© 2025 Juan Hernández Acosta - Universidad de Murcia',
                    style: TextStyle(color: Colors.white),
                  ),
                ),
              ),

              // Left
              if (widget.left != null)
                Positioned(
                  top: widget.topHeight,
                  bottom: widget.bottomHeight,
                  left: 0,
                  width: sidePanelWidth,
                  child: widget.left!,
                ),

              // Right
              if (widget.right != null)
                Positioned(
                  top: widget.topHeight,
                  bottom: widget.bottomHeight,
                  right: 0,
                  width: sidePanelWidth,
                  child: widget.right!,
                ),

              // Center
              if (widget.center != null)
                Positioned(
                  top: widget.topHeight,
                  bottom: widget.bottomHeight,
                  left: sidePanelWidth,
                  right: sidePanelWidth,
                  child: widget.center!,
                ),
            ],
          );
        },
      ),
    );
  }
}
