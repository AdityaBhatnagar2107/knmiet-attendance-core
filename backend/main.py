from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
import random, string

from . import models, database
from .database import engine

# Initialize Database
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
    return {"message": "Database successfully wiped and upgraded to ERP Schema!"}

# --- STUDENT ROUTES ---
@app.post("/register-student")
async def register(erp_id: str, roll_no: str, name: str, branch: str, year: int, device_id: str, db: Session = Depends(database.get_db)):
    if len(roll_no) != 13: raise HTTPException(status_code=400, detail="Roll number must be exactly 13 digits")
    existing = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if existing:
        if existing.name.strip().lower() == name.strip().lower() and existing.erp_id.strip() == erp_id.strip():
            if existing.registered_device == "PENDING_RESET":
                existing.registered_device = device_id
                db.commit()
            return {"status": "success", "message": "Welcome back!"}
        raise HTTPException(status_code=403, detail="Credential Mismatch!")
    
    new_student = models.Student(erp_id=erp_id, name=name, roll_no=roll_no, branch=branch, year=year, registered_device=device_id, is_approved=False, total_lectures=0)
    db.add(new_student)
    db.commit()
    return {"status": "success", "message": "Registered! Awaiting HOD approval."}

@app.get("/student-profile")
async def get_profile(roll_no: str, db: Session = Depends(database.get_db)):
    # Fetching fresh from DB to ensure 'is_approved' status is real-time
    s = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if not s: return {"exists": False}
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
        data.append({"subject_name": sub.name, "code": sub.code, "attended": att, "total_held": sub.total_lectures_held or 0, "s1": m.sessional_1 if m else 0, "s2": m.sessional_2 if m else 0, "put": m.put_marks if m else 0})
    return {"subjects": data, "overall_attended": s.total_lectures}

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
        db.refresh(student) # Crucial: Confirms the save to disk before responding
    return {"message": "Approved", "status": "success"}

@app.post("/add-teacher")
async def add_teacher(name: str, email: str, pin: str, role: str, department: str, admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    db.add(models.Teacher(name=name, email=email, pin=pin, role=role, department=department))
    db.commit()
    return {"message": "Teacher Added"}

@app.post("/assign-subject")
async def assign_subject(name: str, code: str, branch: str, year: int, teacher_id: int, admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    db.add(models.Subject(name=name, code=code, branch=branch, year=year, teacher_id=teacher_id, total_lectures_held=0))
    db.commit()
    return {"message": "Subject Linked"}

@app.get("/all-students-analytics")
async def all_analytics(admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    return db.query(models.Student).all()

# --- TEACHER & QR ROUTES ---
@app.get("/get-teachers")
async def get_t(db: Session = Depends(database.get_db)): return db.query(models.Teacher).all()

@app.get("/teacher-subjects")
async def get_ts(teacher_id: int, db: Session = Depends(database.get_db)): return db.query(models.Subject).filter_by(teacher_id=teacher_id).all()

@app.get("/verify-teacher-pin")
async def verify_pin(teacher_id: int, entered_pin: str, db: Session = Depends(database.get_db)):
    t = db.query(models.Teacher).filter(models.Teacher.id == teacher_id).first()
    if t and t.pin == entered_pin: return {"status": "success", "role": t.role}
    raise HTTPException(status_code=401, detail="Invalid PIN")

@app.get("/generate-qr-string")
async def generate_qr(subject_id: int, is_new: bool = False, db: Session = Depends(database.get_db)):
    global current_qr_string
    if is_new:
        sub = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
        if sub: 
            sub.total_lectures_held = (sub.total_lectures_held or 0) + 1
            db.commit()
    current_qr_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    return {"current_qr_string": current_qr_string}

@app.post("/mark-attendance")
async def mark_attendance(roll_no: str, qr_content: str, subject_id: int, device_id: str, db: Session = Depends(database.get_db)):
    global current_qr_string
    if qr_content != current_qr_string: raise HTTPException(status_code=400, detail="QR Expired!")
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if not student or not student.is_approved: raise HTTPException(status_code=403, detail="Not Approved")
    if student.registered_device != device_id: raise HTTPException(status_code=403, detail="Device Mismatch")
    
    student.total_lectures += 1
    db.add(models.Attendance(student_roll=roll_no, subject_id=subject_id))
    db.commit()
    return {"status": "Success"}

@app.get("/live-attendance")
async def get_live(subject_id: int, db: Session = Depends(database.get_db)):
    records = db.query(models.Attendance).filter(models.Attendance.subject_id == subject_id).order_by(models.Attendance.id.desc()).limit(10).all()
    res = []
    for r in records:
        s = db.query(models.Student).filter(models.Student.roll_no == r.student_roll).first()
        if s: res.append({"name": s.name, "roll_no": s.roll_no, "branch": s.branch, "year": s.year})
    return res

@app.get("/subject-roster")
async def get_roster(subject_id: int, db: Session = Depends(database.get_db)):
    sub = db.query(models.Subject).filter_by(id=subject_id).first()
    students = db.query(models.Student).filter_by(branch=sub.branch, year=sub.year, is_approved=True).all()
    roster = []
    for s in students:
        m = db.query(models.ExamMarks).filter_by(student_roll=s.roll_no, subject_id=sub.id).first()
        roster.append({"name": s.name, "roll_no": s.roll_no, "s1": m.sessional_1 if m else 0, "s2": m.sessional_2 if m else 0, "put": m.put_marks if m else 0})
    return {"roster": roster}

@app.post("/update-marks")
async def update_m(roll_no: str, subject_id: int, s1: float, s2: float, put: float, db: Session = Depends(database.get_db)):
    m = db.query(models.ExamMarks).filter_by(student_roll=roll_no, subject_id=subject_id).first()
    if not m:
        m = models.ExamMarks(student_roll=roll_no, subject_id=subject_id)
        db.add(m)
    if s1 > 0: m.sessional_1 = s1
    if s2 > 0: m.sessional_2 = s2
    if put > 0: m.put_marks = put
    db.commit()
    return {"message": "Saved"}

@app.get("/get-timetable")
async def get_tt(branch_year: str, db: Session = Depends(database.get_db)):
    tt = db.query(models.Timetable).filter_by(branch_year=branch_year).first()
    return {"exists": True, "grid_data": tt.grid_data} if tt else {"exists": False}

@app.post("/save-timetable")
async def save_tt(branch_year: str, grid_data: str, admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    tt = db.query(models.Timetable).filter_by(branch_year=branch_year).first()
    if not tt: db.add(models.Timetable(branch_year=branch_year, grid_data=grid_data))
    else: tt.grid_data = grid_data
    db.commit()
    return {"status": "success"}