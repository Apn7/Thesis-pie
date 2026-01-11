"""
=============================================================================
  AUTONOMOUS SMART CANE - CONFIGURATION MODULE
  Centralized configuration for all system parameters
=============================================================================
"""

# =============================================================================
# NETWORK CONFIGURATION
# =============================================================================
LAPTOP_IP = "192.168.31.140"    # Flutter App IP address
LAPTOP_PORT = 4444              # TCP port the Flutter app listens on
CONNECTION_TIMEOUT = 2.0        # Seconds to wait for connection

# =============================================================================
# VIDEO SOURCE
# =============================================================================
VIDEO_PATH = '/home/pi/Downloads/test_walk2.mp4'

# =============================================================================
# AI MODEL CONFIGURATION
# =============================================================================
MODEL_NAME = 'yolov8n.pt'       # YOLOv8 Nano - optimized for Raspberry Pi

# =============================================================================
# DETECTION PARAMETERS
# =============================================================================
PERSON_CLASS_ID = 0             # COCO dataset: Class 0 = Person
CONFIDENCE_THRESHOLD = 0.5      # Minimum confidence to trigger alert

# =============================================================================
# SAFETY PARAMETERS
# =============================================================================
ALERT_COOLDOWN = 3.0            # Seconds between consecutive alerts

# =============================================================================
# ALERT MESSAGES
# =============================================================================
ALERT_MESSAGE = "CRITICAL: Person Detected Ahead!"

# =============================================================================
# DISPLAY SETTINGS
# =============================================================================
WINDOW_TITLE = "Smart Cane Vision Module - Thesis Demo"
ALERT_DISPLAY_DURATION = 1.0    # Seconds to show "SENDING ALERT" overlay
