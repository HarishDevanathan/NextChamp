from pydantic import BaseModel, Field
from typing import Optional, Literal

class ChatMessageModel(BaseModel):
    user_id: str = Field(..., description="ID of the user sending the message")
    user_name: str = Field(..., description="Name of the user for persona customization")
    message: str = Field(..., min_length=1, description="The user's message to NextChamp")

class ChatUpdateModel(BaseModel):
    user_id: str = Field(..., description="Reference to the user making the request")
    type: Literal["Q", "A"] = Field(..., description="Type of entry: 'user' for user message, 'model' for AI response")
    statement: str = Field(..., min_length=1, description="Text of the message")