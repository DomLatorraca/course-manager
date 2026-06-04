from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


class Settings:
    app_name: str = os.getenv("APP_NAME", "Course Manager")
    app_env: str = os.getenv("APP_ENV", "development")
    secret_key: str = os.getenv("SECRET_KEY", "change-me")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
    course_files_dir: Path = Path(os.getenv("COURSE_FILES_DIR", "./storage")).resolve()
    _default_excel_courses_path = Path.home() / "Downloads" / "Formazione dta 2024).xlsx"
    excel_courses_path: Path = Path(
        os.getenv(
            "EXCEL_COURSES_PATH",
            str(_default_excel_courses_path) if _default_excel_courses_path.exists() else "./data/corsi.xlsx",
        )
    ).resolve()
    excel_courses_sheet_name: str = os.getenv("EXCEL_COURSES_SHEET", "Corsi")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "50"))
    allowed_extensions: set[str] = {
        item.strip().lower()
        for item in os.getenv(
            "ALLOWED_EXTENSIONS",
            "pdf,doc,docx,ppt,pptx,xls,xlsx,png,jpg,jpeg,zip",
        ).split(",")
        if item.strip()
    }
    admin_default_username: str = os.getenv("ADMIN_DEFAULT_USERNAME", "admin")
    admin_default_password: str = os.getenv("ADMIN_DEFAULT_PASSWORD", "change-me-on-first-login")
    session_cookie: str = "course_manager_session"
    session_max_age_seconds: int = 60 * 60 * 8

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.course_files_dir.mkdir(parents=True, exist_ok=True)
    settings.excel_courses_path.parent.mkdir(parents=True, exist_ok=True)
    if settings.database_url.startswith("sqlite:///"):
        db_path = settings.database_url.replace("sqlite:///", "", 1)
        if db_path and db_path != ":memory:":
            Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    return settings

