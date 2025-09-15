import 'package:client/pages/full_register.dart';
import 'package:flutter/material.dart';
import 'package:pinput/pinput.dart';

class OtpVerificationPage extends StatelessWidget {
  const OtpVerificationPage({super.key});

  @override
  Widget build(BuildContext context) {
    // Pinput theme for the OTP fields
    final defaultPinTheme = PinTheme(
      width: 56,
      height: 60,
      textStyle: const TextStyle(
        fontSize: 22,
        color: Colors.white,
      ),
      decoration: BoxDecoration(
        // OLD: color: Colors.white.withOpacity(0.1),
        color: const Color(0x1AFFFFFF), // NEW: 10% opaque white
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.transparent),
      ),
    );

    void navigateToNextScreen() {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (context) => const CompleteProfilePage()),
      );
    }

    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          // 1. Background Image
          Image.asset(
            'assets/otp.png',
            fit: BoxFit.cover,
          ),

          // 2. Uniform dark filter for a very dark effect
          ColorFiltered(
            colorFilter: ColorFilter.mode(
              // OLD: Colors.black.withOpacity(0.75),
              const Color(0xBF000000), // NEW: 75% opaque black
              BlendMode.darken,
            ),
            child: Container(
              color: Colors.transparent,
            ),
          ),

          // 3. Gradient Overlay for the bottom
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                stops: const [0.0, 0.8],
                colors: [
                  // OLD: Colors.black.withOpacity(0.85),
                  const Color(0xD9000000), // NEW: 85% opaque black
                  Colors.transparent,
                ],
                begin: Alignment.bottomCenter,
                end: Alignment.topCenter,
              ),
            ),
          ),

          // 4. UI Content
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Back Button
                  IconButton(
                    icon: const Icon(Icons.arrow_back_ios, color: Colors.white),
                    onPressed: () => Navigator.pop(context),
                  ),
                  const SizedBox(height: 40),

                  // Header Text
                  const Text(
                    'Verify Account',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 34,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const Text(
                    'Enter the 6-digit code sent to your email.',
                    style: TextStyle(
                      color: Colors.white70,
                      fontSize: 18,
                    ),
                  ),

                  const Spacer(), // Pushes form to the bottom

                  // --- FORM CONTENT ---
                  Center(
                    child: Pinput(
                      length: 6,
                      defaultPinTheme: defaultPinTheme,
                      focusedPinTheme: defaultPinTheme.copyWith(
                        decoration: defaultPinTheme.decoration!.copyWith(
                          border: Border.all(color: const Color(0xFFD0FD3E)),
                        ),
                      ),
                      onCompleted: (pin) {
                        navigateToNextScreen();
                      },
                    ),
                  ),
                  const SizedBox(height: 30),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: navigateToNextScreen,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFFD0FD3E),
                        foregroundColor: Colors.black,
                        padding: const EdgeInsets.symmetric(vertical: 18),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: const Text('VERIFY', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                    ),
                  ),
                  const SizedBox(height: 20),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Text("Didn't receive the code?", style: TextStyle(color: Colors.white70)),
                      TextButton(
                        onPressed: () {
                          // TODO: Implement resend OTP logic
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