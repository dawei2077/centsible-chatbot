from fastapi import FastAPI
from contextlib import asynccontextmanager
from routes import router
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Starting iMessage AI Advisor Backend...")
    yield
    # Shutdown logic

app = FastAPI(title="iMessage AI Financial Advisor", lifespan=lifespan)

app.include_router(router)

@app.get("/")
def read_root():
    return {"message": "iMessage AI Financial Advisor Backend is running!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
