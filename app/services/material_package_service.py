from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
import re
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.material import Material
from app.services.file_service import assert_inside_storage, course_storage_dir


@dataclass(frozen=True)
class MaterialPackageResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PackageFile:
    zip_name: str
    package_key: str
    relative_name: str
    original_filename: str
    title: str
    description: str
    size_bytes: int


def import_material_package(
    db: Session,
    zip_path: Path,
    overwrite: bool = True,
    include_archives: bool = False,
    dry_run: bool = False,
) -> MaterialPackageResult:
    zip_path = zip_path.expanduser().resolve()
    if not zip_path.exists():
        raise ValueError(f"Pacchetto materiali non trovato: {zip_path}")

    created = 0
    updated = 0
    skipped = 0
    errors: list[str] = []

    try:
        with ZipFile(zip_path) as archive:
            package_titles = _read_package_titles(archive)
            package_files = _list_package_files(archive, package_titles, include_archives)
            for package_file in package_files:
                course_title = package_titles.get(package_file.package_key)
                if not course_title:
                    skipped += 1
                    errors.append(f"{package_file.zip_name}: manifest corso non trovato.")
                    continue

                course = _find_course(db, course_title)
                if not course:
                    skipped += 1
                    errors.append(f"{package_file.zip_name}: corso non trovato nel database: {course_title}.")
                    continue

                existing = _find_existing_material(db, course.id, package_file.original_filename)
                if existing and not overwrite:
                    skipped += 1
                    continue

                if existing:
                    updated += 1
                else:
                    created += 1

                if dry_run:
                    continue

                content = archive.read(package_file.zip_name)
                destination = _material_destination(course.id, package_file.relative_name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)

                if existing:
                    existing.title = package_file.title
                    existing.description = package_file.description
                    existing.stored_filename = _stored_filename(package_file.relative_name)
                    existing.stored_path = str(destination)
                    existing.size_bytes = len(content)
                    existing.uploaded_at = _utcnow()
                    db.add(existing)
                else:
                    db.add(
                        Material(
                            course_id=course.id,
                            title=package_file.title,
                            description=package_file.description,
                            original_filename=package_file.original_filename,
                            stored_filename=_stored_filename(package_file.relative_name),
                            stored_path=str(destination),
                            size_bytes=len(content),
                        )
                    )
    except BadZipFile as exc:
        raise ValueError(f"File zip non valido: {zip_path}") from exc

    if dry_run:
        db.rollback()
    else:
        db.commit()

    return MaterialPackageResult(created=created, updated=updated, skipped=skipped, errors=errors)


def _read_package_titles(archive: ZipFile) -> dict[str, str]:
    titles: dict[str, str] = {}
    for info in archive.infolist():
        if info.is_dir() or not info.filename.endswith("/manifest.json"):
            continue
        path = PurePosixPath(info.filename)
        if len(path.parts) < 2:
            continue
        try:
            data = json.loads(archive.read(info).decode("utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        title = str(data.get("titolo") or data.get("course_title") or data.get("title") or "").strip()
        if title:
            titles[path.parts[0]] = " ".join(title.split())
    return titles


def _list_package_files(archive: ZipFile, package_titles: dict[str, str], include_archives: bool) -> list[PackageFile]:
    files: list[PackageFile] = []
    for info in archive.infolist():
        if info.is_dir() or info.filename.startswith("__MACOSX/"):
            continue
        path = PurePosixPath(info.filename)
        if path.is_absolute() or ".." in path.parts:
            continue

        package_key = _package_key_for_path(path, package_titles)
        if not package_key:
            continue

        extension = path.suffix.lower()
        if extension == ".zip" and not include_archives:
            continue

        relative_name = _relative_name(path, package_key)
        original_filename = f"{package_key}-{relative_name}".replace("/", "-")
        files.append(
            PackageFile(
                zip_name=info.filename,
                package_key=package_key,
                relative_name=relative_name,
                original_filename=original_filename,
                title=_title_for_file(relative_name),
                description="",
                size_bytes=info.file_size,
            )
        )
    return files


def _package_key_for_path(path: PurePosixPath, package_titles: dict[str, str]) -> str:
    if len(path.parts) > 1 and path.parts[0] in package_titles:
        return path.parts[0]
    if len(path.parts) == 1 and path.suffix.lower() == ".zip":
        stem = path.stem
        if stem in package_titles:
            return stem
    return ""


def _relative_name(path: PurePosixPath, package_key: str) -> str:
    if len(path.parts) > 1 and path.parts[0] == package_key:
        return str(PurePosixPath(*path.parts[1:]))
    return path.name


def _find_course(db: Session, title: str) -> Course | None:
    exact = db.scalar(select(Course).where(Course.title == title))
    if exact:
        return exact

    normalized_title = _normalize_title(title)
    matches = [course for course in db.scalars(select(Course)).all() if _normalize_title(course.title) == normalized_title]
    if len(matches) == 1:
        return matches[0]
    return None


def _find_existing_material(db: Session, course_id: int, original_filename: str) -> Material | None:
    return db.scalar(
        select(Material).where(
            Material.course_id == course_id,
            Material.original_filename == original_filename,
        )
    )


def _material_destination(course_id: int, relative_name: str) -> Path:
    safe_parts = [_slugify_part(part) for part in PurePosixPath(relative_name).parts if part]
    filename = safe_parts[-1] if safe_parts else "materiale"
    folder = course_storage_dir(course_id) / "pacchetto_materiali"
    destination = folder / filename
    return assert_inside_storage(destination)


def _stored_filename(relative_name: str) -> str:
    return str(PurePosixPath("pacchetto_materiali") / PurePosixPath(relative_name).name)


def _title_for_file(relative_name: str) -> str:
    stem = PurePosixPath(relative_name).stem
    labels = {
        "README": "Guida al pacchetto",
        "calendario": "Calendario corso",
        "elenco_partecipanti": "Elenco partecipanti",
        "esercitazioni_e_verifiche": "Esercitazioni e verifiche",
        "manifest": "Manifest corso",
        "programma_didattico": "Programma didattico",
        "registro_presenze": "Registro presenze",
        "scheda_corso": "Scheda corso",
        "traccia_slide": "Traccia slide",
    }
    return labels.get(stem, stem.replace("_", " ").replace("-", " ").strip().title())


def _normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _slugify_part(value: str) -> str:
    path = PurePosixPath(value)
    stem = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-") or "materiale"
    suffix = re.sub(r"[^a-z0-9.]+", "", path.suffix.lower())
    return f"{stem[:90]}{suffix}"


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
