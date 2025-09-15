// In lib/pages/otppicker.dart

import 'dart:convert';
import 'package:client/pages/full_register.dart';
import 'package:flutter/material.dart';
import 'package:pinput/pinput.dart';
import 'package:http/http.dart' as http;

class OtpVerificationPage extends StatefulWidget {
  // 1. Accept the email from the Register Page
  final String email;

  const OtpVerificationPage({super.key, required this.email});

  @override
  State<OtpVerificationPage> createState() => _OtpVerificationPageState();
}

class _OtpVerificationPageState extends State<OtpVerificationPage> {
  final TextEditingController _pinController = TextEditingController();
  bool _isLoading = false;

  // --- API CALL LOGIC TO VERIFY OTP ---
  Future<void> _verifyOtp() async {
    if (_pinController.text.length != 6) {
      _showErrorSnackBar("Please enter the complete 6-digit OTP.");
      return;
    }

    setState(() { _isLoading = true; });

    // IMPORTANT: Replace with your computer's IP address
    const String apiUrl = "http://127.0.0.1:8000/auth/email/verifyotp";

    try {
      final response = await http.post(
        Uri.parse(apiUrl),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': widget.email, // Use the email passed to this widget
          'otp': _pinController.text,
        }),
      );

      if (response.statusCode == 200) {
        // On success, navigate to the final registration page
        // AND PASS THE VERIFIED EMAIL
        if (mounted) {
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(
              builder: (context) => CompleteProfilePage(email: widget.email),
            ),
          );
        }
      } else {
        // Handle errors like invalid or expired OTP
        final responseBody = jsonDecode(response.body);
        _showErrorSnackBar(responseBody['detail'] ?? "An error occurred.");
      }
    } catch (e) {
      _showErrorSnackBar("Failed to connect to the server. Please check your connection and IP address.");
    } finally {
      if (mounted) {
        setState(() { _isLoading = false; });
      }
    }
  }

  void _showErrorSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.redAccent,
      ),
    );
  }

  @override
  void dispose() {
    _pinController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final defaultPinTheme = PinTheme(
      width: 56,
      height: 60,
      textStyle: const TextStyle(fontSize: 22, color: Colors.white),
      decoration: BoxDecoration(
        color: const Color(0x1AFFFFFF),
        borderRadius: BorderRadius.circular(8),
      ),
    );

    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/otp.png', fit: BoxFit.cover),
          ColorFiltered(
            colorFilter: ColorFilter.mode(const Color(0xBF000000), BlendMode.darken),
            child: Container(color: Colors.transparent),
          ),
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                stops: const [0.0, 0.8],
                colors: [const Color(0xD9000000), Colors.transparent],
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
                  const SizedBox(height: 40),
                  const Text('Verify Account', style: TextStyle(color: Colors.white, fontSize: 34, fontWeight: FontWeight.bold)),
                  Text(
                    'Enter the 6-digit code sent to\n${widget.email}', // Show the user's email
                    style: const TextStyle(color: Colors.white70, fontSize: 18, height: 1.4),
                  ),
                  const Spacer(),
                  Center(
                    child: Pinput(
                      controller: _pinController,
                      length: 6,
                      defaultPinTheme: defaultPinTheme,
                      focusedPinTheme: defaultPinTheme.copyWith(
                        decoration: defaultPinTheme.decoration!.copyWith(
                          border: Border.all(color: const Color(0xFFD0FD3E)),
                        ),
                      ),
                      onCompleted: (pin) {
                        // Automatically verify when 6 digits are entered
                        _verifyOtp();
                      },
                    ),
                  ),
                  const SizedBox(height: 30),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: _isLoading ? null : _verifyOtp,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFFD0FD3E),
                        foregroundColor: Colors.black,
                        disabledBackgroundColor: Colors.grey.shade800,
                        padding: const EdgeInsets.symmetric(vertical: 18),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      child: _isLoading
                          ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 3, color: Colors.black))
                          : const Text('VERIFY', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                    ),
                  ),
                  const SizedBox(height: 20),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Text("Didn't receive the code?", style: TextStyle(color: Colors.white70)),
                      TextButton(
                        onPressed: () {
                          // TODO: Implement resend OTP logic (call the sendotp endpoint again)
                        },
                        child: const Text('Resend', style: TextStyle(color: Color(0xFFD0FD3E), fontWeight: FontWeight.bold)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}