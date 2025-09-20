import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;
import 'package:video_player/video_player.dart';
import 'dart:convert';
// Removed: import 'package:file_selector/file_selector.dart'; // Import for desktop file picking

// Enum for exercise types, matching your Python backend
enum ExerciseType {
  VERTICAL_JUMP,
  SHUTTLE_RUN,
  SITUPS,
  PUSHUPS,
  PLANK_HOLD,
  STANDING_BROAD_JUMP,
  SQUATS,
  ENDURANCE_RUN,
}

class UploadVideoPage extends StatefulWidget {
  final String apiBaseUrl;
  final String userId;
  final int height;
  final int weight;
  final int age;

  const UploadVideoPage({
    super.key,
    required this.apiBaseUrl,
    required this.userId,
    required this.height,
    required this.weight,
    required this.age,
  });

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
    // Initialize user data from widget properties
    _userIdController.text = widget.userId;
    _ageController.text = widget.age.toString();
    _heightController.text = widget.height.toString();
    _weightController.text = widget.weight.toString();
  }

  Future<void> _pickVideo(ImageSource source) async {
    XFile? video;
    if (source == ImageSource.camera) {
      video = await _picker.pickVideo(source: ImageSource.camera);
    } else {
      // Use image_picker for gallery on all platforms
      video = await _picker.pickVideo(source: ImageSource.gallery);
    }

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
    if (_videoFile == null ||
        _selectedExercise == null ||
        _userIdController.text.isEmpty) {
      setState(() {
        _analysisMessage =
            "Please select a video, exercise type, and enter a user ID.";
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
      request.fields['age'] =
          _ageController.text.isEmpty ? '0' : _ageController.text;
      request.fields['height'] =
          _heightController.text.isEmpty ? '0' : _heightController.text;
      request.fields['weight'] =
          _weightController.text.isEmpty ? '0' : _weightController.text;

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
              _analysisMessage =
                  '''Analysis Complete!
Score: ${performance['overall_score']?.toStringAsFixed(1) ?? 'N/A'}/100
Grade: ${performance['grade'] ?? 'N/A'}
Reps: ${performance['rep_count'] ?? 0}
Form Accuracy: ${performance['form_accuracy']?.toStringAsFixed(1) ?? 'N/A'}%''';
            }
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('Video analyzed successfully!'),
                backgroundColor: Color(0xFFD0FD3E),
                duration: Duration(seconds: 2),
              ),
            );
          } else {
            _analysisMessage = "Error: ${jsonResponse['message']}";
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text('Error: ${jsonResponse['message']}'),
                backgroundColor: Colors.red,
                duration: const Duration(seconds: 3),
              ),
            );
          }
        });
      } else {
        final errorBody = await http.Response.fromStream(response);
        setState(() {
          _analysisMessage =
              "Error: ${response.statusCode} - ${errorBody.body}";
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Upload failed: ${response.statusCode}'),
              backgroundColor: Colors.red,
              duration: const Duration(seconds: 3),
            ),
          );
        });
      }
    } catch (e) {
      setState(() {
        _analysisMessage = "An error occurred: $e";
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('An error occurred: $e'),
            backgroundColor: Colors.red,
            duration: const Duration(seconds: 3),
          ),
        );
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
                      style: const TextStyle(
                          color: Colors.white70, fontStyle: FontStyle.italic),
                    ),
                  )
                : const SizedBox.shrink(),
            const SizedBox(height: 20),
            ElevatedButton.icon(
              onPressed: _isLoading ? null : _uploadVideo,
              icon: _isLoading
                  ? const SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(
                        color: Colors.black,
                        strokeWidth: 3,
                      ),
                    )
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
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
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
                    border: Border.all(
                      color: _isLoading ? Colors.white30 : const Color(0xFFD0FD3E),
                      width: 1,
                    ),
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
            if (_reportData != null && !_isLoading)
              _buildReportDisplaySection(),
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
        _buildStyledTextField(
          controller: _userIdController,
          labelText: 'User ID *',
          readOnly: true, // User ID is pre-filled and should not be changed
        ),
        const SizedBox(height: 10),
        _buildStyledTextField(
          controller: _userNameController,
          labelText: 'Name (optional)',
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: _buildStyledTextField(
                controller: _ageController,
                labelText: 'Age',
                keyboardType: TextInputType.number,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _buildStyledTextField(
                controller: _heightController,
                labelText: 'Height (cm)',
                keyboardType: TextInputType.number,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _buildStyledTextField(
                controller: _weightController,
                labelText: 'Weight (kg)',
                keyboardType: TextInputType.number,
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildStyledTextField({
    required TextEditingController controller,
    required String labelText,
    TextInputType keyboardType = TextInputType.text,
    bool readOnly = false,
  }) {
    return TextField(
      controller: controller,
      style: const TextStyle(color: Colors.white),
      keyboardType: keyboardType,
      readOnly: readOnly,
      decoration: InputDecoration(
        labelText: labelText,
        labelStyle: const TextStyle(color: Colors.white70),
        filled: true,
        fillColor: Colors.grey.shade900,
        enabledBorder: OutlineInputBorder(
          borderSide: const BorderSide(color: Colors.white30),
          borderRadius: BorderRadius.circular(8),
        ),
        focusedBorder: OutlineInputBorder(
          borderSide: const BorderSide(color: Color(0xFFD0FD3E), width: 2),
          borderRadius: BorderRadius.circular(8),
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
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
          spacing: 8.0, // Reduced spacing
          runSpacing: 8.0, // Reduced run spacing
          children: ExerciseType.values.map((type) {
            final isSelected = _selectedExercise == type;
            return ChoiceChip(
              label: Text(
                type.name.replaceAll('_', ' ').toTitleCase(),
                style: TextStyle(
                  color: isSelected ? Colors.black : Colors.white70,
                  fontWeight: FontWeight.bold,
                  fontSize: 14, // Slightly smaller font for chips
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
                color: isSelected
                    ? const Color(0xFFD0FD3E)
                    : Colors.grey.shade700,
                width: 1.5,
              ),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(20), // More rounded chips
              ),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8), // Adjusted padding
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
              textStyle: const TextStyle(fontSize: 16),
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
              textStyle: const TextStyle(fontSize: 16),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildReportDisplaySection() {
    if (_reportData == null) return const SizedBox.shrink();

    final performance = _reportData!['performance'] ?? {};
    final feedback = _reportData!['feedback'] ?? [];

    return Padding(
      padding: const EdgeInsets.only(top: 20.0),
      child: Card(
        color: Colors.grey.shade900,
        elevation: 5,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(15),
          side: const BorderSide(color: Color(0xFFD0FD3E), width: 1.5),
        ),
        child: Padding(
          padding: const EdgeInsets.all(20.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Analysis Report:',
                style: TextStyle(
                  color: Color(0xFFD0FD3E),
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const Divider(color: Colors.white30, height: 25, thickness: 1),
              _buildReportRow('Test ID', _testId ?? 'N/A'),
              _buildReportRow('Exercise', _selectedExercise?.name.replaceAll('_', ' ').toTitleCase() ?? 'N/A'),
              _buildReportRow('User Name', _userNameController.text.isEmpty ? 'N/A' : _userNameController.text),
              const SizedBox(height: 15),
              const Text(
                'Performance Metrics:',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
              _buildReportRow('Overall Score', '${performance['overall_score']?.toStringAsFixed(1) ?? 'N/A'}/100'),
              _buildReportRow('Grade', performance['grade'] ?? 'N/A'),
              _buildReportRow('Repetitions', performance['rep_count']?.toString() ?? 'N/A'),
              _buildReportRow('Form Accuracy', '${performance['form_accuracy']?.toStringAsFixed(1) ?? 'N/A'}%'),
              _buildReportRow('Duration', '${performance['duration_seconds']?.toStringAsFixed(1) ?? 'N/A'}s'),
              const SizedBox(height: 15),
              const Text(
                'Feedback:',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
              if (feedback.isEmpty)
                const Text(
                  'No specific feedback provided.',
                  style: TextStyle(color: Colors.white70, fontSize: 14),
                ),
              ...feedback.map<Widget>((item) => Padding(
                padding: const EdgeInsets.only(top: 4.0, left: 8.0),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.check_circle_outline, color: Color(0xFFD0FD3E), size: 18),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        item.toString(),
                        style: const TextStyle(color: Colors.white70, fontSize: 14),
                      ),
                    ),
                  ],
                ),
              )).toList(),
              const SizedBox(height: 20),
              Center(
                child: ElevatedButton.icon(
                  onPressed: () {
                    // TODO: Implement viewing of the analyzed video
                    // You would likely get a URL for the analyzed video from your backend
                    // and initialize _analyzedVideoController with it.
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('Viewing analyzed video (feature coming soon!)'),
                        backgroundColor: Colors.blueAccent,
                      ),
                    );
                  },
                  icon: const Icon(Icons.play_circle_fill),
                  label: const Text('View Analyzed Video'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blueAccent,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildReportRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            '$label:',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.w500,
            ),
          ),
          Text(
            value,
            style: const TextStyle(
              color: Color(0xFFD0FD3E), // Highlight values
              fontSize: 16,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

extension StringCasingExtension on String {
  String toTitleCase() {
    return split('_')
        .map(
          (word) => word.isEmpty
              ? ''
              : word[0].toUpperCase() + word.substring(1).toLowerCase(),
        )
        .join(' ');
  }
}