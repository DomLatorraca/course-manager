from __future__ import annotations

import mimetypes
import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.course import Course
from app.models.material import Material


def safe_extension(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def validate_upload(filename: str, size: int) -> None:
    settings = get_settings()
    extension = safe_extension(filename)
    if not extension or extension not in settings.allowed_extensions:
        raise ValueError(f"Estensione non consentita. Estensioni ammesse: {', '.join(sorted(settings.allowed_extensions))}.")
    if size > settings.max_upload_bytes:
        raise ValueError(f"File troppo grande. Dimensione massima: {settings.max_upload_mb} MB.")


def course_storage_dir(course_id: int) -> Path:
    settings = get_settings()
    path = settings.course_files_dir / f"course_{course_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def assert_inside_storage(path: Path) -> Path:
    settings = get_settings()
    resolved = path.resolve()
    storage_root = settings.course_files_dir.resolve()
    if storage_root not in resolved.parents and resolved != storage_root:
        raise ValueError("Percorso file non valido.")
    return resolved


def save_material(db: Session, course: Course, upload: UploadFile, title: str, description: str = "") -> Material:
    original_name = Path(upload.filename or "file").name
    content = upload.file.read()
    validate_upload(original_name, len(content))
    extension = safe_extension(original_name)
    stored_name = f"{uuid.uuid4().hex}.{extension}"
    destination = assert_inside_storage(course_storage_dir(course.id) / stored_name)
    with destination.open("wb") as output:
        output.write(content)
    material = Material(
        course_id=course.id,
        title=title or original_name,
        description=description,
        original_filename=original_name,
        stored_filename=stored_name,
        stored_path=str(destination),
        size_bytes=len(content),
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


def get_material_path(material: Material) -> Path:
    return assert_inside_storage(Path(material.stored_path))


def guess_material_media_type(filename: str) -> str:
    extension = safe_extension(filename)
    explicit = {
        "md": "text/markdown; charset=utf-8",
        "csv": "text/csv; charset=utf-8",
        "ics": "text/calendar; charset=utf-8",
        "json": "application/json; charset=utf-8",
        "txt": "text/plain; charset=utf-8",
    }
    if extension in explicit:
        return explicit[extension]
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def delete_material(db: Session, material: Material) -> None:
    path = get_material_path(material)
    if path.exists():
        path.unlink()
    db.delete(material)
    db.commit()


def delete_course_storage_if_empty(course_id: int) -> None:
    path = course_storage_dir(course_id)
    if path.exists() and not any(path.iterdir()):
        shutil.rmtree(path)

