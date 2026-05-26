from __future__ import annotations

from io import BytesIO

import pytest
from fastapi import UploadFile

from app.schemas.course import CourseCreate
from app.services.course_service import create_course
from app.services.file_service import delete_material, get_material_path, save_material


def make_upload(filename: str, content: bytes) -> UploadFile:
    return UploadFile(filename=filename, file=BytesIO(content))


def test_material_upload_sanitizes_filename_and_can_delete_file(db):
    course = create_course(db, CourseCreate(title="Manuale", short_description="", category="", duration=""))
    material = save_material(db, course, make_upload("../manuale.pdf", b"pdf"), "Manuale", "")
    path = get_material_path(material)
    assert path.exists()
    assert material.original_filename == "manuale.pdf"
    assert "course_" in str(path)

    delete_material(db, material)
    assert not path.exists()


def test_material_rejects_disallowed_extension(db):
    course = create_course(db, CourseCreate(title="Manuale", short_description="", category="", duration=""))
    with pytest.raises(ValueError, match="Estensione non consentita"):
        save_material(db, course, make_upload("script.exe", b"x"), "Script", "")

