from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.dependencies import get_current_user, require_admin
from app.services.export_service import export_courses_csv, export_enrollments_csv, export_students_csv
from app.services.import_service import import_enrollments_csv, import_students_csv


router = APIRouter(prefix="/api", tags=["api-import-export"], dependencies=[Depends(get_current_user)])


def csv_response(content: str, filename: str) -> Response:
    return Response(
        content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/courses.csv")
def api_export_courses(db: Session = Depends(get_db)):
    return csv_response(export_courses_csv(db), "courses.csv")


@router.get("/export/students.csv")
def api_export_students(db: Session = Depends(get_db)):
    return csv_response(export_students_csv(db), "students.csv")


@router.get("/export/enrollments.csv")
def api_export_enrollments(db: Session = Depends(get_db)):
    return csv_response(export_enrollments_csv(db), "enrollments.csv")


@router.post("/import/students", dependencies=[Depends(require_admin)])
def api_import_students(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        return import_students_csv(db, file.file.read())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/import/enrollments", dependencies=[Depends(require_admin)])
def api_import_enrollments(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        return import_enrollments_csv(db, file.file.read())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

