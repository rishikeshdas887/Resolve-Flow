"""Automated tests for the Student Management API.

Every test runs against a temporary SQLite file created in pytest's ``tmp_path`` —
the real ``students.db`` development database is never touched. The app is used
through FastAPI's TestClient with the ``get_db`` dependency overridden; the app
lifespan is not run, so ``init_db()`` never executes against the dev database.
"""

import sqlite3
from collections.abc import Iterator

import pytest
from app.database import Base, get_db
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.main import app


def make_student(student_id: str = "STU001", **overrides) -> dict:
    """A valid dummy student payload; never real personal data."""
    data = {
        "student_id": student_id,
        "full_name": "Asha Verma",
        "date_of_birth": "2004-05-12",
        "email": "asha.verma@example.com",
        "phone": "+91 98765 43210",
        "course": "Computer Science",
        "address": "12 Lake Road, Pune",
        "enrollment_date": "2024-08-01",
    }
    data.update(overrides)
    return data


@pytest.fixture()
def client(tmp_path) -> Iterator[TestClient]:
    """TestClient bound to a fresh temporary SQLite database per test."""
    db_file = tmp_path / "test_students.db"
    engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()


# --------------------------------------------------------------------------- #
# CRUD — happy paths                                                           #
# --------------------------------------------------------------------------- #


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_student(client):
    response = client.post("/students", json=make_student())
    assert response.status_code == 201
    body = response.json()
    assert body["student_id"] == "STU001"
    assert body["full_name"] == "Asha Verma"
    assert body["date_of_birth"] == "2004-05-12"


def test_list_students(client):
    client.post("/students", json=make_student("STU001"))
    client.post(
        "/students",
        json=make_student("STU002", full_name="Rahul Nair", course="Mechanical"),
    )
    response = client.get("/students")
    assert response.status_code == 200
    assert [s["student_id"] for s in response.json()] == ["STU001", "STU002"]


def test_list_students_filters_by_name_and_course(client):
    client.post("/students", json=make_student("STU001"))
    client.post(
        "/students",
        json=make_student("STU002", full_name="Rahul Nair", course="Mechanical"),
    )
    by_name = client.get("/students", params={"name": "rahul"})
    assert [s["student_id"] for s in by_name.json()] == ["STU002"]
    by_course = client.get("/students", params={"course": "computer"})
    assert [s["student_id"] for s in by_course.json()] == ["STU001"]
    no_match = client.get("/students", params={"name": "nobody"})
    assert no_match.status_code == 200
    assert no_match.json() == []


def test_get_student(client):
    client.post("/students", json=make_student())
    response = client.get("/students/STU001")
    assert response.status_code == 200
    assert response.json()["full_name"] == "Asha Verma"


def test_update_student_put(client):
    client.post("/students", json=make_student())
    update = make_student()
    update.pop("student_id")
    update["full_name"] = "Asha Verma-Rao"
    update["course"] = "Data Science"
    response = client.put("/students/STU001", json=update)
    assert response.status_code == 200
    assert response.json()["full_name"] == "Asha Verma-Rao"
    assert response.json()["course"] == "Data Science"


def test_patch_student(client):
    client.post("/students", json=make_student())
    response = client.patch("/students/STU001", json={"course": "Physics"})
    assert response.status_code == 200
    assert response.json()["course"] == "Physics"
    assert response.json()["full_name"] == "Asha Verma"  # untouched


def test_delete_student(client):
    client.post("/students", json=make_student())
    response = client.delete("/students/STU001")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get("/students/STU001").status_code == 404


# --------------------------------------------------------------------------- #
# 404s and duplicates                                                          #
# --------------------------------------------------------------------------- #


def test_get_nonexistent_student(client):
    assert client.get("/students/NOPE").status_code == 404


def test_update_nonexistent_student(client):
    update = make_student()
    update.pop("student_id")
    assert client.put("/students/NOPE", json=update).status_code == 404
    assert client.patch("/students/NOPE", json={"course": "X"}).status_code == 404


def test_delete_nonexistent_student(client):
    assert client.delete("/students/NOPE").status_code == 404


def test_duplicate_student_id_returns_409(client):
    assert client.post("/students", json=make_student()).status_code == 201
    assert client.post("/students", json=make_student()).status_code == 409


# --------------------------------------------------------------------------- #
# Validation                                                                   #
# --------------------------------------------------------------------------- #


def test_missing_required_fields_rejected(client):
    payload = make_student()
    del payload["full_name"]
    assert client.post("/students", json=payload).status_code == 422

    payload = make_student()
    del payload["date_of_birth"]
    assert client.post("/students", json=payload).status_code == 422

    payload = make_student()
    del payload["student_id"]
    assert client.post("/students", json=payload).status_code == 422


def test_invalid_dates_rejected(client):
    assert (
        client.post("/students", json=make_student(date_of_birth="not-a-date")).status_code
        == 422
    )
    assert (
        client.post("/students", json=make_student(date_of_birth="2004-13-40")).status_code
        == 422
    )
    assert (
        client.post("/students", json=make_student(date_of_birth="2999-01-01")).status_code
        == 422
    )


def test_invalid_email_rejected(client):
    assert (
        client.post("/students", json=make_student(email="not-an-email")).status_code == 422
    )


def test_missing_both_email_and_phone_rejected(client):
    assert (
        client.post(
            "/students", json=make_student(email=None, phone=None)
        ).status_code
        == 422
    )


def test_either_email_or_phone_is_enough(client):
    assert client.post("/students", json=make_student(email=None)).status_code == 201
    assert (
        client.post("/students", json=make_student("STU002", phone=None)).status_code == 201
    )


def test_patch_cannot_remove_last_contact(client):
    client.post("/students", json=make_student(phone=None))  # email only
    response = client.patch("/students/STU001", json={"email": None})
    assert response.status_code == 422
    # Nothing was changed by the rejected patch.
    assert client.get("/students/STU001").json()["email"] == "asha.verma@example.com"


def test_enrollment_before_birth_rejected(client):
    assert (
        client.post(
            "/students", json=make_student(enrollment_date="2000-01-01")
        ).status_code
        == 422
    )


# --------------------------------------------------------------------------- #
# Persistence                                                                  #
# --------------------------------------------------------------------------- #


def test_data_persists_across_sessions(client, tmp_path):
    """A new engine/session on the same file sees committed data — as would a
    completely restarted application process."""
    client.post("/students", json=make_student())
    db_file = tmp_path / "test_students.db"

    # Read the raw SQLite file directly, independent of SQLAlchemy/FastAPI.
    with sqlite3.connect(db_file) as conn:
        rows = conn.execute(
            "SELECT student_id, full_name FROM students"
        ).fetchall()
    assert ("STU001", "Asha Verma") in rows

    # A second, independent engine + session sees the same record.
    engine2 = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    Session2 = sessionmaker(bind=engine2)
    with Session2() as db:
        count = db.execute(text("SELECT COUNT(*) FROM students")).scalar()
    assert count == 1
    engine2.dispose()
