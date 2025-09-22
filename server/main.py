from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware

# Import your routers
from auth_services.routes import auth_engine
from test_services.routes import router
from bot_services.routes import bot_engine

app = FastAPI()

# 1️⃣ CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or restrict to your frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2️⃣ Mount static folders
BASE_DIR = Path(__file__).resolve().parent

# Static folder for general assets
app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static"
)

# Videos folder - serves all files in analyzed_videos
app.mount(
    "/analyzed_videos",
    StaticFiles(directory=BASE_DIR / "analyzed_videos"),
    name="analyzed_videos"
)

# Reports folder
app.mount(
    "/reports",
    StaticFiles(directory=BASE_DIR / "reports"),
    name="reports"
)

# 3️⃣ Include your routers
app.include_router(auth_engine)
app.include_router(router)
app.include_router(bot_engine)

# 4️⃣ Root endpoint
@app.get("/")
def root():
    return {"message": "NextChamp API running"}
