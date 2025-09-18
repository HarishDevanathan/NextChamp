import 'package:flutter/material.dart';
import 'package:intl/intl.dart'; // For formatting timestamps

class AIChatbotPage extends StatefulWidget {
  final String userName; // Add this
  final String? userProfilePicUrl; // Add this

  const AIChatbotPage({
    super.key,
    required this.userName, // Update constructor
    this.userProfilePicUrl, // Update constructor
  });

  @override
  State<AIChatbotPage> createState() => _AIChatbotPageState();
}

class _AIChatbotPageState extends State<AIChatbotPage> {
  final TextEditingController _messageController = TextEditingController();
  final List<ChatMessage> _messages = []; // Initialize empty and load messages in initState

  @override
  void initState() {
    super.initState();
    _loadInitialMessages();
  }

  void _loadInitialMessages() {
    _messages.addAll([
      ChatMessage(
        senderName: "NextChamp AI",
        text: "Hello, I'm your AI fitness assistant, NextChamp! How can I help you today?",
        isUser: false,
        timestamp: DateTime.now().subtract(const Duration(minutes: 10)),
      ),
      ChatMessage(
        senderName: widget.userName, // Use widget.userName
        text: "I want to improve my vertical jump.",
        isUser: true,
        timestamp: DateTime.now().subtract(const Duration(minutes: 8)),
      ),
      ChatMessage(
        senderName: "NextChamp AI",
        text: "Great! To improve your vertical jump, we can focus on plyometrics, strength training for legs and core, and proper landing mechanics. Would you like a training plan, or specific exercises?",
        isUser: false,
        timestamp: DateTime.now().subtract(const Duration(minutes: 7)),
      ),
      ChatMessage(
        senderName: widget.userName, // Use widget.userName
        text: "Give me some exercises for plyometrics.",
        isUser: true,
        timestamp: DateTime.now().subtract(const Duration(minutes: 5)),
      ),
      ChatMessage(
        senderName: "NextChamp AI",
        text: "Certainly! Here are a few effective plyometric exercises: Box Jumps, Depth Jumps, Broad Jumps, and Single-Leg Hops. Remember to warm up properly and focus on explosive power with good form.",
        isUser: false,
        timestamp: DateTime.now().subtract(const Duration(minutes: 3)),
      ),
    ]);
  }

  void _handleSendMessage() {
    if (_messageController.text.trim().isEmpty) return;

    setState(() {
      _messages.add(ChatMessage(
        senderName: widget.userName, // Use widget.userName here
        text: _messageController.text,
        isUser: true,
        timestamp: DateTime.now(),
      ));
      // Simulate AI response for now
      _messages.add(ChatMessage(
        senderName: "NextChamp AI",
        text: "Thanks for your message! I'm still learning, but I'll get back to you soon.",
        isUser: false,
        timestamp: DateTime.now().add(const Duration(seconds: 1)),
      ));
    });
    _messageController.clear();
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
    // Determine the name to display for the user, removing dots and truncating to first word
    String displayedUserName = message.senderName.replaceAll('.', '');
    if (message.isUser && displayedUserName.contains(' ')) {
      displayedUserName = displayedUserName.split(' ')[0];
    }
    // Ensure bot name is consistently "NextChamp AI"
    String displayedBotName = "NextChamp AI";


    return Container(
      margin: const EdgeInsets.symmetric(vertical: 10.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: message.isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          if (!message.isUser) // Bot's avatar and name on the left
            Padding(
              padding: const EdgeInsets.only(right: 10.0),
              child: Column(
                children: [
                  CircleAvatar(
                    radius: 20,
                    backgroundColor: const Color(0xFFD0FD3E),
                    child: Icon(Icons.smart_toy_outlined, color: Colors.black, size: 24),
                  ),
                  const SizedBox(height: 4),
                  SizedBox(
                    width: 80,
                    child: Column( // Use Column here
                      children: [
                        Text(
                          "NextChamp",
                          textAlign: TextAlign.center,
                          style: TextStyle(color: Colors.grey.shade400, fontSize: 10),
                          overflow: TextOverflow.ellipsis,
                        ),
                        Text(
                          "AI",
                          textAlign: TextAlign.center,
                          style: TextStyle(color: Colors.grey.shade400, fontSize: 10),
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
              crossAxisAlignment: message.isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
              children: [
                // Sender name and timestamp above the bubble
                if (message.isUser) // User's name on the right
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4.0),
                    child: Text(
                      "${displayedUserName} • ${DateFormat('HH:mm').format(message.timestamp)}", // Use displayedUserName
                      style: TextStyle(color: Colors.grey.shade400, fontSize: 12),
                    ),
                  )
                else // Bot's timestamp next to its name
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4.0),
                    child: Text(
                      DateFormat('HH:mm').format(message.timestamp),
                      style: TextStyle(color: Colors.grey.shade400, fontSize: 12),
                    ),
                  ),
                Container(
                  padding: const EdgeInsets.symmetric(vertical: 10.0, horizontal: 15.0),
                  decoration: BoxDecoration(
                    color: message.isUser ? const Color(0xFFD0FD3E) : Colors.grey.shade800,
                    borderRadius: BorderRadius.only(
                      topLeft: const Radius.circular(15),
                      topRight: const Radius.circular(15),
                      bottomLeft: message.isUser ? const Radius.circular(15) : const Radius.circular(0),
                      bottomRight: message.isUser ? const Radius.circular(0) : const Radius.circular(15),
                    ),
                  ),
                  child: Text(
                    message.text,
                    style: TextStyle(
                      color: message.isUser ? Colors.black : Colors.white,
                      fontSize: 16,
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (message.isUser) // User's avatar and name on the right
            Padding(
              padding: const EdgeInsets.only(left: 10.0),
              child: Column(
                children: [
                  CircleAvatar(
                    radius: 20,
                    backgroundColor: Colors.grey.shade700,
                    backgroundImage: widget.userProfilePicUrl != null
                        ? NetworkImage(widget.userProfilePicUrl!)
                        : null, // Use user's profile pic
                    child: widget.userProfilePicUrl == null
                        ? const Icon(Icons.person, color: Colors.white, size: 24)
                        : null,
                  ),
                  const SizedBox(height: 4),
                  SizedBox(
                    width: 40,
                    child: Text(
                      displayedUserName, // Use displayedUserName here
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Colors.grey.shade400, fontSize: 10),
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
              decoration: InputDecoration(
                hintText: "Type your message...",
                hintStyle: TextStyle(color: Colors.grey.shade400),
                filled: true,
                fillColor: Colors.grey.shade900,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(25.0),
                  borderSide: BorderSide.none,
                ),
                contentPadding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 10.0),
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