# EWB Student Management API

A small, production-shaped CRUD REST API for managing student records, built for the **EWB Edu Tech internship assignment**.

## Objective

Demonstrate a complete, reliable backend service: create, read, update, and delete student records with proper validation, persistent SQLite storage, automated tests, and documentation that lets a reviewer run everything in minutes.

## Features

- Full CRUD for student records (POST/GET/PUT/PATCH/DELETE).
- Server-side validation for names, dates, email addresses, and phone numbers.
- At-least-one-contact rule: every student must have an email **or** a phone number.
- Duplicate `student_id` detection with HTTP `409`.
- Name/course substring filtering, plus `skip`/`limit` pagination on the list endpoint.
- Persistent SQLite storage that survives server restarts.
- Health check that also verifies database connectivity.
- Auto-generated interactive API docs (Swagger UI + OpenAPI).

## Technology Stack

- Python 3.10+
- FastAPI (web framework)
- SQLAlchemy 2.x (ORM)
- SQLite (persistent storage)
- Pydantic 2.x (request/response validation)
- pytest + FastAPI TestClient (automated testing)
- Uvicorn (ASGI server)

## Project Structure

```
student-management-api/
    app/
        __init__.py
        main.py        # FastAPI app, routes, HTTP error handling
        database.py    # SQLite engine, session factory, get_db dependency
        models.py      # SQLAlchemy Student model
        schemas.py     # Pydantic request/response schemas + validators
    tests/
        test_students.py
    pytest.ini         # keeps `pytest -q` scoped to this suite
    .gitignore
    requirements.txt
    README.md
```

## Prerequisites

- Python 3.10 or newer (`python3 --version`)
- `pip` and the `venv` module

## Setup

### 1. Create a virtual environment

```bash
cd student-management-api
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the server

```bash
uvicorn app.main:app --reload
```

The API listens on `http://127.0.0.1:8000` by default. Tables are created automatically on startup — no migration step needed.

- **Swagger UI (interactive docs):** <http://127.0.0.1:8000/docs>
- **OpenAPI schema:** <http://127.0.0.1:8000/openapi.json>

## API Endpoints

| Method | Path                      | Description                              | Success | Errors        |
|--------|---------------------------|------------------------------------------|---------|---------------|
| POST   | `/students`               | Create a student                         | 201     | 409, 422      |
| GET    | `/students`               | List students (`?name=`, `?course=`, `?skip=`, `?limit=`) | 200 | —       |
| GET    | `/students/{student_id}`  | Retrieve one student                     | 200     | 404           |
| PUT    | `/students/{student_id}`  | Replace all fields of a student          | 200     | 404, 422      |
| PATCH  | `/students/{student_id}`  | Update only the supplied fields          | 200     | 404, 422      |
| DELETE | `/students/{student_id}`  | Delete a student                         | 204     | 404           |
| GET    | `/health`                 | App + database health                    | 200     | 503           |

## Example Student JSON

```json
{
  "student_id": "STU001",
  "full_name": "Asha Verma",
  "date_of_birth": "2004-05-12",
  "email": "asha.verma@example.com",
  "phone": "+91 98765 43210",
  "course": "Computer Science",
  "address": "12 Lake Road, Pune",
  "enrollment_date": "2024-08-01"
}
```

Required: `student_id`, `full_name`, `date_of_birth`, and **email or phone** (at least one).
Optional: `course`, `address`, `enrollment_date`.

## curl Examples

```bash
# Create
curl -X POST http://127.0.0.1:8000/students \
  -H "Content-Type: application/json" \
  -d '{"student_id":"STU001","full_name":"Asha Verma","date_of_birth":"2004-05-12","email":"asha.verma@example.com","course":"Computer Science","enrollment_date":"2024-08-01"}'

# List (with optional filters)
curl "http://127.0.0.1:8000/students"
curl "http://127.0.0.1:8000/students?name=asha&course=computer"

# Retrieve one
curl http://127.0.0.1:8000/students/STU001

# Replace (PUT — all required fields must be sent)
curl -X PUT http://127.0.0.1:8000/students/STU001 \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Asha Verma-Rao","date_of_birth":"2004-05-12","email":"asha.rao@example.com","course":"Data Science","enrollment_date":"2024-08-01"}'

# Partial update (PATCH)
curl -X PATCH http://127.0.0.1:8000/students/STU001 \
  -H "Content-Type: application/json" \
  -d '{"course":"Physics"}'

# Delete
curl -X DELETE http://127.0.0.1:8000/students/STU001

# Health
curl http://127.0.0.1:8000/health
```

## Validation & Error Handling

- `student_id`: 1–32 chars, letters/digits/`_`/`-` only; must be unique (`409` on conflict).
- `full_name`: 2–100 characters.
- `date_of_birth`: a real `YYYY-MM-DD` date, not in the future, on/after 1900-01-01.
- `email`: must be a syntactically valid email address (RFC-checked via `email-validator`).
- `phone`: 7–15 digits; `+ ( ) - .` and spaces allowed as separators.
- `enrollment_date`: optional, must not be earlier than `date_of_birth`.
- A record with **neither** email **nor** phone is rejected with `422` — including PATCH requests whose merge would remove the last contact method.
- Malformed payloads return FastAPI's standard `422` body: `{"detail": [{"loc": [...], "msg": ..., "type": ...}]}`.
- Unknown IDs return `404` with `{"detail": "student '<id>' not found"}`.

## Database & Persistence

- SQLite file at `student-management-api/students.db` — the path is derived from the package location, **not** the terminal's working directory.
- Override it with the `STUDENT_DATABASE_URL` environment variable, e.g. `STUDENT_DATABASE_URL="sqlite:////tmp/other.db"`.
- `init_db()` runs `CREATE TABLE IF NOT EXISTS` on startup — data is **never** dropped or reset when the app restarts.
- Requests get sessions through the `get_db` FastAPI dependency, which always closes the session; tests override it with a temporary database.
- Dates are stored as real `DATE` columns.

## Running the Tests

```bash
cd student-management-api
pytest -q        # or: python -m pytest -q
```

Expected output: **20 passed**. The suite covers every endpoint, all validation rules, duplicate/404 handling, and on-disk persistence — all against a throwaway SQLite file in pytest's `tmp_path`. The development `students.db` is never touched (the app lifespan is bypassed in tests, so `init_db()` cannot run against it).

## Known Limitations

- `student_id` is chosen by the caller (not auto-generated); PUT cannot rename it.
- List pagination returns an array only (no total-count header).
- No authentication/authorization — appropriate for a single-user internship demo, not for production exposure.
- SQLite suits this scale; concurrent multi-writer workloads would need a server database.

## Optional AI Extension

**Not implemented.** The assignment lists a natural-language query endpoint (local Ollama model) as optional; the mandatory CRUD scope was prioritized and is fully delivered and tested. The data layer is ready for it — a future `/ask` endpoint could fetch records with deterministic SQL and pass only the relevant rows to the model.
