// In lib/pages/home_page.dart

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  String? _userName;
  String? _userEmail;
  String? _profilePicUrl;
  bool _isLoading = true;

  // IMPORTANT: This must match the IP in your other files
  final String _baseUrl = "http://127.0.0.1:8000";

  @override
  void initState() {
    super.initState();
    _loadUserData();
  }

  // Function to load the saved data from the device
  Future<void> _loadUserData() async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    setState(() {
      _userName = prefs.getString('userName');
      _userEmail = prefs.getString('userEmail');
      
      // Retrieve the path and construct the full URL
      final String? profilePicPath = prefs.getString('profilePic');
      if (profilePicPath != null && profilePicPath.isNotEmpty) {
        _profilePicUrl = _baseUrl + profilePicPath;
      }
      
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: const Text('Home'),
        backgroundColor: Colors.grey.shade900,
        elevation: 0,
        actions: [
          // Add a logout button or other actions here
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () {
              // TODO: Implement logout logic (clear shared_preferences and navigate to login)
            },
          )
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Center(
              child: Padding(
                padding: const EdgeInsets.all(24.0),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    // --- DISPLAY THE PROFILE PICTURE ---
                    CircleAvatar(
                      radius: 80,
                      backgroundColor: Colors.grey.shade800,
                      // Use NetworkImage to load the image from your server
                      backgroundImage: _profilePicUrl != null
                          ? NetworkImage(_profilePicUrl!)
                          : null,
                      child: _profilePicUrl == null
                          // Show a placeholder icon if there's no image URL
                          ? const Icon(Icons.person, size: 80, color: Colors.white70)
                          : null,
                    ),
                    const SizedBox(height: 30),

                    // Display other user information
                    Text(
                      // Use a default value if the name is not found
                      _userName ?? 'Welcome!',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 28,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      _userEmail ?? 'No email found',
                      style: TextStyle(
                        color: Colors.grey.shade400,
                        fontSize: 18,
                      ),
                    ),
                    // You can add more user details here
                  ],
                ),
              ),
            ),
    );
  }
}