import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:flutter_markdown/flutter_markdown.dart'; // Import for markdown

class AIChatbotPage extends StatefulWidget {
  final String userName;
  final String? userProfilePicUrl;
  final String userId;

  const AIChatbotPage({
    super.key,
    required this.userName,
    required this.userProfilePicUrl,
    required this.userId,
  });

  @override
  State<AIChatbotPage> createState() => _AIChatbotPageState();
}

class _AIChatbotPageState extends State<AIChatbotPage> {
  final TextEditingController _messageController = TextEditingController();
  final List<ChatMessage> _messages = [];
  final ScrollController _scrollController = ScrollController();

  final String _baseUrl = "http://127.0.0.1:8000";

  @override
  void initState() {
    super.initState();
    _startNewChat(); // Call this when the widget is initialized
  }

  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _startNewChat() async {
    try {
      final response = await http.post(
        Uri.parse(
          '$_baseUrl/bot/start_new_chat/${widget.userId}/${widget.userName}',
        ),
        headers: {'Content-Type': 'application/json'},
      );

      print(response);

      if (response.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(response.body);
        final String initialGreeting = data['response'];

        setState(() {
          _messages.add(
            ChatMessage(
              senderName: "NextChamp AI",
              text: initialGreeting,
              isUser: false,
              timestamp: DateTime.now(),
            ),
          );
        });
        _scrollToBottom();
      } else {
        print('Failed to start new chat: ${response.statusCode}');
        _showErrorSnackBar("Failed to start a new chat session.");
      }
    } catch (e) {
      print('Error starting new chat: $e');
      _showErrorSnackBar("Network error while starting new chat.");
    }
  }

  void _handleSendMessage() async {
    final String messageText = _messageController.text.trim();
    if (messageText.isEmpty) return;

    // Add user's message to UI immediately
    setState(() {
      _messages.add(
        ChatMessage(
          senderName: widget.userName,
          text: messageText,
          isUser: true,
          timestamp: DateTime.now(),
        ),
      );
    });
    _messageController.clear();
    _scrollToBottom();

    try {
      final response = await http.post(
        Uri.parse('$_baseUrl/bot/chat'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'user_id': widget.userId,
          'user_name': widget.userName,
          'message': messageText,
        }),
      );

      if (response.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(response.body);
        final String aiResponse = data['response'];

        setState(() {
          _messages.add(
            ChatMessage(
              senderName: "NextChamp AI",
              text: aiResponse,
              isUser: false,
              timestamp: DateTime.now(),
            ),
          );
        });
        _scrollToBottom();
      } else {
        print('Failed to send message: ${response.statusCode}');
        _showErrorSnackBar("Failed to get AI response.");
        // Optionally, remove the last user message if AI response failed
        setState(() {
          _messages.removeWhere((msg) => msg.isUser && msg.text == messageText);
        });
      }
    } catch (e) {
      print('Error sending message: $e');
      _showErrorSnackBar("Network error. Please try again.");
      // Optionally, remove the last user message if network failed
      setState(() {
        _messages.removeWhere((msg) => msg.isUser && msg.text == messageText);
      });
    }
  }

  void _showErrorSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.red),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: const Text(
          "NextChamp AI",
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        ),
        backgroundColor: const Color.fromARGB(255, 22, 22, 22),
        foregroundColor: const Color(0xFFD0FD3E),
        elevation: 0,
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(16.0),
              itemCount: _messages.length,
              itemBuilder: (context, index) {
                return _buildMessageItem(_messages[index]);
              },
            ),
          ),
          _buildMessageInput(),
        ],
      ),
    );
  }

  Widget _buildMessageItem(ChatMessage message) {
    String displayedUserName = message.senderName.replaceAll('.', '');
    if (message.isUser && displayedUserName.contains(' ')) {
      displayedUserName = displayedUserName.split(' ')[0];
    }

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 10.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: message.isUser
            ? MainAxisAlignment.end
            : MainAxisAlignment.start,
        children: [
          if (!message.isUser)
            Padding(
              padding: const EdgeInsets.only(right: 10.0),
              child: Column(
                children: [
                  CircleAvatar(
                    radius: 20,
                    backgroundColor: const Color(0xFFD0FD3E),
                    child: Icon(
                      Icons.smart_toy_outlined,
                      color: Colors.black,
                      size: 24,
                    ),
                  ),
                  const SizedBox(height: 4),
                  SizedBox(
                    width: 80,
                    child: Column(
                      children: [
                        Text(
                          "NextChamp",
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            color: Colors.grey.shade400,
                            fontSize: 10,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                        Text(
                          "AI",
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            color: Colors.grey.shade400,
                            fontSize: 10,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          Flexible(
            child: Column(
              crossAxisAlignment: message.isUser
                  ? CrossAxisAlignment.end
                  : CrossAxisAlignment.start,
              children: [
                if (message.isUser)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4.0),
                    child: Text(
                      "${displayedUserName} • ${DateFormat('HH:mm').format(message.timestamp)}",
                      style: TextStyle(
                        color: Colors.grey.shade400,
                        fontSize: 12,
                      ),
                    ),
                  )
                else
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4.0),
                    child: Text(
                      DateFormat('HH:mm').format(message.timestamp),
                      style: TextStyle(
                        color: Colors.grey.shade400,
                        fontSize: 12,
                      ),
                    ),
                  ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    vertical: 10.0,
                    horizontal: 15.0,
                  ),
                  decoration: BoxDecoration(
                    color: message.isUser
                        ? const Color(0xFFD0FD3E)
                        : Colors.grey.shade800,
                    borderRadius: BorderRadius.only(
                      topLeft: const Radius.circular(15),
                      topRight: const Radius.circular(15),
                      bottomLeft: message.isUser
                          ? const Radius.circular(15)
                          : const Radius.circular(0),
                      bottomRight: message.isUser
                          ? const Radius.circular(0)
                          : const Radius.circular(15),
                    ),
                  ),
                  child: MarkdownBody(
                    // Using MarkdownBody for markdown rendering
                    data: message.text,
                    styleSheet: MarkdownStyleSheet(
                      p: TextStyle(
                        color: message.isUser ? Colors.black : Colors.white,
                        fontSize: 16,
                      ),
                      strong: TextStyle(
                        // Style for bold text
                        color: message.isUser ? Colors.black : Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                      // You can add more styles for other markdown elements here
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (message.isUser)
            Padding(
              padding: const EdgeInsets.only(left: 10.0),
              child: Column(
                children: [
                  CircleAvatar(
                    radius: 20,
                    backgroundColor: Colors.grey.shade700,
                    backgroundImage: widget.userProfilePicUrl != null
                        ? NetworkImage(widget.userProfilePicUrl!)
                        : null,
                    child: widget.userProfilePicUrl == null
                        ? const Icon(
                            Icons.person,
                            color: Colors.white,
                            size: 24,
                          )
                        : null,
                  ),
                  const SizedBox(height: 4),
                  SizedBox(
                    width: 40,
                    child: Text(
                      displayedUserName,
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Colors.grey.shade400,
                        fontSize: 10,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildMessageInput() {
    return Container(
      padding: const EdgeInsets.all(16.0),
      decoration: BoxDecoration(
        color: const Color.fromARGB(255, 22, 22, 22),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.3),
            spreadRadius: 2,
            blurRadius: 5,
            offset: const Offset(0, -3),
          ),
        ],
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _messageController,
              onSubmitted: (_) =>
                  _handleSendMessage(), // Call _handleSendMessage on Enter
              decoration: InputDecoration(
                hintText: "Type your message...",
                hintStyle: TextStyle(color: Colors.grey.shade400),
                filled: true,
                fillColor: Colors.grey.shade900,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(25.0),
                  borderSide: BorderSide.none,
                ),
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 20.0,
                  vertical: 10.0,
                ),
              ),
              style: const TextStyle(color: Colors.white),
              cursorColor: const Color(0xFFD0FD3E),
            ),
          ),
          const SizedBox(width: 10),
          FloatingActionButton(
            onPressed: _handleSendMessage,
            backgroundColor: const Color(0xFFD0FD3E),
            elevation: 0,
            child: const Icon(Icons.send, color: Colors.black),
          ),
        ],
      ),
    );
  }
}

class ChatMessage {
  final String senderName;
  final String text;
  final bool isUser;
  final DateTime timestamp;

  ChatMessage({
    required this.senderName,
    required this.text,
    required this.isUser,
    required this.timestamp,
  });
}
