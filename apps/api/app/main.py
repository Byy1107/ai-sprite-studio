import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker

from app.api.router import router
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_engine
from app.services.generation import GenerationService
from app.services.projects import ProjectService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(get_engine())
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as session:
        GenerationService(session).recover_interrupted()
        projects = ProjectService(session, get_settings().workspace_dir)
        for project in projects.list_projects():
            issues = projects.inspect_integrity(project.id)
            if issues:
                logger.warning(
                    "Project %s has %d missing or unsafe files.", project.id, len(issues)
                )
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="AI Sprite Studio API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )
    application.include_router(router)

    return application


app = create_app()

