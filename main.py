
import os
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from routes import router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting iMessage AI Advisor Backend...")
    yield


app = FastAPI(
    title="iMessage AI Financial Advisor",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/")
def read_root():
    return {
        "message": "iMessage AI Financial Advisor Backend is running!"
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=False,
    )
