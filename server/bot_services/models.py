from pydantic import BaseModel, Field
from typing import Optional, Literal


class ChatUpdateModel(BaseModel):
    user_id: str = Field(..., description="Reference to the user making the request")
    type: Optional[Literal["Q", "A"]] = Field(
        None, description="Type of entry: Q for question, A for answer"
    )
    statement: Optional[str] = Field(
        None, min_length=1, description="Updated text of the question/answer"
    )
