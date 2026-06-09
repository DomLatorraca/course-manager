from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
import re

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.material import Material
from app.services.file_service import assert_inside_storage, course_storage_dir


GENERATED_MATERIAL_TITLE = "Dispensa didattica generata"


@dataclass(frozen=True)
class TeachingMaterialResult:
    generated: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def generate_teaching_materials(
    db: Session,
    course_id: int | None = None,
    overwrite: bool = True,
    dry_run: bool = False,
) -> TeachingMaterialResult:
    stmt = select(Course).order_by(Course.title.asc())
    if course_id:
        stmt = stmt.where(Course.id == course_id)
    courses = list(db.scalars(stmt).all())

    generated = 0
    updated = 0
    skipped = 0
    errors: list[str] = []

    for course in courses:
        existing = _existing_generated_material(db, course.id)
        if existing and not overwrite:
            skipped += 1
            continue

        if existing:
            updated += 1
        else:
            generated += 1

        if dry_run:
            continue

        destination = _material_destination(course)
        _render_course_pdf(course, destination)
        size = destination.stat().st_size
        original_filename = destination.name
        description = "Materiale didattico generato automaticamente per il corso."

        if existing:
            old_path = Path(existing.stored_path)
            if old_path != destination and old_path.exists():
                old_path.unlink()
            existing.description = description
            existing.original_filename = original_filename
            existing.stored_filename = destination.name
            existing.stored_path = str(destination)
            existing.size_bytes = size
            existing.uploaded_at = _utcnow()
            db.add(existing)
        else:
            db.add(
                Material(
                    course_id=course.id,
                    title=GENERATED_MATERIAL_TITLE,
                    description=description,
                    original_filename=original_filename,
                    stored_filename=destination.name,
                    stored_path=str(destination),
                    size_bytes=size,
                )
            )

    if dry_run:
        db.rollback()
    else:
        db.commit()

    return TeachingMaterialResult(generated=generated, updated=updated, skipped=skipped, errors=errors)


def _existing_generated_material(db: Session, course_id: int) -> Material | None:
    return db.scalar(
        select(Material).where(
            Material.course_id == course_id,
            Material.title == GENERATED_MATERIAL_TITLE,
        )
    )


def _material_destination(course: Course) -> Path:
    filename = f"dispensa-{course.id}-{_slugify(course.title)}.pdf"
    return assert_inside_storage(course_storage_dir(course.id) / filename)


def _render_course_pdf(course: Course, destination: Path) -> None:
    pdf = canvas.Canvas(str(destination), pagesize=A4)
    width, height = A4
    margin = 54
    y = height - margin

    def heading(text: str, size: int = 16) -> None:
        nonlocal y
        y = _ensure_space(pdf, y, 48, height, margin)
        pdf.setFont("Helvetica-Bold", size)
        pdf.drawString(margin, y, text)
        y -= size + 12

    def paragraph(text: str, size: int = 10, gap: int = 10) -> None:
        nonlocal y
        pdf.setFont("Helvetica", size)
        for line in _wrap_text(text, 92):
            y = _ensure_space(pdf, y, 24, height, margin)
            pdf.drawString(margin, y, line)
            y -= size + 5
        y -= gap

    def bullet(text: str) -> None:
        nonlocal y
        pdf.setFont("Helvetica", 10)
        for index, line in enumerate(_wrap_text(text, 88)):
            y = _ensure_space(pdf, y, 24, height, margin)
            prefix = "- " if index == 0 else "  "
            pdf.drawString(margin, y, f"{prefix}{line}")
            y -= 15

    pdf.setTitle(f"Dispensa didattica - {course.title}")
    heading(f"Dispensa didattica - {course.title}", 18)
    paragraph(f"Durata: {course.duration or 'non specificata'} | Stato: {course.status.value}")
    if course.short_description:
        paragraph(course.short_description)

    heading("Obiettivi formativi", 14)
    for item in _learning_goals(course.title):
        bullet(item)

    heading("Programma suggerito", 14)
    for item in _course_topics(course.title):
        bullet(item)

    heading("Attività pratiche", 14)
    for item in [
        "Esercitazioni guidate con revisione collettiva dei passaggi chiave.",
        "Laboratorio individuale o a coppie con consegna di un elaborato finale.",
        "Discussione dei casi reali emersi durante il percorso formativo.",
    ]:
        bullet(item)

    heading("Verifica finale", 14)
    for item in [
        "Questionario di riepilogo sui concetti principali.",
        "Mini project work o simulazione operativa coerente con il corso.",
        "Feedback finale su competenze acquisite e prossimi passi consigliati.",
    ]:
        bullet(item)

    participants = _participant_names(course)
    if participants:
        heading("Iscritti collegati", 14)
        paragraph(", ".join(participants[:45]) + ("..." if len(participants) > 45 else ""))

    calendar_values = _calendar_values(course)
    if calendar_values:
        heading("Indicazioni calendario", 14)
        paragraph(", ".join(calendar_values))

    pdf.setFont("Helvetica-Oblique", 8)
    pdf.drawString(margin, 32, f"Generato automaticamente il {_utcnow().strftime('%d/%m/%Y %H:%M')}")
    pdf.save()


def _learning_goals(title: str) -> list[str]:
    return [
        f"Comprendere i concetti fondamentali collegati al corso {title}.",
        "Applicare le nozioni apprese in esercitazioni pratiche e casi realistici.",
        "Consolidare un metodo operativo replicabile nel contesto lavorativo.",
    ]


def _course_topics(title: str) -> list[str]:
    normalized = title.lower()
    if "flutter" in normalized:
        return [
            "Introduzione a Flutter, Dart e struttura di un progetto mobile.",
            "Widget, layout responsive e gestione dello stato.",
            "Integrazione API, persistenza locale e build dell'applicazione.",
        ]
    if "full" in normalized and "stack" in normalized:
        return [
            "Fondamenti frontend: HTML, CSS, JavaScript e componenti UI.",
            "Backend, API, database e gestione dell'autenticazione.",
            "Project work full-stack con deploy e revisione finale.",
        ]
    if "microsoft" in normalized:
        return [
            "Panoramica strumenti Microsoft e scenari d'uso aziendali.",
            "Collaborazione, produttività e automazione dei flussi operativi.",
            "Esercitazioni su casi pratici e configurazioni ricorrenti.",
        ]
    if "salesforce" in normalized:
        return [
            "Concetti CRM, oggetti, record e processi Salesforce.",
            "Configurazione base, automazioni e tracciamento attività.",
            "Esercitazioni su pipeline, report e casi cliente.",
        ]
    if "ai" in normalized:
        return [
            "Fondamenti di intelligenza artificiale e casi d'uso applicativi.",
            "Prompting, valutazione output e limiti operativi.",
            "Laboratorio con scenari reali e controllo qualità dei risultati.",
        ]
    if "mkt" in normalized or "marketing" in normalized:
        return [
            "Fondamenti di marketing automation e customer journey.",
            "Segmentazione, contenuti, campagne e metriche di performance.",
            "Esercitazioni su flussi, audience e reportistica.",
        ]
    return [
        "Introduzione al contesto, lessico e obiettivi del percorso.",
        "Approfondimento guidato dei concetti principali.",
        "Esercitazioni applicative e verifica finale delle competenze.",
    ]


def _participant_names(course: Course) -> list[str]:
    names = []
    for enrollment in course.enrollments:
        if enrollment.student:
            names.append(f"{enrollment.student.last_name} {enrollment.student.first_name}")
    return sorted(names)


def _calendar_values(course: Course) -> list[str]:
    values: set[str] = set()
    for enrollment in course.enrollments:
        marker = "Valori calendario:"
        if marker not in enrollment.notes:
            continue
        details = enrollment.notes.split(marker, 1)[1].strip().rstrip(".")
        for item in details.split(","):
            item = item.strip()
            if item:
                values.add(item)
    return sorted(values)


def _ensure_space(pdf: canvas.Canvas, y: float, needed: int, height: float, margin: int) -> float:
    if y - needed > margin:
        return y
    pdf.showPage()
    return height - margin


def _wrap_text(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if len(candidate) > width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines or [""]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "corso"


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
