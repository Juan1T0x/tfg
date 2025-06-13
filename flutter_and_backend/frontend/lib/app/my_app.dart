import 'package:flutter/material.dart';
import '../screens/home_screen.dart';
import '../screens/update_database_screen.dart';
import '../screens/consult_database_screen.dart';
import '../screens/team_builder_screen.dart';
import '../screens/analysis_history_screen.dart';
import '../screens/download_video_screen.dart';

class MyApp extends StatelessWidget {
  const MyApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'TFG MOBA ANALYSIS',
      initialRoute: '/liveAnalysis',
      routes: {
        '/updateDB': (_) => const UpdateDatabaseScreen(),
        '/consultDB': (_) => const ConsultDatabaseScreen(),
        '/teamBuilder': (_) => const TeamBuilderScreen(),
        '/liveAnalysis': (_) => const HomeScreen(),
        '/history': (_) => const AnalysisHistoryScreen(),
        '/downloadVideo': (_) => const DownloadVideoScreen(),
      },
    );
  }
}