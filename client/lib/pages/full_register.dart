import 'dart:io'; // <-- THIS IS THE MISSING LINE THAT FIXES THE ERROR
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:intl/intl.dart';

class CompleteProfilePage extends StatefulWidget {
  const CompleteProfilePage({super.key});

  @override
  State<CompleteProfilePage> createState() => _CompleteProfilePageState();
}

class _CompleteProfilePageState extends State<CompleteProfilePage> {
  final TextEditingController _weightController = TextEditingController();
  final TextEditingController _heightController = TextEditingController();
  final TextEditingController _phoneController = TextEditingController();
  final TextEditingController _dobController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final TextEditingController _confirmPasswordController = TextEditingController();

  XFile? _profileImage;
  final ImagePicker _picker = ImagePicker();
  DateTime? _selectedDate;

  // --- THIS IS THE NEW POP-UP LOGIC ---
  // This function shows the modal bottom sheet with options.
  void _showImagePickerOptions() {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF2C2C2E), // A dark, iOS-style sheet color
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (BuildContext context) {
        return SafeArea(
          child: Wrap(
            children: <Widget>[
              ListTile(
                leading: const Icon(Icons.photo_library, color: Colors.white),
                title: const Text('Choose from Gallery', style: TextStyle(color: Colors.white)),
                onTap: () {
                  _pickImage(ImageSource.gallery);
                  Navigator.of(context).pop(); // Close the sheet
                },
              ),
              ListTile(
                leading: const Icon(Icons.camera_alt, color: Colors.white),
                title: const Text('Take a Picture', style: TextStyle(color: Colors.white)),
                onTap: () {
                  _pickImage(ImageSource.camera);
                  Navigator.of(context).pop(); // Close the sheet
                },
              ),
            ],
          ),
        );
      },
    );
  }

  // This function now handles the actual image picking.
  Future<void> _pickImage(ImageSource source) async {
    try {
      final XFile? pickedFile = await _picker.pickImage(source: source);
      if (pickedFile != null) {
        setState(() {
          _profileImage = pickedFile;
        });
      }
    } catch (e) {
      // Handle potential errors, like permission denial
      print('Failed to pick image: $e');
    }
  }
  // --- END OF NEW POP-UP LOGIC ---


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
    _passwordController.dispose();
    _confirmPasswordController.dispose();
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
            colorFilter: ColorFilter.mode(const Color(0xCC000000), BlendMode.darken),
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
                  const SizedBox(height: 20),
                  const Text('Complete Your Profile', style: TextStyle(color: Colors.white, fontSize: 34, fontWeight: FontWeight.bold)),
                  const Text('Just a few more details to get set up.', style: TextStyle(color: Colors.white70, fontSize: 18)),
                  const SizedBox(height: 20),
                  Expanded(
                    child: SingleChildScrollView(
                      child: Column(
                        children: [
                          GestureDetector(
                            // The onTap now calls the function that shows the pop-up
                            onTap: _showImagePickerOptions,
                            child: CircleAvatar(
                              radius: 50,
                              backgroundColor: const Color(0x1AFFFFFF),
                              backgroundImage: _profileImage != null ? FileImage(File(_profileImage!.path)) : null,
                              child: _profileImage == null
                                  ? const Icon(Icons.add_a_photo, color: Colors.white70, size: 40)
                                  : null,
                            ),
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
                          const SizedBox(height: 16),
                          _buildTextField(controller: _passwordController, hint: 'Password', icon: Icons.lock_outline, obscureText: true),
                          const SizedBox(height: 16),
                          _buildTextField(controller: _confirmPasswordController, hint: 'Confirm Password', icon: Icons.lock, obscureText: true),
                          const SizedBox(height: 30),
                          SizedBox(
                            width: double.infinity,
                            child: ElevatedButton(
                              onPressed: () {
                                // TODO: Validate fields and save user data
                              },
                              style: ElevatedButton.styleFrom(
                                backgroundColor: const Color(0xFFD0FD3E),
                                foregroundColor: Colors.black,
                                padding: const EdgeInsets.symmetric(vertical: 18),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                              ),
                              child: const Text('FINISH', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
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

  Widget _buildTextField({
    required TextEditingController controller,
    required String hint,
    required IconData icon,
    bool obscureText = false,
    bool readOnly = false,
    TextInputType? keyboardType,
    VoidCallback? onTap,
  }) {
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