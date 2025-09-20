from dotenv import load_dotenv
import os
import google.generativeai as genai
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

# Suppress gRPC warnings (only show ERROR and above)
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GRPC_CPP_VERBOSITY"] = "ERROR"

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

model = genai.GenerativeModel("models/gemini-1.5-flash")

# --- NextChamp Persona Integration ---
# This is where we define the AI's role and initial greeting
NEXTCHAMP_PERSONA_TEMPLATE = """You are NextChamp, an AI sports assistant in the "NextChamp" app, which helps athletes and sportspersons with talent assessment, training, and career growth.  
- The user’s name is {user_name}. Use their name naturally in your responses.  
- Answer only sports-related questions: training, techniques, rules, psychology, nutrition, injury prevention, fitness, and career advice.  
- Keep a motivating, professional, and encouraging tone.  
- If a question is about a specific sport, adapt your response to that sport.  
- If you don’t know the answer, admit it politely and suggest reliable resources or general guidance.  
- Keep responses clear, concise, and practical.
"""


async def get_chat_history_from_db(user_id: str, db: AsyncIOMotorDatabase):
    """
    Fetches chat history for a user from the database and formats it for Gemini.
    """
    cursor = db.chatHistory.find({"user_id": user_id}).sort("timestamp", 1)
    history = await cursor.to_list(length=None)

    formatted_history = []
    for doc in history:
        formatted_history.append({
            "role": "user" if doc["type"] == "Q" else "model", # Gemini expects 'role' as 'user' or 'model'
            "parts": [doc["statement"]]
        })
    return formatted_history

async def initialize_and_get_chat_session(user_id: str, user_name: str, db: AsyncIOMotorDatabase):
    # Construct the persona with the dynamic user name
    nextchamp_persona = NEXTCHAMP_PERSONA_TEMPLATE.format(user_name=user_name)

    # Fetch existing chat history from DB
    db_chat_history = await get_chat_history_from_db(user_id, db)
    
    # Check if this is a brand new chat for the user
    if not db_chat_history:
        # If no history, create a fresh start with the persona setup
        initial_history_for_gemini = [
            {"role": "user", "parts": [nextchamp_persona]},
            {"role": "model", "parts": [f"Hello, {user_name}! I'm NextChamp, your dedicated AI sports assistant. I'm here to help you excel in your athletic journey, whether it's through talent assessment, training guidance, or career growth. How can I assist you today? "]}
        ]
    else:
        initial_history_for_gemini = [
            {"role": "user", "parts": [nextchamp_persona]},
            {"role": "model", "parts": [f"Hello, {user_name}! I'm NextChamp, your dedicated AI sports assistant. I'm here to help you excel in your athletic journey, whether it's through talent assessment, training guidance, or career growth. How can I assist you today? "]}
        ]
        initial_history_for_gemini.extend(db_chat_history)
        
    # Start the chat with the constructed history
    chat_session = model.start_chat(history=initial_history_for_gemini)
    print(f"Chat session initialized for {user_name} ({user_id}). History loaded: {len(db_chat_history)} entries.")
    return chat_session

async def send_message_to_gemini(chat_session: genai.GenerativeModel.start_chat, question: str):
    response = chat_session.send_message(question, stream=True)
    answer = ""
    for chunk in response:
        if chunk.candidates and chunk.candidates[0].content.parts:
            part = chunk.candidates[0].content.parts[0].text
            answer += part
    return answer