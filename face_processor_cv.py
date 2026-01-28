"""
Face Detection, Recognition, and Processing Module (OpenCV-only version)
This is a fallback version that doesn't require dlib/face_recognition
Uses OpenCV DNN for face detection and simple template matching for recognition
"""

import cv2
import numpy as np
from scipy.spatial import distance
import pickle
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import hashlib
import config


class LightingNormalizer:
    """
    Handles varying lighting conditions through image preprocessing
    """
    
    def __init__(self):
        self.clahe = cv2.createCLAHE(
            clipLimit=config.CLAHE_CLIP_LIMIT,
            tileGridSize=config.CLAHE_GRID_SIZE
        )
    
    def normalize(self, image: np.ndarray) -> np.ndarray:
        """
        Apply lighting normalization to handle varying conditions
        """
        if len(image.shape) == 2:
            if config.ENABLE_CLAHE:
                return self.clahe.apply(image)
            elif config.ENABLE_HISTOGRAM_EQUALIZATION:
                return cv2.equalizeHist(image)
            return image
        
        # Convert BGR to LAB
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # Apply CLAHE to L channel
        if config.ENABLE_CLAHE:
            l = self.clahe.apply(l)
        elif config.ENABLE_HISTOGRAM_EQUALIZATION:
            l = cv2.equalizeHist(l)
        
        # Merge channels and convert back
        lab = cv2.merge([l, a, b])
        normalized = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        return normalized


class SpoofDetector:
    """
    Anti-spoofing detection using multiple techniques
    """
    
    def __init__(self):
        self.blink_counter = 0
        self.blink_threshold = config.BLINK_THRESHOLD
        
    def analyze_texture_lbp(self, face_image: np.ndarray) -> float:
        """
        Analyze face texture using Local Binary Patterns (LBP)
        """
        if len(face_image.shape) == 3:
            gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        else:
            gray = face_image
        
        # Resize for consistent analysis
        gray = cv2.resize(gray, (128, 128))
        
        # Calculate LBP
        lbp = self._calculate_lbp(gray)
        
        # Calculate histogram
        hist, _ = np.histogram(lbp.ravel(), bins=256, range=(0, 256))
        hist = hist.astype("float")
        hist /= (hist.sum() + 1e-7)
        
        # Calculate texture complexity (entropy)
        entropy = -np.sum(hist * np.log2(hist + 1e-7))
        
        # Normalize to 0-1 range
        texture_score = min(entropy / 8.0, 1.0)
        
        return texture_score
    
    def _calculate_lbp(self, image: np.ndarray, radius: int = 1, 
                       n_points: int = 8) -> np.ndarray:
        """Calculate Local Binary Pattern"""
        lbp = np.zeros_like(image)
        
        for i in range(radius, image.shape[0] - radius):
            for j in range(radius, image.shape[1] - radius):
                center = image[i, j]
                binary_string = 0
                
                for k in range(n_points):
                    angle = 2 * np.pi * k / n_points
                    x = int(round(i + radius * np.cos(angle)))
                    y = int(round(j + radius * np.sin(angle)))
                    
                    if image[x, y] >= center:
                        binary_string |= (1 << k)
                
                lbp[i, j] = binary_string
        
        return lbp
    
    def analyze_reflection(self, face_image: np.ndarray) -> float:
        """
        Analyze specular reflections to detect screens/photos
        """
        if len(face_image.shape) == 3:
            gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        else:
            gray = face_image
        
        # Detect bright spots
        _, bright_mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
        bright_ratio = np.sum(bright_mask > 0) / bright_mask.size
        reflection_score = 1.0 - min(bright_ratio * 10, 1.0)
        
        return reflection_score
    
    def analyze_blur(self, face_image: np.ndarray) -> float:
        """
        Analyze image blur - photos/screens often appear more uniform
        """
        if len(face_image.shape) == 3:
            gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        else:
            gray = face_image
        
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        # Higher variance = more detail = more likely real
        blur_score = min(laplacian_var / 500, 1.0)
        return blur_score
    
    def check_liveness(self, face_image: np.ndarray, 
                       face_landmarks: dict = None) -> Dict[str, any]:
        """
        Comprehensive liveness check
        """
        # Handle invalid input
        if face_image is None or face_image.size == 0:
            return {
                'texture_score': 1.0,
                'reflection_score': 1.0,
                'blur_score': 1.0,
                'confidence': 1.0,
                'is_live': True  # Default to live if we can't analyze
            }
        
        try:
            texture_score = self.analyze_texture_lbp(face_image)
            reflection_score = self.analyze_reflection(face_image)
            blur_score = self.analyze_blur(face_image)
        except Exception as e:
            print(f"Spoof detection error: {e}")
            return {
                'texture_score': 1.0,
                'reflection_score': 1.0,
                'blur_score': 1.0,
                'confidence': 1.0,
                'is_live': True  # Default to live on error
            }
        
        result = {
            'texture_score': texture_score,
            'reflection_score': reflection_score,
            'blur_score': blur_score,
        }
        
        # Combined confidence score
        confidence = (texture_score * 0.4 + reflection_score * 0.3 + blur_score * 0.3)
        result['confidence'] = confidence
        result['is_live'] = confidence >= config.LBP_THRESHOLD
        
        return result
    
    def reset(self):
        """Reset blink counter for new session"""
        self.blink_counter = 0


class FaceProcessorCV:
    """
    Main face processing class using OpenCV only (no dlib required)
    Uses OpenCV DNN face detector and histogram-based face matching
    """
    
    def __init__(self):
        self.lighting_normalizer = LightingNormalizer()
        self.spoof_detector = SpoofDetector()
        self.known_face_features: List[np.ndarray] = []
        self.known_face_ids: List[int] = []
        
        # Initialize face detector (Haar Cascade - works without extra models)
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # Try to load DNN face detector if available
        self.use_dnn = False
        try:
            model_path = Path(__file__).parent / "models"
            prototxt = model_path / "deploy.prototxt"
            caffemodel = model_path / "res10_300x300_ssd_iter_140000.caffemodel"
            
            if prototxt.exists() and caffemodel.exists():
                self.face_net = cv2.dnn.readNetFromCaffe(str(prototxt), str(caffemodel))
                self.use_dnn = True
                print("✓ Using DNN face detector")
        except Exception as e:
            print(f"DNN detector not available, using Haar Cascade: {e}")
        
    def detect_faces(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detect faces in an image
        Returns: List of face locations as (top, right, bottom, left)
        """
        normalized = self.lighting_normalizer.normalize(image)
        gray = cv2.cvtColor(normalized, cv2.COLOR_BGR2GRAY)
        
        if self.use_dnn:
            return self._detect_faces_dnn(normalized)
        else:
            return self._detect_faces_haar(gray)
    
    def _detect_faces_dnn(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Use DNN for face detection"""
        h, w = image.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(image, (300, 300)), 
            1.0, (300, 300), 
            (104.0, 177.0, 123.0)
        )
        self.face_net.setInput(blob)
        detections = self.face_net.forward()
        
        faces = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > 0.5:
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                left, top, right, bottom = box.astype(int)
                # Return as (top, right, bottom, left) to match face_recognition format
                faces.append((top, right, bottom, left))
        
        return faces
    
    def _detect_faces_haar(self, gray: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Use Haar Cascade for face detection"""
        detections = self.face_cascade.detectMultiScale(
            gray, 
            scaleFactor=1.1, 
            minNeighbors=5,
            minSize=(60, 60)
        )
        
        faces = []
        for (x, y, w, h) in detections:
            # Convert to (top, right, bottom, left) format
            faces.append((y, x + w, y + h, x))
        
        return faces
    
    def extract_face_features(self, image: np.ndarray, 
                              face_location: Tuple[int, int, int, int]) -> np.ndarray:
        """
        Extract features from a face for recognition
        Uses histogram-based features + edge features
        """
        top, right, bottom, left = face_location
        
        # Ensure bounds are valid
        h, w = image.shape[:2]
        top = max(0, min(top, h-1))
        bottom = max(0, min(bottom, h))
        left = max(0, min(left, w-1))
        right = max(0, min(right, w))
        
        if bottom <= top or right <= left:
            return None
            
        face_region = image[top:bottom, left:right]
        
        if face_region.size == 0 or face_region.shape[0] < 10 or face_region.shape[1] < 10:
            return None
        
        # Resize to fixed size
        face_resized = cv2.resize(face_region, (100, 100))
        
        # Normalize lighting
        face_normalized = self.lighting_normalizer.normalize(face_resized)
        
        # Convert to different color spaces for features
        gray = cv2.cvtColor(face_normalized, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(face_normalized, cv2.COLOR_BGR2HSV)
        
        features = []
        
        # 1. LBP histogram (texture features)
        lbp = self._calculate_lbp(gray)
        lbp_hist, _ = np.histogram(lbp.ravel(), bins=64, range=(0, 256))
        lbp_hist = lbp_hist.astype(np.float32)
        lbp_hist /= (lbp_hist.sum() + 1e-7)
        features.extend(lbp_hist)
        
        # 2. Histogram of grayscale (intensity distribution)
        gray_hist, _ = np.histogram(gray.ravel(), bins=32, range=(0, 256))
        gray_hist = gray_hist.astype(np.float32)
        gray_hist /= (gray_hist.sum() + 1e-7)
        features.extend(gray_hist)
        
        # 3. HOG-like features (edge direction histograms)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        magnitude = np.sqrt(gx**2 + gy**2)
        angle = np.arctan2(gy, gx) * 180 / np.pi
        angle[angle < 0] += 180
        
        # Histogram of gradient orientations
        hog_hist, _ = np.histogram(angle.ravel(), bins=18, range=(0, 180), 
                                    weights=magnitude.ravel())
        hog_hist = hog_hist.astype(np.float32)
        hog_hist /= (hog_hist.sum() + 1e-7)
        features.extend(hog_hist)
        
        # 4. Color histogram (hue channel for skin color)
        h_channel = hsv[:, :, 0]
        color_hist, _ = np.histogram(h_channel.ravel(), bins=18, range=(0, 180))
        color_hist = color_hist.astype(np.float32)
        color_hist /= (color_hist.sum() + 1e-7)
        features.extend(color_hist)
        
        return np.array(features, dtype=np.float32)
    
    def _calculate_lbp(self, image: np.ndarray) -> np.ndarray:
        """Calculate Local Binary Pattern for texture analysis"""
        lbp = np.zeros_like(image)
        
        for i in range(1, image.shape[0] - 1):
            for j in range(1, image.shape[1] - 1):
                center = image[i, j]
                code = 0
                code |= (image[i-1, j-1] >= center) << 7
                code |= (image[i-1, j] >= center) << 6
                code |= (image[i-1, j+1] >= center) << 5
                code |= (image[i, j+1] >= center) << 4
                code |= (image[i+1, j+1] >= center) << 3
                code |= (image[i+1, j] >= center) << 2
                code |= (image[i+1, j-1] >= center) << 1
                code |= (image[i, j-1] >= center) << 0
                lbp[i, j] = code
        
        return lbp
    
    def encode_face(self, image: np.ndarray, 
                    face_location: Tuple[int, int, int, int] = None) -> Optional[np.ndarray]:
        """
        Generate face encoding (feature vector)
        """
        if face_location is None:
            face_locations = self.detect_faces(image)
            if not face_locations:
                return None
            face_location = face_locations[0]
        
        return self.extract_face_features(image, face_location)
    
    def compare_faces(self, known_features: np.ndarray, 
                      face_features: np.ndarray) -> Tuple[bool, float]:
        """
        Compare two face feature vectors
        Uses histogram intersection + chi-squared distance
        """
        if known_features is None or face_features is None:
            return False, 0.0
        
        # Histogram intersection (higher = more similar)
        intersection = np.minimum(known_features, face_features).sum()
        max_intersection = np.minimum(known_features, known_features).sum()
        similarity = intersection / (max_intersection + 1e-7)
        
        # Threshold for matching
        is_match = similarity >= config.FACE_RECOGNITION_TOLERANCE
        
        return is_match, float(similarity)
    
    def identify_face(self, image: np.ndarray, 
                      face_location: Tuple[int, int, int, int] = None) -> Optional[Dict]:
        """
        Identify a face against known faces
        """
        if not self.known_face_features:
            return None
        
        if face_location is None:
            face_locations = self.detect_faces(image)
            if not face_locations:
                return None
            face_location = face_locations[0]
        
        face_features = self.extract_face_features(image, face_location)
        if face_features is None:
            return None
        
        # Compare with all known faces
        best_match_index = -1
        best_similarity = 0.0
        
        for i, known_features in enumerate(self.known_face_features):
            _, similarity = self.compare_faces(known_features, face_features)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match_index = i
        
        if best_match_index >= 0 and best_similarity >= config.FACE_RECOGNITION_TOLERANCE:
            return {
                'user_id': self.known_face_ids[best_match_index],
                'confidence': float(best_similarity),
                'distance': float(1 - best_similarity)
            }
        
        return None
    
    def load_known_faces(self, users: List[Dict]):
        """
        Load face features from user list
        """
        self.known_face_features = []
        self.known_face_ids = []
        
        # Expected feature size for OpenCV version
        expected_size = 132  # 64 LBP + 32 gray + 18 HOG + 18 color
        
        for user in users:
            if user.get('face_encoding'):
                try:
                    features = np.frombuffer(user['face_encoding'], dtype=np.float32)
                    if len(features) == expected_size:
                        self.known_face_features.append(features)
                        self.known_face_ids.append(user['id'])
                        print(f"  [OK] Loaded encoding for user {user['id']}")
                    else:
                        print(f"  [SKIP] User {user['id']} has incompatible encoding size ({len(features)} vs expected {expected_size})")
                except Exception as e:
                    print(f"  [ERROR] Failed to load encoding for user {user.get('id')}: {e}")
    
    def extract_face_region(self, image: np.ndarray, 
                            face_location: Tuple[int, int, int, int],
                            margin: float = 0.2) -> np.ndarray:
        """
        Extract face region from image with margin
        """
        top, right, bottom, left = face_location
        height = bottom - top
        width = right - left
        
        margin_h = int(height * margin)
        margin_w = int(width * margin)
        
        top = max(0, top - margin_h)
        bottom = min(image.shape[0], bottom + margin_h)
        left = max(0, left - margin_w)
        right = min(image.shape[1], right + margin_w)
        
        return image[top:bottom, left:right]
    
    def get_face_landmarks(self, image: np.ndarray, 
                           face_location: Tuple[int, int, int, int] = None) -> dict:
        """
        Get basic facial landmarks (empty dict in CV-only version)
        Full landmarks require dlib
        """
        return {}
    
    def draw_face_box(self, image: np.ndarray, 
                      face_location: Tuple[int, int, int, int],
                      name: str = None, 
                      confidence: float = None,
                      color: Tuple[int, int, int] = (0, 255, 0)) -> np.ndarray:
        """
        Draw face bounding box with optional label
        """
        top, right, bottom, left = face_location
        
        cv2.rectangle(image, (left, top), (right, bottom), color, 2)
        
        if name or confidence:
            label = name or ""
            if confidence:
                label += f" ({confidence:.1%})"
            
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
            cv2.rectangle(
                image, 
                (left, bottom - 25), 
                (left + label_size[0] + 10, bottom),
                color, 
                cv2.FILLED
            )
            cv2.putText(
                image, label,
                (left + 5, bottom - 7),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6, (0, 0, 0), 1
            )
        
        return image
    
    def process_frame(self, frame: np.ndarray, 
                      perform_identification: bool = True,
                      check_spoof: bool = True) -> Dict:
        """
        Process a single frame for face detection, recognition, and spoof check
        """
        annotated = frame.copy()
        results = {'faces': [], 'annotated_frame': annotated}
        
        face_locations = self.detect_faces(frame)
        
        for face_location in face_locations:
            face_result = {
                'location': face_location,
                'user_id': None,
                'name': None,
                'confidence': 0.0,
                'spoof_result': None
            }
            
            if check_spoof and config.SPOOF_DETECTION_ENABLED:
                face_region = self.extract_face_region(frame, face_location)
                if face_region.size > 0:
                    face_result['spoof_result'] = self.spoof_detector.check_liveness(face_region)
            
            if perform_identification:
                match = self.identify_face(frame, face_location)
                if match:
                    face_result['user_id'] = match['user_id']
                    face_result['confidence'] = match['confidence']
            
            results['faces'].append(face_result)
            
            if face_result['user_id']:
                color = (0, 255, 0)
            else:
                color = (0, 0, 255)
            
            annotated = self.draw_face_box(
                annotated, 
                face_location,
                face_result.get('name'),
                face_result.get('confidence'),
                color
            )
        
        results['annotated_frame'] = annotated
        return results


class CameraManager:
    """
    Manages camera input with proper resource handling
    """
    
    def __init__(self, camera_index: int = None):
        self.camera_index = camera_index or config.CAMERA_INDEX
        self.cap = None
        
    def start(self) -> bool:
        """Start camera capture"""
        self.cap = cv2.VideoCapture(self.camera_index)
        
        if not self.cap.isOpened():
            return False
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, config.FPS)
        
        return True
    
    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read a frame from camera"""
        if self.cap is None:
            return False, None
        return self.cap.read()
    
    def stop(self):
        """Stop camera capture"""
        if self.cap:
            self.cap.release()
            self.cap = None
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


# Use this as the FaceProcessor
FaceProcessor = FaceProcessorCV
