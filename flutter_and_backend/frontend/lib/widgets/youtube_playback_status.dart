import 'dart:async';
import 'package:flutter/material.dart';
import 'package:youtube_player_iframe/youtube_player_iframe.dart';

class YoutubePlaybackStatus extends StatefulWidget {
  final YoutubePlayerController controller;

  const YoutubePlaybackStatus({super.key, required this.controller});

  @override
  State<YoutubePlaybackStatus> createState() => _YoutubePlaybackStatusState();
}

class _YoutubePlaybackStatusState extends State<YoutubePlaybackStatus> {
  String _formattedTime = "00:00.00";
  String _formattedDuration = "00:00.00";
  bool _isPlaying = false;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _startTracking();
  }

  void _startTracking() {
    _timer = Timer.periodic(const Duration(milliseconds: 500), (_) async {
      final currentSeconds = await widget.controller.currentTime;
      final playerState = await widget.controller.playerState;

      final minutes = currentSeconds ~/ 60;
      final seconds = currentSeconds % 60;
      final centiseconds = ((currentSeconds - currentSeconds.floor()) * 100)
          .round();

      final meta = widget.controller.metadata;
      final total = meta.duration.inSeconds.toDouble();
      final durMin = total ~/ 60;
      final durSec = total % 60;
      final durCenti = ((total - total.floor()) * 100).round();

      setState(() {
        _formattedTime =
            '${minutes.toString().padLeft(2, '0')}:${seconds.toStringAsFixed(0).padLeft(2, '0')}.${centiseconds.toString().padLeft(2, '0')}';
        _formattedDuration =
            '${durMin.toString().padLeft(2, '0')}:${durSec.toStringAsFixed(0).padLeft(2, '0')}.${durCenti.toString().padLeft(2, '0')}';
        _isPlaying = playerState == PlayerState.playing;
      });
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '⏱️ Información dinámica',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Text(
            'Estado de reproducción: ${_isPlaying ? 'Reproduciendo' : 'Pausado'}',
          ),
          Text('Instante actual: $_formattedTime'),
          Text('Duración: $_formattedDuration'),
        ],
      ),
    );
  }
}
