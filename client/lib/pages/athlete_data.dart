// In lib/models/athlete_data.dart

class AthleteData {
  final String name;
  final int age;
  final String gender;
  final String sportPreference;
  final int profileCompletion;
  final String fitnessLevel;
  final Map<String, Performance> recentPerformance;
  final List<Challenge> ongoingChallenges;

  AthleteData({
    required this.name,
    required this.age,
    required this.gender,
    required this.sportPreference,
    required this.profileCompletion,
    required this.fitnessLevel,
    required this.recentPerformance,
    required this.ongoingChallenges,
  });
}

class Performance {
  final String score;
  final String bestScore;
  final bool isImproving;

  Performance({required this.score, required this.bestScore, required this.isImproving});
}

class Challenge {
  final String title;
  final String deadline;

  Challenge({required this.title, required this.deadline});
}