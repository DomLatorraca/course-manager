from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["APP_ENV"] = "development"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp()) / 'test.db'}"
os.environ["COURSE_FILES_DIR"] = str(Path(tempfile.mkdtemp()) / "storage")
os.environ["MAX_UPLOAD_MB"] = "1"
os.environ["ALLOWED_EXTENSIONS"] = "pdf,txt,zip"

import pytest

from app.database import Base, SessionLocal, engine
from app.models import Course, Enrollment, Material, Student, User  # noqa: F401


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
