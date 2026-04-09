from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


# ---- User Schemas ----

class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Task Schemas ----

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    assigned_to: Optional[int] = None
    deadline: Optional[str] = None  # expected format: YYYY-MM-DD
    status: Optional[str] = "not_started"


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[int] = None
    deadline: Optional[str] = None
    status: Optional[str] = None


class TaskOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: str
    position: int
    deadline: Optional[datetime]
    assigned_to: Optional[int]
    created_by: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---- Move Task Schema ----

class TaskMove(BaseModel):
    task_id: int
    new_status: str
    new_position: int


# ---- Token Schema ----

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
