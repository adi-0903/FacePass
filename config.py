"""
Configuration settings for FacePass
"""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent

# Database
DATABASE_URL = f"sqlite:///{BASE_DIR}/attendance.db"

# Face Recognition Settings
FACE_RECOGNITION_TOLERANCE = 0.5  # Lower = more strict (0.4-0.6 typical)
FACE_ENCODING_MODEL = "large"  # 'small' or 'large' (large is more accurate)
FACE_DETECTION_MODEL = "hog"  # 'hog' (faster) or 'cnn' (more accurate, GPU)

# Camera Settings
CAMERA_INDEX = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
FPS = 30

# Spoof Detection Settings
SPOOF_DETECTION_ENABLED = True
BLINK_THRESHOLD = 0.25  # Eye aspect ratio threshold
LBP_THRESHOLD = 0.4  # Lower threshold for easier registration (was 0.7)
MIN_BLINKS_FOR_LIVENESS = 2  # Minimum blinks required during registration

# Lighting Normalization
ENABLE_HISTOGRAM_EQUALIZATION = True
ENABLE_CLAHE = True
CLAHE_CLIP_LIMIT = 2.0
CLAHE_GRID_SIZE = (8, 8)

# Attendance Settings
PUNCH_COOLDOWN_MINUTES = 1  # Minimum time between punch-in and punch-out
WORKDAY_START_HOUR = 6  # 6 AM
WORKDAY_END_HOUR = 22  # 10 PM

# Directories
FACE_ENCODINGS_DIR = BASE_DIR / "face_encodings"
REGISTERED_FACES_DIR = BASE_DIR / "registered_faces"
LOGS_DIR = BASE_DIR / "logs"

# Create directories if they don't exist
for directory in [FACE_ENCODINGS_DIR, REGISTERED_FACES_DIR, LOGS_DIR]:
    directory.mkdir(exist_ok=True)

# API Settings
API_HOST = "0.0.0.0"
API_PORT = 8000
DEBUG_MODE = True
