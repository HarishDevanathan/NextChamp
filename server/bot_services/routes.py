from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from db.connection import get_db
from bot_services.models import ChatUpdateModel
from datetime import datetime

bot_engine = APIRouter(prefix="/bot")

@bot_engine.get("/history/{user_id}")
async def get_history(user_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    cursor = db.chatHistory.find({"user_id": user_id}).sort("timestamp", 1)
    history = await cursor.to_list(length=None)

    if not history:
        raise HTTPException(
            status_code=404,
            detail="User ID not found"
        )

    return [
        {
            "type": doc["type"],
            "statement": doc["statement"],
            "timestamp": doc["timestamp"]
        }
        for doc in history
    ]

@bot_engine.put("/update")
async def update_chat(new_chat: ChatUpdateModel, db: AsyncIOMotorDatabase = Depends(get_db)):
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
