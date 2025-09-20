import 'package:client/pages/athlete_data.dart';
import 'package:client/pages/performance_card.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:client/pages/ai_chatbot_page.dart';
import 'package:client/pages/upload_video_page.dart'; // Import the new page
import 'dart:convert'; // Add this for json.decode if you use it in _loadUserData for more complex API calls

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  AthleteData? _athleteData;
  String? _profilePicUrl;
  bool _isLoading = true;

  // --- IMPORTANT: CORRECTED URL FOR BACKEND ---
  // Replace with your computer's local network IP address if running on a real device.
  // For Android emulator, use "http://10.0.2.2:8000"
  // For iOS simulator or web/desktop, use "http://127.0.0.1:8000"
  // If running backend on a different machine, use that machine's IP.
  final String apiBaseUrl = "http://127.0.0.1:8000"; // Example for local dev/emulator
  // --- END of URL Correction ---

  @override
  void initState() {
    super.initState();
    _loadUserData();
  }

  Future<void> _loadUserData() async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();

    final String name = prefs.getString('name') ?? 'Athlete';
    final String? profilePicPath = prefs.getString('profilePic');

    if (profilePicPath != null && profilePicPath.isNotEmpty) {
      _profilePicUrl = apiBaseUrl + profilePicPath; // Assuming profile pics are also served by FastAPI
    }

    await Future.delayed(const Duration(seconds: 1)); // Simulate network delay

    final mockData = AthleteData(
      name: name,
      age: 17,
      gender: "Male",
      sportPreference: "Athletics",
      profileCompletion: 80,
      fitnessLevel: "Intermediate",
      recentPerformance: {
        "Vertical Jump": Performance(
          score: "65 cm",
          bestScore: "68 cm",
          isImproving: true,
        ),
        "Shuttle Run": Performance(
          score: "9.8 s",
          bestScore: "9.5 s",
          isImproving: false,
        ),
        "Endurance": Performance(
          score: "12:30 min",
          bestScore: "12:15 min",
          isImproving: false,
        ),
        "Sit-ups (1 min)": Performance(
          score: "45 reps",
          bestScore: "42 reps",
          isImproving: true,
        ),
      },
      ongoingChallenges: [
        Challenge(title: "National Endurance Test", deadline: "Closes Sept 30"),
        Challenge(title: "7-Day Sit-Up Challenge", deadline: "Ends in 3 days"),
      ],
    );

    setState(() {
      _athleteData = mockData;
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,

      body: _isLoading
          ? const Center(
              child: CircularProgressIndicator(color: Color(0xFFD0FD3E)),
            )
          : CustomScrollView(
              slivers: [
                _buildSliverAppBar(),
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildQuickStartButtons(),
                        const SizedBox(height: 32),
                        _buildSectionHeader("Recent Performance"),
                        const SizedBox(height: 16),
                        _buildPerformanceGrid(),
                        const SizedBox(height: 32),
                        _buildSectionHeader("Ongoing Challenges"),
                        const SizedBox(height: 16),
                        _buildChallengesList(),
                      ],
                    ),
                  ),
                ),
              ],
            ),

      floatingActionButton: FloatingActionButton(
        onPressed: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => AIChatbotPage(
                userName: _athleteData?.name ?? 'Athlete',
                userProfilePicUrl: _profilePicUrl,
              ),
            ),
          );
        },
        backgroundColor: const Color(0xFFD0FD3E),
        foregroundColor: Colors.black,
        tooltip: 'AI Assistant',
        child: const Icon(Icons.smart_toy_outlined),
      ),
    );
  }

  Widget _buildSliverAppBar() {
    return SliverAppBar(
      expandedHeight: 240.0,
      backgroundColor: const Color.fromARGB(255, 22, 22, 22),
      pinned: true,
      stretch: true,
      flexibleSpace: FlexibleSpaceBar(
        centerTitle: false,
        titlePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        title: Text(
          "Welcome, ${_athleteData!.name.split(' ').first}",
          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
        ),
        background: SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 60, 16, 50),
            child: _buildProfileSnapshot(),
          ),
        ),
      ),
    );
  }

  Widget _buildProfileSnapshot() {
    return Row(
      children: [
        CircleAvatar(
          radius: 40,
          backgroundColor: Colors.grey.shade800,
          backgroundImage: _profilePicUrl != null
              ? NetworkImage(_profilePicUrl!)
              : null,
          child: _profilePicUrl == null
              ? const Icon(Icons.person, size: 40, color: Colors.white70)
              : null,
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 4,
                ),
                decoration: BoxDecoration(
                  color: const Color(0xFFD0FD3E),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  _athleteData!.fitnessLevel.toUpperCase(),
                  style: const TextStyle(
                    color: Colors.black,
                    fontWeight: FontWeight.bold,
                    fontSize: 12,
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                '${_athleteData!.age} yrs • ${_athleteData!.sportPreference}',
                style: const TextStyle(color: Colors.white, fontSize: 16),
              ),
              const SizedBox(height: 8),
              LinearProgressIndicator(
                value: _athleteData!.profileCompletion / 100,
                backgroundColor: Colors.grey.shade700,
                valueColor: const AlwaysStoppedAnimation<Color>(
                  Color(0xFFD0FD3E),
                ),
                minHeight: 6,
                borderRadius: BorderRadius.circular(3),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildQuickStartButtons() {
    return Row(
      children: [
        Expanded(
          child: ElevatedButton.icon(
            onPressed: () {
              /* TODO: Navigate to test recording screen or integrate directly here */
            },
            icon: const Icon(Icons.videocam_outlined),
            label: const Text("Start Fitness Test"),
            style: ElevatedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 16),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              textStyle: const TextStyle(fontWeight: FontWeight.bold),
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: OutlinedButton.icon(
            onPressed: () {
              // Navigate to the UploadVideoPage
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => UploadVideoPage(apiBaseUrl: apiBaseUrl),
                ),
              );
            },
            icon: const Icon(Icons.upload_file_outlined),
            label: const Text("Upload Video"),
            style: OutlinedButton.styleFrom(
              foregroundColor: Colors.white,
              side: const BorderSide(color: Colors.white54),
              padding: const EdgeInsets.symmetric(vertical: 16),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              textStyle: const TextStyle(fontWeight: FontWeight.bold),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildPerformanceGrid() {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisSpacing: 12,
      mainAxisSpacing: 12,
      childAspectRatio: 1.6,
      children: _athleteData!.recentPerformance.entries.map((entry) {
        const icons = {
          "Vertical Jump": Icons.arrow_upward_rounded,
          "Shuttle Run": Icons.shuffle_rounded,
          "Endurance": Icons.timer_outlined,
          "Sit-ups (1 min)": Icons.fitness_center,
        };
        return PerformanceCard(
          testName: entry.key,
          icon: icons[entry.key] ?? Icons.help_outline,
          performanceData: entry.value,
        );
      }).toList(),
    );
  }

  Widget _buildChallengesList() {
    return Column(
      children: _athleteData!.ongoingChallenges.map((challenge) {
        return Card(
          color: Colors.grey.shade900.withOpacity(0.6),
          margin: const EdgeInsets.only(bottom: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          child: ListTile(
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 16,
              vertical: 8,
            ),
            title: Text(
              challenge.title,
              style: const TextStyle(
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
            subtitle: Text(
              challenge.deadline,
              style: TextStyle(color: Colors.grey.shade400),
            ),
            trailing: ElevatedButton(
              onPressed: () {
                /* TODO: Join challenge */
              },
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 24),
              ),
              child: const Text("Join"),
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Text(
      title,
      style: const TextStyle(
        color: Colors.white,
        fontSize: 22,
        fontWeight: FontWeight.bold,
      ),
    );
  }
}