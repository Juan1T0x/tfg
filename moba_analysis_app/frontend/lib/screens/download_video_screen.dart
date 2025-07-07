// lib/screens/download_video_screen.dart
import 'package:flutter/material.dart';
import '../layouts/main_layout.dart';
import '../widgets/side_nav.dart';
import '../theme/app_colors.dart';
import '../services/video_service.dart';

class DownloadVideoScreen extends StatefulWidget {
  const DownloadVideoScreen({super.key});

  @override
  State<DownloadVideoScreen> createState() => _DownloadVideoScreenState();
}

class _DownloadVideoScreenState extends State<DownloadVideoScreen> {
  /* ──────────── configuración básica ──────────── */
  final _scaffoldKey = GlobalKey<ScaffoldState>();
  static const int _navIndex = 6; // posición en SideNav

  /* ──────────── control de estado ──────────── */
  final _urlCtrl  = TextEditingController();
  final _videoSrv = const VideoService();

  bool   _isDownloading = false;
  String? _resultMsg;                // éxito / error

  /* ──────────── lógica de descarga ──────────── */
  Future<void> _startDownload() async {
    final url = _urlCtrl.text.trim();
    if (url.isEmpty) {
      _showSnack('Introduce una URL válida');
      return;
    }

    setState(() {
      _isDownloading = true;
      _resultMsg     = null;
    });

    try {
      final res = await _videoSrv.downloadVideo(url);           // ← llamada al backend
      final file = res['file_name'] ?? 'desconocido';
      setState(() => _resultMsg = '✔ Vídeo descargado: $file');
    } catch (e) {
      setState(() => _resultMsg = '❌ Error: $e');
    } finally {
      setState(() => _isDownloading = false);
      _urlCtrl.clear();
    }
  }

  void _showSnack(String msg) => ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(msg), backgroundColor: Colors.red),
      );

  @override
  void dispose() {
    _urlCtrl.dispose();
    super.dispose();
  }

  /* ──────────── UI ──────────── */
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

        /* panel izquierdo vacío (color debug) */
        left: Container(color: AppColors.leftRighDebug),

        /* panel central */
        center: Padding(
          padding: const EdgeInsets.all(24),
          child: _isDownloading
              ? Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: const [
                    CircularProgressIndicator(),
                    SizedBox(height: 16),
                    Text('Descargando vídeo…'),
                  ],
                )
              : Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: _urlCtrl,
                      decoration: const InputDecoration(
                        labelText: 'URL de YouTube',
                        border: OutlineInputBorder(),
                      ),
                      onSubmitted: (_) => _startDownload(),
                    ),
                    const SizedBox(height: 12),
                    ElevatedButton.icon(
                      onPressed: _startDownload,
                      icon: const Icon(Icons.download),
                      label: const Text('Descargar vídeo'),
                    ),
                    if (_resultMsg != null) ...[
                      const SizedBox(height: 20),
                      Text(
                        _resultMsg!,
                        textAlign: TextAlign.center,
                        style: const TextStyle(fontSize: 16),
                      ),
                    ],
                  ],
                ),
        ),

        /* panel derecho vacío (color debug) */
        right: Container(color: AppColors.leftRighDebug),
      ),
    );
  }
}
