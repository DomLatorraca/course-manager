from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.dependencies import get_current_user, require_admin
from app.schemas.course import CourseCreate, CourseRead, CourseUpdate
from app.services import course_service


router = APIRouter(prefix="/api/courses", tags=["api-courses"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[CourseRead])
def api_list_courses(q: str = "", category: str = "", status_filter: str = Query("", alias="status"), db: Session = Depends(get_db)):
    return course_service.list_courses(db, q=q, category=category, status=status_filter)


@router.post("", response_model=CourseRead, dependencies=[Depends(require_admin)])
def api_create_course(data: CourseCreate, db: Session = Depends(get_db)):
    return course_service.create_course(db, data)


@router.get("/{course_id}", response_model=CourseRead)
def api_get_course(course_id: int, db: Session = Depends(get_db)):
    course = course_service.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Corso non trovato.")
    return course


@router.put("/{course_id}", response_model=CourseRead, dependencies=[Depends(require_admin)])
def api_update_course(course_id: int, data: CourseUpdate, db: Session = Depends(get_db)):
    course = course_service.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Corso non trovato.")
    return course_service.update_course(db, course, data)


@router.post("/{course_id}/archive", response_model=CourseRead, dependencies=[Depends(require_admin)])
def api_archive_course(course_id: int, db: Session = Depends(get_db)):
    course = course_service.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Corso non trovato.")
    return course_service.archive_course(db, course)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
def api_delete_course(course_id: int, db: Session = Depends(get_db)):
    course = course_service.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Corso non trovato.")
    try:
        course_service.delete_course(db, course)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

