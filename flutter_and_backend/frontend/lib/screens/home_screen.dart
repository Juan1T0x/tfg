import 'dart:async';
import 'package:flutter/material.dart';
import 'package:youtube_player_iframe/youtube_player_iframe.dart';

import '../layouts/main_layout.dart';
import '../widgets/meta_informacion.dart';
import '../widgets/cargar_video_dialog.dart';
import '../widgets/debug_panel.dart';
import '../widgets/side_nav.dart';
import '../theme/app_colors.dart';
import '../widgets/youtube_video_player.dart';
import '../services/backend_service.dart';

/// Frecuencia (ms) para enviar señales al backend
int backendFrequencyMs = 5_000;

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  // ───────── Reproductor ─────────
  late YoutubePlayerController _controller;
  String _currentUrl = 'https://www.youtube.com/watch?v=jx79sZhjzKQ';
  Key _videoKey = UniqueKey();
  bool _mostrarVideo = true;

  // ───────── Backend ─────────
  final BackendService _backend = BackendService();
  Timer? _backendTimer;
  final List<String> _backendLog = [];

  // ───────── Scaffold ─────────
  // Clave para poder abrir el Drawer desde el icono de menú del MainLayout
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();

  // Índice que debe quedar resaltado en el SideNav
  static const int _navIndex = 4; // 0=Actualizar, 1=Consultar, 2=Gallery, 3=Team, 4=Live, 5=Historial, 6=Descargar

  // ──────────────────────────── init ───────────────────────────
  @override
  void initState() {
    super.initState();
    _loadVideo(_currentUrl);
    _startBackendTimer();
  }

  // ───────────────────── carga vídeo ─────────────────────
  void _loadVideo(String url) {
    final id = YoutubePlayerController.convertUrlToId(url);
    if (id == null) {
      _log('❌ URL inválida');
      return;
    }
    setState(() {
      _currentUrl = url;
      _controller = YoutubePlayerController.fromVideoId(
        videoId: id,
        params: const YoutubePlayerParams(
          showControls: true,
          showFullscreenButton: true,
        ),
      );
      _videoKey = UniqueKey();
    });
  }

  // ───────────────────── timer periódico ─────────────────────
  void _startBackendTimer() {
    _backendTimer?.cancel();
    _backendTimer =
        Timer.periodic(Duration(milliseconds: backendFrequencyMs), (_) async {
      if (await _controller.playerState != PlayerState.playing) return;
      final secs = await _controller.currentTime;
      try {
        await _backend.sendProcessSignal(
          _currentUrl,
          secs,
          onLog: _log,
        );
      } catch (e) {
        _log('❌ $e');
      }
    });
  }

  // ───────────────────── utilidades ─────────────────────
  void _log(String line) {
    setState(() {
      _backendLog.insert(0, line);
      if (_backendLog.length > 50) _backendLog.removeLast();
    });
  }

  // ───────────────────── callbacks Debug ─────────────────────
  void _updateFrequency(int ms) {
    setState(() => backendFrequencyMs = ms);
    _startBackendTimer();
  }

  Future<void> _handleLoadVideo() async {
    _controller.pauseVideo();
    setState(() => _mostrarVideo = false);

    await showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => CargarVideoDialog(
        onSubmit: (url) async {
          _loadVideo(url);
          try {
            await _backend.sendProcessSignal(url, 0, onLog: _log);
          } catch (e) {
            _log('❌ $e');
          }
        },
      ),
    );

    setState(() => _mostrarVideo = true);
  }

  // ───────────────────── lifecycle ─────────────────────
  @override
  void dispose() {
    _backendTimer?.cancel();
    _controller.close();
    super.dispose();
  }

  // ───────────────────── UI ─────────────────────
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: _scaffoldKey,

      // ───────── Drawer principal con SideNav ─────────
      drawer: Drawer(
        width: 250,
        child: Align(
          alignment: Alignment.topLeft,
          child: SideNav(selectedIndex: _navIndex), // 3 = “Analizar partida Live”
        ),
      ),

      // ───────── EndDrawer de depuración ─────────
      endDrawer: DebugPanel(
        frequencyMs: backendFrequencyMs,
        log: _backendLog, 
        onFrequencyChanged: _updateFrequency,
      ),

      // ───────── FAB para abrir el DebugPanel ─────────
      floatingActionButton: FloatingActionButton.extended(
        icon: const Icon(Icons.bug_report),
        label: const Text('Debug'),
        onPressed: () => _scaffoldKey.currentState?.openEndDrawer(),
      ),

      // ───────── Contenido usando MainLayout ─────────
      body: MainLayout(
        onMenuPressed: () => _scaffoldKey.currentState?.openDrawer(),
        left: Container(
          color: AppColors.leftRighDebug,
          child: MetaInformacion(controller: _controller),
        ),
        center: Visibility(
          visible: _mostrarVideo,
          maintainState: true,
          child: Container(
            color: AppColors.centerDebug,
            child: YoutubeVideoPlayer(
              key: _videoKey,
              controller: _controller,
            ),
          ),
        ),
        right: Container(
          color: AppColors.leftRighDebug,
          padding: const EdgeInsets.all(16),
          child: Align(
            alignment: Alignment.topCenter,
            child: ElevatedButton.icon(
              icon: const Icon(Icons.video_library),
              label: const Text('Cargar video'),
              onPressed: _handleLoadVideo,
            ),
          ),
        ),
      ),
    );
  }
}
