from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.dependencies import get_current_user, require_admin
from app.schemas.student import StudentCreate, StudentRead, StudentUpdate
from app.services import student_service


router = APIRouter(prefix="/api/students", tags=["api-students"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[StudentRead])
def api_list_students(q: str = "", db: Session = Depends(get_db)):
    return student_service.list_students(db, q=q)


@router.post("", response_model=StudentRead, dependencies=[Depends(require_admin)])
def api_create_student(data: StudentCreate, db: Session = Depends(get_db)):
    try:
        return student_service.create_student(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{student_id}", response_model=StudentRead)
def api_get_student(student_id: int, db: Session = Depends(get_db)):
    student = student_service.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Iscritto non trovato.")
    return student


@router.put("/{student_id}", response_model=StudentRead, dependencies=[Depends(require_admin)])
def api_update_student(student_id: int, data: StudentUpdate, db: Session = Depends(get_db)):
    student = student_service.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Iscritto non trovato.")
    try:
        return student_service.update_student(db, student, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
def api_delete_student(student_id: int, db: Session = Depends(get_db)):
    student = student_service.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Iscritto non trovato.")
    try:
        student_service.delete_student(db, student)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

