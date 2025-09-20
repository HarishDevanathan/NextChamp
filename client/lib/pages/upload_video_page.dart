import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;
import 'package:video_player/video_player.dart';
import 'dart:convert';

// Enum for exercise types, matching your Python backend
enum ExerciseType {
  VERTICAL_JUMP,
  SHUTTLE_RUN,
  SITUPS,
  PUSHUPS,
  PLANK_HOLD,
  STANDING_BROAD_JUMP,
  SQUATS,
  ENDURANCE_RUN
}

class UploadVideoPage extends StatefulWidget {
  final String apiBaseUrl;

  const UploadVideoPage({super.key, required this.apiBaseUrl});

  @override
  State<UploadVideoPage> createState() => _UploadVideoPageState();
}

class _UploadVideoPageState extends State<UploadVideoPage> {
  XFile? _videoFile;
  ExerciseType? _selectedExercise;
  bool _isLoading = false;
  String? _analysisMessage;
  VideoPlayerController? _analyzedVideoController;
  String? _testId;
  Map<String, dynamic>? _reportData;

  // User profile fields
  final TextEditingController _userIdController = TextEditingController();
  final TextEditingController _userNameController = TextEditingController();
  final TextEditingController _ageController = TextEditingController();
  final TextEditingController _heightController = TextEditingController();
  final TextEditingController _weightController = TextEditingController();

  final ImagePicker _picker = ImagePicker();

  @override
  void initState() {
    super.initState();
    // Set a default user ID
    _userIdController.text = 'user_${DateTime.now().millisecondsSinceEpoch}';
  }

  Future<void> _pickVideo(ImageSource source) async {
    final XFile? video = await _picker.pickVideo(source: source);
    setState(() {
      _videoFile = video;
      _analysisMessage = null;
      _analyzedVideoController?.dispose();
      _analyzedVideoController = null;
      _testId = null;
      _reportData = null;
    });
  }

  Future<void> _uploadVideo() async {
    if (_videoFile == null || _selectedExercise == null || _userIdController.text.isEmpty) {
      setState(() {
        _analysisMessage = "Please select a video, exercise type, and enter a user ID.";
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _analysisMessage = "Uploading and analyzing video...";
      _analyzedVideoController?.dispose();
      _analyzedVideoController = null;
      _testId = null;
      _reportData = null;
    });

    try {
      // Read video bytes (works on Web & mobile)
      Uint8List videoBytes = await _videoFile!.readAsBytes();

      var request = http.MultipartRequest(
        'POST',
        Uri.parse('${widget.apiBaseUrl}/test/analysetest'),
      );

      request.files.add(
        http.MultipartFile.fromBytes(
          'video',
          videoBytes,
          filename: _videoFile!.name,
        ),
      );

      // Add form fields
      request.fields['user_id'] = _userIdController.text;
      request.fields['exercise_type'] = _selectedExercise!.name;
      request.fields['user_name'] = _userNameController.text;
      request.fields['age'] = _ageController.text.isEmpty ? '0' : _ageController.text;
      request.fields['height'] = _heightController.text.isEmpty ? '0' : _heightController.text;
      request.fields['weight'] = _weightController.text.isEmpty ? '0' : _weightController.text;

      var response = await request.send();

      if (response.statusCode == 200) {
        final responseData = await http.Response.fromStream(response);
        final jsonResponse = json.decode(responseData.body);

        setState(() {
          if (jsonResponse['success'] == true) {
            _analysisMessage = jsonResponse['message'] ?? "Analysis complete.";
            _testId = jsonResponse['test_id'];
            _reportData = jsonResponse['report_data'];

            // Display results summary
            if (_reportData != null) {
              final performance = _reportData!['performance'];
              _analysisMessage = '''Analysis Complete!
Score: ${performance['overall_score']?.toStringAsFixed(1) ?? 'N/A'}/100
Grade: ${performance['grade'] ?? 'N/A'}
Reps: ${performance['rep_count'] ?? 0}
Form Accuracy: ${performance['form_accuracy']?.toStringAsFixed(1) ?? 'N/A'}%''';
            }
          } else {
            _analysisMessage = "Error: ${jsonResponse['message']}";
          }
        });
      } else {
        final errorBody = await http.Response.fromStream(response);
        setState(() {
          _analysisMessage = "Error: ${response.statusCode} - ${errorBody.body}";
        });
      }
    } catch (e) {
      setState(() {
        _analysisMessage = "An error occurred: $e";
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  @override
  void dispose() {
    _analyzedVideoController?.dispose();
    _userIdController.dispose();
    _userNameController.dispose();
    _ageController.dispose();
    _heightController.dispose();
    _weightController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Upload Video for Analysis'),
        backgroundColor: Colors.black,
        foregroundColor: const Color(0xFFD0FD3E),
      ),
      backgroundColor: Colors.black,
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _buildUserProfileSection(),
            const SizedBox(height: 20),
            _buildExerciseTypeSelector(),
            const SizedBox(height: 20),
            _buildVideoSelectionButtons(),
            _videoFile != null
                ? Padding(
                    padding: const EdgeInsets.symmetric(vertical: 20.0),
                    child: Text(
                      'Selected Video: ${_videoFile!.name}',
                      style: const TextStyle(color: Colors.white70),
                    ),
                  )
                : const SizedBox.shrink(),
            const SizedBox(height: 20),
            ElevatedButton.icon(
              onPressed: _isLoading ? null : _uploadVideo,
              icon: _isLoading
                  ? const CircularProgressIndicator(color: Colors.black)
                  : const Icon(Icons.cloud_upload_outlined),
              label: Text(_isLoading ? "Analyzing..." : "Analyze Video"),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFD0FD3E),
                foregroundColor: Colors.black,
                padding: const EdgeInsets.symmetric(vertical: 15),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                textStyle: const TextStyle(
                    fontSize: 18, fontWeight: FontWeight.bold),
              ),
            ),
            if (_analysisMessage != null)
              Padding(
                padding: const EdgeInsets.only(top: 20.0),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade800,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    _analysisMessage!,
                    style: TextStyle(
                      color: _isLoading ? Colors.white70 : Colors.white,
                      fontSize: 16,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildUserProfileSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'User Profile:',
          style: TextStyle(
            color: Colors.white,
            fontSize: 18,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 10),
        TextField(
          controller: _userIdController,
          style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(
            labelText: 'User ID *',
            labelStyle: TextStyle(color: Colors.white70),
            enabledBorder: OutlineInputBorder(
              borderSide: BorderSide(color: Colors.white30),
            ),
            focusedBorder: OutlineInputBorder(
              borderSide: BorderSide(color: Color(0xFFD0FD3E)),
            ),
          ),
        ),
        const SizedBox(height: 10),
        TextField(
          controller: _userNameController,
          style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(
            labelText: 'Name (optional)',
            labelStyle: TextStyle(color: Colors.white70),
            enabledBorder: OutlineInputBorder(
              borderSide: BorderSide(color: Colors.white30),
            ),
            focusedBorder: OutlineInputBorder(
              borderSide: BorderSide(color: Color(0xFFD0FD3E)),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildExerciseTypeSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Select Exercise Type:',
          style: TextStyle(
            color: Colors.white,
            fontSize: 18,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 10),
        Wrap(
          spacing: 10.0,
          runSpacing: 10.0,
          children: ExerciseType.values.map((type) {
            final isSelected = _selectedExercise == type;
            return ChoiceChip(
              label: Text(
                type.name.replaceAll('_', ' ').toTitleCase(),
                style: TextStyle(
                  color: isSelected ? Colors.black : Colors.white70,
                  fontWeight: FontWeight.bold,
                ),
              ),
              selected: isSelected,
              selectedColor: const Color(0xFFD0FD3E),
              backgroundColor: Colors.grey.shade800,
              onSelected: (selected) {
                setState(() {
                  _selectedExercise = selected ? type : null;
                });
              },
              side: BorderSide(
                color: isSelected ? const Color(0xFFD0FD3E) : Colors.grey.shade700,
                width: 1.5,
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildVideoSelectionButtons() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: [
        Expanded(
          child: ElevatedButton.icon(
            onPressed: () => _pickVideo(ImageSource.gallery),
            icon: const Icon(Icons.video_library_outlined),
            label: const Text('Pick from Gallery'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.grey.shade700,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 15),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: ElevatedButton.icon(
            onPressed: () => _pickVideo(ImageSource.camera),
            icon: const Icon(Icons.videocam_outlined),
            label: const Text('Capture Video'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.grey.shade700,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 15),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

extension StringCasingExtension on String {
  String toTitleCase() {
    return split('_')
        .map((word) =>
            word.isEmpty ? '' : word[0].toUpperCase() + word.substring(1).toLowerCase())
        .join(' ');
  }
}
