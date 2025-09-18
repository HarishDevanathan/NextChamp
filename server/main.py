from fastapi import FastAPI
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


# 4. STATIC FILES MOUNT
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
