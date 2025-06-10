// lib/widgets/youtube_video_player.dart

import 'package:flutter/material.dart';
import 'package:youtube_player_iframe/youtube_player_iframe.dart';

class YoutubeVideoPlayer extends StatelessWidget {
  final YoutubePlayerController controller;

  const YoutubeVideoPlayer({super.key, required this.controller});

  @override
  Widget build(BuildContext context) {
    return YoutubePlayerScaffold(
      controller: controller,
      aspectRatio: 16 / 9,
      builder: (context, player) => Center(child: player),
    );
  }
}
