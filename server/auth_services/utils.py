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

def calculate_bmi(height_cm: str, weight_kg: str) -> float:
    """
    height_cm: height in centimeters (str or int)
    weight_kg: weight in kilograms (str or int)
    Returns BMI rounded to 1 decimal place
    """
    height_m = float(height_cm) / 100
    weight = float(weight_kg)
    bmi = weight / (height_m ** 2)
    return round(bmi, 1)


