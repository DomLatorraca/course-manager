from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers import auth, courses, enrollments, import_export, materials, pages, students, users


settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("course-manager")


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie=settings.session_cookie,
        max_age=settings.session_max_age_seconds,
        same_site="lax",
        https_only=settings.is_production,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.on_event("startup")
    def startup() -> None:
        init_db()
        logger.info("Application started with database %s and storage %s", settings.database_url, settings.course_files_dir)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        accepts = request.headers.get("accept", "")
        if "text/html" in accepts and request.url.path.startswith("/") and not request.url.path.startswith("/api"):
            if exc.status_code == 401:
                return RedirectResponse("/login")
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s", request.url.path)
        accepts = request.headers.get("accept", "")
        if "text/html" in accepts and not request.url.path.startswith("/api"):
            return JSONResponse(status_code=500, content={"detail": "Errore interno. Consultare i log applicativi."})
        return JSONResponse(status_code=500, content={"detail": "Errore interno."})

    app.include_router(auth.router)
    app.include_router(auth.api_router)
    app.include_router(courses.router)
    app.include_router(students.router)
    app.include_router(enrollments.router)
    app.include_router(materials.router)
    app.include_router(import_export.router)
    app.include_router(users.router)
    app.include_router(pages.router)
    return app


app = create_app()

