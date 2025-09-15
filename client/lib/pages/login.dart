// In lib/pages/login.dart

import 'dart:convert';
import 'dart:io';
import 'package:client/pages/homepage.dart';
import 'package:client/pages/register.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  bool _isLoading = false;

  Future<void> _loginUser() async {
    if (_emailController.text.isEmpty || _passwordController.text.isEmpty) {
      _showErrorSnackBar("Please enter both email and password.");
      return;
    }

    setState(() { _isLoading = true; });

    // IMPORTANT: Make sure this IP is correct and uses dots, not hyphens.
    const String apiUrl = "http://127.0.0.1:8000/auth/email/login"; 

    try {
      final response = await http.post(
        Uri.parse(apiUrl),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': _emailController.text.trim(),
          'pwd': _passwordController.text,
        }),
      );

      // Check for a successful status code from the server
      if (response.statusCode >= 200 && response.statusCode < 300) {
        final responseBody = jsonDecode(response.body);

        if (responseBody['success'] == true) {
          // --- SAVE USER DATA LOCALLY ---
          final SharedPreferences prefs = await SharedPreferences.getInstance();
          await prefs.setString('userid', responseBody['userid']);
          await prefs.setString('name', responseBody['name']);
          await prefs.setString('email', responseBody['email']);
          await prefs.setString('profilePic', responseBody['profilePic'] ?? '');
          // --- END SAVING DATA ---

          if (mounted) {
            Navigator.pushAndRemoveUntil(
              context,
              MaterialPageRoute(builder: (context) => const HomePage()),
              (Route<dynamic> route) => false,
            );
          }
        } else {
          _showErrorSnackBar(responseBody['message'] ?? "Login failed.");
        }
      } else {
        final responseBody = jsonDecode(response.body);
        _showErrorSnackBar(responseBody['detail'] ?? "Invalid email or password.");
      }
    } on SocketException {
      _showErrorSnackBar("Failed to connect to the server. Please check your network connection and the IP address.");
    } on FormatException {
      _showErrorSnackBar("Received an invalid response from the server. Please check server logs.");
    } catch (e) {
      _showErrorSnackBar("An unknown error occurred. Please try again.");
      print("Login Error: $e");
    } finally {
      if (mounted) {
        setState(() { _isLoading = false; });
      }
    }
  }

  void _showErrorSnackBar(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.redAccent,
      ),
    );
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final screenHeight = MediaQuery.of(context).size.height;

    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/login.png', fit: BoxFit.cover),
          Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                stops: [0.0, 0.7],
                colors: [ Color(0xF2000000), Colors.transparent ],
                begin: Alignment.bottomCenter,
                end: Alignment.topCenter,
              ),
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24.0),
              child: SingleChildScrollView(
                child: ConstrainedBox(
                  constraints: BoxConstraints(minHeight: screenHeight - MediaQuery.of(context).padding.top),
                  child: IntrinsicHeight(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (Navigator.canPop(context))
                          IconButton(
                            icon: const Icon(Icons.arrow_back_ios, color: Colors.white),
                            onPressed: () => Navigator.pop(context),
                          ),
                        SizedBox(height: screenHeight * 0.15),
                        const Text('Welcome Back', style: TextStyle(color: Colors.white, fontSize: 34, fontWeight: FontWeight.bold)),
                        const Text('Sign in to continue', style: TextStyle(color: Colors.white70, fontSize: 18)),
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
                        TextField(
                          controller: _passwordController,
                          obscureText: true,
                          style: const TextStyle(color: Colors.white),
                          decoration: InputDecoration(
                            hintText: 'Password',
                            hintStyle: const TextStyle(color: Colors.white70),
                            filled: true,
                            fillColor: const Color(0x1AFFFFFF),
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(12.0), borderSide: BorderSide.none),
                            prefixIcon: const Icon(Icons.lock_outline, color: Colors.white70),
                          ),
                        ),
                        const SizedBox(height: 30),
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton(
                            onPressed: _isLoading ? null : _loginUser,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFFD0FD3E),
                              foregroundColor: Colors.black,
                              disabledBackgroundColor: Colors.grey.shade800,
                              padding: const EdgeInsets.symmetric(vertical: 18),
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                            ),
                            child: _isLoading
                                ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 3, color: Colors.black))
                                : const Text('LOG IN', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                          ),
                        ),
                        const SizedBox(height: 20),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            const Text("Don't have an account?", style: TextStyle(color: Colors.white70)),
                            TextButton(
                              onPressed: () {
                                Navigator.pushReplacement(
                                  context,
                                  MaterialPageRoute(builder: (context) => const RegisterPage()),
                                );
                              },
                              child: const Text('Sign Up', style: TextStyle(color: Color(0xFFD0FD3E), fontWeight: FontWeight.bold)),
                            ),
                          ],
                        ),
                        const SizedBox(height: 20),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}