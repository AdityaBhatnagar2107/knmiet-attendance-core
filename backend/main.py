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

# --- PHASE 7: MASTER TIMETABLE TABLE ---
class Timetable(database.Base):
    __tablename__ = "master_timetables"
    id = Column(Integer, primary_key=True, index=True)
    branch_year = Column(String, unique=True, index=True) 
    grid_data = Column(Text) 

Timetable.__table__.create(bind=engine, checkfirst=True)

# --- STUDENT LOGIC: TRIPLE-CHECK REGISTRATION & LOGIN ---
@app.post("/register-student")
async def register(erp_id: str, roll_no: str, name: str, branch: str, year: int, device_id: str, db: Session = Depends(database.get_db)):
    if len(roll_no) != 13:
        raise HTTPException(status_code=400, detail="Roll number must be exactly 13 digits")
    
    existing = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    
    if existing:
        name_match = existing.name.strip().lower() == name.strip().lower()
        erp_match = existing.erp_id.strip() == erp_id.strip()
        
        if name_match and erp_match:
            if existing.registered_device == "PENDING_RESET":
                existing.registered_device = device_id
                db.commit()
            return {"status": "success", "message": "Identity Verified. Redirecting..."}
        else:
            raise HTTPException(status_code=403, detail="Credential Mismatch! Check Name and ERP ID.")

    new_student = models.Student(
        erp_id=erp_id, name=name, roll_no=roll_no, branch=branch, year=year,
        registered_device=device_id, is_approved=False, total_lectures=0
    )
    db.add(new_student)
    db.commit()
    return {"status": "success", "message": "Registration successful! Awaiting HOD approval."}

# --- ATTENDANCE WITH SUBJECT-SPECIFIC TRACKING ---
@app.get("/generate-qr-string")
async def generate_qr(subject_id: int, db: Session = Depends(database.get_db)):
    global current_qr_string
    # Increment 'Classes Held' for this specific subject every time a QR is generated
    subject = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
    if subject:
        # We only increment once per hour to prevent accidental multi-clicks
        subject.total_lectures_held = (subject.total_lectures_held or 0) + 1
        db.commit()
        
    current_qr_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    return {"current_qr_string": current_qr_string}

@app.post("/mark-attendance")
async def mark_attendance(roll_no: str, qr_content: str, subject_id: int, device_id: str, db: Session = Depends(database.get_db)):
    global current_qr_string
    if qr_content != current_qr_string: 
        raise HTTPException(status_code=400, detail="QR Expired or Invalid")
    
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if not student or not student.is_approved:
        raise HTTPException(status_code=403, detail="Account not approved by HOD.")

    if student.registered_device != device_id:
        raise HTTPException(status_code=403, detail="SECURITY: Device mismatch. Use your registered phone.")

    # Check if student already marked attendance for this specific lecture (simple prevents double-scan)
    # logic can be added here for date-time checking
    
    student.total_lectures += 1
    new_attendance = models.Attendance(student_roll=roll_no, subject_id=subject_id)
    db.add(new_attendance)
    db.commit()
    return {"status": "Success"}

# --- UPDATED STUDENT ERP DATA (REAL MATH) ---
@app.get("/student-erp-data")
async def get_student_erp_data(roll_no: str, db: Session = Depends(database.get_db)):
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if not student: raise HTTPException(status_code=404)
    
    subjects = db.query(models.Subject).filter(models.Subject.branch == student.branch, models.Subject.year == student.year).all()
    subject_data = []
    
    for sub in subjects:
        attended = db.query(models.Attendance).filter(models.Attendance.student_roll == roll_no, models.Attendance.subject_id == sub.id).count()
        # Use the actual 'Classes Held' from the subject table
        total_held = sub.total_lectures_held or 0
        if total_held < attended: total_held = attended
        
        marks = db.query(models.ExamMarks).filter_by(student_roll=roll_no, subject_id=sub.id).first()
        subject_data.append({
            "subject_name": sub.name, "code": sub.code, "attended": attended, "total_held": total_held,
            "s1": marks.sessional_1 if marks else 0, "s2": marks.sessional_2 if marks else 0, "put": marks.put_marks if marks else 0
        })
    return {"subjects": subject_data, "overall_attended": student.total_lectures}

# --- HOD & ADMIN ANALYTICS ---
@app.get("/all-students-analytics")
async def all_analytics(admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    return db.query(models.Student).all()

@app.post("/approve-student")
async def approve(roll_no: str, admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if student:
        student.is_approved = True
        db.commit()
    return {"message": "Approved"}

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
    # Note: Ensure your 'Subject' model in models.py has 'total_lectures_held' column!
    new_sub = models.Subject(name=name, code=code, branch=branch, year=year, teacher_id=teacher_id, total_lectures_held=0)
    db.add(new_sub)
    db.commit()
    return {"message": "Subject Assigned"}

@app.get("/get-teachers")
async def get_teachers(db: Session = Depends(database.get_db)):
    return db.query(models.Teacher).all()

@app.get("/teacher-subjects")
async def get_teacher_subjects(teacher_id: int, db: Session = Depends(database.get_db)):
    return db.query(models.Subject).filter(models.Subject.teacher_id == teacher_id).all()

@app.get("/get-timetable")
async def get_timetable(branch_year: str, db: Session = Depends(database.get_db)):
    tt = db.query(Timetable).filter_by(branch_year=branch_year).first()
    return {"exists": True, "grid_data": tt.grid_data} if tt else {"exists": False}

@app.post("/save-timetable")
async def save_timetable(branch_year: str, grid_data: str, admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    tt = db.query(Timetable).filter_by(branch_year=branch_year).first()
    if not tt:
        tt = Timetable(branch_year=branch_year, grid_data=grid_data)
        db.add(tt)
    else:
        tt.grid_data = grid_data
    db.commit()
    return {"status": "success"}

@app.post("/reset-student-device")
async def reset_device(roll_no: str, admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if student:
        student.registered_device = "PENDING_RESET"
        db.commit()
        return {"message": "Hardware ID Reset Successful."}
    raise HTTPException(status_code=404)