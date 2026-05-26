from __future__ import annotations

import csv
import io

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.student import Student


def rows_to_csv(headers: list[str], rows: list[list[object]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


def export_courses_csv(db: Session) -> str:
    courses = db.scalars(select(Course).order_by(Course.id)).all()
    return rows_to_csv(
        ["id", "titolo", "descrizione_breve", "categoria", "durata", "stato", "data_creazione", "data_aggiornamento"],
        [[c.id, c.title, c.short_description, c.category, c.duration, c.status.value, c.created_at, c.updated_at] for c in courses],
    )


def export_students_csv(db: Session) -> str:
    students = db.scalars(select(Student).order_by(Student.id)).all()
    return rows_to_csv(
        ["id", "nome", "cognome", "email", "telefono", "azienda_ente", "note", "data_creazione", "data_aggiornamento"],
        [[s.id, s.first_name, s.last_name, s.email, s.phone, s.organization, s.notes, s.created_at, s.updated_at] for s in students],
    )


def export_enrollments_csv(db: Session) -> str:
    enrollments = db.scalars(select(Enrollment).order_by(Enrollment.id)).all()
    return rows_to_csv(
        ["id", "corso_id", "corso_titolo", "iscritto_id", "email_iscritto", "stato", "data_iscrizione", "data_completamento", "note", "data_aggiornamento"],
        [
            [
                e.id,
                e.course_id,
                e.course.title if e.course else "",
                e.student_id,
                e.student.email if e.student else "",
                e.status.value,
                e.enrolled_at,
                e.completed_at or "",
                e.notes,
                e.updated_at,
            ]
            for e in enrollments
        ],
    )

