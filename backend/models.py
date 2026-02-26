from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from .database import Base

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    erp_id = Column(String, unique=True, index=True)
    roll_no = Column(String, unique=True, index=True)
    name = Column(String)
    branch = Column(String)
    year = Column(Integer)
    # NEW: Section added for Enterprise Scaling
    section = Column(String) 
    registered_device = Column(String)
    # NEW: Status string replaces is_approved boolean
    status = Column(String, default="Pending") 
    total_lectures = Column(Integer, default=0)

class Teacher(Base):
    __tablename__ = "teachers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True)
    pin = Column(String)
    role = Column(String)
    department = Column(String)

class Subject(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    code = Column(String)
    branch = Column(String)
    year = Column(Integer)
    # NEW: Section isolation for subjects
    section = Column(String) 
    teacher_id = Column(Integer)
    total_lectures_held = Column(Integer, default=0)

class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True, index=True)
    student_roll = Column(String, index=True)
    subject_id = Column(Integer, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class ExamMarks(Base):
    __tablename__ = "exam_marks"
    id = Column(Integer, primary_key=True, index=True)
    student_roll = Column(String, index=True)
    subject_id = Column(Integer, index=True)
    sessional_1 = Column(Float, default=0)
    sessional_2 = Column(Float, default=0)
    put_marks = Column(Float, default=0)

class Timetable(Base):
    __tablename__ = "timetable"
    id = Column(Integer, primary_key=True, index=True)
    branch_year = Column(String, unique=True)
    grid_data = Column(String)