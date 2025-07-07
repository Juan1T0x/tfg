import 'package:flutter/material.dart';
import 'package:youtube_player_iframe/youtube_player_iframe.dart';

import 'frequency_control.dart';
import 'meta_informacion.dart';

class DebugPanel extends StatelessWidget {
  /// Frecuencia actual en milisegundos.
  final int frequencyMs;

  /// Historial de eventos enviados al backend.
  final List<String> log;

  /// Callback para cambiar la frecuencia.
  final ValueChanged<int> onFrequencyChanged;

  /// Controlador del reproductor de YouTube (para MetaInformacion).
  final YoutubePlayerController controller;

  const DebugPanel({
    super.key,
    required this.frequencyMs,
    required this.log,
    required this.onFrequencyChanged,
    required this.controller,
  });

  @override
  Widget build(BuildContext context) {
    return Drawer(
      width: 360,
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Text('DEBUG',
                  style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 24),

              // ───── Meta-información del vídeo ─────
              MetaInformacion(controller: controller),
              const SizedBox(height: 24),

              // ───── Control de frecuencia ─────
              FrequencyControl(
                initialMs: frequencyMs,
                onChanged: onFrequencyChanged,
              ),
              const SizedBox(height: 24),

              // ───── Historial de peticiones ─────
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    border: Border.all(color: Colors.teal.shade200),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  padding: const EdgeInsets.all(8),
                  child: ListView.builder(
                    reverse: true,
                    itemCount: log.length,
                    itemBuilder: (_, i) => Text(
                      log[i],
                      style: const TextStyle(fontSize: 12),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
