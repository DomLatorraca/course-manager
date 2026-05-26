from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.dependencies import get_current_user, require_admin
from app.schemas.enrollment import EnrollmentCreate, EnrollmentRead, EnrollmentUpdate
from app.services import enrollment_service


router = APIRouter(prefix="/api/enrollments", tags=["api-enrollments"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[EnrollmentRead])
def api_list_enrollments(
    course_id: int | None = None,
    student_id: int | None = None,
    status_filter: str = Query("", alias="status"),
    db: Session = Depends(get_db),
):
    return enrollment_service.list_enrollments(db, course_id=course_id, student_id=student_id, status=status_filter)


@router.post("", response_model=EnrollmentRead, dependencies=[Depends(require_admin)])
def api_create_enrollment(data: EnrollmentCreate, db: Session = Depends(get_db)):
    try:
        return enrollment_service.create_enrollment(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{enrollment_id}", response_model=EnrollmentRead, dependencies=[Depends(require_admin)])
def api_update_enrollment(enrollment_id: int, data: EnrollmentUpdate, db: Session = Depends(get_db)):
    enrollment = enrollment_service.get_enrollment(db, enrollment_id)
    if not enrollment:
        raise HTTPException(status_code=404, detail="Iscrizione non trovata.")
    return enrollment_service.update_enrollment(db, enrollment, data)


@router.delete("/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
def api_delete_enrollment(enrollment_id: int, db: Session = Depends(get_db)):
    enrollment = enrollment_service.get_enrollment(db, enrollment_id)
    if not enrollment:
        raise HTTPException(status_code=404, detail="Iscrizione non trovata.")
    enrollment_service.delete_enrollment(db, enrollment)

