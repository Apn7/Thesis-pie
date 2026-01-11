"""
=============================================================================
  AUTONOMOUS SMART CANE - VISION & NETWORKING MODULE
  Thesis: "Autonomous Smart Cane: An IoT-Enabled, Vision and Voice-Assisted
           Navigation Aid"
  
  This script runs on Raspberry Pi 5 and acts as the "Brain" of the cane.
  - Performs real-time object detection using YOLOv8 Nano
  - Sends TCP alerts to Flutter companion app when obstacles detected
=============================================================================
"""

import cv2
import time
import socket
import os
from ultralytics import YOLO

# =============================================================================
# CONFIGURATION - Modify these values for your setup
# =============================================================================

# Network Configuration (Flutter App Receiver)
LAPTOP_IP = "192.168.1.100"  # <-- CHANGE THIS to your laptop's IP address
LAPTOP_PORT = 4444           # Port the Flutter app is listening on

# Video Source (Simulated camera feed)
VIDEO_PATH = '/home/pi/Downloads/test_walk.mp4'

# AI Model Configuration
MODEL_NAME = 'yolov8n.pt'    # YOLOv8 Nano - optimized for Raspberry Pi

# Detection Parameters
PERSON_CLASS_ID = 0          # COCO dataset: Class 0 = Person
CONFIDENCE_THRESHOLD = 0.5   # Minimum confidence to trigger alert

# Safety Parameters
ALERT_COOLDOWN = 3.0         # Seconds between consecutive alerts (anti-spam)

# Alert Message
ALERT_MESSAGE = "CRITICAL: Person Detected Ahead!"

# =============================================================================
# TCP CLIENT - IoT Transmission Module
# =============================================================================

def send_tcp_alert(message: str, host: str, port: int) -> bool:
    """
    Send a TCP message to the Flutter companion app.
    
    Args:
        message: Alert text to transmit
        host: IP address of the receiving device
        port: TCP port number
    
    Returns:
        True if message sent successfully, False otherwise
    """
    try:
        # Create TCP socket
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(2.0)  # 2 second timeout for connection
        
        # Connect to Flutter app
        client_socket.connect((host, port))
        
        # Send alert message (encoded as UTF-8 bytes)
        client_socket.sendall(message.encode('utf-8'))
        
        # Clean disconnect
        client_socket.close()
        
        print(f"[TCP] ✓ Alert sent to {host}:{port}")
        return True
        
    except socket.timeout:
        print(f"[TCP] ✗ Connection timeout - Is the Flutter app running?")
        return False
    except ConnectionRefusedError:
        print(f"[TCP] ✗ Connection refused - Check if app is listening on port {port}")
        return False
    except OSError as e:
        print(f"[TCP] ✗ Network error: {e}")
        return False
    except Exception as e:
        print(f"[TCP] ✗ Unexpected error: {e}")
        return False

# =============================================================================
# COMPUTER VISION PIPELINE
# =============================================================================

def check_for_person(results, confidence_threshold: float) -> tuple:
    """
    Analyze YOLO detection results for person obstacles.
    
    Args:
        results: YOLO prediction results
        confidence_threshold: Minimum confidence to consider valid
    
    Returns:
        Tuple of (person_detected: bool, highest_confidence: float, bbox: tuple or None)
    """
    person_detected = False
    highest_confidence = 0.0
    best_bbox = None
    
    # Iterate through all detections
    for result in results:
        boxes = result.boxes
        
        for box in boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            
            # Check if detection is a Person with sufficient confidence
            if class_id == PERSON_CLASS_ID and confidence > confidence_threshold:
                person_detected = True
                
                if confidence > highest_confidence:
                    highest_confidence = confidence
                    # Extract bounding box coordinates (x1, y1, x2, y2)
                    best_bbox = tuple(map(int, box.xyxy[0].tolist()))
    
    return person_detected, highest_confidence, best_bbox

def draw_alert_overlay(frame, bbox, confidence, sending_alert: bool):
    """
    Draw visual feedback on the frame when obstacle detected.
    
    Args:
        frame: OpenCV image frame
        bbox: Bounding box coordinates (x1, y1, x2, y2)
        confidence: Detection confidence value
        sending_alert: Whether an alert is being transmitted
    """
    if bbox is not None:
        x1, y1, x2, y2 = bbox
        
        # Draw red warning box around detected person
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
        
        # Add confidence label
        label = f"OBSTACLE: {confidence:.0%}"
        cv2.putText(frame, label, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    
    if sending_alert:
        # Flash "SENDING ALERT" warning at top of screen
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], 80), (0, 0, 200), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        cv2.putText(frame, ">>> SENDING ALERT TO APP <<<", (20, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)

# =============================================================================
# MAIN APPLICATION
# =============================================================================

def run_smart_cane_vision():
    """
    Main function - Runs the Smart Cane vision and networking pipeline.
    """
    print("=" * 60)
    print("  AUTONOMOUS SMART CANE - VISION MODULE")
    print("  Thesis Demonstration System")
    print("  Running on: Raspberry Pi 5")
    print("=" * 60)
    print(f"\n[CONFIG] Target App: {LAPTOP_IP}:{LAPTOP_PORT}")
    print(f"[CONFIG] Alert Cooldown: {ALERT_COOLDOWN}s")
    print(f"[CONFIG] Confidence Threshold: {CONFIDENCE_THRESHOLD}")
    print("-" * 60)

    # -------------------------------------------------------------------------
    # 1. LOAD AI MODEL
    # -------------------------------------------------------------------------
    print("\n[INIT] Loading YOLOv8 Nano model...")
    try:
        model = YOLO(MODEL_NAME)
        print("[INIT] ✓ Model loaded successfully")
    except Exception as e:
        print(f"[ERROR] Failed to load model: {e}")
        return

    # -------------------------------------------------------------------------
    # 2. VERIFY VIDEO SOURCE
    # -------------------------------------------------------------------------
    if not os.path.exists(VIDEO_PATH):
        print(f"\n[ERROR] Video file not found: {VIDEO_PATH}")
        print("[HINT] Download a walking/pedestrian video and save it to:")
        print(f"       {VIDEO_PATH}")
        return

    # -------------------------------------------------------------------------
    # 3. OPEN VIDEO STREAM
    # -------------------------------------------------------------------------
    print(f"\n[INIT] Opening video source: {VIDEO_PATH}")
    cap = cv2.VideoCapture(VIDEO_PATH)
    
    if not cap.isOpened():
        print("[ERROR] Could not open video source")
        return
    
    # Get video properties for display
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"[INIT] ✓ Video loaded: {frame_width}x{frame_height} @ {video_fps:.1f}fps")
    print(f"[INIT] ✓ Total frames: {total_frames}")

    # -------------------------------------------------------------------------
    # 4. MAIN PROCESSING LOOP
    # -------------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("  STARTING INFERENCE STREAM")
    print("  Press 'q' to quit | Press 'r' to restart video")
    print("=" * 60 + "\n")

    # State variables
    last_alert_time = 0.0      # Timestamp of last sent alert
    frame_count = 0            # Frame counter
    alert_display_timer = 0.0  # Timer for showing "SENDING ALERT" visual

    while True:
        loop_start = time.time()
        
        # Read frame from video
        ret, frame = cap.read()
        
        if not ret:
            print("\n[INFO] End of video reached. Restarting...")
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Loop video
            continue
        
        frame_count += 1
        
        # ---------------------------------------------------------------------
        # COMPUTER VISION: Run YOLO inference
        # ---------------------------------------------------------------------
        results = model(frame, verbose=False)
        
        # Get annotated frame with all detections
        annotated_frame = results[0].plot()
        
        # Check specifically for Person obstacles
        person_detected, confidence, bbox = check_for_person(results, CONFIDENCE_THRESHOLD)
        
        # ---------------------------------------------------------------------
        # IoT TRANSMISSION: Send alert if person detected (with cooldown)
        # ---------------------------------------------------------------------
        current_time = time.time()
        sending_alert_now = False
        
        if person_detected:
            time_since_last_alert = current_time - last_alert_time
            
            if time_since_last_alert >= ALERT_COOLDOWN:
                # Send TCP alert to Flutter app
                print(f"\n[ALERT] Person detected! Confidence: {confidence:.0%}")
                
                success = send_tcp_alert(ALERT_MESSAGE, LAPTOP_IP, LAPTOP_PORT)
                
                if success:
                    last_alert_time = current_time
                    alert_display_timer = current_time
                    sending_alert_now = True
        
        # Show "SENDING ALERT" visual for 1 second after transmission
        show_alert_visual = (current_time - alert_display_timer) < 1.0
        
        # ---------------------------------------------------------------------
        # VISUAL FEEDBACK: Draw overlays
        # ---------------------------------------------------------------------
        if person_detected:
            draw_alert_overlay(annotated_frame, bbox, confidence, show_alert_visual)
        
        # Calculate and display FPS
        inference_time = time.time() - loop_start
        fps = 1.0 / inference_time if inference_time > 0 else 0
        
        # Status bar at bottom
        status_color = (0, 255, 0) if not person_detected else (0, 165, 255)
        cv2.rectangle(annotated_frame, (0, frame_height - 40), 
                      (frame_width, frame_height), (40, 40, 40), -1)
        
        status_text = f"FPS: {fps:.1f} | Frame: {frame_count} | "
        status_text += "OBSTACLE DETECTED" if person_detected else "Clear Path"
        
        cv2.putText(annotated_frame, status_text, (10, frame_height - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
        
        # Connection status indicator
        cooldown_remaining = max(0, ALERT_COOLDOWN - (current_time - last_alert_time))
        if cooldown_remaining > 0 and last_alert_time > 0:
            cv2.putText(annotated_frame, f"Cooldown: {cooldown_remaining:.1f}s", 
                        (frame_width - 180, frame_height - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        # ---------------------------------------------------------------------
        # DISPLAY OUTPUT
        # ---------------------------------------------------------------------
        cv2.imshow('Smart Cane Vision Module - Thesis Demo', annotated_frame)
        
        # Keyboard controls
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("\n[INFO] User requested exit.")
            break
        elif key == ord('r'):
            print("[INFO] Restarting video...")
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            frame_count = 0

    # -------------------------------------------------------------------------
    # CLEANUP
    # -------------------------------------------------------------------------
    print("\n[CLEANUP] Releasing resources...")
    cap.release()
    cv2.destroyAllWindows()
    print("[CLEANUP] ✓ Done. Goodbye!")
    print("=" * 60)

# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    run_smart_cane_vision()
