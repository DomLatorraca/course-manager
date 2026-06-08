from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.course import Course
from app.models.material import Material
from app.services.file_service import assert_inside_storage


@dataclass(frozen=True)
class StorageMaterialImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def import_storage_materials(
    db: Session,
    root_path: Path | None = None,
    overwrite: bool = True,
    dry_run: bool = False,
) -> StorageMaterialImportResult:
    storage_root = get_settings().course_files_dir.resolve()
    scan_root = (root_path or storage_root).expanduser().resolve()
    if not scan_root.exists():
        raise ValueError(f"Percorso storage non trovato: {scan_root}")
    if storage_root != scan_root and storage_root not in scan_root.parents:
        raise ValueError(f"Il percorso deve essere dentro lo storage configurato: {storage_root}")

    courses = list(db.scalars(select(Course)).all())
    created = 0
    updated = 0
    skipped = 0
    errors: list[str] = []

    for path in sorted(item for item in scan_root.rglob("*") if item.is_file()):
        if _should_skip(path):
            skipped += 1
            continue

        try:
            resolved = assert_inside_storage(path)
        except ValueError as exc:
            skipped += 1
            errors.append(f"{path}: {exc}")
            continue

        course = _course_for_path(resolved, storage_root, courses)
        if not course:
            skipped += 1
            errors.append(f"{resolved}: corso non riconosciuto. Usa una cartella course_<id> oppure una cartella con il titolo del corso.")
            continue

        existing = _existing_material(db, course.id, resolved)
        if existing and not overwrite:
            skipped += 1
            continue

        if existing:
            updated += 1
        else:
            created += 1

        if dry_run:
            continue

        relative = resolved.relative_to(storage_root)
        title = _title_for_file(resolved)
        description = f"Importato da storage esistente: {relative.as_posix()}"
        if existing:
            existing.title = title
            existing.description = description
            existing.original_filename = resolved.name
            existing.stored_filename = relative.as_posix()
            existing.size_bytes = resolved.stat().st_size
            existing.uploaded_at = _utcnow()
            db.add(existing)
        else:
            db.add(
                Material(
                    course_id=course.id,
                    title=title,
                    description=description,
                    original_filename=resolved.name,
                    stored_filename=relative.as_posix(),
                    stored_path=str(resolved),
                    size_bytes=resolved.stat().st_size,
                )
            )

    if dry_run:
        db.rollback()
    else:
        db.commit()

    return StorageMaterialImportResult(created=created, updated=updated, skipped=skipped, errors=errors)


def _should_skip(path: Path) -> bool:
    ignored_suffixes = {".tmp", ".part", ".crdownload", ".db", ".sqlite", ".sqlite3"}
    if any(part.startswith(".") or part == "__MACOSX" for part in path.parts):
        return True
    if path.suffix.lower() in ignored_suffixes:
        return True
    return False


def _course_for_path(path: Path, storage_root: Path, courses: list[Course]) -> Course | None:
    relative = path.relative_to(storage_root)
    parts = relative.parts

    for part in parts:
        match = re.fullmatch(r"course_(\d+)", part, flags=re.IGNORECASE)
        if match:
            course_id = int(match.group(1))
            return next((course for course in courses if course.id == course_id), None)

    candidates = [part for part in parts[:-1]]
    candidates.extend(path.stem.split("_"))
    normalized_candidates = [_normalize(value) for value in candidates if value]

    exact_matches = [
        course
        for course in courses
        if any(_normalize(course.title) == candidate for candidate in normalized_candidates)
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]

    path_text = _normalize(" ".join(parts))
    contains_matches = [course for course in courses if _normalize(course.title) and _normalize(course.title) in path_text]
    if len(contains_matches) == 1:
        return contains_matches[0]

    return None


def _existing_material(db: Session, course_id: int, path: Path) -> Material | None:
    return db.scalar(
        select(Material).where(
            Material.course_id == course_id,
            Material.stored_path == str(path),
        )
    )


def _title_for_file(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").strip().title() or path.name


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
