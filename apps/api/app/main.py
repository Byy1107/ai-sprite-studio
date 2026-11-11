from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router


def create_app() -> FastAPI:
    application = FastAPI(
        title="AI Sprite Studio API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Content-Type"],
    )
    application.include_router(router)
    return application


app = create_app()

