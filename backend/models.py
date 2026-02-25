from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    erp_id = Column(String, unique=True, index=True)      # NEW: ERP ID integration
    roll_no = Column(String, unique=True, index=True)
    name = Column(String)
    branch = Column(String)                               # NEW: e.g., 'CSE', 'IT'
    year = Column(Integer)                                # NEW: 1st, 2nd, 3rd, 4th year
    registered_device = Column(String)
    is_approved = Column(Boolean, default=False)
    total_lectures = Column(Integer, default=0)

class Teacher(Base):
    __tablename__ = "teachers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    pin = Column(String)
    role = Column(String, default="Faculty")              # NEW: 'HOD', 'Coordinator', 'Faculty'
    department = Column(String)                           # NEW: e.g., 'CSE' to restrict HOD view

class Subject(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    code = Column(String, unique=True)
    branch = Column(String)
    year = Column(Integer)
    teacher_id = Column(Integer, ForeignKey("teachers.id"))
    total_lectures_held = Column(Integer, default=0) # <--- ADD THIS LINE

    
class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True, index=True)
    student_roll = Column(String, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id")) # NEW: Tracks exactly WHICH class they attended
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class ExamMarks(Base):
    __tablename__ = "exam_marks"
    id = Column(Integer, primary_key=True, index=True)
    student_roll = Column(String, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    sessional_1 = Column(Float, default=0.0)              # Max 20
    sessional_2 = Column(Float, default=0.0)              # Max 40
    put_marks = Column(Float, default=0.0)                # Max 70

class Timetable(Base):
    __tablename__ = "timetable"
    id = Column(Integer, primary_key=True, index=True)
    branch = Column(String)                               # e.g., CSE
    year = Column(Integer)                                # e.g., 2
    day_of_week = Column(String)                          # Monday, Tuesday, etc.
    
    # Matching your specific KNMIET schedule with breaks
    p1_0905 = Column(String)                              # 09:05 am to 09:55 am
    p2_0955 = Column(String)                              # 09:55 am to 10:45 am
    # 10:45 to 10:55 is Bio Break (Hardcoded in UI later)
    p3_1055 = Column(String)                              # 10:55 am to 11:45 am
    p4_1145 = Column(String)                              # 11:45 am to 12:35 pm
    # 12:35 to 01:25 is Lunch (Hardcoded in UI later)
    p5_1325 = Column(String)                              # 01:25 pm to 02:15 pm
    p6_1415 = Column(String)                              # 02:15 pm to 03:05 pm
    # 03:05 to 03:15 is Bio Break
    p7_1515 = Column(String)                              # 03:15 pm to 04:05 pm
    p8_1605 = Column(String)                              # 04:05 pm to 04:55 pm