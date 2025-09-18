import 'package:client/pages/athlete_data.dart';
import 'package:flutter/material.dart';

class PerformanceCard extends StatelessWidget {
  final String testName;
  final IconData icon;
  final Performance performanceData;

  const PerformanceCard({
    super.key,
    required this.testName,
    required this.icon,
    required this.performanceData,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16.0),
      decoration: BoxDecoration(
        color: Colors.grey.shade900.withOpacity(0.6),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: Colors.white70, size: 18),
              const SizedBox(width: 8),
              Text(testName, style: const TextStyle(color: Colors.white70, fontWeight: FontWeight.w500)),
            ],
          ),
          const Spacer(),
          Text(performanceData.score, style: const TextStyle(color: Colors.white, fontSize: 26, fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Best: ${performanceData.bestScore}', style: TextStyle(color: Colors.grey.shade400, fontSize: 12)),
              Icon(
                performanceData.isImproving ? Icons.arrow_upward : Icons.arrow_downward,
                color: performanceData.isImproving ? Colors.greenAccent : Colors.redAccent,
                size: 16,
              ),
            ],
          ),
        ],
      ),
    );
  }
}