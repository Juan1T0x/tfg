// lib/screens/consult_database_screen.dart
import 'package:flutter/material.dart';
import '../layouts/main_layout.dart';
import '../widgets/side_nav.dart';
import '../theme/app_colors.dart';
import '../services/db_service.dart';

class ConsultDatabaseScreen extends StatefulWidget {
  const ConsultDatabaseScreen({super.key});

  @override
  State<ConsultDatabaseScreen> createState() => _ConsultDatabaseScreenState();
}

class _ConsultDatabaseScreenState extends State<ConsultDatabaseScreen> {
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  static const int _navIndex = 1; // 0=Actualizar, 1=Consultar, 2=Gallery, 3=Team, 4=Live, 5=Historial, 6=Descargar

  final DBService _db = DBService.instance;

  List<String> _tables = [];
  String? _selectedTable;
  Future<List<Map<String, dynamic>>>? _rowsFuture;

  @override
  void initState() {
    super.initState();
    _loadTableNames();
  }

  Future<void> _loadTableNames() async {
    try {
      // ---- CAST explícito a List<String> ----
      final tables = (await _db.getTableNames()).cast<String>();
      if (!mounted) return;
      setState(() {
        _tables = tables;
        if (tables.isNotEmpty) _selectTable(tables.first);
      });
    } catch (e) {
      if (!mounted) return;
      _showError('Error al cargar tablas: $e');
    }
  }

  void _selectTable(String table) {
    setState(() {
      _selectedTable = table;
      _rowsFuture = _db.getTableRows(table);
    });
  }

  void _showError(String msg) => ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(msg, style: const TextStyle(color: Colors.white)),
          backgroundColor: Colors.red,
        ),
      );

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

        /* ───────── Panel izquierdo ───────── */
        left: Container(
          color: AppColors.leftRighDebug,
          padding: const EdgeInsets.all(16),
          child: _tables.isEmpty
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  children: [
                    const Text('Tablas',
                        style: TextStyle(color: Colors.white, fontSize: 18)),
                    const SizedBox(height: 12),
                    for (final t in _tables)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: ElevatedButton(
                          style: ElevatedButton.styleFrom(
                            backgroundColor:
                                t == _selectedTable ? Colors.blueGrey : Colors.blue,
                          ),
                          onPressed: () => _selectTable(t),
                          child: Text(t),
                        ),
                      ),
                  ],
                ),
        ),

        /* ───────── Panel central ───────── */
        center: _selectedTable == null
            ? const Center(child: Text('Seleccione una tabla'))
            : FutureBuilder<List<Map<String, dynamic>>>(
                future: _rowsFuture,
                builder: (context, snapshot) {
                  if (snapshot.connectionState != ConnectionState.done) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snapshot.hasError) {
                    return Center(child: Text('Error: ${snapshot.error}'));
                  }

                  final rows = snapshot.data ?? [];
                  if (rows.isEmpty) {
                    return Center(child: Text('$_selectedTable está vacía'));
                  }

                  final cols = rows.first.keys.toList();
                  return SingleChildScrollView(
                    child: PaginatedDataTable(
                      header: Text('$_selectedTable (${rows.length} filas)'),
                      columns: [
                        for (final c in cols) DataColumn(label: Text(c)),
                      ],
                      source: _DataSource(rows, cols),
                      rowsPerPage: rows.length < 10 ? rows.length : 10,
                      showCheckboxColumn: false,
                    ),
                  );
                },
              ),

        right: Container(color: AppColors.leftRighDebug),
      ),
    );
  }
}

/* ───────────────────────────────────────────── */
class _DataSource extends DataTableSource {
  final List<Map<String, dynamic>> rows;
  final List<String> cols;

  _DataSource(this.rows, this.cols);

  @override
  DataRow getRow(int index) => DataRow.byIndex(
        index: index,
        cells: [for (final c in cols) DataCell(Text('${rows[index][c]}'))],
      );

  @override
  bool get isRowCountApproximate => false;
  @override
  int get rowCount => rows.length;
  @override
  int get selectedRowCount => 0;
}
