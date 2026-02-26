from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, Column, Integer, String, Boolean, Float, DateTime
from datetime import datetime, timedelta
import random, string

from . import models, database
from .database import engine

# --- We must dynamically alter the SQLite schema for the new features if they don't exist ---
# (In PostgreSQL, we'd use Alembic. For now, wiping the DB handles this).
models.Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ADMIN_SECRET = "KNM@2026!Admin" 
current_qr_string = ""

@app.get("/")
async def root(): return RedirectResponse(url="/frontend/index.html")

@app.get("/reset-database-danger")
async def reset_db(admin_key: str):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    return {"message": "Database wiped! Ready for Sections and Expanded Branches."}

# --- STUDENT REGISTRATION (NOW WITH SECTIONS) ---
@app.post("/register-student")
async def register(erp_id: str, roll_no: str, name: str, branch: str, year: int, section: str, device_id: str, db: Session = Depends(database.get_db)):
    if len(roll_no) != 13: raise HTTPException(status_code=400, detail="Roll number must be 13 digits")
    existing = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    
    if existing:
        if existing.status == "Rejected":
            # Allow re-registration if rejected
            existing.name = name; existing.branch = branch; existing.year = year; existing.section = section; existing.registered_device = device_id; existing.status = "Pending"
            db.commit()
            return {"status": "success", "message": "Re-application submitted to Director."}
        if existing.name.strip().lower() == name.strip().lower():
            return {"status": "success", "message": "Welcome back!"}
        raise HTTPException(status_code=403, detail="Roll Number already registered!")
    
    # Notice we now use 'status' instead of 'is_approved'
    new_student = models.Student(erp_id=erp_id, name=name, roll_no=roll_no, branch=branch, year=year, section=section, registered_device=device_id, status="Pending", total_lectures=0)
    db.add(new_student)
    db.commit()
    return {"status": "success", "message": "Registered! Awaiting Director approval."}

@app.get("/student-profile")
async def get_profile(roll_no: str, db: Session = Depends(database.get_db)):
    s = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if not s: return {"exists": False}
    db.refresh(s)
    return {"exists": True, "status": s.status, "name": s.name, "branch": s.branch, "year": s.year, "section": s.section, "total_lectures": s.total_lectures}

# --- DIRECTOR (ADMIN) ROUTES ---
@app.get("/pending-students")
async def get_pending(admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    return db.query(models.Student).filter(models.Student.status == "Pending").all()

@app.post("/update-student-status")
async def update_status(roll_no: str, status: str, admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    if status not in ["Approved", "Rejected"]: raise HTTPException(status_code=400)
    
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if student: 
        student.status = status
        db.commit()
        db.refresh(student)
    return {"message": f"Student {status}"}

@app.post("/assign-subject")
async def assign_subject(name: str, code: str, branch: str, year: int, section: str, teacher_id: int, admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    db.add(models.Subject(name=name, code=code, branch=branch, year=year, section=section, teacher_id=teacher_id, total_lectures_held=0))
    db.commit()
    return {"message": "Subject Linked"}

@app.post("/add-teacher")
async def add_teacher(name: str, email: str, pin: str, role: str, department: str, admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    db.add(models.Teacher(name=name, email=email, pin=pin, role=role, department=department))
    db.commit()
    return {"message": "Teacher Added"}

@app.get("/get-teachers")
async def get_t(db: Session = Depends(database.get_db)): return db.query(models.Teacher).all()

@app.get("/all-students-analytics")
async def all_analytics(admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    return db.query(models.Student).all()

# --- We will update the Teacher/QR logic in Phase 2, keeping these stubs for now so the app doesn't crash ---
@app.get("/teacher-subjects")
async def get_ts(teacher_id: int, db: Session = Depends(database.get_db)): return db.query(models.Subject).filter_by(teacher_id=teacher_id).all()
@app.get("/verify-teacher-pin")
async def verify_pin(teacher_id: int, entered_pin: str, db: Session = Depends(database.get_db)): return {"status": "success", "role": "Faculty"}