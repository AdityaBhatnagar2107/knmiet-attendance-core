from fastapi import FastAPI, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from . import models, database
from .database import engine
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import random, string
import os

from fastapi.staticfiles import StaticFiles
import os

# This tells FastAPI to serve everything in the "frontend" folder
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
# Initialize database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# UNIVERSAL CORS: Essential for preventing "Failed to Fetch" during deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Admin Key configuration
ADMIN_SECRET = "KNM@2026!Admin" 
current_qr_string = ""

# --- STUDENT LOGIC ---

@app.post("/register-student")
async def register(data: dict = Body(...), db: Session = Depends(database.get_db)):
    # Enforces the 13-digit integrity check for KNMIET Roll Numbers
    roll = str(data.get('roll_no', ''))
    if len(roll) != 13:
        raise HTTPException(status_code=400, detail="Roll number must be exactly 13 digits")
    
    new_student = models.Student(
        name=data.get('name'),
        roll_no=roll,
        registered_device=data.get('device_id'),
        is_approved=False,
        total_lectures=0
    )
    db.add(new_student)
    db.commit()
    return {"message": "Success! Registration sent to Admin for approval."}

@app.get("/student-profile")
async def get_profile(roll_no: str, db: Session = Depends(database.get_db)):
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if not student:
        return {"exists": False}
    return {
        "exists": True,
        "name": student.name,
        "roll_no": student.roll_no,
        "is_approved": student.is_approved,
        "lectures": student.total_lectures
    }

# --- ADMIN LOGIC ---

@app.get("/pending-students")
async def get_pending(admin_key: str, db: Session = Depends(database.get_db)):
    # Debug print to verify connectivity in your terminal logs
    print(f"DEBUG: Admin key received: {admin_key}") 
    if admin_key != ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return db.query(models.Student).all()

@app.post("/approve-student")
async def approve(roll_no: str, admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET:
        raise HTTPException(status_code=401)
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if student:
        student.is_approved = True
        db.commit()
    return {"message": "Student Approved"}

# Added Remove Student logic for easier database management
@app.delete("/remove-student")
async def remove_student(roll_no: str, admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if student:
        db.delete(student)
        db.commit()
    return {"message": "Deleted"}

# --- TEACHER & ATTENDANCE LOGIC ---

@app.get("/verify-teacher-pin")
async def verify_pin(teacher_id: int, entered_pin: str, db: Session = Depends(database.get_db)):
    teacher = db.query(models.Teacher).filter(models.Teacher.id == teacher_id).first()
    if teacher and teacher.pin == entered_pin:
        return {"status": "success"}
    raise HTTPException(status_code=401, detail="Invalid PIN")

@app.post("/mark-attendance")
async def mark_attendance(roll_no: str, qr_content: str, db: Session = Depends(database.get_db)):
    global current_qr_string
    if qr_content != current_qr_string:
        raise HTTPException(status_code=400, detail="QR Expired")
    
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if student and student.is_approved:
        student.total_lectures += 1
        new_attendance = models.Attendance(student_roll=roll_no, class_name="CSE22")
        db.add(new_attendance)
        db.commit()
        return {"status": "Success"}
    raise HTTPException(status_code=403, detail="Not Approved")

@app.get("/generate-qr-string")
async def generate_qr():
    global current_qr_string
    current_qr_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    return {"current_qr_string": current_qr_string}

@app.get("/get-teachers")
async def get_teachers(db: Session = Depends(database.get_db)):
    return db.query(models.Teacher).all()

@app.post("/add-teacher")
async def add_teacher(name: str, subject: str, email: str, pin: str, admin_key: str, db: Session = Depends(database.get_db)):
    if admin_key != ADMIN_SECRET: raise HTTPException(status_code=401)
    new_t = models.Teacher(name=name, subject=subject, email=email, pin=pin)
    db.add(new_t)
    db.commit()
    return {"message": "Teacher added"}

@app.get("/live-logs")
async def live_logs(db: Session = Depends(database.get_db)):
    return db.query(models.Attendance).order_by(models.Attendance.timestamp.desc()).limit(10).all()