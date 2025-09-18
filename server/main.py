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

from fastapi.middleware.cors import CORSMiddleware   # 1. IMPORT THIS
from fastapi.staticfiles import StaticFiles          # 2. IMPORT THIS
from pathlib import Path
from auth_services.routes import auth_engine

app = FastAPI()



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Allow all origins (for testing)
    allow_credentials=True,
    allow_methods=["*"],          # Allow all HTTP methods
    allow_headers=["*"],          # Allow all headers
)


app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "static"),
    name="static"
)

# 5. ROUTERS
app.include_router(auth_engine)

# 6. ROOT
@app.get("/")
def root():
    return {"message": "NextChamp API running"}
