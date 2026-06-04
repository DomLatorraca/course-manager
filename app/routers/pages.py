from __future__ import annotations

from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.material import Material
from app.models.student import Student
from app.models.user import User, UserRole
from app.routers.dependencies import current_user_or_none
from app.schemas.course import CourseCreate, CourseUpdate
from app.schemas.enrollment import EnrollmentCreate, EnrollmentUpdate
from app.schemas.student import StudentCreate, StudentUpdate
from app.services import course_service, enrollment_service, excel_course_service, student_service
from app.services.auth_service import change_password, create_user
from app.services.excel_course_service import ExcelCourseError, ExcelCoursePayload
from app.services.export_service import export_courses_csv, export_enrollments_csv, export_students_csv
from app.services.file_service import delete_material, get_material_path, save_material
from app.services.import_service import import_enrollments_csv, import_students_csv


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def render(request: Request, template: str, context: dict[str, object] | None = None):
    base = {
        "request": request,
        "current_user": getattr(request.state, "current_user", None),
        "error": request.query_params.get("error"),
        "success": request.query_params.get("success"),
    }
    if context:
        base.update(context)
    return templates.TemplateResponse(request,template, base)


def redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=status.HTTP_303_SEE_OTHER)


def quote_message(message: str) -> str:
    return quote_plus(message)


def require_page_user(request: Request, user: User | None) -> User | RedirectResponse:
    request.state.current_user = user
    if not user:
        return redirect("/login")
    return user


def ensure_admin(user: User) -> RedirectResponse | None:
    if user.role != UserRole.admin:
        return redirect("/?error=Permessi+admin+richiesti")
    return None


@router.get("/login")
def login_page(request: Request, user: User | None = Depends(current_user_or_none)):
    request.state.current_user = user
    if user:
        return redirect("/")
    return render(request, "login.html")


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    stats = {
        "courses": db.scalar(select(func.count()).select_from(Course)) or 0,
        "students": db.scalar(select(func.count()).select_from(Student)) or 0,
        "completed": db.scalar(select(func.count()).select_from(Enrollment).where(Enrollment.status == EnrollmentStatus.completato)) or 0,
        "not_completed": db.scalar(select(func.count()).select_from(Enrollment).where(Enrollment.status == EnrollmentStatus.non_completato)) or 0,
    }
    latest_courses = db.scalars(select(Course).order_by(Course.created_at.desc()).limit(5)).all()
    latest_enrollments = db.scalars(select(Enrollment).order_by(Enrollment.updated_at.desc()).limit(6)).all()
    return render(request, "dashboard.html", {"stats": stats, "latest_courses": latest_courses, "latest_enrollments": latest_enrollments})


@router.get("/courses")
def courses_list(request: Request, q: str = "", category: str = "", status_filter: str = "", db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    courses = course_service.list_courses(db, q=q, category=category, status=status_filter)
    return render(request, "courses_list.html", {"courses": courses, "q": q, "category": category, "status_filter": status_filter})


@router.get("/courses/new")
def course_new(request: Request, user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    return render(request, "course_form.html", {"course": None, "action": "/courses/new"})


@router.post("/courses/new")
def course_create(
    request: Request,
    title: str = Form(...),
    short_description: str = Form(""),
    category: str = Form(""),
    duration: str = Form(""),
    status_value: str = Form("attivo", alias="status"),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user_or_none),
):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    course = course_service.create_course(db, CourseCreate(title=title, short_description=short_description, category=category, duration=duration, status=status_value))
    return redirect(f"/courses/{course.id}?success=Corso+creato")


@router.get("/courses/{course_id}")
def course_detail(request: Request, course_id: int, status_filter: str = "", db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    course = course_service.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Corso non trovato.")
    enrollments = enrollment_service.list_enrollments(db, course_id=course_id, status=status_filter)
    all_course_enrollments = enrollment_service.list_enrollments(db, course_id=course_id)
    enrolled_student_ids = {e.student_id for e in all_course_enrollments}
    students = [student for student in student_service.list_students(db) if student.id not in enrolled_student_ids]
    return render(request, "course_detail.html", {"course": course, "enrollments": enrollments, "students": students, "status_filter": status_filter})


@router.get("/courses/{course_id}/edit")
def course_edit(request: Request, course_id: int, db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    course = course_service.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Corso non trovato.")
    return render(request, "course_form.html", {"course": course, "action": f"/courses/{course.id}/edit"})


@router.post("/courses/{course_id}/edit")
def course_update(
    request: Request,
    course_id: int,
    title: str = Form(...),
    short_description: str = Form(""),
    category: str = Form(""),
    duration: str = Form(""),
    status_value: str = Form("attivo", alias="status"),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user_or_none),
):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    course = course_service.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Corso non trovato.")
    course_service.update_course(db, course, CourseUpdate(title=title, short_description=short_description, category=category, duration=duration, status=status_value))
    return redirect(f"/courses/{course.id}?success=Corso+aggiornato")


@router.post("/courses/{course_id}/archive")
def course_archive(request: Request, course_id: int, db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    course = course_service.get_course(db, course_id)
    if course:
        course_service.archive_course(db, course)
    return redirect("/courses?success=Corso+archiviato")


@router.post("/courses/{course_id}/delete")
def course_delete(request: Request, course_id: int, db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    course = course_service.get_course(db, course_id)
    if not course:
        return redirect("/courses?error=Corso+non+trovato")
    try:
        course_service.delete_course(db, course)
        return redirect("/courses?success=Corso+eliminato")
    except ValueError as exc:
        return redirect(f"/courses/{course_id}?error={str(exc).replace(' ', '+')}")


@router.get("/excel-courses")
def excel_courses_list(request: Request, q: str = "", category: str = "", status_filter: str = "", user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    try:
        courses = excel_course_service.list_excel_courses(q=q, category=category, status=status_filter)
        return render(
            request,
            "excel_courses_list.html",
            {
                "courses": courses,
                "q": q,
                "category": category,
                "status_filter": status_filter,
                "workbook_path": excel_course_service.get_excel_path(),
                "sheet_name": excel_course_service.get_sheet_name(),
            },
        )
    except ExcelCourseError as exc:
        return render(
            request,
            "excel_courses_list.html",
            {
                "courses": [],
                "q": q,
                "category": category,
                "status_filter": status_filter,
                "workbook_path": excel_course_service.get_excel_path(),
                "sheet_name": excel_course_service.get_sheet_name(),
                "error": str(exc),
            },
        )


@router.get("/excel-courses/new")
def excel_course_new(request: Request, user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    return render(
        request,
        "excel_course_form.html",
        {"course": None, "action": "/excel-courses/new", "workbook_path": excel_course_service.get_excel_path()},
    )


@router.post("/excel-courses/new")
def excel_course_create(
    request: Request,
    title: str = Form(...),
    short_description: str = Form(""),
    category: str = Form(""),
    duration: str = Form(""),
    status_value: str = Form("attivo", alias="status"),
    user: User | None = Depends(current_user_or_none),
):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    try:
        excel_course_service.create_excel_course(
            ExcelCoursePayload(
                title=title,
                short_description=short_description,
                category=category,
                duration=duration,
                status=status_value,
            )
        )
        return redirect("/excel-courses?success=Corso+inserito+nel+file+Excel")
    except ExcelCourseError as exc:
        return redirect(f"/excel-courses/new?error={quote_message(str(exc))}")


@router.get("/excel-courses/{course_id}/edit")
def excel_course_edit(request: Request, course_id: int, user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    course = excel_course_service.get_excel_course(course_id)
    if not course:
        return redirect("/excel-courses?error=Corso+Excel+non+trovato")
    return render(
        request,
        "excel_course_form.html",
        {"course": course, "action": f"/excel-courses/{course.id}/edit", "workbook_path": excel_course_service.get_excel_path()},
    )


@router.post("/excel-courses/{course_id}/edit")
def excel_course_update(
    request: Request,
    course_id: int,
    title: str = Form(...),
    short_description: str = Form(""),
    category: str = Form(""),
    duration: str = Form(""),
    status_value: str = Form("attivo", alias="status"),
    user: User | None = Depends(current_user_or_none),
):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    try:
        excel_course_service.update_excel_course(
            course_id,
            ExcelCoursePayload(
                title=title,
                short_description=short_description,
                category=category,
                duration=duration,
                status=status_value,
            ),
        )
        return redirect("/excel-courses?success=Corso+Excel+aggiornato")
    except ExcelCourseError as exc:
        return redirect(f"/excel-courses/{course_id}/edit?error={quote_message(str(exc))}")


@router.post("/excel-courses/{course_id}/archive")
def excel_course_archive(request: Request, course_id: int, user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    try:
        excel_course_service.archive_excel_course(course_id)
        return redirect("/excel-courses?success=Corso+Excel+archiviato")
    except ExcelCourseError as exc:
        return redirect(f"/excel-courses?error={quote_message(str(exc))}")


@router.post("/excel-courses/{course_id}/delete")
def excel_course_delete(request: Request, course_id: int, user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    try:
        excel_course_service.delete_excel_course(course_id)
        return redirect("/excel-courses?success=Corso+Excel+eliminato")
    except ExcelCourseError as exc:
        return redirect(f"/excel-courses?error={quote_message(str(exc))}")


@router.post("/courses/{course_id}/materials")
def material_upload(
    request: Request,
    course_id: int,
    title: str = Form(""),
    description: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user_or_none),
):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    course = course_service.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Corso non trovato.")
    try:
        save_material(db, course, file, title, description)
        return redirect(f"/courses/{course_id}?success=Materiale+caricato")
    except ValueError as exc:
        return redirect(f"/courses/{course_id}?error={str(exc).replace(' ', '+')}")


@router.get("/materials/{material_id}/download")
def material_download(material_id: int, db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    if not user:
        return redirect("/login")
    material = db.get(Material, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Materiale non trovato.")
    path = get_material_path(material)
    return FileResponse(path, filename=material.original_filename)


@router.post("/materials/{material_id}/delete")
def material_delete(request: Request, material_id: int, db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    material = db.get(Material, material_id)
    if not material:
        return redirect("/courses?error=Materiale+non+trovato")
    course_id = material.course_id
    delete_material(db, material)
    return redirect(f"/courses/{course_id}?success=Materiale+eliminato")


@router.post("/courses/{course_id}/enrollments")
def course_enroll_student(request: Request, course_id: int, student_id: int = Form(...), db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    try:
        enrollment_service.create_enrollment(db, EnrollmentCreate(course_id=course_id, student_id=student_id))
        return redirect(f"/courses/{course_id}?success=Iscrizione+creata")
    except ValueError as exc:
        return redirect(f"/courses/{course_id}?error={str(exc).replace(' ', '+')}")


@router.post("/enrollments/{enrollment_id}/status")
def enrollment_update_status(
    request: Request,
    enrollment_id: int,
    status_value: str = Form(..., alias="status"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user_or_none),
):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    enrollment = enrollment_service.get_enrollment(db, enrollment_id)
    if not enrollment:
        return redirect("/courses?error=Iscrizione+non+trovata")
    enrollment_service.update_enrollment(db, enrollment, EnrollmentUpdate(status=status_value, notes=notes))
    return redirect(f"/courses/{enrollment.course_id}?success=Stato+aggiornato")


@router.post("/enrollments/{enrollment_id}/delete")
def enrollment_delete(request: Request, enrollment_id: int, db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    enrollment = enrollment_service.get_enrollment(db, enrollment_id)
    if not enrollment:
        return redirect("/courses?error=Iscrizione+non+trovata")
    course_id = enrollment.course_id
    enrollment_service.delete_enrollment(db, enrollment)
    return redirect(f"/courses/{course_id}?success=Iscrizione+rimossa")


@router.get("/students")
def students_list(request: Request, q: str = "", db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    return render(request, "students_list.html", {"students": student_service.list_students(db, q=q), "q": q})


@router.get("/students/new")
def student_new(request: Request, user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    return render(request, "student_form.html", {"student": None, "action": "/students/new"})


@router.post("/students/new")
def student_create(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    organization: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user_or_none),
):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    try:
        student = student_service.create_student(db, StudentCreate(first_name=first_name, last_name=last_name, email=email, phone=phone, organization=organization, notes=notes))
        return redirect(f"/students/{student.id}?success=Iscritto+creato")
    except ValueError as exc:
        return redirect(f"/students/new?error={str(exc).replace(' ', '+')}")


@router.get("/students/{student_id}")
def student_detail(request: Request, student_id: int, db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    student = student_service.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Iscritto non trovato.")
    enrollments = enrollment_service.list_enrollments(db, student_id=student_id)
    return render(request, "student_detail.html", {"student": student, "enrollments": enrollments})


@router.get("/students/{student_id}/edit")
def student_edit(request: Request, student_id: int, db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    student = student_service.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Iscritto non trovato.")
    return render(request, "student_form.html", {"student": student, "action": f"/students/{student.id}/edit"})


@router.post("/students/{student_id}/edit")
def student_update(
    request: Request,
    student_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    organization: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user_or_none),
):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    student = student_service.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Iscritto non trovato.")
    try:
        student_service.update_student(db, student, StudentUpdate(first_name=first_name, last_name=last_name, email=email, phone=phone, organization=organization, notes=notes))
        return redirect(f"/students/{student_id}?success=Iscritto+aggiornato")
    except ValueError as exc:
        return redirect(f"/students/{student_id}/edit?error={str(exc).replace(' ', '+')}")


@router.post("/students/{student_id}/delete")
def student_delete(request: Request, student_id: int, db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    student = student_service.get_student(db, student_id)
    if not student:
        return redirect("/students?error=Iscritto+non+trovato")
    try:
        student_service.delete_student(db, student)
        return redirect("/students?success=Iscritto+eliminato")
    except ValueError as exc:
        return redirect(f"/students/{student_id}?error={str(exc).replace(' ', '+')}")


@router.get("/import-export")
def import_export_page(request: Request, user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    return render(request, "import_export.html")


@router.get("/export/{kind}.csv")
def export_csv(kind: str, db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    if not user:
        return redirect("/login")
    exporters = {
        "courses": export_courses_csv,
        "students": export_students_csv,
        "enrollments": export_enrollments_csv,
    }
    if kind not in exporters:
        raise HTTPException(status_code=404, detail="Export non trovato.")
    return Response(exporters[kind](db), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'})


@router.post("/import/students")
def import_students(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    result = import_students_csv(db, file.file.read())
    return render(request, "import_export.html", {"result": result, "import_type": "iscritti"})


@router.post("/import/enrollments")
def import_enrollments(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    result = import_enrollments_csv(db, file.file.read())
    return render(request, "import_export.html", {"result": result, "import_type": "iscrizioni"})


@router.get("/users")
def users_page(request: Request, db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    users = db.scalars(select(User).order_by(User.username)).all()
    return render(request, "users.html", {"users": users, "roles": UserRole})


@router.post("/users")
def users_create(request: Request, username: str = Form(...), password: str = Form(...), role: str = Form("viewer"), db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    try:
        create_user(db, username, password, UserRole(role))
        return redirect("/users?success=Utente+creato")
    except ValueError as exc:
        return redirect(f"/users?error={str(exc).replace(' ', '+')}")


@router.post("/users/{user_id}/password")
def users_change_password(request: Request, user_id: int, password: str = Form(...), db: Session = Depends(get_db), user: User | None = Depends(current_user_or_none)):
    current = require_page_user(request, user)
    if isinstance(current, RedirectResponse):
        return current
    if response := ensure_admin(current):
        return response
    target = db.get(User, user_id)
    if not target:
        return redirect("/users?error=Utente+non+trovato")
    if len(password) < 8:
        return redirect("/users?error=Password+minimo+8+caratteri")
    change_password(db, target, password)
    return redirect("/users?success=Password+aggiornata")
