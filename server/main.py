from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles   # 1. IMPORT THIS
from pathlib import Path                      # 2. IMPORT THIS
from auth_services.routes import auth_engine  # make sure path is correct
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],  # allows GET, POST, PUT, DELETE, OPTIONS
    allow_headers=["*"],
)
# 3. ADD THIS MOUNTING LOGIC
# This line tells FastAPI that any request starting with "/static"
# should be served from the "static" folder in your project directory.
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "static"),
    name="static"
)

# Register your router (this remains the same)
app.include_router(auth_engine)

@app.get("/")
def root():
    return {"message": "NextChamp API running"}