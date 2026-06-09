from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi import UploadFile
from sqlalchemy import select

from app.config import get_settings
from app.models.material import Material
from app.schemas.course import CourseCreate
from app.services.course_service import create_course
from app.services.file_service import delete_material, get_material_path, guess_material_media_type, save_material
from app.services.material_package_service import import_material_package
from app.services.storage_material_import_service import import_storage_materials
from app.services.teaching_material_service import GENERATED_MATERIAL_TITLE, generate_teaching_materials


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


def test_generated_teaching_material_is_registered_and_idempotent(db):
    course = create_course(db, CourseCreate(title="CORSO FULL STACK 2025", short_description="", category="Foglio3", duration="24h"))

    first = generate_teaching_materials(db)

    assert first.generated == 1
    material = db.scalar(select(Material).where(Material.course_id == course.id, Material.title == GENERATED_MATERIAL_TITLE))
    assert material is not None
    path = get_material_path(material)
    assert path.exists()
    assert path.read_bytes().startswith(b"%PDF")

    second = generate_teaching_materials(db)

    assert second.generated == 0
    assert second.updated == 1
    materials = db.scalars(select(Material).where(Material.course_id == course.id, Material.title == GENERATED_MATERIAL_TITLE)).all()
    assert len(materials) == 1


def test_material_package_import_registers_files_and_is_idempotent(db, tmp_path: Path):
    course = create_course(db, CourseCreate(title="CORSO AI 2025 - 2026", short_description="", category="", duration=""))
    package = tmp_path / "pacchetto.zip"
    with ZipFile(package, "w") as archive:
        archive.writestr("08_CORSO_AI_2025_2026/manifest.json", '{"titolo": "CORSO AI 2025 - 2026"}')
        archive.writestr("08_CORSO_AI_2025_2026/README.md", "# Materiale AI")
        archive.writestr("08_CORSO_AI_2025_2026/calendario.csv", "data,argomento\n2026-01-01,Intro")
        archive.writestr("08_CORSO_AI_2025_2026.zip", b"archive")

    first = import_material_package(db, package)

    assert first.created == 3
    assert first.updated == 0
    assert first.skipped == 0
    materials = db.scalars(select(Material).where(Material.course_id == course.id).order_by(Material.original_filename)).all()
    assert len(materials) == 3
    assert all(get_material_path(material).exists() for material in materials)
    assert not any(material.original_filename.endswith(".zip") for material in materials)

    second = import_material_package(db, package)

    assert second.created == 0
    assert second.updated == 3
    materials_after = db.scalars(select(Material).where(Material.course_id == course.id)).all()
    assert len(materials_after) == 3


def test_material_package_import_supports_pdf_package_without_manifest(db, tmp_path: Path):
    course = create_course(db, CourseCreate(title="CORSO TEST PDF 2025", short_description="", category="", duration=""))
    package = tmp_path / "pacchetto_pdf.zip"
    with ZipFile(package, "w") as archive:
        archive.writestr("01_CORSO_TEST_PDF_2025/programma_corso.pdf", b"%PDF-1.4\n/Title (Programma corso - CORSO TEST PDF 2025)\n")
        archive.writestr("01_CORSO_TEST_PDF_2025/slide_01_intro.pdf", b"%PDF-1.4\n/Title (CORSO TEST PDF 2025 - Intro)\n")

    result = import_material_package(db, package)

    assert result.created == 2
    assert result.skipped == 0
    materials = db.scalars(select(Material).where(Material.course_id == course.id).order_by(Material.original_filename)).all()
    assert [material.title for material in materials] == ["Programma corso", "Slide 01 Intro"]


def test_material_media_types_are_browser_viewable():
    assert guess_material_media_type("programma_didattico.md").startswith("text/markdown")
    assert guess_material_media_type("calendario.csv").startswith("text/csv")
    assert guess_material_media_type("calendario.ics").startswith("text/calendar")


def test_import_storage_materials_registers_files_from_course_id_folder(db):
    course = create_course(db, CourseCreate(title="CORSO STORAGE", short_description="", category="", duration=""))
    scan_root = get_settings().course_files_dir / "existing-storage-id"
    folder = scan_root / f"course_{course.id}"
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / "manuale.pdf"
    file_path.write_bytes(b"%PDF storage")

    first = import_storage_materials(db, root_path=scan_root)

    assert first.created == 1
    material = db.scalar(select(Material).where(Material.course_id == course.id, Material.original_filename == "manuale.pdf"))
    assert material is not None
    assert get_material_path(material) == file_path.resolve()

    second = import_storage_materials(db, root_path=scan_root)

    assert second.created == 0
    assert second.updated == 1
    materials = db.scalars(select(Material).where(Material.course_id == course.id)).all()
    assert len(materials) == 1


def test_import_storage_materials_registers_files_from_course_title_folder(db):
    course = create_course(db, CourseCreate(title="CORSO AI 2025 - 2026", short_description="", category="", duration=""))
    scan_root = get_settings().course_files_dir / "existing-storage-title"
    folder = scan_root / "CORSO AI 2025 - 2026"
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / "programma.md"
    file_path.write_text("# Programma", encoding="utf-8")

    result = import_storage_materials(db, root_path=scan_root)

    assert result.created == 1
    material = db.scalar(select(Material).where(Material.course_id == course.id, Material.original_filename == "programma.md"))
    assert material is not None
    assert get_material_path(material) == file_path.resolve()

