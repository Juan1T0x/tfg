import 'package:flutter/material.dart';
import 'frequency_control.dart';

class DebugPanel extends StatelessWidget {
  /// Frecuencia actual en milisegundos.
  final int frequencyMs;

  /// Historial de eventos enviados al backend.
  final List<String> log;

  /// Callback para cambiar la frecuencia.
  final ValueChanged<int> onFrequencyChanged;

  const DebugPanel({
    super.key,
    required this.frequencyMs,
    required this.log,
    required this.onFrequencyChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Drawer(
      width: 340,
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Text('DEBUG', style: Theme.of(context).textTheme.titleMedium),

              const SizedBox(height: 24),

              /// Control de frecuencia
              FrequencyControl(
                initialMs: frequencyMs,
                onChanged: onFrequencyChanged,
              ),

              const SizedBox(height: 24),

              /// Historial
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
