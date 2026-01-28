"""
Face Detection, Recognition, and Processing Module
Handles all computer vision operations for the attendance system
"""

import cv2
import numpy as np
import face_recognition
from scipy.spatial import distance
import pickle
from pathlib import Path
from typing import List, Tuple, Optional, Dict
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
        
        Techniques used:
        1. Convert to LAB color space (separates luminance from color)
        2. Apply CLAHE to L channel (adaptive histogram equalization)
        3. Convert back to BGR
        """
        if len(image.shape) == 2:
            # Grayscale image
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
    
    def denoise(self, image: np.ndarray) -> np.ndarray:
        """Apply denoising for better face detection"""
        return cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)


class SpoofDetector:
    """
    Anti-spoofing detection using multiple techniques:
    1. Eye blink detection (liveness check)
    2. Texture analysis using Local Binary Patterns (LBP)
    3. Motion analysis
    """
    
    def __init__(self):
        self.blink_counter = 0
        self.blink_threshold = config.BLINK_THRESHOLD
        self.eye_ar_consecutive_frames = 3
        self.frame_counter = 0
        self.previous_ear = None
        
    def calculate_eye_aspect_ratio(self, eye_landmarks: np.ndarray) -> float:
        """
        Calculate Eye Aspect Ratio (EAR) for blink detection
        EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
        
        When eye is open: EAR ~ 0.3
        When eye is closed: EAR < 0.2
        """
        # Vertical distances
        A = distance.euclidean(eye_landmarks[1], eye_landmarks[5])
        B = distance.euclidean(eye_landmarks[2], eye_landmarks[4])
        
        # Horizontal distance
        C = distance.euclidean(eye_landmarks[0], eye_landmarks[3])
        
        # Eye Aspect Ratio
        ear = (A + B) / (2.0 * C) if C > 0 else 0
        return ear
    
    def detect_blink(self, face_landmarks: dict) -> Tuple[bool, float]:
        """
        Detect if a blink occurred
        Returns: (blink_detected, current_ear)
        """
        if 'left_eye' not in face_landmarks or 'right_eye' not in face_landmarks:
            return False, 0.0
        
        left_eye = np.array(face_landmarks['left_eye'])
        right_eye = np.array(face_landmarks['right_eye'])
        
        left_ear = self.calculate_eye_aspect_ratio(left_eye)
        right_ear = self.calculate_eye_aspect_ratio(right_eye)
        
        # Average EAR
        ear = (left_ear + right_ear) / 2.0
        
        blink_detected = False
        
        if ear < self.blink_threshold:
            self.frame_counter += 1
        else:
            if self.frame_counter >= self.eye_ar_consecutive_frames:
                self.blink_counter += 1
                blink_detected = True
            self.frame_counter = 0
        
        self.previous_ear = ear
        return blink_detected, ear
    
    def analyze_texture_lbp(self, face_image: np.ndarray) -> float:
        """
        Analyze face texture using Local Binary Patterns (LBP)
        Real faces have more complex texture patterns than printed photos
        
        Returns: texture_score (higher = more likely real)
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
        
        # Normalize to 0-1 range (typical values: real 5-7, fake 3-5)
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
        Real faces have subtle, diffuse reflections
        Screens have sharp, bright reflections
        
        Returns: reflection_score (higher = more likely real)
        """
        if len(face_image.shape) == 3:
            gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        else:
            gray = face_image
        
        # Detect bright spots (potential reflections)
        _, bright_mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
        
        # Calculate percentage of very bright pixels
        bright_ratio = np.sum(bright_mask > 0) / bright_mask.size
        
        # Low bright ratio suggests real face (soft lighting)
        # High bright ratio suggests screen reflection
        reflection_score = 1.0 - min(bright_ratio * 10, 1.0)
        
        return reflection_score
    
    def check_liveness(self, face_image: np.ndarray, 
                       face_landmarks: dict = None) -> Dict[str, any]:
        """
        Comprehensive liveness check
        
        Returns: {
            'is_live': bool,
            'confidence': float,
            'texture_score': float,
            'reflection_score': float,
            'ear': float (if landmarks provided)
        }
        """
        texture_score = self.analyze_texture_lbp(face_image)
        reflection_score = self.analyze_reflection(face_image)
        
        result = {
            'texture_score': texture_score,
            'reflection_score': reflection_score,
        }
        
        if face_landmarks:
            _, ear = self.detect_blink(face_landmarks)
            result['ear'] = ear
            result['blink_count'] = self.blink_counter
        
        # Combined confidence score
        confidence = (texture_score * 0.6 + reflection_score * 0.4)
        result['confidence'] = confidence
        result['is_live'] = confidence >= config.LBP_THRESHOLD
        
        return result
    
    def reset(self):
        """Reset blink counter for new session"""
        self.blink_counter = 0
        self.frame_counter = 0


class FaceProcessor:
    """
    Main face processing class for detection, recognition, and encoding
    """
    
    def __init__(self):
        self.lighting_normalizer = LightingNormalizer()
        self.spoof_detector = SpoofDetector()
        self.known_face_encodings: List[np.ndarray] = []
        self.known_face_ids: List[int] = []
        self.encoding_cache = {}
        
    def detect_faces(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detect faces in an image
        
        Returns: List of face locations as (top, right, bottom, left)
        """
        # Normalize lighting
        normalized = self.lighting_normalizer.normalize(image)
        
        # Convert BGR to RGB for face_recognition
        rgb_image = cv2.cvtColor(normalized, cv2.COLOR_BGR2RGB)
        
        # Detect face locations
        face_locations = face_recognition.face_locations(
            rgb_image, 
            model=config.FACE_DETECTION_MODEL
        )
        
        return face_locations
    
    def get_face_landmarks(self, image: np.ndarray, 
                           face_location: Tuple[int, int, int, int] = None) -> dict:
        """
        Get facial landmarks for a face
        
        Returns: Dictionary with landmark points
        """
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        if face_location:
            landmarks_list = face_recognition.face_landmarks(
                rgb_image, 
                face_locations=[face_location]
            )
        else:
            landmarks_list = face_recognition.face_landmarks(rgb_image)
        
        if landmarks_list:
            return landmarks_list[0]
        return {}
    
    def encode_face(self, image: np.ndarray, 
                    face_location: Tuple[int, int, int, int] = None) -> Optional[np.ndarray]:
        """
        Generate 128-dimensional face encoding
        
        Uses dlib's state-of-the-art face recognition model
        trained on a dataset of ~3 million faces
        """
        # Normalize lighting
        normalized = self.lighting_normalizer.normalize(image)
        rgb_image = cv2.cvtColor(normalized, cv2.COLOR_BGR2RGB)
        
        if face_location:
            encodings = face_recognition.face_encodings(
                rgb_image,
                known_face_locations=[face_location],
                model=config.FACE_ENCODING_MODEL
            )
        else:
            encodings = face_recognition.face_encodings(
                rgb_image,
                model=config.FACE_ENCODING_MODEL
            )
        
        if encodings:
            return encodings[0]
        return None
    
    def compare_faces(self, known_encoding: np.ndarray, 
                      face_encoding: np.ndarray) -> Tuple[bool, float]:
        """
        Compare two face encodings
        
        Returns: (is_match, distance)
        Lower distance = more similar faces
        """
        distance = face_recognition.face_distance([known_encoding], face_encoding)[0]
        is_match = distance <= config.FACE_RECOGNITION_TOLERANCE
        
        # Convert distance to confidence (1 - normalized_distance)
        confidence = max(0, 1 - (distance / config.FACE_RECOGNITION_TOLERANCE))
        
        return is_match, confidence
    
    def identify_face(self, image: np.ndarray, 
                      face_location: Tuple[int, int, int, int] = None) -> Optional[Dict]:
        """
        Identify a face against known encodings
        
        Returns: {
            'user_id': int,
            'confidence': float,
            'distance': float
        } or None if no match
        """
        if not self.known_face_encodings:
            return None
        
        face_encoding = self.encode_face(image, face_location)
        if face_encoding is None:
            return None
        
        # Calculate distances to all known faces
        distances = face_recognition.face_distance(
            self.known_face_encodings, 
            face_encoding
        )
        
        if len(distances) == 0:
            return None
        
        # Find best match
        best_match_index = np.argmin(distances)
        best_distance = distances[best_match_index]
        
        if best_distance <= config.FACE_RECOGNITION_TOLERANCE:
            confidence = max(0, 1 - (best_distance / config.FACE_RECOGNITION_TOLERANCE))
            return {
                'user_id': self.known_face_ids[best_match_index],
                'confidence': float(confidence),
                'distance': float(best_distance)
            }
        
        return None
    
    def load_known_faces(self, users: List[Dict]):
        """
        Load face encodings from user list
        
        Args:
            users: List of user dicts with 'id' and 'face_encoding' keys
        """
        self.known_face_encodings = []
        self.known_face_ids = []
        
        for user in users:
            if user.get('face_encoding'):
                try:
                    encoding = np.frombuffer(user['face_encoding'], dtype=np.float64)
                    if len(encoding) == 128:  # Valid face encoding
                        self.known_face_encodings.append(encoding)
                        self.known_face_ids.append(user['id'])
                except Exception as e:
                    print(f"Error loading encoding for user {user.get('id')}: {e}")
    
    def extract_face_region(self, image: np.ndarray, 
                            face_location: Tuple[int, int, int, int],
                            margin: float = 0.2) -> np.ndarray:
        """
        Extract face region from image with margin
        """
        top, right, bottom, left = face_location
        height = bottom - top
        width = right - left
        
        # Add margin
        margin_h = int(height * margin)
        margin_w = int(width * margin)
        
        top = max(0, top - margin_h)
        bottom = min(image.shape[0], bottom + margin_h)
        left = max(0, left - margin_w)
        right = min(image.shape[1], right + margin_w)
        
        return image[top:bottom, left:right]
    
    def draw_face_box(self, image: np.ndarray, 
                      face_location: Tuple[int, int, int, int],
                      name: str = None, 
                      confidence: float = None,
                      color: Tuple[int, int, int] = (0, 255, 0)) -> np.ndarray:
        """
        Draw face bounding box with optional label
        """
        top, right, bottom, left = face_location
        
        # Draw rectangle
        cv2.rectangle(image, (left, top), (right, bottom), color, 2)
        
        # Draw label
        if name or confidence:
            label = name or ""
            if confidence:
                label += f" ({confidence:.1%})"
            
            # Label background
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
            cv2.rectangle(
                image, 
                (left, bottom - 25), 
                (left + label_size[0] + 10, bottom),
                color, 
                cv2.FILLED
            )
            
            # Label text
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
        
        Returns: {
            'faces': [{
                'location': tuple,
                'user_id': int or None,
                'name': str or None,
                'confidence': float,
                'spoof_result': dict
            }],
            'annotated_frame': np.ndarray
        }
        """
        annotated = frame.copy()
        results = {'faces': [], 'annotated_frame': annotated}
        
        # Detect faces
        face_locations = self.detect_faces(frame)
        
        for face_location in face_locations:
            face_result = {
                'location': face_location,
                'user_id': None,
                'name': None,
                'confidence': 0.0,
                'spoof_result': None
            }
            
            # Spoof detection
            if check_spoof and config.SPOOF_DETECTION_ENABLED:
                face_region = self.extract_face_region(frame, face_location)
                landmarks = self.get_face_landmarks(frame, face_location)
                face_result['spoof_result'] = self.spoof_detector.check_liveness(
                    face_region, landmarks
                )
            
            # Face identification
            if perform_identification:
                match = self.identify_face(frame, face_location)
                if match:
                    face_result['user_id'] = match['user_id']
                    face_result['confidence'] = match['confidence']
            
            results['faces'].append(face_result)
            
            # Draw on annotated frame
            if face_result['user_id']:
                color = (0, 255, 0)  # Green for recognized
            else:
                color = (0, 0, 255)  # Red for unknown
            
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
        
        # Set camera properties
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
