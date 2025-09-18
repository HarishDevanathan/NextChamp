from dotenv import load_dotenv
import os

# Suppress gRPC warnings (only show ERROR and above)
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GRPC_CPP_VERBOSITY"] = "ERROR"

import google.generativeai as genai


# Load env
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Use Flash instead of Pro
model = genai.GenerativeModel("models/gemini-1.5-flash")

# --- NextChamp Persona Integration ---
# This is where we define the AI's role and initial greeting
USER_NAME = "Harivansh B" # You would set this dynamically in a real app
NEXTCHAMP_PERSONA = f"""You are NextChamp, an AI sports assistant in the "NextChamp" app, which helps athletes and sportspersons with talent assessment, training, and career growth.  
- The user’s name is {USER_NAME}. Use their name naturally in your responses.  
- Answer only sports-related questions: training, techniques, rules, psychology, nutrition, injury prevention, fitness, and career advice.  
- Keep a motivating, professional, and encouraging tone.  
- If a question is about a specific sport, adapt your response to that sport.  
- If you don’t know the answer, admit it politely and suggest reliable resources or general guidance.  
- Keep responses clear, concise, and practical.
"""

# Start the chat with the persona as the initial system instruction
chat = model.start_chat(history=[
    {"role": "user", "parts": [NEXTCHAMP_PERSONA]},
    {"role": "model", "parts": [f"Hello, {USER_NAME}! I'm NextChamp, your dedicated AI sports assistant. I'm here to help you excel in your athletic journey, whether it's through talent assessment, training guidance, or career growth. How can I assist you today? "]}
])

def get_gemini_response(question):
    response = chat.send_message(question, stream=True)
    answer = ""
    for chunk in response:
        if chunk.candidates and chunk.candidates[0].content.parts:
            part = chunk.candidates[0].content.parts[0].text
            print(part, end="", flush=True)
            answer += part
    print("\n")
    return answer

if __name__ == "__main__":
    # You might want to get the user's name here in a real application
    # For this example, we'll just use the placeholder.
    print(f"Welcome to NextChamp, {USER_NAME}!")
    print("Type 'exit', 'quit', or 'bye' to end the chat.")
    while True:
        question = input("You: ")
        if question.lower() in ["exit", "quit", "bye"]:
            print("Chat ended.")
            break
        get_gemini_response(question)