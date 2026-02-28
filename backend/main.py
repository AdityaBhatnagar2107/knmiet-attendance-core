from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Header
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, Column, Integer, String, Boolean, Float, DateTime
from datetime import datetime, timedelta
import random, string, csv, io

from . import models, database
from .database import engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

ADMIN_KEYS = {"KNM@2026!Admin": "ALL", "CSE@2026!HOD": "CSE", "IT@2026!HOD": "IT", "AI@2026!HOD": "AI", "ECE@2026!HOD": "ECE", "EE@2026!HOD": "EE", "CHE@2026!HOD": "CHE"}
def get_admin_branch(key: str):
    branch = ADMIN_KEYS.get(key)
    if not branch: raise HTTPException(status_code=401, detail="Unauthorized Admin Key")
    return branch

active_sessions = {}

@app.get("/")
async def root(): return RedirectResponse(url="/frontend/index.html")

@app.get("/admin-verify")
async def verify_admin(x_admin_key: str = Header(...)): return {"branch": get_admin_branch(x_admin_key)}

@app.get("/reset-database-danger")
async def reset_db(x_admin_key: str = Header(...)):
    if get_admin_branch(x_admin_key) != "ALL": raise HTTPException(status_code=403, detail="Director Access Required")
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    return {"message": "Database wiped! Ready for Sections and Expanded Branches."}

@app.post("/upload-roster")
async def upload_roster(file: UploadFile = File(...), x_admin_key: str = Header(...), db: Session = Depends(database.get_db)):
    admin_branch = get_admin_branch(x_admin_key)
    content = await file.read(); decoded = content.decode('utf-8'); reader = csv.DictReader(io.StringIO(decoded)); count = 0
    for row in reader:
        r_key = next((k for k in row.keys() if k and 'roll' in k.lower()), None)
        n_key = next((k for k in row.keys() if k and 'name' in k.lower()), None)
        b_key = next((k for k in row.keys() if k and 'branch' in k.lower()), None)
        y_key = next((k for k in row.keys() if k and 'year' in k.lower()), None)
        s_key = next((k for k in row.keys() if k and 'sec' in k.lower()), None)
        if not r_key or not row[r_key]: continue
        row_branch = str(row[b_key]).strip().upper() if b_key else "CSE"
        if admin_branch != "ALL" and row_branch != admin_branch: continue
        roll_no = str(row[r_key]).strip()
        existing = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
        if not existing:
            # FIXED: Securing Section character mapping during upload
            sec_val = str(row[s_key]).strip().upper().replace("SEC ", "").replace("SECTION ", "") if s_key else "A"
            new_student = models.Student(erp_id="PENDING", roll_no=roll_no, name=str(row[n_key]).strip() if n_key else "Unknown", branch=row_branch, year=int(row[y_key]) if y_key else 1, section=sec_val, registered_device="UNREGISTERED", status="Approved", total_lectures=0)
            db.add(new_student); count += 1
    db.commit()
    return {"message": f"Successfully pre-approved {count} students!"}

@app.post("/register-student")
async def register(erp_id: str, roll_no: str, name: str, branch: str, year: int, section: str, device_id: str, db: Session = Depends(database.get_db)):
    if len(roll_no) != 13: raise HTTPException(status_code=400, detail="Roll number must be 13 digits")
    existing = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if existing:
        if existing.status == "Rejected": existing.name = name; existing.branch = branch; existing.year = year; existing.section = section; existing.registered_device = device_id; existing.status = "Pending"; db.commit(); return {"status": "success", "message": "Re-application submitted."}
        if existing.registered_device == "UNREGISTERED" or existing.registered_device == "PENDING_RESET": existing.erp_id = erp_id; existing.name = name; existing.branch = branch; existing.year = year; existing.section = section; existing.registered_device = device_id; existing.status = "Approved"; db.commit(); return {"status": "success", "message": "Device Linked Successfully!"}
        if existing.name.strip().lower() == name.strip().lower(): return {"status": "success", "message": "Welcome back!"}
        raise HTTPException(status_code=403, detail="Roll Number already registered to another device!")
    new_student = models.Student(erp_id=erp_id, name=name, roll_no=roll_no, branch=branch, year=year, section=section, registered_device=device_id, status="Pending", total_lectures=0)
    db.add(new_student); db.commit(); return {"status": "success", "message": "Registered! Awaiting approval."}

@app.get("/student-profile")
async def get_profile(roll_no: str, db: Session = Depends(database.get_db)):
    s = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if not s: return {"exists": False}
    leaves = db.query(models.LeaveRequest).filter_by(student_roll=roll_no, status="Approved").count()
    db.refresh(s); return {"exists": True, "status": s.status, "name": s.name, "branch": s.branch, "year": s.year, "section": s.section, "total_lectures": s.total_lectures, "official_leaves": leaves}

@app.get("/student-erp-data")
async def student_erp(roll_no: str, db: Session = Depends(database.get_db)):
    s = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if not s: raise HTTPException(status_code=404)
    subs = db.query(models.Subject).filter(or_(models.Subject.branch == s.branch, models.Subject.branch == "ALL"), models.Subject.year == s.year, models.Subject.section == s.section).all()
    data = []
    for sub in subs:
        att = db.query(models.Attendance).filter(models.Attendance.student_roll == roll_no, models.Attendance.subject_id == sub.id).count()
        m = db.query(models.ExamMarks).filter_by(student_roll=roll_no, subject_id=sub.id).first()
        data.append({"subject_name": sub.name, "code": sub.code, "attended": att, "total_held": sub.total_lectures_held or 0, "s1": m.sessional_1 if m else 0, "s2": m.sessional_2 if m else 0, "put": m.put_marks if m else 0})
    return {"subjects": data, "overall_attended": s.total_lectures}

@app.get("/student-attendance-history")
async def student_history(roll_no: str, db: Session = Depends(database.get_db)):
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if not student: raise HTTPException(status_code=404)
    subjects = db.query(models.Subject).filter(or_(models.Subject.branch == student.branch, models.Subject.branch == "ALL"), models.Subject.year == student.year, models.Subject.section == student.section).all()
    attendance_records = db.query(models.Attendance).filter(models.Attendance.student_roll == roll_no).order_by(models.Attendance.timestamp.desc()).all()
    history_by_date = {}
    for record in attendance_records:
        date_str = record.timestamp.strftime("%d-%m-%y")
        if date_str not in history_by_date: history_by_date[date_str] = []
        history_by_date[date_str].append(record.subject_id)
    approved_leaves = [l.date_req for l in db.query(models.LeaveRequest).filter_by(student_roll=roll_no, status="Approved").all()]
    for d in approved_leaves:
        if d not in history_by_date: history_by_date[d] = [] 
    return {"subjects": [{"id": s.id, "code": s.code} for s in subjects], "history": history_by_date, "approved_leaves": approved_leaves}

@app.post("/mark-attendance")
async def mark_attendance(roll_no: str, qr_content: str, subject_id: int, device_id: str, db: Session = Depends(database.get_db)):
    if subject_id not in active_sessions or active_sessions[subject_id] != qr_content: raise HTTPException(status_code=400, detail="QR Expired or Class Not Active!")
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if not student or student.status != "Approved": raise HTTPException(status_code=403, detail="Director Approval Required")
    if student.registered_device != device_id: raise HTTPException(status_code=403, detail="Device ID Security Mismatch")
    subject = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
    if not subject: raise HTTPException(status_code=404, detail="Subject not found")
    
    if (student.branch != subject.branch and subject.branch != "ALL") or student.year != subject.year or student.section != subject.section: 
        raise HTTPException(status_code=403, detail=f"Access Denied! Sub:{subject.branch} YR{subject.year} SEC{subject.section} | You:{student.branch} YR{student.year} SEC{student.section}")
        
    time_limit = datetime.utcnow() - timedelta(minutes=40)
    duplicate = db.query(models.Attendance).filter(models.Attendance.student_roll == roll_no, models.Attendance.subject_id == subject_id, models.Attendance.timestamp >= time_limit).first()
    if duplicate: raise HTTPException(status_code=400, detail="Duplicate: Wait 40m to scan this subject again")
    student.total_lectures += 1
    db.add(models.Attendance(student_roll=roll_no, subject_id=subject_id)); db.commit()
    return {"status": "Success"}

@app.post("/request-leave")
async def request_leave(roll_no: str, date_req: str, reason: str, db: Session = Depends(database.get_db)):
    db.add(models.LeaveRequest(student_roll=roll_no, date_req=date_req, reason=reason)); db.commit(); return {"message": "Leave requested"}
@app.get("/student-leaves")
async def get_student_leaves(roll_no: str, db: Session = Depends(database.get_db)): return db.query(models.LeaveRequest).filter_by(student_roll=roll_no).order_by(models.LeaveRequest.id.desc()).all()
@app.get("/pending-leaves")
async def get_pending_leaves(x_admin_key: str = Header(...), db: Session = Depends(database.get_db)):
    admin_branch = get_admin_branch(x_admin_key)
    leaves = db.query(models.LeaveRequest).filter_by(status="Pending").all(); res = []
    for l in leaves:
        s = db.query(models.Student).filter_by(roll_no=l.student_roll).first()
        if s and (admin_branch == "ALL" or s.branch == admin_branch): res.append({"id": l.id, "name": s.name, "roll_no": s.roll_no, "date_req": l.date_req, "reason": l.reason})
    return res
@app.post("/update-leave-status")
async def update_leave_status(leave_id: int, status: str, x_admin_key: str = Header(...), db: Session = Depends(database.get_db)):
    l = db.query(models.LeaveRequest).filter_by(id=leave_id).first()
    if l: l.status = status; db.commit()
    return {"message": "Success"}

@app.get("/pending-students")
async def get_pending(x_admin_key: str = Header(...), db: Session = Depends(database.get_db)):
    admin_branch = get_admin_branch(x_admin_key)
    query = db.query(models.Student).filter(models.Student.status == "Pending")
    if admin_branch != "ALL": query = query.filter(models.Student.branch == admin_branch)
    return query.all()

@app.post("/update-student-status")
async def update_status(roll_no: str, status: str, x_admin_key: str = Header(...), db: Session = Depends(database.get_db)):
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if student: student.status = status; db.commit()
    return {"message": f"Student {status}"}
@app.post("/reset-student-device")
async def reset_device(roll_no: str, x_admin_key: str = Header(...), db: Session = Depends(database.get_db)):
    student = db.query(models.Student).filter(models.Student.roll_no == roll_no).first()
    if student: student.registered_device = "PENDING_RESET"; db.commit(); return {"message": "Device reset successful"}
    raise HTTPException(status_code=404)
@app.post("/assign-subject")
async def assign_subject(name: str, code: str, branch: str, year: int, section: str, teacher_id: int, x_admin_key: str = Header(...), db: Session = Depends(database.get_db)):
    db.add(models.Subject(name=name, code=code, branch=branch, year=year, section=section, teacher_id=teacher_id, total_lectures_held=0)); db.commit()
    return {"message": "Subject Linked"}
@app.post("/add-teacher")
async def add_teacher(name: str, email: str, pin: str, role: str, department: str, x_admin_key: str = Header(...), db: Session = Depends(database.get_db)):
    db.add(models.Teacher(name=name, email=email, pin=pin, role=role, department=department)); db.commit()
    return {"message": "Teacher Added"}
@app.get("/get-teachers")
async def get_t(db: Session = Depends(database.get_db)): return db.query(models.Teacher).all()
@app.get("/all-students-analytics")
async def all_analytics(x_admin_key: str = Header(...), db: Session = Depends(database.get_db)):
    admin_branch = get_admin_branch(x_admin_key)
    query = db.query(models.Student)
    if admin_branch != "ALL": query = query.filter(models.Student.branch == admin_branch)
    return query.all()
@app.get("/teacher-subjects")
async def get_ts(teacher_id: int, db: Session = Depends(database.get_db)): return db.query(models.Subject).filter_by(teacher_id=teacher_id).all()
@app.get("/verify-teacher-pin")
async def verify_pin(teacher_id: int, entered_pin: str, db: Session = Depends(database.get_db)):
    t = db.query(models.Teacher).filter(models.Teacher.id == teacher_id).first()
    if t and t.pin == entered_pin: return {"status": "success", "role": t.role}
    raise HTTPException(status_code=401, detail="Invalid PIN")
@app.get("/generate-qr-string")
async def generate_qr(subject_id: int, is_new: bool = False, db: Session = Depends(database.get_db)):
    if is_new:
        sub = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
        if sub: sub.total_lectures_held = (sub.total_lectures_held or 0) + 1; db.commit()
    active_sessions[subject_id] = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    return {"current_qr_string": active_sessions[subject_id]}
@app.post("/stop-session")
async def stop_session(subject_id: int): active_sessions.pop(subject_id, None); return {"status": "stopped"}
@app.get("/live-attendance")
async def get_live(subject_id: int, db: Session = Depends(database.get_db)):
    records = db.query(models.Attendance).filter(models.Attendance.subject_id == subject_id).order_by(models.Attendance.id.desc()).limit(10).all()
    res = []
    for r in records:
        s = db.query(models.Student).filter(models.Student.roll_no == r.student_roll).first()
        if s: res.append({"name": s.name, "roll_no": s.roll_no, "branch": s.branch, "year": s.year, "section": s.section})
    return res
@app.get("/subject-roster")
async def get_roster(subject_id: int, db: Session = Depends(database.get_db)):
    sub = db.query(models.Subject).filter_by(id=subject_id).first()
    if not sub: raise HTTPException(status_code=404)
    if sub.branch == "ALL": students = db.query(models.Student).filter_by(year=sub.year, section=sub.section, status="Approved").all()
    else: students = db.query(models.Student).filter_by(branch=sub.branch, year=sub.year, section=sub.section, status="Approved").all()
    roster = []
    for s in students:
        m = db.query(models.ExamMarks).filter_by(student_roll=s.roll_no, subject_id=sub.id).first()
        att = db.query(models.Attendance).filter_by(student_roll=s.roll_no, subject_id=sub.id).count()
        roster.append({"name": s.name, "roll_no": s.roll_no, "s1": m.sessional_1 if m else 0, "s2": m.sessional_2 if m else 0, "put": m.put_marks if m else 0, "attended": att})
    return {"roster": roster, "total_held": sub.total_lectures_held or 0, "filename_data": f"{sub.branch}_Year{sub.year}_Sec{sub.section}_{sub.code}"}
@app.post("/update-marks")
async def update_m(roll_no: str, subject_id: int, s1: float, s2: float, put: float, db: Session = Depends(database.get_db)):
    m = db.query(models.ExamMarks).filter_by(student_roll=roll_no, subject_id=subject_id).first()
    if not m: m = models.ExamMarks(student_roll=roll_no, subject_id=subject_id); db.add(m)
    if s1 > 0: m.sessional_1 = s1; 
    if s2 > 0: m.sessional_2 = s2; 
    if put > 0: m.put_marks = put; 
    db.commit(); return {"message": "Saved"}

@app.get("/get-timetable")
async def get_tt(group_id: str, db: Session = Depends(database.get_db)):
    tt = db.query(models.Timetable).filter_by(branch_year=group_id).first()
    return {"exists": True, "grid_data": tt.grid_data} if tt else {"exists": False}
@app.post("/save-timetable")
async def save_tt(group_id: str, grid_data: str, x_admin_key: str = Header(...), db: Session = Depends(database.get_db)):
    tt = db.query(models.Timetable).filter_by(branch_year=group_id).first()
    if not tt: db.add(models.Timetable(branch_year=group_id, grid_data=grid_data))
    else: tt.grid_data = grid_data
    db.commit(); return {"status": "success"}