import cv2
import time
import os
from ultralytics import YOLO

# --- CONFIGURATION ---
# Path to your test video. 
# Ensure you downloaded a video to your Downloads folder and named it 'test_walk.mp4'
VIDEO_PATH = '/home/pi/Downloads/test_walk.mp4' 

# Thesis Model: Using YOLOv8 Nano (Lightweight for Pi 5)
MODEL_NAME = 'yolov8n.pt'
# ---------------------

def run_vision_demo():
    print("-" * 30)
    print("  SMART CANE VISION MODULE")
    print("  Running on Raspberry Pi 5")
    print("-" * 30)

    # 1. Load the AI Model
    print(f">> Loading {MODEL_NAME} model... (First run downloads data)")
    try:
        model = YOLO(MODEL_NAME)
    except Exception as e:
        print(f"Error loading model: {e}")
        return

    # 2. Check Video File
    if not os.path.exists(VIDEO_PATH):
        print(f"\n[ERROR] Video file not found at: {VIDEO_PATH}")
        print("Please download a walking video and rename it to 'test_walk.mp4'")
        return

    # 3. Open Video Stream
    cap = cv2.VideoCapture(VIDEO_PATH)
    
    if not cap.isOpened():
        print("[ERROR] Could not open video source.")
        return

    print(">> System Ready. Starting Inference Stream...")
    print(">> Press 'q' to stop.")

    # 4. Processing Loop (Simulates Real-time Camera)
    while True:
        start_time = time.time()
        
        ret, frame = cap.read()
        if not ret:
            print(">> End of video simulation.")
            break

        # --- THE CORE AI TASK ---
        # Predict objects in the frame
        results = model(frame, verbose=False) 

        # Draw boxes (Visualization)
        annotated_frame = results[0].plot()

        # Calculate FPS (Performance Metric)
        fps = 1.0 / (time.time() - start_time)

        # Display FPS on screen (Crucial for your Supervisor!)
        cv2.putText(annotated_frame, f"Pi 5 Inference: {fps:.1f} FPS", (20, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow('Thesis Prototype: Vision Module', annotated_frame)

        # Exit on 'q' key
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_vision_demo()
