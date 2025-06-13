// lib/services/db_service.dart
import 'package:sqflite/sqflite.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'dart:io' show Platform;
import 'package:path/path.dart';
import 'package:path_provider/path_provider.dart';
import 'package:flutter/services.dart' show rootBundle;

class DBService {
  DBService._();
  static final DBService instance = DBService._();
  Database? _db;

  Future<Database> get db async => _db ??= await _initDB();

  Future<Database> _initDB() async {
    if (kIsWeb) {
      // Web: solo nombre lógico
      final db = await openDatabase('moba_analysis');
      // Si no existen, crea las tablas mínimas para tus pruebas
      await _ensureSchema(db);
      return db;
    } else {
      // Móvil/escritorio: la lógica que ya tenías
      final dir = await getApplicationSupportDirectory();
      final path = join(dir.path, 'moba_analysis.sqlite');
      if (!await File(path).exists()) {
        final data = await rootBundle.load('assets/db/moba_analysis.sqlite');
        await File(path).writeAsBytes(
            data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes),
            flush: true);
      }
      return openDatabase(path,
          version: 1,
          onConfigure: (db) => db.execute('PRAGMA foreign_keys = ON'));
    }
  }

  Future<void> _ensureSchema(Database db) async {
    // Crea SOLO si no existen
    await db.execute('''
      CREATE TABLE IF NOT EXISTS partidas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        jugador TEXT,
        resultado TEXT,
        fecha TEXT
      )
    ''');
    await db.execute('''
      CREATE TABLE IF NOT EXISTS jugadores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        elo INTEGER
      )
    ''');
    await db.execute('''
      CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT,
        titulo TEXT
      )
    ''');
  }

  // --- utilidades ya existentes ---
  Future<List<String>> getTableNames() async {
    final database = await db;
    final res = await database.rawQuery(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'");
    return res.map((e) => e['name'] as String).toList();
  }

  Future<List<Map<String, dynamic>>> getAllRows(String table) async {
    final database = await db;
    return database.query(table);
  }
}
