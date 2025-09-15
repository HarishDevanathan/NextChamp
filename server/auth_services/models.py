from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class SignupModel(BaseModel):
    username: str
    email: EmailStr
    pwd: str
    dob: str                # date of birth
    height: str             # in cm
    weight: str             # in kg
    phoneno: Optional[str] = None
    profilePic: Optional[str] = None


class EmailRequest(BaseModel):
    email: EmailStr

class OtpModel(BaseModel):
    email: EmailStr
    otp: str

class LoginModel(BaseModel):
    email: EmailStr
    pwd: str

