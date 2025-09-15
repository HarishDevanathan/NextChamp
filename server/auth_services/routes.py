from fastapi import APIRouter, HTTPException
from auth_services.models import SignupModel, EmailRequest, OtpModel
from db.connection import get_db
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from datetime import datetime, timezone
from pathlib import Path
from auth_services import utils as auth_util  

auth_engine = APIRouter(prefix="/auth")
db = get_db()

mail_config = ConnectionConfig(
    MAIL_USERNAME="nextchamp18@gmail.com",
    MAIL_PASSWORD="rkyglmcpvxqmiayn",
    MAIL_FROM="nextchamp18@gmail.com",
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    TEMPLATE_FOLDER=Path(__file__).resolve().parent.parent / "static" / "templates"
)
@auth_engine.post("/email/signup")
async def signup_api(signup: SignupModel):
    existing_user = await db.user.find_one({"email": signup.email})
    if existing_user:
        return {"success": False, "message": "User already exists"}
    
    age = auth_util.calculate_age(signup.dob)
    bmi = auth_util.calculate_bmi(signup.height, signup.weight)
    
    user_id = await auth_util.generate_userid(signup.username, db)
    hashed_pwd = auth_util.get_password_hash(signup.pwd)

    # Include remaining fields: phoneno and profilePic
    user_doc = {
        "_id": user_id,
        "name": signup.username,
        "email": signup.email,
        "pwd": hashed_pwd,
        "dob": signup.dob,
        "age": str(age),
        "height": signup.height,
        "weight": signup.weight,
        "bmi": str(bmi),
        "phoneno": getattr(signup, "phoneno", ""),       # default to empty string
        "profilePic": getattr(signup, "profilePic", ""), # default to empty string
        "createdAt": datetime.now(timezone.utc)
    }
    
    await db.user.insert_one(user_doc)
    
    return {"success": True, "message": "User registered successfully", "userid": user_id}

@auth_engine.post("/email/signup/sendotp")
async def sendotp_api(request: EmailRequest):
    email = request.email
    otp = auth_util.generate_otp()
    
    # Store OTP in DB
    await db.otp_store.update_one(
        {"email": email}, 
        {"$set": {"otp": otp, "createdAt": datetime.now(timezone.utc)}},
        upsert=True
    )
    
    # Send OTP email
    message = MessageSchema(
        subject="Your OTP Code",
        recipients=[email],
        template_body={
            "otp": otp,
            "purpose": "To complete your signup",
            "date": datetime.now(timezone.utc).strftime("%d-%B-%Y")
        },
        subtype=MessageType.html
    )
    
    fm = FastMail(mail_config)
    await fm.send_message(message, template_name="otp_template.html")
    
    return {"message": "OTP sent successfully"}

from datetime import datetime, timezone

@auth_engine.post("/email/verifyotp")
async def verifyotp_api(request: OtpModel):
    otp_entry = await db.otp_store.find_one({"email": request.email, "otp": request.otp})
    if not otp_entry:
        raise HTTPException(status_code=401, detail="Invalid OTP or email mismatch")
    
    # Convert naive datetime from DB to aware UTC datetime
    created_at = otp_entry["createdAt"]
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    # Check expiry (10 mins)
    if (datetime.now(timezone.utc) - created_at).total_seconds() > 10 * 60:
        await db.otp_store.delete_one({"email": request.email, "otp": request.otp})
        raise HTTPException(status_code=401, detail="OTP expired")
    
    return {
        "success": True,
        "message": "OTP verified successfully",
        "email": request.email
    }
