"""
Database models and operations for FacePass
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Boolean, LargeBinary, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import config

engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """User model for registered employees"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True)
    department = Column(String(100))
    face_encoding = Column(LargeBinary)  # Stored as numpy array bytes
    face_image_path = Column(String(255))
    registered_at = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    
    # Relationship with attendance records
    attendance_records = relationship("AttendanceRecord", back_populates="user")


class AttendanceRecord(Base):
    """Attendance record model"""
    __tablename__ = "attendance_records"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime, default=datetime.now)
    punch_in_time = Column(DateTime)
    punch_out_time = Column(DateTime)
    confidence_score = Column(Float)  # Face recognition confidence
    spoof_check_passed = Column(Boolean, default=True)
    notes = Column(String(255))
    
    # Relationship with user
    user = relationship("User", back_populates="attendance_records")


class AuditLog(Base):
    """Audit log for tracking system events"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.now)
    event_type = Column(String(50))  # registration, punch_in, punch_out, failed_attempt
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    details = Column(String(500))
    ip_address = Column(String(50))


def init_db():
    """Initialize the database tables"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Database operations
class UserOperations:
    @staticmethod
    def create_user(db, employee_id: str, name: str, email: str = None, 
                    department: str = None, face_encoding: bytes = None,
                    face_image_path: str = None):
        """Create a new user"""
        user = User(
            employee_id=employee_id,
            name=name,
            email=email,
            department=department,
            face_encoding=face_encoding,
            face_image_path=face_image_path
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def get_user_by_employee_id(db, employee_id: str):
        """Get user by employee ID"""
        return db.query(User).filter(User.employee_id == employee_id).first()
    
    @staticmethod
    def get_user_by_id(db, user_id: int):
        """Get user by ID"""
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    def get_user_by_email(db, email: str):
        """Get user by email"""
        return db.query(User).filter(User.email == email).first()
    
    @staticmethod
    def get_all_active_users(db):
        """Get all active users"""
        return db.query(User).filter(User.is_active == True).all()
    
    @staticmethod
    def update_user_encoding(db, user_id: int, face_encoding: bytes):
        """Update user's face encoding"""
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.face_encoding = face_encoding
            db.commit()
            db.refresh(user)
        return user
    
    @staticmethod
    def deactivate_user(db, user_id: int):
        """Deactivate a user"""
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.is_active = False
            db.commit()
        return user


class AttendanceOperations:
    @staticmethod
    def create_punch_in(db, user_id: int, confidence_score: float, 
                        spoof_check_passed: bool = True):
        """Create a punch-in record"""
        record = AttendanceRecord(
            user_id=user_id,
            punch_in_time=datetime.now(),
            confidence_score=confidence_score,
            spoof_check_passed=spoof_check_passed
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    
    @staticmethod
    def create_punch_out(db, record_id: int):
        """Update record with punch-out time"""
        record = db.query(AttendanceRecord).filter(AttendanceRecord.id == record_id).first()
        if record:
            record.punch_out_time = datetime.now()
            db.commit()
            db.refresh(record)
        return record
    
    @staticmethod
    def get_today_record(db, user_id: int):
        """Get today's attendance record for a user"""
        today = datetime.now().date()
        return db.query(AttendanceRecord).filter(
            AttendanceRecord.user_id == user_id,
            AttendanceRecord.date >= datetime(today.year, today.month, today.day)
        ).order_by(AttendanceRecord.id.desc()).first()
    
    @staticmethod
    def get_user_attendance_history(db, user_id: int, limit: int = 30):
        """Get attendance history for a user"""
        return db.query(AttendanceRecord).filter(
            AttendanceRecord.user_id == user_id
        ).order_by(AttendanceRecord.date.desc()).limit(limit).all()
    
    @staticmethod
    def get_all_today_records(db):
        """Get all attendance records for today"""
        today = datetime.now().date()
        return db.query(AttendanceRecord).filter(
            AttendanceRecord.date >= datetime(today.year, today.month, today.day)
        ).all()


class AuditOperations:
    @staticmethod
    def log_event(db, event_type: str, user_id: int = None, 
                  details: str = None, ip_address: str = None):
        """Log an audit event"""
        log = AuditLog(
            event_type=event_type,
            user_id=user_id,
            details=details,
            ip_address=ip_address
        )
        db.add(log)
        db.commit()
        return log


# Initialize database on import
init_db()
