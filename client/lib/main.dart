import 'package:client/pages/login.dart';
import 'package:client/pages/register.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
  // Make sure this path is correct

// The main entry point for the application.
void main() {
  runApp(const MyApp());
}

// MyApp is the root widget of your application.
class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'FitLife App',
      debugShowCheckedModeBanner: false,
      // Define the overall theme for the application to match the design.
      theme: ThemeData(
        brightness: Brightness.dark,
        fontFamily: 'Roboto', // Or any other modern font you prefer
        // Define the primary color used for the main action button.
        primaryColor: const Color(0xFFD0FD3E),
        scaffoldBackgroundColor: Colors.black,
      ),
      // Set WelcomePage as the initial route of the app.
      home: const WelcomePage(),
    );
  }
}

// The WelcomePage is the first screen the user sees.
class WelcomePage extends StatelessWidget {
  const WelcomePage({super.key});

  @override
  Widget build(BuildContext context) {
    // This ensures the status bar icons (time, battery) are visible.
    SystemChrome.setSystemUIOverlayStyle(SystemUiOverlayStyle.light);

    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          // 1. Background Image
          Image.asset(
            'assets/backround.png', // Ensure this image is in your assets folder
            fit: BoxFit.cover,
          ),

          // 2. Gradient Overlay for text readability
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  Colors.black.withOpacity(0.8),
                  Colors.black.withOpacity(0.6),
                  Colors.transparent
                ],
                begin: Alignment.bottomCenter,
                end: Alignment.topCenter,
              ),
            ),
          ),

          // 3. UI Content (Logo, Text, Buttons)
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 20.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Top section with your app's logo
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.9),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      Icons.sports_gymnastics, // Placeholder logo icon
                      color: Colors.black,
                      size: 24,
                    ),
                  ),

                  const Spacer(), // Pushes content below it to the bottom

                  // Motivational Text
                  const Text(
                    'TRAIN\nRECORD\nACHEIVE',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 38,
                      fontWeight: FontWeight.bold,
                      height: 1.2,
                    ),
                  ),
                  const SizedBox(height: 30),

                  // Action Buttons
                  Row(
                    children: [
                      // "Join Now" Button
                      Expanded(
                        child: ElevatedButton(
                          onPressed: () {
                            // Navigate to the SignUpPage when pressed
                            Navigator.push(
                              context,
                              MaterialPageRoute(builder: (context) => const RegisterPage()),
                            );
                          },
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Theme.of(context).primaryColor, // Use theme color
                            foregroundColor: Colors.black,
                            padding: const EdgeInsets.symmetric(vertical: 18),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(50),
                            ),
                          ),
                          child: const Text(
                            'Join Now',
                            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                          ),
                        ),
                      ),
                      const SizedBox(width: 15),
                      
                      // "Log In" Button
                      Expanded(
                        child: ElevatedButton(
                          onPressed: () {
                            // Navigate to the LoginPage when pressed
                            Navigator.push(
                              context,
                              MaterialPageRoute(builder: (context) => const LoginPage()),
                            );
                          },
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.white.withOpacity(0.2),
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(vertical: 18),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(50),
                            ),
                          ),
                          child: const Text(
                            'Log In',
                            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}