"""
FacePass Demo - Standalone Camera Test
Run this script to test face detection, recognition, and spoof detection
without the web interface.
"""

import cv2
import numpy as np
import sys
import os
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from face_processor import FaceProcessor, CameraManager, LightingNormalizer, SpoofDetector
from database import SessionLocal, UserOperations, init_db


class DemoApp:
    def __init__(self):
        self.face_processor = FaceProcessor()
        self.camera = CameraManager()
        self.spoof_detector = SpoofDetector()
        self.lighting_normalizer = LightingNormalizer()
        
        # Load known faces
        self._load_known_faces()
        
        # Display settings
        self.window_name = "FacePass Demo"
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.info_panel_height = 150
        
        # State
        self.mode = "identify"  # identify, register
        self.capture_cooldown = 0
        self.last_result = None
        self.user_cache = {}
        
    def _load_known_faces(self):
        """Load registered faces from database"""
        db = SessionLocal()
        try:
            users = UserOperations.get_all_active_users(db)
            user_data = []
            for u in users:
                if u.face_encoding:
                    user_data.append({
                        'id': u.id,
                        'face_encoding': u.face_encoding
                    })
                    self.user_cache[u.id] = u.name
            self.face_processor.load_known_faces(user_data)
            print(f"✓ Loaded {len(user_data)} registered faces")
        finally:
            db.close()
    
    def draw_info_panel(self, frame):
        """Draw information panel at the bottom"""
        h, w = frame.shape[:2]
        
        # Create semi-transparent overlay
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h - self.info_panel_height), (w, h), (20, 20, 30), -1)
        cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)
        
        # Draw separator line
        cv2.line(frame, (0, h - self.info_panel_height), (w, h - self.info_panel_height), (80, 80, 120), 2)
        
        # Mode indicator
        mode_text = f"Mode: {self.mode.upper()}"
        mode_color = (0, 255, 0) if self.mode == "identify" else (255, 165, 0)
        cv2.putText(frame, mode_text, (15, h - self.info_panel_height + 30), 
                   self.font, 0.7, mode_color, 2)
        
        # Instructions
        instructions = [
            "SPACE: Capture/Identify | R: Register Mode | I: Identify Mode | Q: Quit"
        ]
        for i, text in enumerate(instructions):
            cv2.putText(frame, text, (15, h - 30), 
                       self.font, 0.5, (180, 180, 180), 1)
        
        # Last result
        if self.last_result:
            result_text = self.last_result['message']
            result_color = (0, 255, 0) if self.last_result['success'] else (0, 0, 255)
            cv2.putText(frame, result_text, (15, h - self.info_panel_height + 70), 
                       self.font, 0.6, result_color, 2)
            
            if self.last_result.get('name'):
                name_text = f"User: {self.last_result['name']}"
                cv2.putText(frame, name_text, (15, h - self.info_panel_height + 100), 
                           self.font, 0.6, (255, 255, 255), 2)
            
            if self.last_result.get('confidence'):
                conf_text = f"Confidence: {self.last_result['confidence']:.1%}"
                cv2.putText(frame, conf_text, (15, h - self.info_panel_height + 130), 
                           self.font, 0.6, (255, 255, 255), 2)
        
        # Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, timestamp, (w - 200, h - self.info_panel_height + 30), 
                   self.font, 0.5, (150, 150, 150), 1)
        
        return frame
    
    def draw_face_analysis(self, frame, face_location, spoof_result, match=None):
        """Draw face bounding box and analysis info"""
        top, right, bottom, left = face_location
        
        # Determine color based on match and spoof
        if match and spoof_result.get('is_live', True):
            color = (0, 255, 0)  # Green - known and live
            label = f"{self.user_cache.get(match['user_id'], 'Unknown')} ({match['confidence']:.0%})"
        elif not spoof_result.get('is_live', True):
            color = (0, 0, 255)  # Red - spoof detected
            label = "SPOOF DETECTED"
        else:
            color = (0, 165, 255)  # Orange - unknown
            label = "Unknown Face"
        
        # Draw box with rounded corners effect
        thickness = 2
        cv2.rectangle(frame, (left, top), (right, bottom), color, thickness)
        
        # Corner accents
        corner_len = 15
        cv2.line(frame, (left, top), (left + corner_len, top), color, 3)
        cv2.line(frame, (left, top), (left, top + corner_len), color, 3)
        cv2.line(frame, (right, top), (right - corner_len, top), color, 3)
        cv2.line(frame, (right, top), (right, top + corner_len), color, 3)
        cv2.line(frame, (left, bottom), (left + corner_len, bottom), color, 3)
        cv2.line(frame, (left, bottom), (left, bottom - corner_len), color, 3)
        cv2.line(frame, (right, bottom), (right - corner_len, bottom), color, 3)
        cv2.line(frame, (right, bottom), (right, bottom - corner_len), color, 3)
        
        # Label background
        label_size = cv2.getTextSize(label, self.font, 0.6, 2)[0]
        cv2.rectangle(frame, (left, top - 30), (left + label_size[0] + 10, top), color, -1)
        cv2.putText(frame, label, (left + 5, top - 8), self.font, 0.6, (0, 0, 0), 2)
        
        # Spoof metrics
        if spoof_result:
            metrics_y = bottom + 25
            texture = spoof_result.get('texture_score', 0)
            reflection = spoof_result.get('reflection_score', 0)
            
            cv2.putText(frame, f"Texture: {texture:.2f}", (left, metrics_y), 
                       self.font, 0.4, (200, 200, 200), 1)
            cv2.putText(frame, f"Reflection: {reflection:.2f}", (left, metrics_y + 18), 
                       self.font, 0.4, (200, 200, 200), 1)
        
        return frame
    
    def process_identification(self, frame):
        """Process frame for face identification"""
        face_locations = self.face_processor.detect_faces(frame)
        
        if not face_locations:
            return None, "No face detected"
        
        face_location = face_locations[0]
        
        # Extract face region for spoof detection
        face_region = self.face_processor.extract_face_region(frame, face_location)
        landmarks = self.face_processor.get_face_landmarks(frame, face_location)
        spoof_result = self.spoof_detector.check_liveness(face_region, landmarks)
        
        if not spoof_result['is_live']:
            return {
                'success': False,
                'message': 'Spoof detected! Please use your real face.',
                'spoof_result': spoof_result
            }, None
        
        # Identify face
        match = self.face_processor.identify_face(frame, face_location)
        
        if match:
            return {
                'success': True,
                'message': 'Face recognized!',
                'name': self.user_cache.get(match['user_id'], 'Unknown'),
                'confidence': match['confidence'],
                'spoof_result': spoof_result
            }, match
        else:
            return {
                'success': False,
                'message': 'Face not recognized. Register first.',
                'spoof_result': spoof_result
            }, None
    
    def run(self):
        """Main demo loop"""
        print("\n" + "="*60)
        print("    FACEPASS - DEMO")
        print("="*60)
        print("\nStarting camera...")
        
        if not self.camera.start():
            print("ERROR: Could not open camera!")
            return
        
        print("✓ Camera started")
        print("\nControls:")
        print("  SPACE : Capture and process face")
        print("  R     : Switch to Registration mode")
        print("  I     : Switch to Identification mode")
        print("  Q     : Quit")
        print("\n" + "-"*60)
        
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, 800, 600 + self.info_panel_height)
        
        while True:
            ret, frame = self.camera.read_frame()
            if not ret:
                print("Failed to read frame")
                break
            
            # Mirror the frame
            frame = cv2.flip(frame, 1)
            
            # Apply lighting normalization
            normalized = self.lighting_normalizer.normalize(frame)
            
            # Detect faces for display
            face_locations = self.face_processor.detect_faces(frame)
            
            # Draw face boxes with real-time analysis
            for face_location in face_locations:
                face_region = self.face_processor.extract_face_region(frame, face_location)
                landmarks = self.face_processor.get_face_landmarks(frame, face_location)
                spoof_result = self.spoof_detector.check_liveness(face_region, landmarks)
                
                # Quick identification
                match = None
                if self.mode == "identify":
                    match = self.face_processor.identify_face(frame, face_location)
                
                frame = self.draw_face_analysis(frame, face_location, spoof_result, match)
            
            # Draw info panel
            frame = self.draw_info_panel(frame)
            
            # Show frame
            cv2.imshow(self.window_name, frame)
            
            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q') or key == 27:  # Q or ESC
                break
            elif key == ord(' '):  # Space - capture
                if self.capture_cooldown <= 0:
                    if face_locations:
                        result, match = self.process_identification(frame)
                        self.last_result = result
                        self.capture_cooldown = 30  # Frames of cooldown
                        print(f"\n[CAPTURE] {result['message']}")
                        if match:
                            print(f"  User: {self.user_cache.get(match['user_id'])}")
                            print(f"  Confidence: {match['confidence']:.1%}")
                    else:
                        self.last_result = {'success': False, 'message': 'No face detected'}
            elif key == ord('r'):  # R - register mode
                self.mode = "register"
                print("\nSwitched to REGISTER mode")
            elif key == ord('i'):  # I - identify mode
                self.mode = "identify"
                print("\nSwitched to IDENTIFY mode")
            
            # Decrease cooldown
            if self.capture_cooldown > 0:
                self.capture_cooldown -= 1
        
        # Cleanup
        self.camera.stop()
        cv2.destroyAllWindows()
        print("\n✓ Demo ended")


def main():
    """Main entry point"""
    # Initialize database
    init_db()
    
    # Run demo
    app = DemoApp()
    app.run()


if __name__ == "__main__":
    main()
