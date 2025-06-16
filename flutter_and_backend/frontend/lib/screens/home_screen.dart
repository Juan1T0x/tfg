// lib/screens/home_screen.dart
//
// Home Screen (Live Game Analysis) — ahora el botón
// “Empezar análisis de Champion Select” llama directamente al
// end-point `/api/pipeline/startChampionSelect` a través de
// `PipelineService`.
//
// El *match title* se toma del propio título del vídeo de YouTube
// (`controller.metadata.title`).  Si no estuviera disponible
// (p. ej. mientras se descarga el player), se usa la URL como
// valor de reserva.
//
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:youtube_player_iframe/youtube_player_iframe.dart';

import '../layouts/main_layout.dart';
import '../widgets/cargar_video_dialog.dart';
import '../widgets/debug_panel.dart';
import '../widgets/side_nav.dart';
import '../widgets/youtube_video_player.dart';
import '../theme/app_colors.dart';
import '../services/video_service.dart';
import '../services/pipeline_service.dart';   // ⇦ NUEVO

// Frecuencia por defecto (ms) para la cola del backend
int backendFrequencyMs = 5_000;

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  /*───────── YouTube player ─────────*/
  late YoutubePlayerController _controller;
  String _currentUrl = 'https://www.youtube.com/watch?v=jx79sZhjzKQ';
  Key _videoKey = UniqueKey();
  bool _mostrarVideo = true;

  /*───────── Servicios ─────────*/
  final VideoService     _video     = const VideoService();
  final PipelineService  _pipeline  = PipelineService.instance;   // ⇦ NUEVO
  Timer? _backendTimer;
  final List<String> _backendLog = [];

  /*───────── Navegación ─────────*/
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  static const int _navIndex = 4;

  /*──────────────────── init ────────────────────*/
  @override
  void initState() {
    super.initState();
    _loadVideo(_currentUrl);
  }

  /*───────── cargar vídeo ─────────*/
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

  /*───────── Timer periódico (Main-Game) ─────────*/
  void _startBackendTimer() {
    _backendTimer?.cancel();
    _backendTimer = Timer.periodic(
      Duration(milliseconds: backendFrequencyMs),
      (_) async {
        final secs = await _controller.currentTime;
        try {
          await _video.queueFrameExtraction(_currentUrl, secs, onLog: _log);
        } catch (e) {
          _log('❌ $e');
        }
      },
    );
    _log('▶️ Inicio análisis Main Game (cada ${backendFrequencyMs} ms)');
  }

  void _stopBackendTimer() {
    _backendTimer?.cancel();
    _backendTimer = null;
    _log('⏹ Análisis Main Game detenido');
  }

  /*───────── utilidades ─────────*/
  void _log(String line) {
    setState(() {
      _backendLog.insert(0, line);
      if (_backendLog.length > 60) _backendLog.removeLast();
    });
  }

  void _updateFrequency(int ms) {
    setState(() => backendFrequencyMs = ms);
    if (_backendTimer != null) _startBackendTimer();
  }

  void _openDebugPanel() => _scaffoldKey.currentState?.openEndDrawer();

  

  /*───────── callbacks de botones ─────────*/
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
            // pre-calienta el backend con un frame del segundo 0
            await _video.queueFrameExtraction(url, 0);
          } catch (e) {
            _log('❌ $e');
          }
        },
      ),
    );

    setState(() => _mostrarVideo = true);
  }

  /// ⇨ Botón «Empezar análisis de Champion Select»
  Future<void> _startChampionSelectAnalysis() async {
    final secs   = await _controller.currentTime;
    final title  = _controller.metadata.title?.trim().isNotEmpty == true
        ? _controller.metadata.title!
        : _currentUrl;                      // reserva si no hay título

    final minute = secs ~/ 60;
    final second = secs.floor() % 60;

    _log('🏁 Champion Select @ ${minute.toString().padLeft(2, '0')}:'
         '${second.toString().padLeft(2, '0')}  –  “$title”');

    try {
      final res = await _pipeline.startChampionSelect(
        matchTitle: title,
        youtubeUrl: _currentUrl,
        minute: minute,
        second: second,
      );
      _log('✅ Frame: ${res['frame_file']}');
      _log('   BLUE: ${res['champions']['blue']}');
      _log('   RED : ${res['champions']['red']}');
    } catch (e) {
      _log('❌ $e');
    }
  }

  void _startMainGameAnalysis() {
    if (_backendTimer == null) _startBackendTimer();
  }

  void _stopMatchAnalysis() => _stopBackendTimer();

  /*───────── lifecycle ─────────*/
  @override
  void dispose() {
    _stopBackendTimer();
    _controller.close();
    super.dispose();
  }

  /*───────── UI ─────────*/
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

      endDrawer: DebugPanel(
        frequencyMs: backendFrequencyMs,
        log: _backendLog,
        onFrequencyChanged: _updateFrequency,
        controller: _controller,
      ),

      body: MainLayout(
        onMenuPressed: () => _scaffoldKey.currentState?.openDrawer(),

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
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                ElevatedButton.icon(
                  icon: const Icon(Icons.video_library),
                  label: const Text('Cargar vídeo'),
                  onPressed: _handleLoadVideo,
                ),
                const SizedBox(height: 12),

                ElevatedButton.icon(
                  icon: const Icon(Icons.bug_report),
                  label: const Text('Debug'),
                  onPressed: _openDebugPanel,
                ),
                const SizedBox(height: 24),

                ElevatedButton(
                  onPressed: _startChampionSelectAnalysis,
                  child: const Text('Empezar análisis de Champion Select'),
                ),
                const SizedBox(height: 12),

                ElevatedButton(
                  onPressed: _startMainGameAnalysis,
                  child: const Text('Empezar análisis de Main Game'),
                ),
                const SizedBox(height: 12),

                ElevatedButton(
                  onPressed: _stopMatchAnalysis,
                  child: const Text('Terminar análisis de partida'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
