import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;
import 'package:video_player/video_player.dart';
import 'dart:convert';
import 'package:chewie/chewie.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'dart:io';
import 'package:url_launcher/url_launcher.dart'; // Import for launching URLs

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
  final String name;

  const UploadVideoPage({
    super.key,
    required this.apiBaseUrl,
    required this.userId,
    required this.height,
    required this.weight,
    required this.age,
    required this.name,
  });

  @override
  State<UploadVideoPage> createState() => _UploadVideoPageState();
}

class _UploadVideoPageState extends State<UploadVideoPage> {
  XFile? _videoFile;
  ExerciseType? _selectedExercise;
  bool _isLoading = false;
  String? _analysisMessage;
  VideoPlayerController? _localVideoController;
  ChewieController? _localChewieController;
  VideoPlayerController? _analyzedVideoController;
  ChewieController? _analyzedChewieController;
  String? _testId;
  Map<String, dynamic>? _reportData;
  String? _analyzedVideoPathFromServer; // Stores the path like "analyzed_videos/..."

  final ImagePicker _picker = ImagePicker();

  @override
  void initState() {
    super.initState();
  }

  // Helper to construct the full analyzed video URL
  String? _getFullAnalyzedVideoUrl() {
    if (_analyzedVideoPathFromServer == null || _analyzedVideoPathFromServer!.isEmpty) {
      return null;
    }
    // Normalize path separators from Windows-style '\' to URL-friendly '/'
    String normalizedPath = _analyzedVideoPathFromServer!.replaceAll('\\', '/');
    // Ensure the base URL does not end with a slash and the path does not start with one, or vice-versa
    String baseUrl = widget.apiBaseUrl;
    if (baseUrl.endsWith('/')) {
      baseUrl = baseUrl.substring(0, baseUrl.length - 1);
    }
    String path = normalizedPath;
    if (path.startsWith('/')) {
      path = path.substring(1);
    }

    return '$baseUrl/$path';
  }

  Future<void> _pickVideo(ImageSource source) async {
    XFile? video;
    if (source == ImageSource.camera) {
      video = await _picker.pickVideo(source: ImageSource.camera);
    } else {
      video = await _picker.pickVideo(source: ImageSource.gallery);
    }

    if (!mounted) return;

    setState(() {
      _videoFile = video;
      _analysisMessage = null;
      _testId = null;
      _reportData = null;
      _analyzedVideoPathFromServer = null;

      _localChewieController?.dispose();
      _localVideoController?.dispose();
      _localVideoController = null;
      _localChewieController = null;

      _analyzedChewieController?.dispose();
      _analyzedVideoController?.dispose();
      _analyzedVideoController = null;
      _analyzedChewieController = null;
    });

    if (_videoFile != null) {
      // --- Platform-specific video controller initialization ---
      if (kIsWeb) {
        // For web, use VideoPlayerController.networkUrl with the XFile's path
        _localVideoController = VideoPlayerController.networkUrl(Uri.parse(_videoFile!.path));
      } else {
        // For native platforms, use VideoPlayerController.file with dart:io.File
        _localVideoController = VideoPlayerController.file(File(_videoFile!.path));
      }
      // --- End Platform-specific initialization ---

      try {
        await _localVideoController!.initialize();
        if (!mounted) return;
        setState(() {
          _localChewieController = ChewieController(
            videoPlayerController: _localVideoController!,
            autoPlay: false,
            looping: false,
            aspectRatio: _localVideoController!.value.aspectRatio,
          );
        });
      } catch (e) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error initializing local video: $e'),
            backgroundColor: Colors.red,
          ),
        );
        setState(() {
          _videoFile = null;
        });
      }
    }
  }

  Future<void> _uploadVideo() async {
    if (_videoFile == null || _selectedExercise == null) {
      if (!mounted) return;
      setState(() {
        _analysisMessage = "Please select a video and an exercise type.";
      });
      return;
    }

    if (!mounted) return;
    setState(() {
      _isLoading = true;
      _analysisMessage = "Uploading and analyzing video...";
      _analyzedVideoPathFromServer = null;
      _testId = null;
      _reportData = null;

      _analyzedChewieController?.dispose();
      _analyzedVideoController?.dispose();
      _analyzedVideoController = null;
      _analyzedChewieController = null;
    });

    try {
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

      request.fields['user_id'] = widget.userId;
      request.fields['exercise_type'] = _selectedExercise!.name;
      request.fields['age'] = widget.age.toString();
      request.fields['height'] = widget.height.toString();
      request.fields['weight'] = widget.weight.toString();
      request.fields['name'] = widget.name;

      var response = await request.send();

      if (!mounted) return;

      if (response.statusCode == 200) {
        final responseData = await http.Response.fromStream(response);
        final jsonResponse = json.decode(responseData.body);

        setState(() {
          if (jsonResponse['success'] == true) {
            _analysisMessage = jsonResponse['message'] ?? "Analysis complete.";
            _testId = jsonResponse['test_id'];
            _reportData = jsonResponse['report_data'];
            // Correctly get the analyzed_video_path
            _analyzedVideoPathFromServer = jsonResponse['video_path']; // Changed to 'video_path' as per your backend

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
        if (!mounted) return;
        setState(() {
          _analysisMessage = "Error: ${response.statusCode} - ${errorBody.body}";
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
      if (!mounted) return;
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
      if (!mounted) return;
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _viewLocalVideo() async {
    if (_localChewieController == null || !_localVideoController!.value.isInitialized) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('No uploaded video available to view or video not initialized.'),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }
    _showVideoPlayerDialog(_localChewieController!, 'Uploaded Video');
  }

  Future<void> _viewAnalyzedVideo() async {
    final String? fullAnalyzedUrl = _getFullAnalyzedVideoUrl();

    if (fullAnalyzedUrl != null) {
      // Play analyzed video from constructed URL
      _analyzedChewieController?.dispose();
      _analyzedVideoController?.dispose();
      _analyzedVideoController = null;
      _analyzedChewieController = null;

      _analyzedVideoController = VideoPlayerController.networkUrl(
        Uri.parse(fullAnalyzedUrl),
      );
      try {
        await _analyzedVideoController!.initialize();
        if (!mounted) return;
        setState(() {
          _analyzedChewieController = ChewieController(
            videoPlayerController: _analyzedVideoController!,
            autoPlay: true,
            looping: true,
            aspectRatio: _analyzedVideoController!.value.aspectRatio,
          );
        });
        _showVideoPlayerDialog(_analyzedChewieController!, 'Analyzed Video');
      } catch (e) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error playing analyzed video from URL "$fullAnalyzedUrl": $e. Ensure backend is serving this path correctly.'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('No analyzed video available to view.'),
          backgroundColor: Colors.orange,
        ),
      );
    }
  }

  void _showVideoPlayerDialog(ChewieController controller, String title) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return Dialog(
          backgroundColor: Colors.black,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(15),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              AppBar(
                title: Text(
                  title,
                  style: const TextStyle(color: Color(0xFFD0FD3E)),
                ),
                backgroundColor: Colors.black,
                elevation: 0,
                leading: IconButton(
                  icon: const Icon(Icons.close, color: Color(0xFFD0FD3E)),
                  onPressed: () {
                    Navigator.of(context).pop();
                    controller.pause();
                  },
                ),
              ),
              if (controller.videoPlayerController.value.isInitialized)
                AspectRatio(
                  aspectRatio: controller.videoPlayerController.value.aspectRatio,
                  child: Chewie(controller: controller),
                )
              else
                const Padding(
                  padding: EdgeInsets.all(20.0),
                  child: CircularProgressIndicator(color: Color(0xFFD0FD3E)),
                ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _downloadReport() async {
    if (_testId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('No test ID available to download report.'),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }

    final String reportUrl = '${widget.apiBaseUrl}/test/download/report/$_testId';
    try {
      if (!await launchUrl(Uri.parse(reportUrl), mode: LaunchMode.externalApplication)) {
        throw 'Could not launch $reportUrl';
      }
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Downloading report...'),
          backgroundColor: Color(0xFFD0FD3E),
          duration: Duration(seconds: 2),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to download report: $e'),
          backgroundColor: Colors.red,
          duration: const Duration(seconds: 3),
        ),
      );
    }
  }

  Future<void> _downloadAnalyzedVideo() async {
    if (_testId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('No test ID available to download analyzed video.'),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }

    final String videoDownloadUrl = '${widget.apiBaseUrl}/test/download/analyzed-video/$_testId';
    try {
      if (!await launchUrl(Uri.parse(videoDownloadUrl), mode: LaunchMode.externalApplication)) {
        throw 'Could not launch $videoDownloadUrl';
      }
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Downloading analyzed video...'),
          backgroundColor: Color(0xFFD0FD3E),
          duration: Duration(seconds: 2),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to download analyzed video: $e'),
          backgroundColor: Colors.red,
          duration: const Duration(seconds: 3),
        ),
      );
    }
  }

  @override
  void dispose() {
    _localChewieController?.dispose();
    _localVideoController?.dispose();
    _analyzedChewieController?.dispose();
    _analyzedVideoController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Determine if the "View Analyzed Video" button should be enabled
    final bool canViewAnalyzedVideo = _getFullAnalyzedVideoUrl() != null;

    // Determine if the "Download Report" button should be enabled
    final bool canDownloadReport = _testId != null;

    // Determine if the "Download Analyzed Video" button should be enabled
    final bool canDownloadAnalyzedVideo = _testId != null && _analyzedVideoPathFromServer != null;


    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'AI Fitness Coach',
          style: TextStyle(
            fontFamily: 'Montserrat',
            fontWeight: FontWeight.bold,
          ),
        ),
        backgroundColor: Colors.black,
        foregroundColor: const Color(0xFFD0FD3E),
        centerTitle: true,
        elevation: 0,
      ),
      backgroundColor: Colors.black,
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Color(0xFF1A1A1A),
              Colors.black,
              Color(0xFF0A0A0A),
            ],
          ),
        ),
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _buildExerciseTypeSelector(),
              const SizedBox(height: 30),
              _buildVideoSelectionButtons(),
              const SizedBox(height: 20),
              if (_videoFile != null && _localChewieController != null && _localVideoController!.value.isInitialized)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 10.0),
                  child: ElevatedButton.icon(
                    onPressed: _viewLocalVideo,
                    icon: const Icon(Icons.play_arrow_outlined, size: 26),
                    label: const Text('View Uploaded Video'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.teal.shade700,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 15),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      textStyle: const TextStyle(
                        fontSize: 17,
                        fontFamily: 'Montserrat',
                        fontWeight: FontWeight.w600,
                      ),
                      elevation: 5,
                    ),
                  ),
                ),
              if (_videoFile != null && (_localVideoController == null || !_localVideoController!.value.isInitialized))
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 20.0),
                  child: Text(
                    'Selected Video: ${_videoFile!.name} (Initializing...)',
                    style: const TextStyle(
                      color: Colors.white70,
                      fontStyle: FontStyle.italic,
                      fontSize: 16,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ),
              const SizedBox(height: 30),
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
                    : const Icon(Icons.fitness_center, size: 28),
                label: Text(
                  _isLoading ? "Analyzing..." : "Analyze Performance",
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFD0FD3E),
                  foregroundColor: Colors.black,
                  padding: const EdgeInsets.symmetric(vertical: 18),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(15),
                  ),
                  textStyle: const TextStyle(
                    fontSize: 19,
                    fontWeight: FontWeight.bold,
                    fontFamily: 'Montserrat',
                  ),
                  elevation: 8,
                ),
              ),

              if (_analysisMessage != null && !_isLoading && _reportData == null)
                Padding(
                  padding: const EdgeInsets.only(top: 20.0),
                  child: Text(
                    _analysisMessage!,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: Colors.white70,
                      fontSize: 16,
                      fontFamily: 'Montserrat',
                    ),
                  ),
                ),

              if (_reportData != null && !_isLoading)
                _buildReportDisplaySection(canViewAnalyzedVideo, canDownloadReport, canDownloadAnalyzedVideo),
            ],
          ),
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
            fontSize: 20,
            fontWeight: FontWeight.bold,
            fontFamily: 'Montserrat',
          ),
        ),
        const SizedBox(height: 15),
        Wrap(
          spacing: 10.0,
          runSpacing: 10.0,
          children: ExerciseType.values.map((type) {
            final isSelected = _selectedExercise == type;
            return ExerciseChip(
              key: ValueKey(type),
              type: type,
              isSelected: isSelected,
              icon: _getExerciseIcon(type),
              onSelected: (selected) {
                setState(() {
                  _selectedExercise = selected ? type : null;
                });
              },
            );
          }).toList(),
        ),
      ],
    );
  }

  IconData _getExerciseIcon(ExerciseType type) {
    switch (type) {
      case ExerciseType.VERTICAL_JUMP:
        return Icons.keyboard_arrow_up;
      case ExerciseType.SHUTTLE_RUN:
        return Icons.directions_run;
      case ExerciseType.SITUPS:
        return Icons.accessibility_new;
      case ExerciseType.PUSHUPS:
        return Icons.fitness_center;
      case ExerciseType.PLANK_HOLD:
        return Icons.hourglass_empty;
      case ExerciseType.STANDING_BROAD_JUMP:
        return Icons.directions_walk;
      case ExerciseType.SQUATS:
        return Icons.accessibility;
      case ExerciseType.ENDURANCE_RUN:
        return Icons.run_circle;
      default:
        return Icons.help_outline;
    }
  }

  Widget _buildVideoSelectionButtons() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: [
        Expanded(
          child: ElevatedButton.icon(
            onPressed: () => _pickVideo(ImageSource.gallery),
            icon: const Icon(Icons.video_library_outlined, size: 26),
            label: const Text('Gallery'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.blueGrey.shade700,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 15),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              textStyle: const TextStyle(
                fontSize: 17,
                fontFamily: 'Montserrat',
                fontWeight: FontWeight.w600,
              ),
              elevation: 5,
            ),
          ),
        ),
        const SizedBox(width: 15),
        Expanded(
          child: ElevatedButton.icon(
            onPressed: () => _pickVideo(ImageSource.camera),
            icon: const Icon(Icons.videocam_outlined, size: 26),
            label: const Text('Capture'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.deepPurple.shade700,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 15),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              textStyle: const TextStyle(
                fontSize: 17,
                fontFamily: 'Montserrat',
                fontWeight: FontWeight.w600,
              ),
              elevation: 5,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildReportDisplaySection(bool canViewAnalyzedVideo, bool canDownloadReport, bool canDownloadAnalyzedVideo) {
    if (_reportData == null) return const SizedBox.shrink();

    final performance = _reportData!['performance'] ?? {};
    final feedback = _reportData!['feedback'] ?? [];

    return Padding(
      padding: const EdgeInsets.only(top: 30.0),
      child: Card(
        color: Colors.grey.shade900.withOpacity(0.8),
        elevation: 10,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: Color(0xFFD0FD3E), width: 2),
        ),
        child: Padding(
          padding: const EdgeInsets.all(25.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Performance Report',
                style: TextStyle(
                  color: Color(0xFFD0FD3E),
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                  fontFamily: 'Montserrat',
                ),
              ),
              const Divider(color: Colors.white30, height: 30, thickness: 1.5),
              _buildReportRow(
                'Exercise',
                _selectedExercise?.name.replaceAll('_', ' ').toTitleCase() ??
                    'N/A',
                icon: _selectedExercise != null ? _getExerciseIcon(_selectedExercise!) : Icons.help_outline,
              ),
              _buildReportRow('Test ID', _testId ?? 'N/A', icon: Icons.tag),
              const SizedBox(height: 20),
              const Text(
                'Key Metrics:',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  fontFamily: 'Montserrat',
                ),
              ),
              _buildMetricTile(
                'Overall Score',
                '${performance['overall_score']?.toStringAsFixed(1) ?? 'N/A'}/100',
                Icons.star_half,
              ),
              _buildMetricTile(
                'Grade',
                performance['grade'] ?? 'N/A',
                Icons.grade,
              ),
              _buildMetricTile(
                'Repetitions',
                performance['rep_count']?.toString() ?? 'N/A',
                Icons.repeat,
              ),
              _buildMetricTile(
                'Form Accuracy',
                '${performance['form_accuracy']?.toStringAsFixed(1) ?? 'N/A'}%',
                Icons.accessibility_new,
              ),
              _buildMetricTile(
                'Duration',
                '${performance['duration_seconds']?.toStringAsFixed(1) ?? 'N/A'}s',
                Icons.timer,
              ),
              const SizedBox(height: 25),
              const Text(
                'Feedback for Improvement:',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  fontFamily: 'Montserrat',
                ),
              ),
              const SizedBox(height: 10),
              if (feedback.isEmpty)
                const Text(
                  'Great job! No specific feedback provided, keep up the good work.',
                  style: TextStyle(color: Colors.white70, fontSize: 16),
                ),
              ...feedback
                  .map<Widget>(
                    (item) => Padding(
                      padding: const EdgeInsets.only(top: 8.0, left: 5.0),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(
                            Icons.lightbulb_outline,
                            color: Color(0xFFD0FD3E),
                            size: 20,
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              item.toString(),
                              style: const TextStyle(
                                color: Colors.white70,
                                fontSize: 16,
                                fontFamily: 'Montserrat',
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  )
                  .toList(),
              const SizedBox(height: 30),
              Center(
                child: ElevatedButton.icon(
                  onPressed: canViewAnalyzedVideo ? _viewAnalyzedVideo : null,
                  icon: const Icon(Icons.play_circle_fill, size: 28),
                  label: const Text('View Analyzed Video'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: canViewAnalyzedVideo ? Colors.blueAccent : Colors.grey,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 25,
                      vertical: 15,
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    textStyle: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      fontFamily: 'Montserrat',
                    ),
                    elevation: 8,
                  ),
                ),
              ),
              const SizedBox(height: 15),
              Center(
                child: ElevatedButton.icon(
                  onPressed: canDownloadReport ? _downloadReport : null,
                  icon: const Icon(Icons.download, size: 28),
                  label: const Text('Download Report (PDF)'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: canDownloadReport ? Colors.green.shade700 : Colors.grey,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 25,
                      vertical: 15,
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    textStyle: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      fontFamily: 'Montserrat',
                    ),
                    elevation: 8,
                  ),
                ),
              ),
              const SizedBox(height: 15),
              Center(
                child: ElevatedButton.icon(
                  onPressed: canDownloadAnalyzedVideo ? _downloadAnalyzedVideo : null,
                  icon: const Icon(Icons.cloud_download, size: 28),
                  label: const Text('Download Analyzed Video'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: canDownloadAnalyzedVideo ? Colors.orange.shade700 : Colors.grey,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 25,
                      vertical: 15,
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    textStyle: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      fontFamily: 'Montserrat',
                    ),
                    elevation: 8,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildReportRow(String label, String value, {IconData? icon}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              if (icon != null) Icon(icon, color: Colors.white, size: 20),
              if (icon != null) const SizedBox(width: 10),
              Text(
                '$label:',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 17,
                  fontWeight: FontWeight.w500,
                  fontFamily: 'Montserrat',
                ),
              ),
            ],
          ),
          Text(
            value,
            style: const TextStyle(
              color: Color(0xFFD0FD3E),
              fontSize: 17,
              fontWeight: FontWeight.w600,
              fontFamily: 'Montserrat',
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMetricTile(String title, String value, IconData icon) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.grey.shade800.withOpacity(0.5),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: Colors.white12, width: 0.5),
        ),
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Icon(icon, color: const Color(0xFFD0FD3E), size: 24),
            const SizedBox(width: 15),
            Expanded(
              child: Text(
                title,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  fontFamily: 'Montserrat',
                ),
              ),
            ),
            Text(
              value,
              style: const TextStyle(
                color: Color(0xFFD0FD3E),
                fontSize: 17,
                fontWeight: FontWeight.bold,
                fontFamily: 'Montserrat',
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class ExerciseChip extends StatefulWidget {
  final ExerciseType type;
  final bool isSelected;
  final ValueChanged<bool> onSelected;
  final IconData icon;

  const ExerciseChip({
    super.key,
    required this.type,
    required this.isSelected,
    required this.onSelected,
    required this.icon,
  });

  @override
  State<ExerciseChip> createState() => _ExerciseChipState();
}

class _ExerciseChipState extends State<ExerciseChip> {
  bool _isHovering = false;

  @override
  Widget build(BuildContext context) {
    final Color hoverGreen = const Color(0xFFE0FF7F);

    return MouseRegion(
      onEnter: (_) => setState(() => _isHovering = true),
      onExit: (_) => setState(() => _isHovering = false),
      child: ChoiceChip(
        label: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              widget.icon,
              color: widget.isSelected || _isHovering ? Colors.black : Colors.white70,
              size: 20,
            ),
            const SizedBox(width: 8),
            Text(
              widget.type.name.replaceAll('_', ' ').toTitleCase(),
              style: TextStyle(
                color: widget.isSelected || _isHovering ? Colors.black : Colors.white70,
                fontWeight: FontWeight.bold,
                fontSize: 15,
                fontFamily: 'Montserrat',
              ),
            ),
          ],
        ),
        selected: widget.isSelected,
        selectedColor: const Color(0xFFD0FD3E),
        backgroundColor: _isHovering && !widget.isSelected
            ? Colors.grey.shade700.withOpacity(0.8)
            : Colors.grey.shade800.withOpacity(0.6),
        onSelected: widget.onSelected,
        side: BorderSide(
          color: widget.isSelected
              ? const Color(0xFFD0FD3E)
              : (_isHovering ? hoverGreen : Colors.grey.shade700),
          width: 1.5,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(25),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
        elevation: widget.isSelected ? 5 : (_isHovering ? 4 : 2),
        shadowColor: widget.isSelected
            ? const Color(0xFFD0FD3E).withOpacity(0.4)
            : (_isHovering ? hoverGreen.withOpacity(0.3) : Colors.transparent),
        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
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