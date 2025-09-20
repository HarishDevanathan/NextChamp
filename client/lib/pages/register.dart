import 'dart:convert';
import 'package:client/pages/google_sign.dart';
import 'package:client/pages/login.dart';
import 'package:client/pages/otppicker.dart';
import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:http/http.dart' as http;
import 'package:firebase_auth/firebase_auth.dart';

class RegisterPage extends StatefulWidget {
  const RegisterPage({super.key});

  @override
  State<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends State<RegisterPage> {
  final TextEditingController _emailController = TextEditingController();
  bool _isLoading = false;

  final GoogleSignIn _googleSignIn = GoogleSignIn();

  Future<void> _sendOtpAndNavigate() async {
    if (_emailController.text.isEmpty || !_emailController.text.contains('@')) {
      _showErrorSnackBar("Please enter a valid email address.");
      return;
    }

    setState(() { _isLoading = true; });

    const String apiUrl = "http://127.0.0.1:8000/auth/email/signup/sendotp";

    try {
      final response = await http.post(
        Uri.parse(apiUrl),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'email': _emailController.text.trim()}),
      );
      
      final responseBody = jsonDecode(response.body);

      if (response.statusCode == 200) {
        if (mounted) {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => OtpVerificationPage(email: _emailController.text.trim()),
            ),
          );
        }
      } else {
        _showErrorSnackBar(responseBody['message'] ?? "An error occurred.");
      }
    } catch (e) {
      _showErrorSnackBar("Failed to connect to the server. Please check your connection and IP address.");
      print("Connection Error: $e");
    } finally {
      if (mounted) setState(() { _isLoading = false; });
    }
  }

  // --- Google Sign-In with passing data ---
  Future<void> _handleGoogleSignIn() async {
    try {
      final GoogleSignInAccount? googleUser = await _googleSignIn.signIn();
      if (googleUser == null) return; // user canceled

      final GoogleSignInAuthentication googleAuth = await googleUser.authentication;

      final credential = GoogleAuthProvider.credential(
        accessToken: googleAuth.accessToken,
        idToken: googleAuth.idToken,
      );

      // Sign in with Firebase
      await FirebaseAuth.instance.signInWithCredential(credential);

      // Extract user info
      final String email = googleUser.email;
      final String? name = googleUser.displayName;
      final String? photoUrl = googleUser.photoUrl;

      if (mounted) {
        // Navigate to Google Signup page with user data
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (context) => GoogleSignUpPage(
              email: email,
              name: name ?? '',
              profilePic: photoUrl ?? '',
            ),
          ),
        );
      }
    } catch (e) {
      print('Google Sign-In Error: $e');
      _showErrorSnackBar('Failed to sign in with Google.');
    }
  }

  void _showErrorSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.redAccent),
    );
  }

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/backround.png', fit: BoxFit.cover),
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                stops: const [0.0, 0.7],
                colors: [const Color(0xF2000000), Colors.transparent],
                begin: Alignment.bottomCenter,
                end: Alignment.topCenter,
              ),
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  IconButton(
                    icon: const Icon(Icons.arrow_back_ios, color: Colors.white),
                    onPressed: () => Navigator.pop(context),
                  ),
                  const SizedBox(height: 20),
                  const Text('Join the Club', style: TextStyle(color: Colors.white, fontSize: 34, fontWeight: FontWeight.bold)),
                  const Text('Create your account to start', style: TextStyle(color: Colors.white70, fontSize: 18)),
                  const Spacer(),
                  TextField(
                    controller: _emailController,
                    keyboardType: TextInputType.emailAddress,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      hintText: 'Email Address',
                      hintStyle: const TextStyle(color: Colors.white70),
                      filled: true,
                      fillColor: const Color(0x1AFFFFFF),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12.0), borderSide: BorderSide.none),
                      prefixIcon: const Icon(Icons.email_outlined, color: Colors.white70),
                    ),
                  ),
                  const SizedBox(height: 20),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: _isLoading ? null : _sendOtpAndNavigate,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFFD0FD3E),
                        foregroundColor: Colors.black,
                        disabledBackgroundColor: Colors.grey.shade800,
                        padding: const EdgeInsets.symmetric(vertical: 18),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      child: _isLoading
                          ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 3, color: Colors.black))
                          : const Text('CONTINUE', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                    ),
                  ),
                  const SizedBox(height: 25),
                  const Row(
                    children: [
                      Expanded(child: Divider(color: Colors.white54)),
                      Padding(
                        padding: EdgeInsets.symmetric(horizontal: 16.0),
                        child: Text('Or sign up with', style: TextStyle(color: Colors.white70)),
                      ),
                      Expanded(child: Divider(color: Colors.white54)),
                    ],
                  ),
                  const SizedBox(height: 25),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      GestureDetector(
                        onTap: _handleGoogleSignIn,
                        child: const CircleAvatar(
                          radius: 28,
                          backgroundColor: Colors.white,
                          backgroundImage: AssetImage('assets/google.png'),
                        ),
                      ),
                      const SizedBox(width: 25),
                      GestureDetector(
                        onTap: () { /* TODO: Facebook login */ },
                        child: const CircleAvatar(
                          radius: 28,
                          backgroundColor: Color(0xFF1877F2),
                          child: Icon(Icons.facebook, color: Colors.white, size: 35),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 25),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Text("Already a member?", style: TextStyle(color: Colors.white70)),
                      TextButton(
                        onPressed: () {
                          Navigator.pushReplacement(
                            context,
                            MaterialPageRoute(builder: (context) => const LoginPage()),
                          );
                        },
                        child: const Text('Log In', style: TextStyle(color: Color(0xFFD0FD3E), fontWeight: FontWeight.bold)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
