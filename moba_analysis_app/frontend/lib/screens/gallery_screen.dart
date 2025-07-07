// lib/screens/gallery_screen.dart
import 'package:flutter/material.dart';
import '../layouts/main_layout.dart';
import '../widgets/side_nav.dart';
import '../theme/app_colors.dart';
import '../services/db_service.dart';
import '../services/image_service.dart';

class GalleryScreen extends StatefulWidget {
  const GalleryScreen({super.key});

  @override
  State<GalleryScreen> createState() => _GalleryScreenState();
}

class _GalleryScreenState extends State<GalleryScreen> {
  final _scaffoldKey = GlobalKey<ScaffoldState>();
  static const int _navIndex = 2; // 0=Actualizar, 1=Consultar, 2=Gallery, 3=Team, 4=Live, 5=Historial, 6=Descargar

  final _db = DBService.instance;
  final _img = ImageService();

  late Future<List<String>> _namesFuture;
  String? _selected;
  Future<Map<String, String>>? _urlsFuture;  // icon/splash/loading

  @override
  void initState() {
    super.initState();
    _namesFuture = _db.getChampionNames();
  }

  void _loadChampion(String name) {
    setState(() {
      _selected = name;
      _urlsFuture = _img.fetchImagesForChampion(name.replaceAll(' ', ''));
      // Quitamos espacios porque las URLs usan la “key” tal cual (“AurelionSol”)
    });
  }

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
      body: MainLayout(
        onMenuPressed: () => _scaffoldKey.currentState?.openDrawer(),

        /*────────── Panel izquierdo: lista de campeones ─────────*/
        left: FutureBuilder<List<String>>(
          future: _namesFuture,
          builder: (_, snap) {
            if (!snap.hasData) {
              return const Center(child: CircularProgressIndicator());
            }
            final names = snap.data!;
            return Container(
              color: AppColors.leftRighDebug,
              padding: const EdgeInsets.all(12),
              child: ListView.separated(
                itemCount: names.length,
                separatorBuilder: (_, __) => const SizedBox(height: 6),
                itemBuilder: (_, i) {
                  final n = names[i];
                  return ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor:
                          n == _selected ? Colors.blueGrey : Colors.blue,
                    ),
                    onPressed: () => _loadChampion(n),
                    child: Text(n, textAlign: TextAlign.center),
                  );
                },
              ),
            );
          },
        ),

        /*────────── Panel central: imágenes ─────────*/
        center: _selected == null
            ? const Center(child: Text('Selecciona un campeón'))
            : FutureBuilder<Map<String, String>>(
                future: _urlsFuture,
                builder: (_, snap) {
                  if (!snap.hasData) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  final urls = snap.data!;
                  return SingleChildScrollView(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          _selected!,
                          style: const TextStyle(
                              fontSize: 26, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 16),
                        _ImageCard(url: urls['icon']!, label: 'Icon'),
                        const SizedBox(height: 12),
                        _ImageCard(url: urls['splash_art']!, label: 'Splash'),
                        const SizedBox(height: 12),
                        _ImageCard(
                            url: urls['loading_screen']!, label: 'Loading'),
                      ],
                    ),
                  );
                },
              ),

        right: Container(color: AppColors.leftRighDebug),
      ),
    );
  }
}

/*────────── Widget auxiliar para mostrar cada imagen ─────────*/
class _ImageCard extends StatelessWidget {
  final String url;
  final String label;
  const _ImageCard({required this.url, required this.label});

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 4,
      child: Column(
        children: [
          Image.network(url, fit: BoxFit.contain),
          Padding(
            padding: const EdgeInsets.all(4),
            child: Text(label,
                style: const TextStyle(fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }
}
