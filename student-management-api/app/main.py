"""FastAPI application: routes, HTTP error handling, and the health check.

Endpoints
---------
POST   /students                create a student                -> 201 / 409 / 422
GET    /students                list students (name/course)     -> 200
GET    /students/{student_id}   fetch one student               -> 200 / 404
PUT    /students/{student_id}   replace a student               -> 200 / 404 / 422
PATCH  /students/{student_id}   partially update a student      -> 200 / 404 / 422
DELETE /students/{student_id}   delete a student                -> 204 / 404
GET    /health                  liveness + database check       -> 200 / 503
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.models import Student
from app.schemas import StudentBase, StudentCreate, StudentOut, StudentPatch

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Create missing tables on startup. Existing data is never dropped."""
    init_db()
    yield


app = FastAPI(
    title="EWB Student Management API",
    description=(
        "CRUD API for managing student records, backed by SQLite via SQLAlchemy. "
        "Built for the EWB Edu Tech internship assignment."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


@app.get(
    "/health",
    summary="Application and database health check",
    responses={503: {"description": "Database unreachable"}},
)
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    """Return `{"status": "ok"}` when the app and its database are reachable."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.exception("Health check failed: database unreachable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from exc
    return {"status": "ok", "database": "connected"}


@app.post(
    "/students",
    status_code=status.HTTP_201_CREATED,
    response_model=StudentOut,
    summary="Create a new student",
    responses={409: {"description": "student_id already exists"}},
)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)) -> Student:
    """Create a student. `student_id` must be unique; duplicates return 409."""
    if db.get(Student, payload.student_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"student_id '{payload.student_id}' already exists",
        )
    student = Student(**payload.model_dump())
    db.add(student)
    try:
        db.commit()
    except IntegrityError as exc:  # race-safe backstop for the pre-check above
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"student_id '{payload.student_id}' already exists",
        ) from exc
    db.refresh(student)
    return student


@app.get(
    "/students",
    response_model=list[StudentOut],
    summary="List students",
)
def list_students(
    db: Session = Depends(get_db),
    name: str | None = Query(default=None, description="Case-insensitive substring of full_name"),
    course: str | None = Query(default=None, description="Case-insensitive substring of course"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[Student]:
    """List students, optionally filtered by `name` and/or `course` substrings."""
    query = db.query(Student)
    if name:
        query = query.filter(Student.full_name.ilike(f"%{name}%"))
    if course:
        query = query.filter(Student.course.ilike(f"%{course}%"))
    return query.order_by(Student.student_id).offset(skip).limit(limit).all()


@app.get(
    "/students/{student_id}",
    response_model=StudentOut,
    summary="Retrieve one student",
    responses={404: {"description": "Student not found"}},
)
def get_student(student_id: str, db: Session = Depends(get_db)) -> Student:
    """Fetch a single student by `student_id`; 404 if it does not exist."""
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"student '{student_id}' not found",
        )
    return student


@app.put(
    "/students/{student_id}",
    response_model=StudentOut,
    summary="Replace a student",
    responses={404: {"description": "Student not found"}},
)
def replace_student(
    student_id: str,
    payload: StudentBase,
    db: Session = Depends(get_db),
) -> Student:
    """Replace every field of an existing student (full update).

    `student_id` itself cannot be changed. All required fields must be sent.
    """
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"student '{student_id}' not found",
        )
    for field, value in payload.model_dump().items():
        setattr(student, field, value)
    db.commit()
    db.refresh(student)
    return student


@app.patch(
    "/students/{student_id}",
    response_model=StudentOut,
    summary="Partially update a student",
    responses={404: {"description": "Student not found"}},
)
def patch_student(
    student_id: str,
    payload: StudentPatch,
    db: Session = Depends(get_db),
) -> Student:
    """Update only the supplied fields of an existing student.

    The merged record must still satisfy all validation rules (e.g. at least
    one contact method); otherwise 422 is returned and nothing is changed.
    """
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"student '{student_id}' not found",
        )
    merged = StudentOut.model_validate(student).model_dump(mode="python")
    merged.update(payload.model_dump(exclude_unset=True))
    try:
        validated = StudentBase.model_validate(merged)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    for field, value in validated.model_dump().items():
        setattr(student, field, value)
    db.commit()
    db.refresh(student)
    return student


@app.delete(
    "/students/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a student",
    responses={404: {"description": "Student not found"}},
)
def delete_student(student_id: str, db: Session = Depends(get_db)) -> Response:
    """Delete a student; 404 if it does not exist. Returns an empty body."""
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"student '{student_id}' not found",
        )
    db.delete(student)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
