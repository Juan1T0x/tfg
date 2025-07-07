import 'package:flutter/material.dart';

class CargarVideoDialog extends StatefulWidget {
  final void Function(String url) onSubmit;

  const CargarVideoDialog({super.key, required this.onSubmit});

  @override
  State<CargarVideoDialog> createState() => _CargarVideoDialogState();
}

class _CargarVideoDialogState extends State<CargarVideoDialog> {
  final TextEditingController _controller = TextEditingController();
  final FocusNode _focusNode = FocusNode();
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _focusNode.requestFocus();
    });
  }

  void _handleAceptar() {
    final url = _controller.text.trim();
    final isValid = Uri.tryParse(url)?.host.contains('youtube.com') ?? false;

    if (!isValid) {
      setState(() {
        _error = "Introduce una URL válida de YouTube.";
      });
      return;
    }

    widget.onSubmit(url);
    Navigator.of(context).pop();
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FocusScope(
      autofocus: true,
      child: AlertDialog(
        title: const Text("Cargar nuevo video"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _controller,
              focusNode: _focusNode,
              decoration: InputDecoration(
                labelText: "Enlace de YouTube",
                errorText: _error,
                border: const OutlineInputBorder(),
              ),
              onSubmitted: (_) => _handleAceptar(),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text("Cancelar"),
          ),
          ElevatedButton(
            onPressed: _handleAceptar,
            child: const Text("Aceptar"),
          ),
        ],
      ),
    );
  }
}
