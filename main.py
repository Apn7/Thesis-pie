#!/usr/bin/env python3
"""
=============================================================================
  AUTONOMOUS SMART CANE - MAIN APPLICATION
  
  Thesis: "Autonomous Smart Cane: An IoT-Enabled, Vision and Voice-Assisted
           Navigation Aid"
  
  This is the main entry point that orchestrates:
  - Computer Vision (YOLOv8 obstacle detection)
  - IoT Communication (TCP alerts to Flutter app)
  
  Author: [Your Name]
  Platform: Raspberry Pi 5
=============================================================================
"""

import cv2
import time
import os

# Import modules
from config import (
    LAPTOP_IP, LAPTOP_PORT, VIDEO_PATH, ALERT_COOLDOWN,
    WINDOW_TITLE, ALERT_DISPLAY_DURATION,
    CONFIDENCE_THRESHOLD, ALL_OBSTACLES
)
from detector import ObstacleDetector, FrameAnnotator
from tcp_client import TCPClient


def print_banner():
    """Print startup banner with configuration info."""
    print("=" * 65)
    print("  ╔═══════════════════════════════════════════════════════════╗")
    print("  ║     AUTONOMOUS SMART CANE - VISION & IoT MODULE          ║")
    print("  ║     Thesis Demonstration System                          ║")
    print("  ╚═══════════════════════════════════════════════════════════╝")
    print("=" * 65)
    print(f"\n  Platform:    Raspberry Pi 5")
    print(f"  Target App:  {LAPTOP_IP}:{LAPTOP_PORT}")
    print(f"  Cooldown:    {ALERT_COOLDOWN}s")
    print(f"  Threshold:   {CONFIDENCE_THRESHOLD}")
    print(f"  Detectable:  {len(ALL_OBSTACLES)} obstacle types")
    print("-" * 65)


def main():
    """
    Main application loop.
    Combines vision detection with IoT transmission.
    """
    print_banner()
    
    # =========================================================================
    # INITIALIZATION
    # =========================================================================
    
    # 1. Initialize Detector
    print("\n[INIT] Initializing obstacle detector...")
    detector = ObstacleDetector()
    if not detector.load_model():
        print("[FATAL] Cannot proceed without AI model.")
        return
    
    # 2. Initialize TCP Client (Persistent Connection)
    print(f"\n[INIT] Initializing TCP client -> {LAPTOP_IP}:{LAPTOP_PORT}")
    tcp_client = TCPClient(LAPTOP_IP, LAPTOP_PORT)
    
    # Establish persistent connection
    if tcp_client.connect():
        print("[INIT] ✓ Persistent connection established!")
    else:
        print("[INIT] ⚠ Flutter app not reachable (will auto-reconnect)")
    
    # 3. Initialize Frame Annotator
    annotator = FrameAnnotator()
    
    # 4. Open Video Source
    print(f"\n[INIT] Opening video: {VIDEO_PATH}")
    if not os.path.exists(VIDEO_PATH):
        print(f"[FATAL] Video file not found: {VIDEO_PATH}")
        print("[HINT] Download a walking video and save to that path.")
        return
    
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print("[FATAL] Could not open video source.")
        return
    
    # Get video properties
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"[INIT] ✓ Video: {frame_width}x{frame_height} @ {video_fps:.1f}fps")
    print(f"[INIT] ✓ Frames: {total_frames}")
    
    # =========================================================================
    # MAIN LOOP
    # =========================================================================
    print("\n" + "=" * 65)
    print("  STARTING SMART CANE VISION SYSTEM")
    print("  Controls: [Q] Quit | [R] Restart Video | [T] Test Alert")
    print("=" * 65 + "\n")
    
    # State variables
    last_alert_time = 0.0
    frame_count = 0
    alert_display_timer = 0.0
    total_alerts_sent = 0
    
    try:
        while True:
            loop_start = time.time()
            
            # -----------------------------------------------------------------
            # READ FRAME
            # -----------------------------------------------------------------
            ret, frame = cap.read()
            
            if not ret:
                print("\n[INFO] Video ended. Looping...")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            
            frame_count += 1
            
            # -----------------------------------------------------------------
            # COMPUTER VISION - Obstacle Detection
            # -----------------------------------------------------------------
            results = detector.detect(frame)
            annotated_frame = detector.get_annotated_frame(results)
            
            # Check for ALL obstacles (multi-object detection)
            obstacles = detector.check_for_obstacles(results)
            primary_obstacle = detector.get_most_critical_obstacle(results)
            
            # -----------------------------------------------------------------
            # IoT TRANSMISSION - Send Alert (with cooldown)
            # -----------------------------------------------------------------
            current_time = time.time()
            show_alert_banner = False
            alert_level = "CRITICAL"
            alert_message = ""
            
            if primary_obstacle:
                time_since_last = current_time - last_alert_time
                
                if time_since_last >= ALERT_COOLDOWN:
                    obstacle_name = primary_obstacle['name']
                    obstacle_level = primary_obstacle['level']
                    confidence = primary_obstacle['confidence']
                    alert_message = primary_obstacle['message']
                    
                    print(f"\n[ALERT] {obstacle_level}: {obstacle_name} detected! ({confidence:.0%})")
                    
                    # Send TCP alert with specific message
                    success = tcp_client.send_alert(alert_message)
                    
                    if success:
                        last_alert_time = current_time
                        alert_display_timer = current_time
                        total_alerts_sent += 1
                        alert_level = obstacle_level
                    
                    if success:
                        last_alert_time = current_time
                        alert_display_timer = current_time
                        total_alerts_sent += 1
            
            # Show banner for ALERT_DISPLAY_DURATION seconds after send
            show_alert_banner = (current_time - alert_display_timer) < ALERT_DISPLAY_DURATION
            
            # -----------------------------------------------------------------
            # VISUAL FEEDBACK
            # -----------------------------------------------------------------
            # Draw ALL detected obstacles with their respective colors
            if obstacles:
                annotator.draw_all_obstacles(annotated_frame, obstacles)
            
            if show_alert_banner and primary_obstacle:
                alert_msg = f">>> ALERT: {primary_obstacle['name'].upper()} <<<" 
                annotator.draw_alert_banner(annotated_frame, alert_msg, alert_level)
            
            # Calculate FPS
            inference_time = time.time() - loop_start
            fps = 1.0 / inference_time if inference_time > 0 else 0
            
            # Cooldown remaining
            cooldown_remaining = max(0, ALERT_COOLDOWN - (current_time - last_alert_time))
            if last_alert_time == 0:
                cooldown_remaining = 0
            
            # Draw status bar with obstacle info
            obstacle_name = primary_obstacle['name'] if primary_obstacle else None
            annotator.draw_status_bar(
                annotated_frame, fps, frame_count,
                len(obstacles), cooldown_remaining, obstacle_name
            )
            
            # Alert counter (top-right)
            cv2.putText(annotated_frame, f"Alerts: {total_alerts_sent}",
                        (frame_width - 130, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Connection status indicator (top-left under FPS area)
            conn_status = tcp_client.status
            conn_color = (0, 255, 0) if tcp_client.is_connected else (0, 0, 255)
            cv2.putText(annotated_frame, f"TCP: {conn_status}",
                        (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, conn_color, 2)
            
            # -----------------------------------------------------------------
            # DISPLAY
            # -----------------------------------------------------------------
            cv2.imshow(WINDOW_TITLE, annotated_frame)
            
            # -----------------------------------------------------------------
            # KEYBOARD CONTROLS
            # -----------------------------------------------------------------
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                print("\n[INFO] User requested exit.")
                break
            
            elif key == ord('r'):
                print("[INFO] Restarting video...")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                frame_count = 0
            
            elif key == ord('t'):
                # Manual test alert
                print("\n[TEST] Sending manual test alert...")
                tcp_client.send_alert("TEST: Manual alert from Smart Cane")
                alert_display_timer = time.time()
    
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user (Ctrl+C)")
    
    # =========================================================================
    # CLEANUP
    # =========================================================================
    print("\n" + "-" * 65)
    print("[CLEANUP] Releasing resources...")
    
    # Disconnect TCP client gracefully
    tcp_client.disconnect()
    
    cap.release()
    cv2.destroyAllWindows()
    
    print(f"\n  Session Summary:")
    print(f"  - Frames processed: {frame_count}")
    print(f"  - Alerts sent: {total_alerts_sent}")
    print("\n[CLEANUP] ✓ Shutdown complete. Goodbye!")
    print("=" * 65)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    main()
