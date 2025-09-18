import 'dart:convert';
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:intl/intl.dart';
import 'package:client/pages/login.dart';

class GoogleSignUpPage extends StatefulWidget {
  final String email;
  final String name;
  final String profilePic;

  const GoogleSignUpPage({
    super.key,
    required this.email,
    required this.name,
    required this.profilePic,
  });

  @override
  State<GoogleSignUpPage> createState() => _GoogleSignUpPageState();
}

class _GoogleSignUpPageState extends State<GoogleSignUpPage> {
  final TextEditingController _weightController = TextEditingController();
  final TextEditingController _heightController = TextEditingController();
  final TextEditingController _phoneController = TextEditingController();
  final TextEditingController _dobController = TextEditingController();

  DateTime? _selectedDate;
  bool _isLoading = false;

  Future<void> _finishGoogleRegistration() async {
    if (_weightController.text.isEmpty ||
        _heightController.text.isEmpty ||
        _phoneController.text.isEmpty ||
        _dobController.text.isEmpty) {
      _showErrorSnackBar("Please fill all required fields.");
      return;
    }

    setState(() { _isLoading = true; });

    try {
      final Map<String, dynamic> userData = {
        "username": widget.name,
        "email": widget.email,
        "dob": _dobController.text,
        "height": _heightController.text.trim(),
        "weight": _weightController.text.trim(),
        "phoneno": _phoneController.text.trim(),
        "profilePic": widget.profilePic,
      };

      const String apiUrl = "http://127.0.0.1:8000/auth/google/register";

      final response = await http.post(
        Uri.parse(apiUrl),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(userData),
      );

      final responseBody = jsonDecode(response.body);

      if (response.statusCode == 200 && responseBody['success'] == true) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text("Registration successful!"), backgroundColor: Colors.green),
          );
          Navigator.pushAndRemoveUntil(
            context,
            MaterialPageRoute(builder: (context) => const LoginPage()),
            (Route<dynamic> route) => false,
          );
        }
      } else {
        _showErrorSnackBar(responseBody['detail'] ?? "Registration failed.");
      }
    } catch (e) {
      _showErrorSnackBar("An error occurred. Please check your connection.");
      print("Google Registration Error: $e");
    } finally {
      if (mounted) setState(() { _isLoading = false; });
    }
  }

  void _showErrorSnackBar(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.redAccent),
    );
  }

  Future<void> _selectDate(BuildContext context) async {
    final DateTime? picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate ?? DateTime.now(),
      firstDate: DateTime(1920),
      lastDate: DateTime.now(),
      builder: (context, child) {
        return Theme(
          data: ThemeData.dark().copyWith(
            colorScheme: const ColorScheme.dark(
              primary: Color(0xFFD0FD3E), onPrimary: Colors.black, onSurface: Colors.white,
            ),
            dialogBackgroundColor: const Color(0xFF1E1E1E),
          ),
          child: child!,
        );
      },
    );
    if (picked != null && picked != _selectedDate) {
      setState(() {
        _selectedDate = picked;
        _dobController.text = DateFormat('yyyy-MM-dd').format(picked);
      });
    }
  }

  @override
  void dispose() {
    _weightController.dispose();
    _heightController.dispose();
    _phoneController.dispose();
    _dobController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/fullreg.png', fit: BoxFit.cover),
          ColorFiltered(
            colorFilter: const ColorFilter.mode(Color(0xCC000000), BlendMode.darken),
            child: Container(color: Colors.transparent),
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
                  const Text('Almost There!', style: TextStyle(color: Colors.white, fontSize: 34, fontWeight: FontWeight.bold)),
                  Text('Welcome, ${widget.name}. Just a few more details.', style: const TextStyle(color: Colors.white70, fontSize: 18)),
                  const SizedBox(height: 20),
                  Expanded(
                    child: SingleChildScrollView(
                      child: Column(
                        children: [
                          CircleAvatar(
                            radius: 50,
                            backgroundColor: const Color(0x1AFFFFFF),
                            backgroundImage: widget.profilePic.isNotEmpty
                                ? NetworkImage(widget.profilePic)
                                : null,
                            child: widget.profilePic.isEmpty
                                ? const Icon(Icons.account_circle, size: 50, color: Colors.white70)
                                : null,
                          ),
                          const SizedBox(height: 20),
                          Row(
                            children: [
                              Expanded(child: _buildTextField(controller: _weightController, hint: 'Weight (kg)', icon: Icons.fitness_center, keyboardType: TextInputType.number)),
                              const SizedBox(width: 16),
                              Expanded(child: _buildTextField(controller: _heightController, hint: 'Height (cm)', icon: Icons.height, keyboardType: TextInputType.number)),
                            ],
                          ),
                          const SizedBox(height: 16),
                          _buildTextField(controller: _phoneController, hint: 'Phone Number', icon: Icons.phone, keyboardType: TextInputType.phone),
                          const SizedBox(height: 16),
                          _buildTextField(controller: _dobController, hint: 'Date of Birth', icon: Icons.calendar_today, readOnly: true, onTap: () => _selectDate(context)),
                          const SizedBox(height: 30),
                          SizedBox(
                            width: double.infinity,
                            child: ElevatedButton(
                              onPressed: _isLoading ? null : _finishGoogleRegistration,
                              style: ElevatedButton.styleFrom(
                                backgroundColor: const Color(0xFFD0FD3E),
                                foregroundColor: Colors.black,
                                disabledBackgroundColor: Colors.grey.shade800,
                                padding: const EdgeInsets.symmetric(vertical: 18),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                              ),
                              child: _isLoading
                                  ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 3, color: Colors.black))
                                  : const Text('FINISH', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                            ),
                          ),
                          const SizedBox(height: 20),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTextField({ required TextEditingController controller, required String hint, required IconData icon, bool obscureText = false, bool readOnly = false, TextInputType? keyboardType, VoidCallback? onTap }) {
    return TextField(
      controller: controller,
      keyboardType: keyboardType,
      obscureText: obscureText,
      readOnly: readOnly,
      onTap: onTap,
      style: const TextStyle(color: Colors.white),
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: const TextStyle(color: Colors.white70),
        filled: true,
        fillColor: const Color(0x1AFFFFFF),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12.0), borderSide: BorderSide.none),
        prefixIcon: Icon(icon, color: Colors.white70),
      ),
    );
  }
}
