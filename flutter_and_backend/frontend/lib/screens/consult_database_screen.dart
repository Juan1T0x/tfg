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
  final _scaffoldKey = GlobalKey<ScaffoldState>();
  static const int _navIndex = 1;

  late Future<List<String>> _tablesFuture;
  String? _selectedTable;
  Future<List<Map<String, dynamic>>>? _rowsFuture;

  @override
  void initState() {
    super.initState();
    _tablesFuture = DBService.instance.getTableNames();
  }

  void _selectTable(String table) {
    setState(() {
      _selectedTable = table;
      _rowsFuture = DBService.instance.getAllRows(table);
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

        // ───────── Panel izquierdo: lista de tablas ─────────
        left: FutureBuilder<List<String>>(
          future: _tablesFuture,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return Center(child: Text('Error: ${snap.error}'));
            }

            final tables = snap.data!;
            // Seleccionar la primera tabla automáticamente
            if (_selectedTable == null && tables.isNotEmpty) {
              // esperar al próximo frame para evitar setState en build
              WidgetsBinding.instance.addPostFrameCallback(
                (_) => _selectTable(tables.first),
              );
            }

            return Container(
              color: AppColors.leftRighDebug,
              padding: const EdgeInsets.all(16),
              child: ListView(
                children: [
                  const Text('Tablas:',
                      style: TextStyle(color: Colors.white)),
                  const SizedBox(height: 8),
                  for (final t in tables)
                    ListTile(
                      title: Text(t,
                          style: const TextStyle(color: Colors.white)),
                      selected: t == _selectedTable,
                      onTap: () => _selectTable(t),
                    ),
                ],
              ),
            );
          },
        ),

        // ───────── Centro: tabla con filas ─────────
        center: _selectedTable == null
            ? const Center(child: CircularProgressIndicator())
            : FutureBuilder<List<Map<String, dynamic>>>(
                future: _rowsFuture,
                builder: (context, snap) {
                  if (snap.connectionState != ConnectionState.done) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snap.hasError) {
                    return Center(child: Text('Error: ${snap.error}'));
                  }

                  final rows = snap.data!;
                  if (rows.isEmpty) {
                    return Center(child: Text('$_selectedTable está vacía'));
                  }

                  final cols = rows.first.keys.toList();
                  return SingleChildScrollView(
                    child: PaginatedDataTable(
                      header: Text('$_selectedTable (${rows.length} filas)'),
                      columns: [
                        for (final c in cols) DataColumn(label: Text(c))
                      ],
                      source: _DataSource(rows, cols),
                      rowsPerPage:
                          rows.length < 10 ? rows.length : 10, // ajuste dinámico
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

class _DataSource extends DataTableSource {
  final List<Map<String, dynamic>> rows;
  final List<String> cols;
  _DataSource(this.rows, this.cols);

  @override
  DataRow getRow(int index) => DataRow.byIndex(
        index: index,
        cells: [
          for (final c in cols) DataCell(Text('${rows[index][c]}'))
        ],
      );

  @override
  bool get isRowCountApproximate => false;
  @override
  int get rowCount => rows.length;
  @override
  int get selectedRowCount => 0;
}
