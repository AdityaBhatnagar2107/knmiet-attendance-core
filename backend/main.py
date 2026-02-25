from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, Column, Integer, String, Text
import random, string
import os

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

class Timetable(database.Base):
    __tablename__ = "master_timetables"
    id = Column(Integer, primary_key=True, index=True)
    branch_year = Column(String, unique=True, index=True) 
    grid_data = Column(Text) 

Timetable.__table__.create(bind=engine, checkfirst=True)

@app.get("/")
async def root():
    return RedirectResponse(url="/frontend/index.html")

# --- AUTH & REGISTRATION ---
@app.post("/register-student")
async def register(erp_id: str, roll_no: str, name: str, branch: str, year: int, device_id: str, db: Session = Depends(database.get_db)):
    existing = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if existing:
        if existing.name.strip().lower() == name.strip().lower() and existing.erp_id.strip() == erp_id.strip():
            if existing.registered_device == "PENDING_RESET":
                existing.registered_device = device_id
                db.commit()
            return {"status": "success", "message": "Login Successful"}
        raise HTTPException(status_code=403, detail="Credential Mismatch")
    
    new_student = models.Student(erp_id=erp_id, name=name, roll_no=roll_no, branch=branch, year=year, registered_device=device_id, is_approved=False, total_lectures=0)
    db.add(new_student)
    db.commit()
    return {"status": "success", "message": "Registered! Awaiting Approval."}

# --- ATTENDANCE ENGINE ---
@app.get("/generate-qr-string")
async def generate_qr(subject_id: int, db: Session = Depends(database.get_db)):
    global current_qr_string
    sub = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
    if sub:
        sub.total_lectures_held = (sub.total_lectures_held or 0) + 1
        db.commit()
    current_qr_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    return {"current_qr_string": current_qr_string}

@app.post("/mark-attendance")
async def mark_attendance(roll_no: str, qr_content: str, subject_id: int, device_id: str, db: Session = Depends(database.get_db)):
    global current_qr_string
    if qr_content != current_qr_string: raise HTTPException(status_code=400, detail="QR Expired")
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if not student or not student.is_approved: raise HTTPException(status_code=403, detail="Not Approved")
    if student.registered_device != device_id: raise HTTPException(status_code=403, detail="Device Mismatch")
    
    student.total_lectures += 1
    db.add(models.Attendance(student_roll=roll_no, subject_id=subject_id))
    db.commit()
    return {"status": "Success"}

# --- DATA ANALYTICS (HOD vs COORDINATOR) ---
@app.get("/all-students-analytics")
async def all_analytics(admin_key: str, teacher_id: int = None, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    if teacher_id:
        t = db.query(models.Teacher).filter(models.Teacher.id == teacher_id).first()
        if t and t.role == "Coordinator":
            return db.query(models.Student).filter(models.Student.branch == t.department).all()
    return db.query(models.Student).all()

# --- OTHER CORE ROUTES ---
@app.get("/student-profile")
async def get_profile(roll_no: str, db: Session = Depends(database.get_db)):
    s = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    return {"exists": True, **s.__dict__} if s else {"exists": False}

@app.get("/student-erp-data")
async def student_erp(roll_no: str, db: Session = Depends(database.get_db)):
    s = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    subs = db.query(models.Subject).filter(models.Subject.branch == s.branch, models.Subject.year == s.year).all()
    data = []
    for sub in subs:
        att = db.query(models.Attendance).filter(models.Attendance.student_roll == roll_no, models.Attendance.subject_id == sub.id).count()
        m = db.query(models.ExamMarks).filter_by(student_roll=roll_no, subject_id=sub.id).first()
        data.append({"subject_name": sub.name, "code": sub.code, "attended": att, "total_held": sub.total_lectures_held or 0, "s1": m.sessional_1 if m else 0, "s2": m.sessional_2 if m else 0, "put": m.put_marks if m else 0})
    return {"subjects": data, "overall_attended": s.total_lectures}

@app.get("/get-teachers")
async def get_t(db: Session = Depends(database.get_db)): return db.query(models.Teacher).all()

@app.get("/teacher-subjects")
async def get_ts(teacher_id: int, db: Session = Depends(database.get_db)): return db.query(models.Subject).filter_by(teacher_id=teacher_id).all()