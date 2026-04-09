# Task Manager API

A simple Jira-like task management backend built with **FastAPI**, **SQLAlchemy**, and **SQLite**.

## Features

- JWT-based authentication (register/login)
- Full CRUD for tasks
- Assign tasks to users with deadline tracking
- Jira-style board logic — move tasks between columns, reorder within columns
- Dashboard with analytics (task counts, overdue, completion %)
- Filter tasks by status, assigned user, or deadline
- Auto-generated Swagger docs at `/docs`

## Tech Stack

| Component    | Technology           |
|-------------|----------------------|
| Framework   | FastAPI              |
| Database    | SQLite (via SQLAlchemy ORM) |
| Auth        | JWT (python-jose)    |
| Passwords   | bcrypt (passlib)     |
| Validation  | Pydantic v2          |

## Setup Instructions

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd task-manager
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the server

```bash
uvicorn main:app --reload
```

Server starts at `http://127.0.0.1:8000`

### 5. Open Swagger Docs

Visit `http://127.0.0.1:8000/docs` in your browser for interactive API documentation.

## Database Schema

### Users Table

| Column     | Type         | Notes              |
|-----------|--------------|---------------------|
| id        | Integer (PK) | Auto-increment      |
| name      | String(100)  | Required            |
| email     | String(150)  | Unique, indexed     |
| password  | String(255)  | Stored as bcrypt hash |
| created_at| DateTime     | Auto-set on creation |

### Tasks Table

| Column      | Type         | Notes                                    |
|------------|--------------|-------------------------------------------|
| id         | Integer (PK) | Auto-increment                            |
| title      | String(200)  | Required                                  |
| description| Text         | Optional                                  |
| status     | String(20)   | `not_started`, `in_progress`, `completed` |
| position   | Integer      | Order within status column                |
| deadline   | DateTime     | Optional, format: YYYY-MM-DD             |
| assigned_to| Integer (FK) | References users.id                       |
| created_by | Integer (FK) | References users.id (auto from JWT)       |
| created_at | DateTime     | Auto-set                                  |
| updated_at | DateTime     | Auto-updated on modification              |

### Relationships

- A **User** can create many tasks (`created_by` → `users.id`)
- A **User** can be assigned many tasks (`assigned_to` → `users.id`)
- Each **Task** belongs to one creator and optionally one assignee

## API Endpoints

### Authentication

| Method | Endpoint          | Description        | Auth Required |
|--------|-------------------|--------------------|----|
| POST   | `/auth/register`  | Register new user  | No  |
| POST   | `/auth/login`     | Login, get JWT     | No  |

### Users

| Method | Endpoint          | Description        | Auth Required |
|--------|-------------------|--------------------|-----|
| GET    | `/users`          | List all users     | Yes |
| GET    | `/users/{id}`     | Get user by ID     | Yes |

### Tasks

| Method | Endpoint          | Description             | Auth Required |
|--------|-------------------|------------------------|------|
| POST   | `/tasks`          | Create task            | Yes |
| GET    | `/tasks`          | List tasks (with filters) | Yes |
| GET    | `/tasks/{id}`     | Get single task        | Yes |
| PUT    | `/tasks/{id}`     | Update task            | Yes |
| DELETE | `/tasks/{id}`     | Delete task            | Yes |
| PUT    | `/tasks/move`     | Move/reorder task      | Yes |

### Dashboard

| Method | Endpoint      | Description              | Auth Required |
|--------|---------------|--------------------------|-----|
| GET    | `/dashboard`  | Analytics overview       | Yes |

## Filtering Tasks

The `GET /tasks` endpoint supports query params:

- `?status=in_progress` — filter by status
- `?assigned_to=2` — filter by user ID
- `?deadline=2025-04-15` — tasks with deadline on or before this date

## Move Logic (Jira-style)

Send a PUT to `/tasks/move` with body:

```json
{
    "task_id": 1,
    "new_status": "in_progress",
    "new_position": 0
}
```

This will:
- Move the task to the `in_progress` column
- Place it at position 0 (top of the column)
- Automatically adjust positions of other tasks in both the old and new columns

## Postman

Import `task_manager_postman_collection.json` into Postman to test all endpoints.
Make sure to:
1. Register a user first
2. Login to get a token
3. Set the token in the `Authorization` header as `Bearer <token>` for subsequent requests

## Project Structure

```
├── main.py           # FastAPI app with all routes
├── models.py         # SQLAlchemy ORM models
├── schemas.py        # Pydantic request/response schemas
├── auth.py           # JWT and password utilities
├── database.py       # DB connection and session
├── requirements.txt  # Python dependencies
├── README.md         # This file
└── task_manager_postman_collection.json
```
