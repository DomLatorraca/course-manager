from __future__ import annotations

import pytest

from app.schemas.course import CourseCreate
from app.schemas.enrollment import EnrollmentCreate
from app.schemas.student import StudentCreate
from app.services.course_service import create_course
from app.services.enrollment_service import create_enrollment
from app.models.student import Student
from app.services.student_service import create_student, delete_student, normalize_all_student_email_domains


def test_student_email_is_unique(db):
    create_student(db, StudentCreate(first_name="Luca", last_name="Bianchi", email="luca@example.com"))
    with pytest.raises(ValueError, match="Email già presente"):
        create_student(db, StudentCreate(first_name="Luca", last_name="Verdi", email="luca@example.com"))


def test_student_email_domain_is_normalized(db):
    student = create_student(db, StudentCreate(first_name="Luca", last_name="Bianchi", email="luca@example.com"))

    assert student.email == "luca@digitaltrainingacademy.it"


def test_existing_student_email_domains_are_normalized(db):
    db.add_all(
        [
            Student(first_name="A", last_name="Rossi", email="a@example.com"),
            Student(first_name="A", last_name="Verdi", email="a@course-manager.invalid"),
        ]
    )
    db.commit()

    result = normalize_all_student_email_domains(db)

    students = db.query(Student).order_by(Student.id).all()
    assert result.updated == 2
    assert students[0].email == "a@digitaltrainingacademy.it"
    assert students[1].email == "a-2@digitaltrainingacademy.it"


def test_student_with_enrollments_cannot_be_deleted(db):
    course = create_course(db, CourseCreate(title="Qualità", short_description="", category="", duration=""))
    student = create_student(db, StudentCreate(first_name="Marta", last_name="Neri", email="marta@example.com"))
    create_enrollment(db, EnrollmentCreate(course_id=course.id, student_id=student.id))
    with pytest.raises(ValueError, match="iscrizioni associate"):
        delete_student(db, student)

