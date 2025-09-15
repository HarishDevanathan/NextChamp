from fastapi import FastAPI
from auth_services.routes import auth_engine   # make sure path is correct

app = FastAPI()

# Register your router
app.include_router(auth_engine)

@app.get("/")
def root():
    return {"message": "NextChamp API running"}
