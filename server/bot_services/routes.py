from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from db.connection import get_db
from bot_services.models import *
from bot_services.util import * 

bot_engine = APIRouter(prefix="/bot")

@bot_engine.get("/history/{user_id}")
async def get_history(user_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    cursor = db.chatHistory.find({"user_id": user_id}).sort("timestamp", 1)
    history = await cursor.to_list(length=None)

    if not history:
        # If no history, it's not an error, just an empty list
        return []

    return [
        {
            "type": doc["type"],
            "statement": doc["statement"],
            "timestamp": doc["timestamp"]
        }
        for doc in history
    ]

@bot_engine.put("/insert")
async def insert_chat(new_chat: ChatUpdateModel, db: AsyncIOMotorDatabase = Depends(get_db)):
    async with await db.client.start_session() as session:
        async with session.start_transaction():
            result = await db.chatHistory.insert_one(
                {
                    "user_id": new_chat.user_id,
                    "type": new_chat.type,
                    "statement": new_chat.statement,
                    "timestamp": datetime.utcnow()
                },
                session=session
            )

    return {"message": "Chat inserted successfully", "id": str(result.inserted_id)}

@bot_engine.post("/chat")
async def chat_with_nextchamp(
    message_data: ChatMessageModel, # This model is not defined in the snippet you provided, but assumed to exist
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    user_id = message_data.user_id
    user_name = message_data.user_name
    user_message = message_data.message

    # 1. Initialize/Get chat session with history
    chat_session = await initialize_and_get_chat_session(user_id, user_name, db)

    # 2. Save user's message to DB
    user_chat_entry = ChatUpdateModel(user_id=user_id, type="Q", statement=user_message)
    await insert_chat(user_chat_entry, db)

    # 3. Get response from Gemini
    nextchamp_response = await send_message_to_gemini(chat_session, user_message)
    
    # 4. Save NextChamp's response to DB
    model_chat_entry = ChatUpdateModel(user_id=user_id, type="A", statement=nextchamp_response)
    await insert_chat(model_chat_entry, db)

    return {"response": nextchamp_response}

# Optional: A route to explicitly "start" a new conversation, resetting history
@bot_engine.post("/start_new_chat/{user_id}/{user_name}")
async def start_new_chat(
    user_id: str, 
    user_name: str, 
    db: AsyncIOMotorDatabase = Depends(get_db)
):

    # Construct the persona with the dynamic user name
    nextchamp_persona = NEXTCHAMP_PERSONA_TEMPLATE.format(user_name=user_name)

    # Prepare only the initial history for Gemini
    initial_history_for_gemini = [
        {"role": "user", "parts": [nextchamp_persona]},
        {"role": "model", "parts": [f"Hello, {user_name}! I'm NextChamp, your dedicated AI sports assistant. I'm here to help you excel in your athletic journey, whether it's through talent assessment, training guidance, or career growth. How can I assist you today? "]}
    ]
    
    # Start a chat purely for getting the initial greeting
    fresh_chat_session = model.start_chat(history=initial_history_for_gemini)
    
    # The first "message" in a truly new chat is the model's greeting
    # We can extract it directly from the `initial_history_for_gemini` or let Gemini generate it.
    # For a deterministic greeting, we'll use the one defined.
    initial_greeting = f"Hello, {user_name}! I'm NextChamp, your dedicated AI sports assistant. I'm here to help you excel in your athletic journey, whether it's through talent assessment, training guidance, or career growth. How can I assist you today? "
    
    # Save the initial greeting to DB
    model_chat_entry = ChatUpdateModel(user_id=user_id, type="A", statement=initial_greeting)
    await insert_chat(model_chat_entry, db)

    return {"response": initial_greeting}