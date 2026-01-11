"""
=============================================================================
  AUTONOMOUS SMART CANE - OBJECT DETECTION MODULE
  YOLOv8-based obstacle detection for visually impaired navigation
=============================================================================
"""

import cv2
from ultralytics import YOLO
from config import (
    MODEL_NAME, CONFIDENCE_THRESHOLD, ALL_OBSTACLES,
    get_obstacle_info, generate_alert_message
)


class ObstacleDetector:
    """
    YOLO-based obstacle detector optimized for Raspberry Pi 5.
    Detects multiple obstacle types for blind navigation assistance.
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
            print(f"[DETECTOR] ✓ Monitoring {len(ALL_OBSTACLES)} obstacle types")
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
    
    def check_for_obstacles(self, results) -> list:
        """
        Analyze detection results for ALL obstacle types.
        
        Args:
            results: YOLO prediction results
        
        Returns:
            List of detected obstacles, each as dict with:
            {class_id, name, level, confidence, bbox, color}
            Sorted by danger level (CRITICAL first) then confidence
        """
        obstacles = []
        
        for result in results:
            boxes = result.boxes
            
            for box in boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                
                # Check if this class is one of our monitored obstacles
                if class_id in ALL_OBSTACLES and confidence > self.confidence_threshold:
                    name, level, color = get_obstacle_info(class_id)
                    
                    if name:  # Valid obstacle
                        bbox = tuple(map(int, box.xyxy[0].tolist()))
                        obstacles.append({
                            'class_id': class_id,
                            'name': name,
                            'level': level,
                            'confidence': confidence,
                            'bbox': bbox,
                            'color': color,
                            'message': generate_alert_message(name, level)
                        })
        
        # Sort by priority: CRITICAL > WARNING > CAUTION, then by confidence
        level_priority = {'CRITICAL': 0, 'WARNING': 1, 'CAUTION': 2}
        obstacles.sort(key=lambda x: (level_priority.get(x['level'], 3), -x['confidence']))
        
        return obstacles
    
    def get_most_critical_obstacle(self, results) -> dict:
        """
        Get the most critical/dangerous obstacle from results.
        
        Args:
            results: YOLO prediction results
        
        Returns:
            Dict with obstacle info or None if no obstacles
        """
        obstacles = self.check_for_obstacles(results)
        return obstacles[0] if obstacles else None
    
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
    def draw_obstacle_warning(frame, obstacle: dict):
        """
        Draw warning box around detected obstacle with appropriate color.
        
        Args:
            frame: OpenCV image frame
            obstacle: Dict with obstacle info (bbox, name, level, confidence, color)
        """
        if obstacle is None or 'bbox' not in obstacle:
            return
        
        x1, y1, x2, y2 = obstacle['bbox']
        color = obstacle.get('color', (0, 0, 255))
        name = obstacle.get('name', 'Unknown')
        level = obstacle.get('level', 'WARNING')
        confidence = obstacle.get('confidence', 0)
        
        # Draw bounding box with level-appropriate color
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
        
        # Label with name, level, and confidence
        label = f"{level}: {name} ({confidence:.0%})"
        
        # Background for label
        (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(frame, (x1, y1 - label_h - 10), (x1 + label_w + 5, y1), color, -1)
        cv2.putText(frame, label, (x1 + 2, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    @staticmethod
    def draw_all_obstacles(frame, obstacles: list):
        """
        Draw warnings for all detected obstacles.
        
        Args:
            frame: OpenCV image frame
            obstacles: List of obstacle dicts
        """
        for obstacle in obstacles:
            FrameAnnotator.draw_obstacle_warning(frame, obstacle)
    
    @staticmethod
    def draw_alert_banner(frame, message: str = ">>> SENDING ALERT TO APP <<<", 
                          level: str = "CRITICAL"):
        """
        Draw alert banner at top of frame with level-appropriate color.
        
        Args:
            frame: OpenCV image frame
            message: Alert message to display
            level: Danger level (CRITICAL/WARNING/CAUTION)
        """
        # Color based on level
        colors = {
            'CRITICAL': (0, 0, 200),    # Red
            'WARNING': (0, 100, 200),   # Orange
            'CAUTION': (0, 180, 200),   # Yellow
        }
        bg_color = colors.get(level, (0, 0, 200))
        
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], 80), bg_color, -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        cv2.putText(frame, message, (20, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
    
    @staticmethod
    def draw_status_bar(frame, fps: float, frame_count: int, 
                        obstacle_count: int = 0, cooldown_remaining: float = 0,
                        obstacle_name: str = None):
        """
        Draw status bar at bottom of frame.
        
        Args:
            frame: OpenCV image frame
            fps: Current frames per second
            frame_count: Current frame number
            obstacle_count: Number of obstacles detected
            cooldown_remaining: Seconds until next alert can be sent
            obstacle_name: Name of primary detected obstacle
        """
        height, width = frame.shape[:2]
        
        # Background bar
        cv2.rectangle(frame, (0, height - 40), (width, height), (40, 40, 40), -1)
        
        # Status text
        if obstacle_count > 0:
            status_color = (0, 165, 255)  # Orange
            status_text = f"FPS: {fps:.1f} | {obstacle_count} obstacle(s): {obstacle_name or 'detected'}"
        else:
            status_color = (0, 255, 0)    # Green
            status_text = f"FPS: {fps:.1f} | Frame: {frame_count} | Clear Path"
        
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
    from config import VIDEO_PATH, ALL_OBSTACLES
    
    print("=" * 60)
    print("  MULTI-OBSTACLE DETECTOR MODULE TEST")
    print("=" * 60)
    print(f"  Tracking {len(ALL_OBSTACLES)} obstacle types")
    print("-" * 60)
    
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
    
    print("\n[TEST] Running multi-obstacle detection...")
    print("Press 'q' to quit.\n")
    
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        
        frame_count += 1
        results = detector.detect(frame)
        
        # Get ALL obstacles
        obstacles = detector.check_for_obstacles(results)
        primary = detector.get_most_critical_obstacle(results)
        
        annotated = detector.get_annotated_frame(results)
        
        # Draw all obstacles
        annotator.draw_all_obstacles(annotated, obstacles)
        
        # Draw status
        primary_name = primary['name'] if primary else None
        annotator.draw_status_bar(annotated, 30, frame_count, len(obstacles), 0, primary_name)
        
        # Log detections
        if obstacles:
            names = [f"{o['name']}({o['level'][0]})" for o in obstacles]
            print(f"  Frame {frame_count}: {len(obstacles)} obstacle(s) - {', '.join(names)}")
        
        cv2.imshow('Multi-Obstacle Detector Test', annotated)
        if cv2.waitKey(50) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    print("\n✓ Multi-obstacle detector test complete!")
