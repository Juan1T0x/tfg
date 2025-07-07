import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../constants/layout_constants.dart';

///  Un layout estilo “border-pane” (top, bottom, left, right, center)
///  que puede reutilizarse en cualquier pantalla.
///  NO incluye su propio Scaffold; eso lo gestiona la pantalla que lo use.
class MainLayout extends StatelessWidget {
  final Widget? left;
  final Widget? right;
  final Widget? center;
  final VoidCallback? onMenuPressed;

  final double topHeight;
  final double bottomHeight;

  const MainLayout({
    super.key,
    this.left,
    this.right,
    this.center,
    this.onMenuPressed,
    this.topHeight = 80,
    this.bottomHeight = 80,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (_, constraints) {
        final totalWidth = constraints.maxWidth;
        final sidePanelWidth = totalWidth * kPanelSideRatio;

        return Stack(
          children: [
            // ───────────── Barra superior ─────────────
            Positioned(
              top: 0,
              left: 0,
              right: 0,
              height: topHeight,
              child: Container(
                color: AppColors.headerFooter,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Row(
                  children: [
                    IconButton(
                      icon: const Icon(Icons.menu, color: Colors.white),
                      onPressed: onMenuPressed, // lo controla la pantalla
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

            // ───────────── Barra inferior ─────────────
            Positioned(
              bottom: 0,
              left: 0,
              right: 0,
              height: bottomHeight,
              child: Container(
                color: AppColors.headerFooter,
                alignment: Alignment.center,
                child: const Text(
                  '© 2025 Juan Hernández Acosta - Universidad de Murcia',
                  style: TextStyle(color: Colors.white),
                ),
              ),
            ),

            // ───────────── Panel izquierdo ─────────────
            if (left != null)
              Positioned(
                top: topHeight,
                bottom: bottomHeight,
                left: 0,
                width: sidePanelWidth,
                child: left!,
              ),

            // ───────────── Panel derecho ─────────────
            if (right != null)
              Positioned(
                top: topHeight,
                bottom: bottomHeight,
                right: 0,
                width: sidePanelWidth,
                child: right!,
              ),

            // ───────────── Contenido central ─────────────
            if (center != null)
              Positioned(
                top: topHeight,
                bottom: bottomHeight,
                left: sidePanelWidth,
                right: sidePanelWidth,
                child: center!,
              ),
          ],
        );
      },
    );
  }
}
