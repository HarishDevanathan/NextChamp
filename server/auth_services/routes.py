# --- Standard Imports ---
import base64
import os
from datetime import datetime, timezone
from pathlib import Path

# --- FastAPI and Pydantic Imports ---
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pydantic_settings import BaseSettings

# --- Library Imports ---
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType

# --- Firebase Admin SDK Imports ---
import firebase_admin
from firebase_admin import credentials, auth

# --- Local Imports ---
from .models import SignupModel, EmailRequest, OtpModel, GoogleSignupModel
from db.connection import get_db
from . import utils as auth_util  

# --- Initial Setup ---
auth_engine = APIRouter(prefix="/auth")
db = get_db()

# --- Firebase Admin SDK Initialization ---
try:
    cred_path = Path(__file__).resolve().parent.parent / "firebase-service-account.json"
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    print("Firebase Admin SDK initialized successfully.")
except Exception as e:
    print(f"CRITICAL ERROR: Failed to initialize Firebase Admin SDK: {e}")

# --- Secure Configuration Loading for Mail ---
class EnvironmentSettings(BaseSettings):
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    USE_CREDENTIALS: bool = True
    TEMPLATE_FOLDER: Path = Path(__file__).resolve().parent.parent / "email-templates"
    MONGO_URI: str
    MONGO_DB_NAME: str
    GOOGLE_API_KEY : str
    BOT_API_KEY: str
    HUGGING_FACE: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = EnvironmentSettings()

mail_config = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_FROM_NAME="NextChamp App",
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=settings.USE_CREDENTIALS,
    TEMPLATE_FOLDER=settings.TEMPLATE_FOLDER
)

# --- Directory Setup for Image Uploads ---
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
IMAGES_DIR = STATIC_DIR / "images"
os.makedirs(IMAGES_DIR, exist_ok=True)


# --- API Endpoints ---

@auth_engine.post("/email/signup")
async def signup_api(signup: SignupModel):
    if await db.user.find_one({"email": signup.email}):
        raise HTTPException(status_code=400, detail="User with this email already exists")

    profile_pic_url = ""
    if signup.profilePic:
        if signup.profilePic.startswith("http"):
            profile_pic_url = signup.profilePic
        else:
            try:
                base64_image_data = signup.profilePic
                if "," in base64_image_data:
                    _, base64_image_data = base64_image_data.split(",", 1)
                
                image_bytes = base64.b64decode(base64_image_data)
                unique_filename = f"{datetime.now().timestamp()}_{signup.username}.jpg"
                file_location = IMAGES_DIR / unique_filename
                with open(file_location, "wb") as file_object:
                    file_object.write(image_bytes)
                profile_pic_url = f"/static/images/{unique_filename}"
            except Exception as e:
                print(f"Error decoding or saving Base64 image: {e}")
                raise HTTPException(status_code=500, detail="Could not process profile picture.")
    
    age = auth_util.calculate_age(signup.dob)
    bmi = auth_util.calculate_bmi(signup.height, signup.weight)
    user_id = await auth_util.generate_userid(signup.username, db)
    hashed_pwd = auth_util.get_password_hash(signup.pwd) if signup.pwd else None

    user_doc = {
        "_id": user_id, "name": signup.username, "email": signup.email, "pwd": hashed_pwd,
        "dob": signup.dob, "age": str(age), "height": signup.height, "weight": signup.weight,
        "bmi": str(bmi), "phoneno": signup.phoneno, "profilePic": profile_pic_url, 
        "createdAt": datetime.now(timezone.utc)
    }
    
    await db.user.insert_one(user_doc)
    
    return {"success": True, "message": "User registered successfully", "userid": str(user_id)}


@auth_engine.post("/email/signup/sendotp")
async def sendotp_api(request: EmailRequest):
    email = request.email
    otp = auth_util.generate_otp()
    await db.otp_store.update_one(
        {"email": email}, 
        {"$set": {"otp": otp, "createdAt": datetime.now(timezone.utc)}},
        upsert=True
    )
    message = MessageSchema(
        subject="Your OTP Code", recipients=[email],
        template_body={"otp": otp, "purpose": "To complete your signup", "date": datetime.now(timezone.utc).strftime("%d-%B-%Y")},
        subtype=MessageType.html
    )
    fm = FastMail(mail_config)
    await fm.send_message(message, template_name="otp_template.html")
    return {"message": "OTP sent successfully"}


@auth_engine.post("/email/verifyotp")
async def verifyotp_api(request: OtpModel):
    otp_entry = await db.otp_store.find_one({"email": request.email, "otp": request.otp})
    if not otp_entry:
        raise HTTPException(status_code=401, detail="Invalid OTP or email mismatch")
    created_at = otp_entry["createdAt"].replace(tzinfo=timezone.utc)
    if (datetime.now(timezone.utc) - created_at).total_seconds() > 10 * 60:
        await db.otp_store.delete_one({"email": request.email, "otp": request.otp})
        raise HTTPException(status_code=401, detail="OTP expired")
    return {"success": True, "message": "OTP verified successfully", "email": request.email}


class LoginModel(BaseModel):
    email: str
    pwd: str


@auth_engine.post("/email/login")
async def login_api(login: LoginModel):
    user = await db.user.find_one({"email": login.email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("pwd"):
        raise HTTPException(status_code=401, detail="This account uses Google Sign-In. Please use the Google Sign-In button.")
    if not auth_util.verify_password(login.pwd, user["pwd"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    response = {
        "success": True, "message": "Login successful", "userid": str(user["_id"]), "name": user["name"],
        "email": user["email"], "age": user.get("age"), "height": user.get("height"),
        "weight": user.get("weight"), "bmi": user.get("bmi"), "phoneno": user.get("phoneno", ""),
        "profilePic": user.get("profilePic", "") , "gender" : user.get("gender" , "Male")
    }
    
    #print(response)

    return response

class GoogleToken(BaseModel):
    idToken: str


@auth_engine.post("/google/check")
async def google_check_api(token: GoogleToken):
    try:
        decoded_token = auth.verify_id_token(token.idToken)
        email = decoded_token.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email not found in Google token.")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Firebase ID Token: {e}")

    user = await db.user.find_one({"email": email})
    if user:
        return {
            "exists": True,
            "userData": {
                "userid": str(user["_id"]), "name": user["name"], "email": user["email"],
                "profilePic": user.get("profilePic", "")
            }
        }
    else:
        return {
            "exists": False,
            "prefillData": {
                "email": email, "name": decoded_token.get("name", ""),
                "profilePic": decoded_token.get("picture", "")
            }
        }


@auth_engine.post("/google/register")
async def google_register_api(signup_data: GoogleSignupModel):
    if await db.user.find_one({"email": signup_data.email}):
        raise HTTPException(status_code=400, detail="User with this email already exists.")
    
    age = auth_util.calculate_age(signup_data.dob)
    bmi = auth_util.calculate_bmi(signup_data.height, signup_data.weight)
    user_id = await auth_util.generate_userid(signup_data.username, db)

    user_doc = {
        "_id": user_id, "name": signup_data.username, "email": signup_data.email, "pwd": None,
        "dob": signup_data.dob, "age": str(age), "height": signup_data.height,
        "weight": signup_data.weight, "bmi": str(bmi), "phoneno": signup_data.phoneno,
        "profilePic": signup_data.profilePic, "createdAt": datetime.now(timezone.utc)
    }
    
    await db.user.insert_one(user_doc)
    return {"success": True, "message": "User registered successfully", "userid": str(user_id)}
