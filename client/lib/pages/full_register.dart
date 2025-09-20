// In lib/pages/full_register.dart

import 'dart:convert';
import 'dart:io';
import 'dart:ui';
import 'package:client/pages/login.dart';
import 'package:flutter/foundation.dart'; // Required for Uint8List
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'package:intl/intl.dart';

class CompleteProfilePage extends StatefulWidget {
  final String email;
  const CompleteProfilePage({super.key, required this.email});

  @override
  State<CompleteProfilePage> createState() => _CompleteProfilePageState();
}

class _CompleteProfilePageState extends State<CompleteProfilePage> {
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _weightController = TextEditingController();
  final TextEditingController _heightController = TextEditingController();
  final TextEditingController _phoneController = TextEditingController();
  final TextEditingController _dobController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final TextEditingController _confirmPasswordController = TextEditingController();

  XFile? _profileImage;
  final ImagePicker _picker = ImagePicker();
  DateTime? _selectedDate;
  bool _isLoading = false;

  // --- UPDATED API CALL TO SEND IMAGE AS BASE64 STRING ---
  Future<void> _finishRegistration() async {
    // 1. --- VALIDATION ---
    if (_usernameController.text.isEmpty ||
        _weightController.text.isEmpty ||
        _heightController.text.isEmpty ||
        _phoneController.text.isEmpty ||
        _dobController.text.isEmpty ||
        _passwordController.text.isEmpty) {
      _showErrorSnackBar("Please fill all fields.");
      return;
    }
    if (_passwordController.text != _confirmPasswordController.text) {
      _showErrorSnackBar("Passwords do not match.");
      return;
    }
    if (_profileImage == null) {
      _showErrorSnackBar("Please select a profile picture.");
      return;
    }
    // --- END VALIDATION ---

    setState(() { _isLoading = true; });

    try {
      // --- 2. CONVERT IMAGE TO BASE64 STRING ---
      final Uint8List imageBytes = await _profileImage!.readAsBytes();
      final String base64Image = base64Encode(imageBytes);
      // --- END IMAGE CONVERSION ---
      
      // --- 3. ASSEMBLE JSON DATA PAYLOAD ---
      final Map<String, dynamic> userData = {
        "username": _usernameController.text.trim(),
        "email": widget.email,
        "pwd": _passwordController.text,
        "dob": _dobController.text,
        "height": _heightController.text.trim(),
        "weight": _weightController.text.trim(),
        "phoneno": _phoneController.text.trim(),
        // Send the very long Base64 string as the profilePic
        "profilePic": base64Image,
      };
      // --- END DATA ASSEMBLY ---

      // --- 4. MAKE JSON API CALL ---
      // IMPORTANT: Replace with your computer's IP address
      const String apiUrl = "http://127.0.0.1:8000/auth/email/signup";

      final response = await http.post(
        Uri.parse(apiUrl),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(userData),
      );
      
      final responseBody = jsonDecode(response.body);

      if (response.statusCode == 200 && responseBody['success'] == true) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text("Registration successful! Please log in."),
              backgroundColor: Colors.green,
            ),
          );
          Navigator.pushAndRemoveUntil(
            context,
            MaterialPageRoute(builder: (context) => const LoginPage()),
            (Route<dynamic> route) => false,
          );
        }
      } else {
        _showErrorSnackBar(responseBody['message'] ?? "An unknown error occurred.");
      }
      // --- END API CALL ---

    } catch (e) {
      _showErrorSnackBar("An error occurred. Please check your connection.");
      print("Registration Error: $e");
    } finally {
      if (mounted) {
        setState(() { _isLoading = false; });
      }
    }
  }

  // --- Helper functions (error snackbar, image picker, date picker) ---

  void _showErrorSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.redAccent),
    );
  }

  void _showImagePickerOptions() {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF2C2C2E),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (BuildContext context) {
        return SafeArea(
          child: Wrap(
            children: <Widget>[
              ListTile(
                leading: const Icon(Icons.photo_library, color: Colors.white),
                title: const Text('Choose from Gallery', style: TextStyle(color: Colors.white)),
                onTap: () { _pickImage(ImageSource.gallery); Navigator.of(context).pop(); },
              ),
              ListTile(
                leading: const Icon(Icons.camera_alt, color: Colors.white),
                title: const Text('Take a Picture', style: TextStyle(color: Colors.white)),
                onTap: () { _pickImage(ImageSource.camera); Navigator.of(context).pop(); },
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _pickImage(ImageSource source) async {
    try {
      final XFile? pickedFile = await _picker.pickImage(source: source);
      if (pickedFile != null) {
        setState(() { _profileImage = pickedFile; });
      }
    } catch (e) {
      print('Failed to pick image: $e');
    }
  }

  Future<void> _selectDate(BuildContext context) async {
    final DateTime? picked = await showDatePicker(
      context: context, initialDate: _selectedDate ?? DateTime.now(), firstDate: DateTime(1920), lastDate: DateTime.now(),
      builder: (context, child) {
        return Theme(
          data: ThemeData.dark().copyWith(
            colorScheme: const ColorScheme.dark(primary: Color(0xFFD0FD3E), onPrimary: Colors.black, onSurface: Colors.white), dialogTheme: DialogThemeData(backgroundColor: const Color(0xFF1E1E1E)),
          ),
          child: child!,
        );
      },
    );
    if (picked != null && picked != _selectedDate) {
      setState(() { _selectedDate = picked; _dobController.text = DateFormat('yyyy-MM-dd').format(picked); });
    }
  }

  @override
  void dispose() {
    _usernameController.dispose(); _weightController.dispose(); _heightController.dispose(); _phoneController.dispose(); _dobController.dispose(); _passwordController.dispose(); _confirmPasswordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // --- UI is unchanged ---
    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/fullreg.png', fit: BoxFit.cover),
          ColorFiltered(
            colorFilter: ColorFilter.mode(const Color(0xCC000000), BlendMode.darken),
            child: Container(color: Colors.transparent),
          ),
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                stops: const [0.0, 0.8], colors: [const Color(0xD9000000), Colors.transparent], begin: Alignment.bottomCenter, end: Alignment.topCenter,
              ),
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SizedBox(height: 20),
                  const Text('Complete Your Profile', style: TextStyle(color: Colors.white, fontSize: 34, fontWeight: FontWeight.bold)),
                  const Text('Just a few more details to get set up.', style: TextStyle(color: Colors.white70, fontSize: 18)),
                  const SizedBox(height: 20),
                  Expanded(
                    child: SingleChildScrollView(
                      child: Column(
                        children: [
                          GestureDetector(
                            onTap: _showImagePickerOptions,
                            child: CircleAvatar(
                              radius: 50, backgroundColor: const Color(0x1AFFFFFF),
                              backgroundImage: _profileImage != null ? FileImage(File(_profileImage!.path)) : null,
                              child: _profileImage == null ? const Icon(Icons.add_a_photo, color: Colors.white70, size: 40) : null,
                            ),
                          ),
                          const SizedBox(height: 20),
                          _buildTextField(controller: _usernameController, hint: 'Username', icon: Icons.person),
                          const SizedBox(height: 16),
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
                          const SizedBox(height: 16),
                          _buildTextField(controller: _passwordController, hint: 'Password', icon: Icons.lock_outline, obscureText: true),
                          const SizedBox(height: 16),
                          _buildTextField(controller: _confirmPasswordController, hint: 'Confirm Password', icon: Icons.lock, obscureText: true),
                          const SizedBox(height: 30),
                          SizedBox(
                            width: double.infinity,
                            child: ElevatedButton(
                              onPressed: _isLoading ? null : _finishRegistration,
                              style: ElevatedButton.styleFrom(
                                backgroundColor: const Color(0xFFD0FD3E), foregroundColor: Colors.black, disabledBackgroundColor: Colors.grey.shade800,
                                padding: const EdgeInsets.symmetric(vertical: 18), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
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

  Widget _buildTextField({ required TextEditingController controller, required String hint, required IconData icon, bool obscureText = false, bool readOnly = false, TextInputType? keyboardType, VoidCallback? onTap, }) {
    return TextField( controller: controller, keyboardType: keyboardType, obscureText: obscureText, readOnly: readOnly, onTap: onTap, style: const TextStyle(color: Colors.white),
      decoration: InputDecoration(
        hintText: hint, hintStyle: const TextStyle(color: Colors.white70), filled: true, fillColor: const Color(0x1AFFFFFF),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12.0), borderSide: BorderSide.none),
        prefixIcon: Icon(icon, color: Colors.white70),
      ),
    );
  }
}