"""
Face Authentication Attendance System - Main Application
FastAPI Backend with Real-time Face Recognition
"""

import os
import sys
import base64
import io
import json
from datetime import datetime, timedelta
from typing import Optional, List
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from fastapi import FastAPI, HTTPException, Depends, Request, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

import config
from database import (
    get_db, SessionLocal, User, AttendanceRecord,
    UserOperations, AttendanceOperations, AuditOperations
)

# Try to import face_recognition version, fall back to OpenCV-only
try:
    import face_recognition
    from face_processor import FaceProcessor, CameraManager, SpoofDetector
    print("[OK] Using face_recognition library (dlib-based)")
except ImportError:
    from face_processor_cv import FaceProcessor, CameraManager, SpoofDetector
    print("[INFO] face_recognition not available, using OpenCV-only version")

# Initialize FastAPI app
app = FastAPI(
    title="FacePass - Smart Face Authentication",
    description="Your Face, Your Access. Real-time face recognition for employee attendance tracking.",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize face processor
face_processor = FaceProcessor()

# Pydantic models for API
class UserRegistration(BaseModel):
    employee_id: str
    name: str
    email: Optional[str] = None
    department: Optional[str] = None

class AttendanceResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    action: Optional[str] = None  # punch_in or punch_out
    timestamp: Optional[str] = None
    confidence: Optional[float] = None

class UserResponse(BaseModel):
    id: int
    employee_id: str
    name: str
    email: Optional[str]
    department: Optional[str]
    registered_at: str
    is_active: bool


def load_known_faces():
    """Load all registered face encodings into memory"""
    db = SessionLocal()
    try:
        users = UserOperations.get_all_active_users(db)
        user_data = [{
            'id': u.id,
            'face_encoding': u.face_encoding
        } for u in users if u.face_encoding]
        face_processor.load_known_faces(user_data)
        print(f"Loaded {len(user_data)} face encodings")
    finally:
        db.close()


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    load_known_faces()
    print("FacePass Started")


# ============ API Endpoints ============

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page"""
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return html_path.read_text()
    return """
    <html>
        <head><title>Face Auth Attendance</title></head>
        <body>
            <h1>Face Authentication Attendance System</h1>
            <p>Static files not found. Please ensure static/index.html exists.</p>
        </body>
    </html>
    """


@app.post("/api/register")
async def register_user(
    employee_id: str = Form(...),
    name: str = Form(...),
    email: str = Form(None),
    department: str = Form(None),
    face_image: UploadFile = File(...)
):
    """
    Register a new user with their face
    """
    print(f"\n[REGISTER] Starting registration for: {name} ({employee_id})")
    db = SessionLocal()
    try:
        # Check if employee ID already exists
        existing = UserOperations.get_user_by_employee_id(db, employee_id)
        if existing:
            print(f"[REGISTER] ERROR: Employee ID {employee_id} already registered")
            raise HTTPException(status_code=400, detail="Employee ID already registered. Please use a different ID.")
        
        # Check if email already exists (if email provided)
        if email:
            existing_email = UserOperations.get_user_by_email(db, email)
            if existing_email:
                print(f"[REGISTER] ERROR: Email {email} already registered")
                raise HTTPException(status_code=400, detail="Email already registered. Please use a different email.")
        
        # Read and process image
        image_bytes = await face_image.read()
        print(f"[REGISTER] Received image: {len(image_bytes)} bytes")
        
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            print(f"[REGISTER] ERROR: Could not decode image")
            raise HTTPException(status_code=400, detail="Invalid image format")
        
        print(f"[REGISTER] Image decoded: {image.shape}")
        
        # Detect face
        face_locations = face_processor.detect_faces(image)
        print(f"[REGISTER] Faces detected: {len(face_locations)}")
        
        if not face_locations:
            print(f"[REGISTER] ERROR: No face detected")
            raise HTTPException(status_code=400, detail="No face detected in image. Please ensure your face is clearly visible.")
        
        if len(face_locations) > 1:
            print(f"[REGISTER] ERROR: Multiple faces detected")
            raise HTTPException(status_code=400, detail="Multiple faces detected. Please provide image with single face")
        
        # Perform spoof check
        face_location = face_locations[0]
        print(f"[REGISTER] Face location: {face_location}")
        
        face_region = face_processor.extract_face_region(image, face_location)
        print(f"[REGISTER] Face region shape: {face_region.shape if face_region is not None else 'None'}")
        
        landmarks = face_processor.get_face_landmarks(image, face_location)
        spoof_result = face_processor.spoof_detector.check_liveness(face_region, landmarks)
        print(f"[REGISTER] Spoof check result: {spoof_result}")
        
        if not spoof_result['is_live']:
            print(f"[REGISTER] ERROR: Spoof detection failed")
            raise HTTPException(
                status_code=400, 
                detail=f"Spoof detection failed. Confidence: {spoof_result['confidence']:.2f}. Please use your real face with good lighting."
            )
        
        # Generate face encoding
        encoding = face_processor.encode_face(image, face_location)
        print(f"[REGISTER] Encoding generated: {encoding is not None}, length: {len(encoding) if encoding is not None else 0}")
        
        if encoding is None:
            print(f"[REGISTER] ERROR: Could not generate face encoding")
            raise HTTPException(status_code=400, detail="Could not generate face encoding. Please try again with a clearer image.")
        
        # Check if this face is already registered (duplicate face detection)
        existing_match = face_processor.identify_face(image, face_location)
        if existing_match and existing_match['confidence'] >= 0.7:  # High confidence match
            matched_user = UserOperations.get_user_by_id(db, existing_match['user_id'])
            if matched_user:
                print(f"[REGISTER] ERROR: Face already registered as {matched_user.name}")
                raise HTTPException(
                    status_code=400, 
                    detail=f"This face is already registered as '{matched_user.name}' (Employee ID: {matched_user.employee_id}). Each person can only register once."
                )
        
        # Save face image
        face_image_path = config.REGISTERED_FACES_DIR / f"{employee_id}.jpg"
        cv2.imwrite(str(face_image_path), face_region)
        
        # Create user in database
        encoding_bytes = encoding.tobytes()
        user = UserOperations.create_user(
            db,
            employee_id=employee_id,
            name=name,
            email=email,
            department=department,
            face_encoding=encoding_bytes,
            face_image_path=str(face_image_path)
        )
        
        # Reload faces
        load_known_faces()
        
        # Log event
        AuditOperations.log_event(
            db,
            event_type="registration",
            user_id=user.id,
            details=f"User {name} registered with employee ID {employee_id}"
        )
        
        return {
            "success": True,
            "message": f"User {name} registered successfully",
            "user_id": user.id,
            "spoof_confidence": spoof_result['confidence']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.post("/api/identify")
async def identify_face(face_image: UploadFile = File(...)):
    """
    Identify a face and mark attendance (punch-in or punch-out)
    """
    db = SessionLocal()
    try:
        # Read and process image
        image_bytes = await face_image.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="Invalid image format")
        
        # Detect face
        face_locations = face_processor.detect_faces(image)
        if not face_locations:
            return AttendanceResponse(
                success=False,
                message="No face detected"
            )
        
        face_location = face_locations[0]
        
        # Perform spoof check
        face_region = face_processor.extract_face_region(image, face_location)
        landmarks = face_processor.get_face_landmarks(image, face_location)
        spoof_result = face_processor.spoof_detector.check_liveness(face_region, landmarks)
        
        if not spoof_result['is_live']:
            AuditOperations.log_event(
                db,
                event_type="failed_spoof",
                details=f"Spoof detection failed with confidence {spoof_result['confidence']:.2f}"
            )
            return AttendanceResponse(
                success=False,
                message=f"Spoof detection failed. Please use real face."
            )
        
        # Identify face
        match = face_processor.identify_face(image, face_location)
        
        if not match:
            AuditOperations.log_event(
                db,
                event_type="unrecognized",
                details="Face detected but not recognized"
            )
            return AttendanceResponse(
                success=False,
                message="Face not recognized. Please register first."
            )
        
        # Get user
        user = UserOperations.get_user_by_id(db, match['user_id'])
        if not user:
            return AttendanceResponse(
                success=False,
                message="User not found in database"
            )
        
        # Check today's attendance
        today_record = AttendanceOperations.get_today_record(db, user.id)
        
        now = datetime.now()  # Use local time instead of UTC
        
        if today_record is None:
            # First punch of the day - Punch In
            record = AttendanceOperations.create_punch_in(
                db,
                user_id=user.id,
                confidence_score=match['confidence'],
                spoof_check_passed=True
            )
            action = "punch_in"
            message = f"Welcome {user.name}! Punched in successfully."
        elif today_record.punch_out_time is None:
            # Already punched in, check cooldown
            time_since_punch_in = now - today_record.punch_in_time
            if time_since_punch_in < timedelta(minutes=config.PUNCH_COOLDOWN_MINUTES):
                return AttendanceResponse(
                    success=False,
                    message=f"Please wait {config.PUNCH_COOLDOWN_MINUTES} minute(s) before punching out",
                    user_name=user.name
                )
            
            # Punch Out
            AttendanceOperations.create_punch_out(db, today_record.id)
            action = "punch_out"
            
            # Calculate work duration
            work_duration = now - today_record.punch_in_time
            hours = work_duration.seconds // 3600
            minutes = (work_duration.seconds % 3600) // 60
            message = f"Goodbye {user.name}! Worked for {hours}h {minutes}m today."
        else:
            # Already punched out - create new punch in
            record = AttendanceOperations.create_punch_in(
                db,
                user_id=user.id,
                confidence_score=match['confidence'],
                spoof_check_passed=True
            )
            action = "punch_in"
            message = f"Welcome back {user.name}! Punched in again."
        
        # Log event
        AuditOperations.log_event(
            db,
            event_type=action,
            user_id=user.id,
            details=f"{action} with confidence {match['confidence']:.2f}"
        )
        
        return AttendanceResponse(
            success=True,
            message=message,
            user_id=user.id,
            user_name=user.name,
            action=action,
            timestamp=now.isoformat(),
            confidence=match['confidence']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/api/users", response_model=List[UserResponse])
async def get_users():
    """Get all registered users"""
    db = SessionLocal()
    try:
        users = UserOperations.get_all_active_users(db)
        return [
            UserResponse(
                id=u.id,
                employee_id=u.employee_id,
                name=u.name,
                email=u.email,
                department=u.department,
                registered_at=u.registered_at.isoformat(),
                is_active=u.is_active
            )
            for u in users
        ]
    finally:
        db.close()


@app.get("/api/attendance/today")
async def get_today_attendance():
    """Get today's attendance records"""
    db = SessionLocal()
    try:
        records = AttendanceOperations.get_all_today_records(db)
        result = []
        for r in records:
            user = UserOperations.get_user_by_id(db, r.user_id)
            result.append({
                "id": r.id,
                "user_id": r.user_id,
                "user_name": user.name if user else "Unknown",
                "employee_id": user.employee_id if user else "Unknown",
                "punch_in": r.punch_in_time.isoformat() if r.punch_in_time else None,
                "punch_out": r.punch_out_time.isoformat() if r.punch_out_time else None,
                "confidence": r.confidence_score,
                "status": "Checked Out" if r.punch_out_time else "Checked In"
            })
        return result
    finally:
        db.close()


@app.get("/api/attendance/history/{employee_id}")
async def get_attendance_history(employee_id: str, limit: int = 30):
    """Get attendance history for an employee"""
    db = SessionLocal()
    try:
        user = UserOperations.get_user_by_employee_id(db, employee_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        records = AttendanceOperations.get_user_attendance_history(db, user.id, limit)
        return [
            {
                "id": r.id,
                "date": r.date.isoformat(),
                "punch_in": r.punch_in_time.isoformat() if r.punch_in_time else None,
                "punch_out": r.punch_out_time.isoformat() if r.punch_out_time else None,
                "confidence": r.confidence_score
            }
            for r in records
        ]
    finally:
        db.close()


@app.delete("/api/users/{employee_id}")
async def deactivate_user(employee_id: str):
    """Deactivate a user"""
    db = SessionLocal()
    try:
        user = UserOperations.get_user_by_employee_id(db, employee_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        UserOperations.deactivate_user(db, user.id)
        load_known_faces()
        
        AuditOperations.log_event(
            db,
            event_type="deactivation",
            user_id=user.id,
            details=f"User {user.name} deactivated"
        )
        
        return {"success": True, "message": f"User {user.name} deactivated"}
    finally:
        db.close()


@app.post("/api/analyze-frame")
async def analyze_frame(face_image: UploadFile = File(...)):
    """
    Analyze a single frame - used for real-time feedback
    Returns face detection results without marking attendance
    """
    try:
        image_bytes = await face_image.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            return {"faces": [], "error": "Invalid image"}
        
        results = face_processor.process_frame(
            image, 
            perform_identification=True,
            check_spoof=True
        )
        
        faces_data = []
        db = SessionLocal()
        try:
            for face in results['faces']:
                face_data = {
                    "location": face['location'],
                    "confidence": face.get('confidence', 0),
                    "is_recognized": face['user_id'] is not None,
                    "spoof_check": face.get('spoof_result', {})
                }
                
                if face['user_id']:
                    user = UserOperations.get_user_by_id(db, face['user_id'])
                    if user:
                        face_data["user_name"] = user.name
                        face_data["employee_id"] = user.employee_id
                
                faces_data.append(face_data)
        finally:
            db.close()
        
        return {"faces": faces_data}
        
    except Exception as e:
        return {"faces": [], "error": str(e)}


# Mount static files
static_path = Path(__file__).parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


if __name__ == "__main__":
    print("Starting FacePass...")
    print(f"Server running at http://localhost:{config.API_PORT}")
    uvicorn.run(
        "main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=config.DEBUG_MODE
    )
