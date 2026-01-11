"""
=============================================================================
  AUTONOMOUS SMART CANE - OBJECT DETECTION MODULE
  YOLOv8-based obstacle detection for visually impaired navigation
=============================================================================
"""

import cv2
from ultralytics import YOLO
from config import MODEL_NAME, PERSON_CLASS_ID, CONFIDENCE_THRESHOLD


class ObstacleDetector:
    """
    YOLO-based obstacle detector optimized for Raspberry Pi 5.
    Focuses on detecting persons as primary obstacles.
    """
    
    def __init__(self, model_path: str = MODEL_NAME):
        """
        Initialize the obstacle detector with YOLO model.
        
        Args:
            model_path: Path to YOLO model weights file
        """
        self.model_path = model_path
        self.model = None
        self.confidence_threshold = CONFIDENCE_THRESHOLD
        self.person_class_id = PERSON_CLASS_ID
    
    def load_model(self) -> bool:
        """
        Load the YOLO model into memory.
        
        Returns:
            True if model loaded successfully, False otherwise
        """
        try:
            print(f"[DETECTOR] Loading {self.model_path}...")
            self.model = YOLO(self.model_path)
            print("[DETECTOR] ✓ Model loaded successfully")
            return True
        except Exception as e:
            print(f"[DETECTOR] ✗ Failed to load model: {e}")
            return False
    
    def detect(self, frame):
        """
        Run object detection on a frame.
        
        Args:
            frame: OpenCV image frame (BGR format)
        
        Returns:
            YOLO Results object
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        
        return self.model(frame, verbose=False)
    
    def check_for_obstacle(self, results) -> tuple:
        """
        Analyze detection results for person obstacles.
        
        Args:
            results: YOLO prediction results
        
        Returns:
            Tuple of (detected: bool, confidence: float, bbox: tuple or None)
        """
        detected = False
        highest_confidence = 0.0
        best_bbox = None
        
        for result in results:
            boxes = result.boxes
            
            for box in boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                
                # Check if detection is a Person with sufficient confidence
                if class_id == self.person_class_id and confidence > self.confidence_threshold:
                    detected = True
                    
                    if confidence > highest_confidence:
                        highest_confidence = confidence
                        # Extract bounding box coordinates (x1, y1, x2, y2)
                        best_bbox = tuple(map(int, box.xyxy[0].tolist()))
        
        return detected, highest_confidence, best_bbox
    
    def get_annotated_frame(self, results) -> any:
        """
        Get frame with all detection annotations drawn.
        
        Args:
            results: YOLO prediction results
        
        Returns:
            Annotated frame with bounding boxes and labels
        """
        return results[0].plot()


class FrameAnnotator:
    """
    Handles drawing custom overlays and visual feedback on frames.
    """
    
    @staticmethod
    def draw_obstacle_warning(frame, bbox, confidence):
        """
        Draw red warning box around detected obstacle.
        
        Args:
            frame: OpenCV image frame
            bbox: Bounding box (x1, y1, x2, y2)
            confidence: Detection confidence
        """
        if bbox is None:
            return
        
        x1, y1, x2, y2 = bbox
        
        # Red warning box
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
        
        # Confidence label
        label = f"OBSTACLE: {confidence:.0%}"
        cv2.putText(frame, label, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    
    @staticmethod
    def draw_alert_banner(frame):
        """
        Draw "SENDING ALERT" banner at top of frame.
        
        Args:
            frame: OpenCV image frame
        """
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], 80), (0, 0, 200), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        cv2.putText(frame, ">>> SENDING ALERT TO APP <<<", (20, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
    
    @staticmethod
    def draw_status_bar(frame, fps: float, frame_count: int, 
                        obstacle_detected: bool, cooldown_remaining: float = 0):
        """
        Draw status bar at bottom of frame.
        
        Args:
            frame: OpenCV image frame
            fps: Current frames per second
            frame_count: Current frame number
            obstacle_detected: Whether obstacle is currently detected
            cooldown_remaining: Seconds until next alert can be sent
        """
        height, width = frame.shape[:2]
        
        # Background bar
        cv2.rectangle(frame, (0, height - 40), (width, height), (40, 40, 40), -1)
        
        # Status text
        status_color = (0, 165, 255) if obstacle_detected else (0, 255, 0)
        status_text = f"FPS: {fps:.1f} | Frame: {frame_count} | "
        status_text += "OBSTACLE DETECTED" if obstacle_detected else "Clear Path"
        
        cv2.putText(frame, status_text, (10, height - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
        
        # Cooldown indicator
        if cooldown_remaining > 0:
            cv2.putText(frame, f"Cooldown: {cooldown_remaining:.1f}s",
                        (width - 180, height - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)


# Standalone test
if __name__ == "__main__":
    import os
    from config import VIDEO_PATH
    
    print("=" * 50)
    print("  DETECTOR MODULE TEST")
    print("=" * 50)
    
    # Initialize detector
    detector = ObstacleDetector()
    if not detector.load_model():
        exit(1)
    
    # Check video
    if not os.path.exists(VIDEO_PATH):
        print(f"\n[ERROR] Video not found: {VIDEO_PATH}")
        exit(1)
    
    cap = cv2.VideoCapture(VIDEO_PATH)
    annotator = FrameAnnotator()
    
    print("\n[TEST] Running detection on first 30 frames...")
    print("Press 'q' to quit early.\n")
    
    for i in range(30):
        ret, frame = cap.read()
        if not ret:
            break
        
        results = detector.detect(frame)
        detected, conf, bbox = detector.check_for_obstacle(results)
        
        if detected:
            print(f"  Frame {i+1}: Person detected (confidence: {conf:.0%})")
        
        annotated = detector.get_annotated_frame(results)
        if detected:
            annotator.draw_obstacle_warning(annotated, bbox, conf)
        
        cv2.imshow('Detector Test', annotated)
        if cv2.waitKey(100) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    print("\n✓ Detector test complete!")
