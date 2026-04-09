from fastapi import FastAPI, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from database import engine, get_db, Base
from models import User, Task
from schemas import (
    UserRegister, UserLogin, UserOut, Token,
    TaskCreate, TaskUpdate, TaskOut, TaskMove,
)
from auth import hash_password, verify_password, create_access_token, get_current_user

# create tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Task Manager API",
    description="A Jira-like task management backend",
    version="1.0.0",
)

VALID_STATUSES = ["not_started", "in_progress", "completed"]


# helper to parse deadline strings
def parse_deadline(deadline_str: str):
    try:
        return datetime.strptime(deadline_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid deadline format. Use YYYY-MM-DD"
        )


# ==========================================
#               AUTH ROUTES
# ==========================================

@app.post("/auth/register", response_model=UserOut, tags=["Authentication"])
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    # check if email already taken
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        name=user_data.name,
        email=user_data.email,
        password=hash_password(user_data.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/auth/login", response_model=Token, tags=["Authentication"])
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"user_id": user.id, "email": user.email})
    return {"access_token": token, "token_type": "bearer"}


# ==========================================
#             USER ROUTES
# ==========================================

@app.get("/users", response_model=list[UserOut], tags=["Users"])
def list_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get all users — useful for the 'assign to' dropdown."""
    users = db.query(User).all()
    return users


@app.get("/users/{user_id}", response_model=UserOut, tags=["Users"])
def get_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ==========================================
#             TASK ROUTES
# ==========================================

@app.post("/tasks", response_model=TaskOut, status_code=201, tags=["Tasks"])
def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # validate status
    if task_data.status and task_data.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {VALID_STATUSES}")

    # validate assigned user exists
    if task_data.assigned_to:
        assignee = db.query(User).filter(User.id == task_data.assigned_to).first()
        if not assignee:
            raise HTTPException(status_code=400, detail="Assigned user does not exist")

    # parse deadline
    deadline = None
    if task_data.deadline:
        deadline = parse_deadline(task_data.deadline)

    # figure out position — put it at the end of its status column
    status_col = task_data.status or "not_started"
    max_pos = db.query(Task).filter(Task.status == status_col).count()

    new_task = Task(
        title=task_data.title,
        description=task_data.description,
        status=status_col,
        position=max_pos,
        deadline=deadline,
        assigned_to=task_data.assigned_to,
        created_by=current_user.id,
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task


@app.get("/tasks", response_model=list[TaskOut], tags=["Tasks"])
def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    assigned_to: Optional[int] = Query(None, description="Filter by assigned user ID"),
    deadline: Optional[str] = Query(None, description="Filter by deadline (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Task)

    if status:
        if status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status filter. Must be one of: {VALID_STATUSES}")
        query = query.filter(Task.status == status)

    if assigned_to:
        query = query.filter(Task.assigned_to == assigned_to)

    if deadline:
        dl = parse_deadline(deadline)
        query = query.filter(Task.deadline <= dl)

    # order by status column and position
    tasks = query.order_by(Task.status, Task.position).all()
    return tasks


# ==========================================
#         JIRA-LIKE MOVE LOGIC
# ==========================================
# NOTE: this route must be defined BEFORE /tasks/{task_id}
# otherwise FastAPI will try to parse "move" as a task_id

@app.put("/tasks/move", response_model=TaskOut, tags=["Task Board"])
def move_task(
    move_data: TaskMove,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Move a task to a different status column and/or reorder within a column.
    Send task_id, new_status, and new_position.
    """
    if move_data.new_status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {VALID_STATUSES}")

    task = db.query(Task).filter(Task.id == move_data.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    old_status = task.status
    old_position = task.position

    # if moving within the same column
    if old_status == move_data.new_status:
        if move_data.new_position > old_position:
            # shift tasks between old and new position up by 1
            db.query(Task).filter(
                Task.status == old_status,
                Task.position > old_position,
                Task.position <= move_data.new_position,
            ).update({"position": Task.position - 1})
        elif move_data.new_position < old_position:
            # shift tasks between new and old position down by 1
            db.query(Task).filter(
                Task.status == old_status,
                Task.position >= move_data.new_position,
                Task.position < old_position,
            ).update({"position": Task.position + 1})
    else:
        # moving to a different column
        # close the gap in the old column
        db.query(Task).filter(
            Task.status == old_status,
            Task.position > old_position,
        ).update({"position": Task.position - 1})

        # make space in the new column
        db.query(Task).filter(
            Task.status == move_data.new_status,
            Task.position >= move_data.new_position,
        ).update({"position": Task.position + 1})

    task.status = move_data.new_status
    task.position = move_data.new_position
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task


# ==========================================
#         TASK BY ID ROUTES
# ==========================================

@app.get("/tasks/{task_id}", response_model=TaskOut, tags=["Tasks"])
def get_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.put("/tasks/{task_id}", response_model=TaskOut, tags=["Tasks"])
def update_task(
    task_id: int,
    task_data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task_data.title is not None:
        task.title = task_data.title

    if task_data.description is not None:
        task.description = task_data.description

    if task_data.status is not None:
        if task_data.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {VALID_STATUSES}")
        task.status = task_data.status

    if task_data.assigned_to is not None:
        assignee = db.query(User).filter(User.id == task_data.assigned_to).first()
        if not assignee:
            raise HTTPException(status_code=400, detail="Assigned user does not exist")
        task.assigned_to = task_data.assigned_to

    if task_data.deadline is not None:
        task.deadline = parse_deadline(task_data.deadline)

    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task


@app.delete("/tasks/{task_id}", tags=["Tasks"])
def delete_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()
    return {"message": "Task deleted successfully"}


# ==========================================
#          DASHBOARD ANALYTICS
# ==========================================

@app.get("/dashboard", tags=["Dashboard"])
def dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    total_tasks = db.query(Task).count()

    # count per status
    not_started = db.query(Task).filter(Task.status == "not_started").count()
    in_progress = db.query(Task).filter(Task.status == "in_progress").count()
    completed = db.query(Task).filter(Task.status == "completed").count()

    # overdue tasks — deadline has passed and not completed
    overdue = db.query(Task).filter(
        Task.deadline < datetime.utcnow(),
        Task.status != "completed",
        Task.deadline.isnot(None),
    ).count()

    # tasks per user
    users = db.query(User).all()
    tasks_per_user = []
    for u in users:
        count = db.query(Task).filter(Task.assigned_to == u.id).count()
        tasks_per_user.append({"user_id": u.id, "name": u.name, "task_count": count})

    # completion percentage
    completion_pct = round((completed / total_tasks) * 100, 2) if total_tasks > 0 else 0

    return {
        "total_tasks": total_tasks,
        "status_breakdown": {
            "not_started": not_started,
            "in_progress": in_progress,
            "completed": completed,
        },
        "overdue_tasks": overdue,
        "tasks_per_user": tasks_per_user,
        "completed_tasks": completed,
        "completion_percentage": completion_pct,
    }


# run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
