import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

class TestResultsPage extends StatefulWidget {
  final String apiBaseUrl;

  const TestResultsPage({super.key, required this.apiBaseUrl});

  @override
  State<TestResultsPage> createState() => _TestResultsPageState();
}

class _TestResultsPageState extends State<TestResultsPage> {
  final TextEditingController _userIdController = TextEditingController();
  List<dynamic> _testResults = [];
  bool _isLoading = false;
  String? _errorMessage;
  Map<String, dynamic>? _userStats;

  Future<void> _fetchUserResults() async {
    if (_userIdController.text.isEmpty) {
      setState(() {
        _errorMessage = "Please enter a User ID";
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
      _testResults = [];
      _userStats = null;
    });

    try {
      // Fetch test results
      final resultsResponse = await http.get(
        Uri.parse('${widget.apiBaseUrl}/test/results/${_userIdController.text}?limit=20'),
      );

      // Fetch user stats
      final statsResponse = await http.get(
        Uri.parse('${widget.apiBaseUrl}/test/stats/${_userIdController.text}'),
      );

      if (resultsResponse.statusCode == 200 && statsResponse.statusCode == 200) {
        setState(() {
          _testResults = json.decode(resultsResponse.body);
          _userStats = json.decode(statsResponse.body);
        });
      } else {
        setState(() {
          _errorMessage = "Failed to fetch data. Status: ${resultsResponse.statusCode}";
        });
      }
    } catch (e) {
      setState(() {
        _errorMessage = "Error: $e";
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _downloadReport(String testId) async {
    try {
      final response = await http.get(
        Uri.parse('${widget.apiBaseUrl}/test/download/report/$testId'),
      );

      if (response.statusCode == 200) {
        // Handle PDF download - you might want to save it to device storage
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Report downloaded successfully')),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to download report: ${response.statusCode}')),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error downloading report: $e')),
      );
    }
  }

  String _formatDateTime(String? dateTimeString) {
    if (dateTimeString == null) return 'N/A';
    try {
      final dateTime = DateTime.parse(dateTimeString);
      return '${dateTime.day}/${dateTime.month}/${dateTime.year} ${dateTime.hour}:${dateTime.minute.toString().padLeft(2, '0')}';
    } catch (e) {
      return dateTimeString;
    }
  }

  Color _getScoreColor(double? score) {
    if (score == null) return Colors.grey;
    if (score >= 85) return Colors.green;
    if (score >= 70) return Colors.yellow.shade700;
    if (score >= 50) return Colors.orange;
    return Colors.red;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Test Results'),
        backgroundColor: Colors.black,
        foregroundColor: const Color(0xFFD0FD3E),
      ),
      backgroundColor: Colors.black,
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // User ID input section
            Card(
              color: Colors.grey.shade900,
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  children: [
                    TextField(
                      controller: _userIdController,
                      style: const TextStyle(color: Colors.white),
                      decoration: const InputDecoration(
                        labelText: 'Enter User ID',
                        labelStyle: TextStyle(color: Colors.white70),
                        enabledBorder: OutlineInputBorder(
                          borderSide: BorderSide(color: Colors.white30),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderSide: BorderSide(color: Color(0xFFD0FD3E)),
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    ElevatedButton.icon(
                      onPressed: _isLoading ? null : _fetchUserResults,
                      icon: _isLoading 
                          ? const CircularProgressIndicator(color: Colors.black, strokeWidth: 2)
                          : const Icon(Icons.search),
                      label: Text(_isLoading ? 'Loading...' : 'Get Results'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFFD0FD3E),
                        foregroundColor: Colors.black,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                    ),
                  ],
                ),
              ),
            ),

            if (_errorMessage != null) ...[
              const SizedBox(height: 16),
              Card(
                color: Colors.red.shade900,
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Text(
                    _errorMessage!,
                    style: const TextStyle(color: Colors.white),
                  ),
                ),
              ),
            ],

            // User stats section
            if (_userStats != null) ...[
              const SizedBox(height: 16),
              Card(
                color: Colors.grey.shade900,
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'User Statistics',
                        style: TextStyle(
                          color: Color(0xFFD0FD3E),
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          _buildStatItem('Total Tests', '${_userStats!['total_tests']}'),
                          _buildStatItem('Average Score', '${_userStats!['avg_score']?.toStringAsFixed(1) ?? 'N/A'}'),
                          _buildStatItem('Best Score', '${_userStats!['max_score']?.toStringAsFixed(1) ?? 'N/A'}'),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Trend: ${_userStats!['progress_trend'] ?? 'N/A'}',
                        style: TextStyle(
                          color: _userStats!['progress_trend'] == 'improving' 
                              ? Colors.green 
                              : _userStats!['progress_trend'] == 'declining' 
                                  ? Colors.red 
                                  : Colors.white70,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],

            // Results list
            if (_testResults.isNotEmpty) ...[
              const SizedBox(height: 16),
              const Text(
                'Recent Test Results',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Expanded(
                child: ListView.builder(
                  itemCount: _testResults.length,
                  itemBuilder: (context, index) {
                    final result = _testResults[index];
                    return Card(
                      color: Colors.grey.shade900,
                      margin: const EdgeInsets.only(bottom: 8),
                      child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor: _getScoreColor(result['score']?.toDouble()),
                          child: Text(
                            '${result['score']?.toInt() ?? 0}',
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                        title: Text(
                          (result['exercise_type'] ?? 'Unknown Exercise').replaceAll('_', ' '),
                          style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        subtitle: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _formatDateTime(result['timestamp']),
                              style: const TextStyle(color: Colors.white70),
                            ),
                            if (result['feedback'] != null && result['feedback']['summary'] != null)
                              Text(
                                result['feedback']['summary'].toString().length > 60
                                    ? '${result['feedback']['summary'].toString().substring(0, 60)}...'
                                    : result['feedback']['summary'].toString(),
                                style: const TextStyle(color: Colors.white60, fontSize: 12),
                              ),
                          ],
                        ),
                        trailing: PopupMenuButton<String>(
                          icon: const Icon(Icons.more_vert, color: Colors.white70),
                          color: Colors.grey.shade800,
                          onSelected: (String value) {
                            switch (value) {
                              case 'download':
                                _downloadReport(result['test_id']);
                                break;
                              case 'details':
                                _showTestDetails(result);
                                break;
                            }
                          },
                          itemBuilder: (BuildContext context) => [
                            const PopupMenuItem<String>(
                              value: 'details',
                              child: Row(
                                children: [
                                  Icon(Icons.info_outline, color: Colors.white70),
                                  SizedBox(width: 8),
                                  Text('View Details', style: TextStyle(color: Colors.white)),
                                ],
                              ),
                            ),
                            const PopupMenuItem<String>(
                              value: 'download',
                              child: Row(
                                children: [
                                  Icon(Icons.download, color: Colors.white70),
                                  SizedBox(width: 8),
                                  Text('Download Report', style: TextStyle(color: Colors.white)),
                                ],
                              ),
                            ),
                          ],
                        ),
                        onTap: () => _showTestDetails(result),
                      ),
                    );
                  },
                ),
              ),
            ] else if (!_isLoading && _userIdController.text.isNotEmpty) ...[
              const SizedBox(height: 40),
              const Center(
                child: Text(
                  'No test results found for this user',
                  style: TextStyle(color: Colors.white70, fontSize: 16),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildStatItem(String label, String value) {
    return Column(
      children: [
        Text(
          value,
          style: const TextStyle(
            color: Color(0xFFD0FD3E),
            fontSize: 20,
            fontWeight: FontWeight.bold,
          ),
        ),
        Text(
          label,
          style: const TextStyle(
            color: Colors.white70,
            fontSize: 12,
          ),
        ),
      ],
    );
  }

  void _showTestDetails(Map<String, dynamic> result) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        final feedback = result['feedback'] ?? {};
        
        return AlertDialog(
          backgroundColor: Colors.grey.shade900,
          title: Text(
            '${(result['exercise_type'] ?? 'Unknown').replaceAll('_', ' ')} Analysis',
            style: const TextStyle(color: Color(0xFFD0FD3E)),
          ),
          content: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                _buildDetailRow('Score', '${result['score']?.toStringAsFixed(1) ?? 'N/A'}/100'),
                _buildDetailRow('Date', _formatDateTime(result['timestamp'])),
                _buildDetailRow('Test ID', result['test_id'] ?? 'N/A'),
                
                const SizedBox(height: 16),
                const Text(
                  'Summary:',
                  style: TextStyle(color: Color(0xFFD0FD3E), fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                Text(
                  feedback['summary'] ?? 'No summary available',
                  style: const TextStyle(color: Colors.white70),
                ),

                if (feedback['key_findings'] != null && (feedback['key_findings'] as List).isNotEmpty) ...[
                  const SizedBox(height: 16),
                  const Text(
                    'Key Findings:',
                    style: TextStyle(color: Color(0xFFD0FD3E), fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  ...((feedback['key_findings'] as List<dynamic>).map((finding) => 
                    Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: Text('• $finding', style: const TextStyle(color: Colors.white70)),
                    )
                  )),
                ],

                if (feedback['recommendations'] != null && (feedback['recommendations'] as List).isNotEmpty) ...[
                  const SizedBox(height: 16),
                  const Text(
                    'Recommendations:',
                    style: TextStyle(color: Color(0xFFD0FD3E), fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  ...((feedback['recommendations'] as List<dynamic>).map((rec) => 
                    Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: Text('• $rec', style: const TextStyle(color: Colors.white70)),
                    )
                  )),
                ],

                if (feedback['form_errors_breakdown'] != null) ...[
                  const SizedBox(height: 16),
                  const Text(
                    'Form Issues:',
                    style: TextStyle(color: Color(0xFFD0FD3E), fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  ...((feedback['form_errors_breakdown'] as Map<String, dynamic>).entries.where((e) => e.value > 0).map((entry) =>
                    Text('• ${entry.key.replaceAll('_', ' ')}: ${entry.value} times', 
                         style: const TextStyle(color: Colors.white70))
                  )),
                ],
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Close', style: TextStyle(color: Color(0xFFD0FD3E))),
            ),
            TextButton(
              onPressed: () {
                Navigator.of(context).pop();
                _downloadReport(result['test_id']);
              },
              child: const Text('Download Report', style: TextStyle(color: Color(0xFFD0FD3E))),
            ),
          ],
        );
      },
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '$label: ',
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(color: Colors.white70),
            ),
          ),
        ],
      ),
    );
  }
}