from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
import random, string

from . import models, database
from .database import engine

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

# --- STUDENT PROFILE (MOBILE OPTIMIZED DATA) ---
@app.get("/student-profile")
async def get_profile(roll_no: str, db: Session = Depends(database.get_db)):
    s = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if not s: return {"exists": False}
    db.refresh(s)
    return {
        "exists": True, 
        "is_approved": s.is_approved, 
        "name": s.name, 
        "branch": s.branch, 
        "year": s.year, 
        "total_lectures": s.total_lectures
    }

@app.get("/student-erp-data")
async def student_erp(roll_no: str, db: Session = Depends(database.get_db)):
    s = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if not s: raise HTTPException(status_code=404)
    subs = db.query(models.Subject).filter(models.Subject.branch == s.branch, models.Subject.year == s.year).all()
    data = []
    for sub in subs:
        att = db.query(models.Attendance).filter(models.Attendance.student_roll == roll_no, models.Attendance.subject_id == sub.id).count()
        m = db.query(models.ExamMarks).filter_by(student_roll=roll_no, subject_id=sub.id).first()
        data.append({
            "subject_name": sub.name, 
            "code": sub.code, 
            "attended": att, 
            "total_held": sub.total_lectures_held or 0, 
            "s1": m.sessional_1 if m else 0, 
            "s2": m.sessional_2 if m else 0, 
            "put": m.put_marks if m else 0
        })
    return {"subjects": data, "overall_attended": s.total_lectures}

# --- ATTENDANCE WITH 40-MIN LOCK ---
@app.post("/mark-attendance")
async def mark_attendance(roll_no: str, qr_content: str, subject_id: int, device_id: str, db: Session = Depends(database.get_db)):
    global current_qr_string
    if qr_content != current_qr_string: raise HTTPException(status_code=400, detail="QR Expired!")
    
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if not student or not student.is_approved: raise HTTPException(status_code=403, detail="HOD Approval Required")
    if student.registered_device != device_id: raise HTTPException(status_code=403, detail="Hardware ID Mismatch")
    
    time_limit = datetime.utcnow() - timedelta(minutes=40)
    duplicate = db.query(models.Attendance).filter(
        models.Attendance.student_roll == roll_no,
        models.Attendance.subject_id == subject_id,
        models.Attendance.timestamp >= time_limit
    ).first()

    if duplicate: raise HTTPException(status_code=400, detail="Duplicate Scan: 40m Lock")

    student.total_lectures += 1
    db.add(models.Attendance(student_roll=roll_no, subject_id=subject_id))
    db.commit()
    return {"status": "Success"}

# --- ADMIN ROUTES ---
@app.get("/pending-students")
async def get_pending(admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    return db.query(models.Student).filter(models.Student.is_approved == False).all()

@app.post("/approve-student")
async def approve(roll_no: str, admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if student: 
        student.is_approved = True
        db.commit()
        db.refresh(student)
    return {"message": "Approved"}

@app.post("/add-teacher")
async def add_teacher(name: str, email: str, pin: str, role: str, department: str, admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    db.add(models.Teacher(name=name, email=email, pin=pin, role=role, department=department))
    db.commit()
    return {"message": "Success"}

@app.post("/assign-subject")
async def assign_subject(name: str, code: str, branch: str, year: int, teacher_id: int, admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    db.add(models.Subject(name=name, code=code, branch=branch, year=year, teacher_id=teacher_id))
    db.commit()
    return {"message": "Linked"}

@app.get("/get-teachers")
async def get_t(db: Session = Depends(database.get_db)): return db.query(models.Teacher).all()

@app.get("/teacher-subjects")
async def get_ts(teacher_id: int, db: Session = Depends(database.get_db)): return db.query(models.Subject).filter_by(teacher_id=teacher_id).all()

@app.get("/generate-qr-string")
async def generate_qr(subject_id: int, is_new: bool = False, db: Session = Depends(database.get_db)):
    global current_qr_string
    if is_new:
        sub = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
        if sub: sub.total_lectures_held = (sub.total_lectures_held or 0) + 1; db.commit()
    current_qr_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    return {"current_qr_string": current_qr_string}

@app.get("/all-students-analytics")
async def all_analytics(admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    return db.query(models.Student).all()