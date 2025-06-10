import 'package:flutter/material.dart';
import 'package:youtube_player_iframe/youtube_player_iframe.dart';
import 'youtube_video_info.dart';
import 'youtube_playback_status.dart';

class MetaInformacion extends StatelessWidget {
  final YoutubePlayerController controller;

  const MetaInformacion({super.key, required this.controller});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Encabezado visual
          Row(
            children: const [
              Icon(Icons.info_outline, color: Colors.teal),
              SizedBox(width: 8),
              Text(
                'Metainformación',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
              ),
            ],
          ),
          const Divider(height: 24),

          // Subcomponentes
          YoutubeVideoInfo(controller: controller),
          const SizedBox(height: 16),
          YoutubePlaybackStatus(controller: controller),
        ],
      ),
    );
  }
}
