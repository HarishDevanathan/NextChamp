from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserModel(BaseModel):
    _id: str
    name: str
    pwd: str
    email: EmailStr
    height: str
    weight: str
    bmi: str
    createdAt: datetime
    phoneno: str
    profilePic: str
    dob: str
    age: str

from pydantic import BaseModel, EmailStr

class SignupModel(BaseModel):
    email: EmailStr
    username: str
    pwd: str

class EmailRequest(BaseModel):
    email: EmailStr

class OtpModel(BaseModel):
    email: EmailStr
    otp: str

class LoginModel(BaseModel):
    email: EmailStr
    pwd: str

