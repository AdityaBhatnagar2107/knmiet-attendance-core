from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, Column, Integer, String, Text  # Added columns for Phase 7
from datetime import datetime
import random, string
import os

from . import models, database
from .database import engine

# Initialize database tables
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

@app.get("/")
async def root():
    return RedirectResponse(url="/frontend/index.html")

ADMIN_SECRET = "KNM@2026!Admin" 
current_qr_string = ""

# --- SECRET DATABASE RESET (RUN THIS ONCE) ---
@app.get("/reset-database-danger")
async def reset_db(admin_key: str):
    if admin_key != ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")
    # This safely drops old tables and builds the new ERP ones!
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    
    # Also reset the Timetable table safely
    Timetable.__table__.drop(bind=engine, checkfirst=True)
    Timetable.__table__.create(bind=engine, checkfirst=True)
    
    return {"message": "Database successfully wiped and upgraded to ERP Schema!"}

# --- STUDENT LOGIC ---
@app.post("/register-student")
async def register(erp_id: str, roll_no: str, name: str, branch: str, year: int, device_id: str, db: Session = Depends(database.get_db)):
    if len(roll_no) != 13:
        raise HTTPException(status_code=400, detail="Roll number must be exactly 13 digits")
    
    existing = db.query(models.Student).filter((models.Student.roll_no == roll_no) | (models.Student.erp_id == erp_id)).first()
    
    if existing:
        # SMART LOGIN: If they perfectly match their existing data, log them back in!
        if existing.roll_no == roll_no and existing.erp_id == erp_id and existing.name.strip().lower() == name.strip().lower():
            return {"status": "success", "message": "Welcome back! Restoring your session..."}
        else:
            raise HTTPException(status_code=403, detail="Account exists, but details do not match.")

    new_student = models.Student(
        erp_id=erp_id, name=name, roll_no=roll_no, branch=branch, year=year,
        registered_device=device_id, is_approved=False, total_lectures=0
    )
    db.add(new_student)
    db.commit()
    return {"status": "success", "message": "Success! Registration sent to Admin for approval."}

@app.get("/student-profile")
async def get_profile(roll_no: str, db: Session = Depends(database.get_db)):
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if not student:
        return {"exists": False}
    return {
        "exists": True, "erp_id": student.erp_id, "name": student.name, 
        "roll_no": student.roll_no, "branch": student.branch, "year": student.year,
        "is_approved": student.is_approved, "lectures": student.total_lectures
    }

# --- ADMIN & HOD LOGIC ---
@app.get("/pending-students")
async def get_pending(admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET:
        raise HTTPException(status_code=401)
    return db.query(models.Student).filter(models.Student.is_approved == False).all()

@app.post("/approve-student")
async def approve(roll_no: str, admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if student:
        student.is_approved = True
        db.commit()
    return {"message": "Student Approved"}

@app.post("/add-teacher")
async def add_teacher(name: str, email: str, pin: str, role: str, department: str, admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    new_t = models.Teacher(name=name, email=email, pin=pin, role=role, department=department)
    db.add(new_t)
    db.commit()
    return {"message": f"{role} added successfully"}

@app.post("/assign-subject")
async def assign_subject(name: str, code: str, branch: str, year: int, teacher_id: int, admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    new_sub = models.Subject(name=name, code=code, branch=branch, year=year, teacher_id=teacher_id)
    db.add(new_sub)
    db.commit()
    return {"message": "Subject Assigned"}

# --- TEACHER & ATTENDANCE LOGIC ---
@app.get("/get-teachers")
async def get_teachers(db: Session = Depends(database.get_db)):
    return db.query(models.Teacher).all()

@app.get("/verify-teacher-pin")
async def verify_pin(teacher_id: int, entered_pin: str, db: Session = Depends(database.get_db)):
    teacher = db.query(models.Teacher).filter(models.Teacher.id == teacher_id).first()
    if teacher and teacher.pin == entered_pin:
        return {"status": "success", "role": teacher.role}
    raise HTTPException(status_code=401, detail="Invalid PIN")

@app.get("/generate-qr-string")
async def generate_qr():
    global current_qr_string
    current_qr_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    return {"current_qr_string": current_qr_string}

@app.post("/mark-attendance")
async def mark_attendance(roll_no: str, qr_content: str, subject_id: int, db: Session = Depends(database.get_db)):
    global current_qr_string
    if qr_content != current_qr_string: raise HTTPException(status_code=400, detail="QR Expired")
    
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if student and student.is_approved:
        student.total_lectures += 1
        new_attendance = models.Attendance(student_roll=roll_no, subject_id=subject_id)
        db.add(new_attendance)
        db.commit()
        return {"status": "Success"}
    raise HTTPException(status_code=403, detail="Not Approved")

# --- EXAM LOGIC ---
@app.post("/update-marks")
async def update_marks(roll_no: str, subject_id: int, s1: float, s2: float, put: float, db: Session = Depends(database.get_db)):
    mark_entry = db.query(models.ExamMarks).filter_by(student_roll=roll_no, subject_id=subject_id).first()
    if not mark_entry:
        mark_entry = models.ExamMarks(student_roll=roll_no, subject_id=subject_id)
        db.add(mark_entry)
    
    mark_entry.sessional_1 = s1
    mark_entry.sessional_2 = s2
    mark_entry.put_marks = put
    db.commit()
    return {"message": "Marks Updated Successfully"}

# --- PHASE 4.5: FACULTY ERP ROUTES ---
@app.get("/teacher-subjects")
async def get_teacher_subjects(teacher_id: int, db: Session = Depends(database.get_db)):
    # Safely fetches ONLY the subjects assigned to the logged-in teacher
    subjects = db.query(models.Subject).filter(models.Subject.teacher_id == teacher_id).all()
    return subjects

@app.get("/subject-roster")
async def get_subject_roster(subject_id: int, db: Session = Depends(database.get_db)):
    subject = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
        
    students = db.query(models.Student).filter(
        models.Student.branch == subject.branch,
        models.Student.year == subject.year,
        models.Student.is_approved == True
    ).all()
    
    roster = []
    for s in students:
        marks = db.query(models.ExamMarks).filter_by(student_roll=s.roll_no, subject_id=subject.id).first()
        roster.append({
            "name": s.name,
            "roll_no": s.roll_no,
            "erp_id": s.erp_id,
            "s1": marks.sessional_1 if marks else 0,
            "s2": marks.sessional_2 if marks else 0,
            "put": marks.put_marks if marks else 0
        })
        
    return {"subject_name": subject.name, "roster": roster}

# --- PHASE 6: STUDENT DASHBOARD ANALYTICS ---
@app.get("/student-erp-data")
async def get_student_erp_data(roll_no: str, db: Session = Depends(database.get_db)):
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    subjects = db.query(models.Subject).filter(
        models.Subject.branch == student.branch,
        models.Subject.year == student.year
    ).all()

    subject_data = []
    total_attended_overall = 0
    total_classes_overall = 0

    for sub in subjects:
        attended = db.query(models.Attendance).filter(
            models.Attendance.student_roll == roll_no,
            models.Attendance.subject_id == sub.id
        ).count()
        
        max_att = db.query(func.count(models.Attendance.id)).filter(
            models.Attendance.subject_id == sub.id
        ).group_by(models.Attendance.student_roll).order_by(func.count(models.Attendance.id).desc()).first()
        
        total_held = max_att[0] if max_att else 0
        if total_held < attended: total_held = attended 

        marks = db.query(models.ExamMarks).filter_by(student_roll=roll_no, subject_id=sub.id).first()
        
        subject_data.append({
            "subject_name": sub.name,
            "code": sub.code,
            "attended": attended,
            "total_held": total_held,
            "s1": marks.sessional_1 if marks else 0,
            "s2": marks.sessional_2 if marks else 0,
            "put": marks.put_marks if marks else 0
        })
        total_attended_overall += attended
        total_classes_overall += total_held

    return {
        "overall_attended": total_attended_overall,
        "overall_total": total_classes_overall,
        "subjects": subject_data
    }

# --- PHASE 7: MASTER TIMETABLE ---
class Timetable(database.Base):
    __tablename__ = "master_timetables"
    id = Column(Integer, primary_key=True, index=True)
    branch_year = Column(String, unique=True, index=True) # e.g., "CSE-2"
    grid_data = Column(Text) # Saves the entire HTML grid as a JSON string

# Safely creates ONLY this new table without touching your existing students/teachers!
Timetable.__table__.create(bind=engine, checkfirst=True)

@app.post("/save-timetable")
async def save_timetable(branch_year: str, grid_data: str, admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: 
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    tt = db.query(Timetable).filter_by(branch_year=branch_year).first()
    if not tt:
        tt = Timetable(branch_year=branch_year, grid_data=grid_data)
        db.add(tt)
    else:
        tt.grid_data = grid_data
    db.commit()
    return {"status": "success", "message": "Timetable Published"}

@app.get("/get-timetable")
async def get_timetable(branch_year: str, db: Session = Depends(database.get_db)):
    tt = db.query(Timetable).filter_by(branch_year=branch_year).first()
    if not tt:
        return {"exists": False}
    return {"exists": True, "grid_data": tt.grid_data}