from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, Text
from .database import Base

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    erp_id = Column(String, unique=True, index=True)
    roll_no = Column(String, unique=True, index=True)
    name = Column(String)
    branch = Column(String)
    year = Column(Integer)
    registered_device = Column(String)
    is_approved = Column(Boolean, default=False)
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
    code = Column(String, unique=True)
    branch = Column(String)
    year = Column(Integer)
    teacher_id = Column(Integer, ForeignKey("teachers.id"))
    total_lectures_held = Column(Integer, default=0)

class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True, index=True)
    student_roll = Column(String, ForeignKey("students.roll_no"))
    subject_id = Column(Integer, ForeignKey("subjects.id"))

class ExamMarks(Base):
    __tablename__ = "exam_marks"
    id = Column(Integer, primary_key=True, index=True)
    student_roll = Column(String, ForeignKey("students.roll_no"))
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    sessional_1 = Column(Float, default=0.0)
    sessional_2 = Column(Float, default=0.0)
    put_marks = Column(Float, default=0.0)

class Timetable(Base):
    __tablename__ = "master_timetables"
    id = Column(Integer, primary_key=True, index=True)
    branch_year = Column(String, unique=True, index=True) 
    grid_data = Column(Text)