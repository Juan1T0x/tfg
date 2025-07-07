import 'package:flutter/material.dart';
import 'package:youtube_player_iframe/youtube_player_iframe.dart';

class YoutubeVideoInfo extends StatelessWidget {
  final YoutubePlayerController controller;

  const YoutubeVideoInfo({super.key, required this.controller});

  @override
  Widget build(BuildContext context) {
    return YoutubeValueBuilder(
      controller: controller,
      builder: (context, value) {
        final meta = value.metaData;

        return Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                '🎬 Información Estática',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Text(
                'Título: ${meta.title.isEmpty ? 'Cargando...' : meta.title}',
              ),
              Text(
                'Canal: ${meta.author.isEmpty ? 'Cargando...' : meta.author}',
              ),
            ],
          ),
        );
      },
    );
  }
}
