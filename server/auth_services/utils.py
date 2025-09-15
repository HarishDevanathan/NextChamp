from db.connection import db
import random
from passlib.context import CryptContext
from datetime import datetime, timezone
import typing

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ------------------- User ID -------------------
async def generate_userid(username: str, db):
    base = username.lower().replace(" ", "_")
    while True:
        random_number = str(random.randint(10000, 99999))
        tempname = base + random_number
        existing = await db.user.find_one({"_id": tempname})
        if not existing:
            return tempname

# ------------------- Password -------------------
def get_password_hash(password: str) -> str:
    return bcrypt_context.hash(password)

def verify_password(plain_pwd: str, hashed_pwd: str) -> bool:
    return bcrypt_context.verify(plain_pwd, hashed_pwd)

# ------------------- OTP -------------------
def generate_otp() -> str:
    return str(random.randint(100000, 999999))

# ------------------- Age from DOB -------------------
def calculate_age(dob_str: str) -> int:
    """
    dob_str: format "YYYY-MM-DD"
    """
    dob = datetime.strptime(dob_str, "%Y-%m-%d")
    today = datetime.now()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return age

# ------------------- BMI -------------------
def calculate_bmi(height_str: str, weight_str: str) -> float:
    """
    height_str: e.g., "170cm" or "1.7m"
    weight_str: e.g., "65kg"
    Returns BMI rounded to 1 decimal place
    """
    # Convert height to meters
    if "cm" in height_str:
        height = float(height_str.replace("cm", "")) / 100
    elif "m" in height_str:
        height = float(height_str.replace("m", ""))
    else:
        height = float(height_str)  # assume meters if no unit
    
    # Convert weight to kg
    if "kg" in weight_str:
        weight = float(weight_str.replace("kg", ""))
    else:
        weight = float(weight_str)
    
    bmi = weight / (height ** 2)
    return round(bmi, 1)
