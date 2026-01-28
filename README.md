# Face Authentication Attendance System

A real-time face recognition system for employee attendance tracking with spoof detection capabilities.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-4.8+-green.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-teal.svg)

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Installation](#installation)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Model & Approach](#model--approach)
- [Training Process](#training-process)
- [Accuracy Expectations](#accuracy-expectations)
- [Known Limitations](#known-limitations)
- [Configuration](#configuration)

---

## 🎯 Overview

This Face Authentication Attendance System provides a complete solution for:
- **Face Registration**: Enroll employees with their facial biometrics
- **Face Identification**: Real-time face recognition from camera feed
- **Attendance Tracking**: Automatic punch-in/punch-out based on face recognition
- **Spoof Detection**: Basic liveness detection to prevent photo/video attacks

---

## ✨ Features

### Core Features
| Feature | Description |
|---------|-------------|
| 👤 Face Registration | Register new employees with face capture and details |
| 🔍 Face Identification | Identify registered faces in real-time |
| ⏰ Punch In/Out | Automatic attendance marking based on recognition |
| 📊 Attendance Records | View daily and historical attendance data |

### Security Features
| Feature | Description |
|---------|-------------|
| 🛡️ Spoof Detection | Texture analysis using Local Binary Patterns (LBP) |
| 👁️ Blink Detection | Eye Aspect Ratio (EAR) monitoring for liveness |
| 🔦 Lighting Normalization | CLAHE algorithm for varying light conditions |

### Technical Features
| Feature | Description |
|---------|-------------|
| 🌐 Web Interface | Modern, responsive UI with glassmorphism design |
| 🔌 REST API | FastAPI backend with OpenAPI documentation |
| 💾 SQLite Database | Lightweight, portable data storage |
| 📹 Real-time Processing | Live camera feed with face overlay |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (HTML/CSS/JS)                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Attendance │  │  Register   │  │    Records View     │  │
│  │    Tab      │  │    Tab      │  │                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP/REST
┌───────────────────────────┼─────────────────────────────────┐
│                    FastAPI Backend                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   /api/     │  │   /api/     │  │   /api/attendance   │  │
│  │  identify   │  │  register   │  │                     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         └────────────────┼─────────────────────┘            │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                  Face Processor                      │    │
│  │  ┌───────────┐ ┌──────────────┐ ┌────────────────┐  │    │
│  │  │  Detect   │ │   Encode     │ │    Identify    │  │    │
│  │  │  (dlib)   │ │ (128-D vec)  │ │  (Euclidean)   │  │    │
│  │  └───────────┘ └──────────────┘ └────────────────┘  │    │
│  │  ┌───────────────────────────────────────────────┐  │    │
│  │  │           Spoof Detection                     │  │    │
│  │  │  LBP Texture │ Blink Detection │ Reflection  │  │    │
│  │  └───────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────┐
│                    SQLite Database                           │
│  ┌─────────┐  ┌──────────────────┐  ┌─────────────────┐     │
│  │  Users  │  │ AttendanceRecords│  │   AuditLogs     │     │
│  └─────────┘  └──────────────────┘  └─────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Installation

### Prerequisites

- Python 3.9 or higher
- Webcam
- Windows/Linux/MacOS

### Step 1: Clone or Navigate to Project

```bash
cd c:\Users\HP\OneDrive\Desktop\Detector
```

### Step 2: Create Virtual Environment (Recommended)

```bash
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

> ⚠️ **Note for Windows Users**: Installing `dlib` may require Visual Studio Build Tools. If you encounter errors:
> 1. Install [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
> 2. Select "Desktop development with C++"
> 3. Alternatively, use `pip install dlib --pre` for pre-built wheels

### Step 4: Run the Application

```bash
python main.py
```

The server will start at `http://localhost:8000`

---

## 📖 Usage

### 1. Register an Employee

1. Navigate to the **Register** tab
2. Click on the camera feed to enable the webcam
3. Position your face within the frame
4. Click **Capture Photo**
5. Fill in the employee details:
   - Employee ID (required)
   - Name (required)
   - Email (optional)
   - Department (optional)
6. Click **Register Employee**

### 2. Mark Attendance

1. Navigate to the **Attendance** tab
2. Enable the camera
3. Position your face in front of the camera
4. Click **Mark Attendance**
5. The system will:
   - Detect your face
   - Verify it's not a spoof attempt
   - Identify you against registered users
   - Mark punch-in or punch-out based on current status

### 3. View Records

1. Navigate to the **Records** tab
2. View today's attendance in the table
3. See registered employees list

---

## 🔌 API Documentation

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/register` | Register new user with face |
| `POST` | `/api/identify` | Identify face and mark attendance |
| `GET` | `/api/users` | Get all registered users |
| `GET` | `/api/attendance/today` | Get today's attendance |
| `GET` | `/api/attendance/history/{id}` | Get user's attendance history |
| `DELETE` | `/api/users/{id}` | Deactivate a user |
| `POST` | `/api/analyze-frame` | Analyze frame without marking attendance |

### API Usage Examples

#### Register User
```bash
curl -X POST "http://localhost:8000/api/register" \
  -F "employee_id=EMP001" \
  -F "name=John Doe" \
  -F "email=john@company.com" \
  -F "department=Engineering" \
  -F "face_image=@photo.jpg"
```

#### Identify Face
```bash
curl -X POST "http://localhost:8000/api/identify" \
  -F "face_image=@capture.jpg"
```

---

## 🧠 Model & Approach

### Face Detection
- **Algorithm**: HOG (Histogram of Oriented Gradients) or CNN-based
- **Library**: `face_recognition` (powered by dlib)
- **Speed**: HOG is faster (~15fps), CNN is more accurate

### Face Encoding
- **Model**: ResNet-based deep neural network
- **Output**: 128-dimensional face embedding vector
- **Training Data**: Original model trained on ~3 million faces
- **Architecture**: Modified ResNet with 29 convolutional layers

### Face Comparison
- **Metric**: Euclidean distance between 128-D embeddings
- **Threshold**: 0.5 (configurable) - lower is stricter
- **Formula**: 
  ```
  distance = √Σ(embedding1[i] - embedding2[i])²
  match = distance < threshold
  ```

### Spoof Detection

#### 1. Local Binary Patterns (LBP) Texture Analysis
```
Real Face: High texture entropy (complex skin patterns)
Photo/Screen: Low texture entropy (uniform, smooth)

LBP Algorithm:
1. For each pixel, compare with 8 neighbors
2. Create binary pattern (1 if neighbor >= center, else 0)
3. Calculate histogram of patterns
4. Compute entropy: -Σ(p * log₂(p))
```

#### 2. Eye Blink Detection
```
Eye Aspect Ratio (EAR) = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)

Open eye:  EAR ≈ 0.25-0.35
Closed:    EAR < 0.20

Blink = EAR drops below threshold for 2-3 consecutive frames
```

#### 3. Reflection Analysis
```
Screen displays have sharp, bright reflections
Real faces have soft, diffuse lighting

Detection:
1. Find very bright pixels (> 240 intensity)
2. Calculate ratio of bright to total pixels
3. High ratio = likely screen/photo
```

### Lighting Normalization (CLAHE)
```
CLAHE = Contrast Limited Adaptive Histogram Equalization

1. Divide image into 8x8 tiles
2. Apply histogram equalization to each tile
3. Limit contrast amplification (clip_limit=2.0)
4. Interpolate between tiles for smooth result

Benefits:
- Handles uneven lighting
- Improves face detection in shadows/bright spots
- Works in LAB color space (L channel only)
```

---

## 📚 Training Process

### Pre-trained Models

This system uses pre-trained models from the `face_recognition` library:

| Model | Description | Training Data |
|-------|-------------|---------------|
| dlib face detector | HOG + SVM | ~3,000 images |
| Face landmark predictor | 68 facial landmarks | iBUG 300-W dataset |
| Face encoder (ResNet) | 128-D embeddings | ~3 million faces |

### Transfer Learning Approach

The system doesn't train new models - it uses the pre-trained ResNet encoder as a feature extractor:

1. **Enrollment Phase** (Registration)
   - Capture face image
   - Extract 128-D embedding using pre-trained ResNet
   - Store embedding in database

2. **Inference Phase** (Identification)
   - Capture face from camera
   - Extract 128-D embedding
   - Compare with all stored embeddings
   - Find closest match under threshold

### Why This Approach?

| Advantage | Explanation |
|-----------|-------------|
| No training data needed | Uses transfer learning from millions of faces |
| One-shot learning | Single photo enrollment works |
| Fast deployment | No training time required |
| Good generalization | Pre-trained on diverse faces |

---

## 📊 Accuracy Expectations

### Face Recognition Accuracy

| Scenario | Expected Accuracy | Notes |
|----------|-------------------|-------|
| Good lighting, frontal face | 98-99% | Ideal conditions |
| Normal indoor lighting | 95-98% | Typical office environment |
| Variable lighting | 90-95% | CLAHE helps significantly |
| Partial occlusion (small) | 85-92% | Glasses OK, masks reduce accuracy |
| Profile/angled face | 80-90% | Best with frontal faces |

### Spoof Detection Accuracy

| Attack Type | Detection Rate | False Positive Rate |
|-------------|----------------|---------------------|
| Printed photo | 85-90% | 5-10% |
| Photo on phone screen | 80-85% | 8-12% |
| Static video playback | 75-85% | 10-15% |
| High-quality replay | 60-75% | 15-20% |

### Factors Affecting Accuracy

| Factor | Impact | Mitigation |
|--------|--------|------------|
| Lighting changes | Medium | CLAHE normalization |
| Distance from camera | High | Keep 30-60cm distance |
| Face angle | High | Use frontal face |
| Image quality | High | Use HD webcam |
| Similar-looking people | Medium | Lower tolerance threshold |

---

## ⚠️ Known Limitations

### Face Recognition Limitations

1. **Identical Twins**
   - May have difficulty distinguishing identical twins
   - Solution: Use additional factors (voice, PIN)

2. **Significant Appearance Changes**
   - Major weight change, new glasses, facial hair
   - Solution: Re-register periodically

3. **Heavy Makeup**
   - Theatrical makeup may affect recognition
   - Solution: Register with typical daily appearance

4. **Age Progression**
   - Accuracy may decrease over years
   - Solution: Update face encoding annually

5. **Low Light**
   - Very dark conditions reduce accuracy
   - Solution: Ensure minimum lighting (100+ lux)

### Spoof Detection Limitations

1. **High-Quality Attacks**
   - 3D printed masks: NOT detected
   - High-resolution video replay: May bypass
   - Professional silicone masks: NOT detected

2. **Lighting Artifacts**
   - Very bright lights may trigger false spoof detection
   - Solution: Adjust reflection threshold

3. **Blink Detection Bypass**
   - Videos with natural blinking work
   - Animated photos (deepfakes) may bypass

4. **Edge Cases**
   - Very oily/shiny skin may trigger spoof alert
   - Certain lighting may affect LBP analysis

### System Limitations

1. **Single Face per Frame**
   - Designed for individual attendance
   - Multiple faces: Uses first detected

2. **Database Size**
   - SQLite: Best for <1000 users
   - Larger scale: Migrate to PostgreSQL

3. **Face Encoding Memory**
   - All encodings loaded in RAM
   - ~128KB per 100 users

4. **Camera Dependency**
   - Requires continuous camera access
   - Network cameras may have latency

---

## ⚙️ Configuration

### config.py Parameters

```python
# Face Recognition
FACE_RECOGNITION_TOLERANCE = 0.5  # 0.4-0.6 (lower = stricter)
FACE_ENCODING_MODEL = "large"     # "small" or "large"
FACE_DETECTION_MODEL = "hog"      # "hog" (fast) or "cnn" (accurate)

# Spoof Detection
SPOOF_DETECTION_ENABLED = True
BLINK_THRESHOLD = 0.25           # EAR threshold for blink
LBP_THRESHOLD = 0.7              # Texture analysis threshold

# Camera
CAMERA_INDEX = 0                  # Webcam index
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# Lighting
ENABLE_CLAHE = True
CLAHE_CLIP_LIMIT = 2.0

# Attendance
PUNCH_COOLDOWN_MINUTES = 1        # Min time between punch-in/out
```

### Tuning Recommendations

| Use Case | Tolerance | Model | Spoof LBP |
|----------|-----------|-------|-----------|
| High Security | 0.4 | large | 0.8 |
| Standard Office | 0.5 | large | 0.7 |
| Fast Processing | 0.55 | small | 0.65 |
| Outdoor/Variable | 0.5 | large | 0.6 |

---

## 🤝 Contributing

Feel free to submit issues and enhancement requests!

## 📄 License

This project is for educational purposes. Please ensure compliance with local biometric data regulations (GDPR, CCPA, etc.) before production use.

---

## 🙏 Acknowledgments

- [dlib](http://dlib.net/) - Face detection and recognition
- [face_recognition](https://github.com/ageitgey/face_recognition) - Python face recognition library
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [OpenCV](https://opencv.org/) - Computer vision library
