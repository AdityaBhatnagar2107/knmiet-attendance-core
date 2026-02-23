CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    full_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL, -- 'DIRECTOR', 'PROFESSOR', 'STUDENT'
    device_id VARCHAR(255) UNIQUE, -- The Proxy Killer: permanently bound to one phone
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE courses (
    course_id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    course_code VARCHAR(20) UNIQUE NOT NULL, -- e.g., 'CS-201'
    course_name VARCHAR(100) NOT NULL, -- e.g., 'Data Structures'
    professor_id UUID REFERENCES users (user_id), -- Links directly to the professor
    semester INTEGER NOT NULL
);

CREATE TABLE sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    course_id UUID REFERENCES courses (course_id),
    totp_secret VARCHAR(64) NOT NULL, -- The hidden cryptographic key generating the QR
    start_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP WITH TIME ZONE, -- Closes the loop when class ends
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE attendance_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    session_id UUID REFERENCES sessions (session_id),
    student_id UUID REFERENCES users (user_id),
    scanned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'PRESENT',
    UNIQUE (session_id, student_id) -- Prevents a student from scanning twice in one class
);