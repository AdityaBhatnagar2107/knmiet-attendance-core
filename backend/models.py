from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
from .database import Base

class Teacher(Base):
    __tablename__ = "teachers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    pin = Column(String, default="0000")
    # NEW: Stores the time when a teacher is allowed to try again after lockout
    lockout_until = Column(DateTime, nullable=True)

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    roll_no = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    is_approved = Column(Boolean, default=False)
    # NEW: Locks the student account to a single unique device
    registered_device = Column(String, unique=True, nullable=True) 
    # NEW: Keeps track of total verified attendance
    total_lectures = Column(Integer, default=0)

class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True, index=True)
    student_roll = Column(String)
    class_name = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)