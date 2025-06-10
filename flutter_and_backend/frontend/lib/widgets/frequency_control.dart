import 'package:flutter/material.dart';

class FrequencyControl extends StatefulWidget {
  final int initialMs;
  final ValueChanged<int> onChanged;

  const FrequencyControl({
    super.key,
    required this.initialMs,
    required this.onChanged,
  });

  @override
  State<FrequencyControl> createState() => _FrequencyControlState();
}

class _FrequencyControlState extends State<FrequencyControl> {
  late final TextEditingController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = TextEditingController(text: widget.initialMs.toString());
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: TextField(
            controller: _ctrl,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: 'Frecuencia (ms)',
              border: OutlineInputBorder(),
              isDense: true,
            ),
          ),
        ),
        const SizedBox(width: 8),
        ElevatedButton(
          onPressed: () {
            final v = int.tryParse(_ctrl.text);
            if (v != null && v > 0) {
              widget.onChanged(v);
            } else {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Introduce un número positivo válido.'),
                ),
              );
            }
          },
          child: const Text('Aplicar'),
        ),
      ],
    );
  }
}
