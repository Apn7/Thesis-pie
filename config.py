"""
=============================================================================
  AUTONOMOUS SMART CANE - CONFIGURATION MODULE
  Centralized configuration for all system parameters
=============================================================================
"""

# =============================================================================
# NETWORK CONFIGURATION
# =============================================================================
LAPTOP_IP = "192.168.31.222"    # Flutter App IP address (from phone)
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
CONFIDENCE_THRESHOLD = 0.4      # Minimum confidence to trigger alert

# =============================================================================
# OBSTACLE CLASSES (COCO Dataset IDs)
# Categorized by danger level for blind navigation
# =============================================================================

# CRITICAL - Immediate danger, requires urgent alert
CRITICAL_OBSTACLES = {
    0: "Person",
    1: "Bicycle", 
    2: "Car",
    3: "Motorcycle",
    5: "Bus",
    7: "Truck",
}

# WARNING - Potential obstacles in path
WARNING_OBSTACLES = {
    13: "Bench",
    14: "Bird",
    15: "Cat",
    16: "Dog",
    56: "Chair",
    57: "Couch",
    58: "Potted Plant",
    59: "Bed",
    60: "Dining Table",
    62: "TV",
    63: "Laptop",
    67: "Cell Phone",
    73: "Book",
}

# CAUTION - Street objects and infrastructure
CAUTION_OBSTACLES = {
    9: "Traffic Light",
    10: "Fire Hydrant",
    11: "Stop Sign",
    12: "Parking Meter",
    24: "Backpack",
    25: "Umbrella",
    26: "Handbag",
    28: "Suitcase",
    32: "Sports Ball",
    36: "Skateboard",
    39: "Bottle",
    41: "Cup",
}

# Combined dictionary for all detectable obstacles
ALL_OBSTACLES = {**CRITICAL_OBSTACLES, **WARNING_OBSTACLES, **CAUTION_OBSTACLES}

# =============================================================================
# SAFETY PARAMETERS
# =============================================================================
ALERT_COOLDOWN = 3.0            # Seconds between consecutive alerts

# =============================================================================
# ALERT MESSAGE TEMPLATES
# =============================================================================
ALERT_TEMPLATES = {
    "CRITICAL": "DANGER: {object} Detected Ahead!",
    "WARNING": "WARNING: {object} in Path!",
    "CAUTION": "CAUTION: {object} Nearby!",
}

# =============================================================================
# DISPLAY SETTINGS
# =============================================================================
WINDOW_TITLE = "Smart Cane Vision Module - Thesis Demo"
ALERT_DISPLAY_DURATION = 1.0    # Seconds to show "SENDING ALERT" overlay

# =============================================================================
# HELPER FUNCTION
# =============================================================================
def get_obstacle_info(class_id: int) -> tuple:
    """
    Get obstacle name and danger level for a given class ID.
    
    Returns:
        Tuple of (name, level, color_bgr) or (None, None, None) if not an obstacle
    """
    if class_id in CRITICAL_OBSTACLES:
        return CRITICAL_OBSTACLES[class_id], "CRITICAL", (0, 0, 255)  # Red
    elif class_id in WARNING_OBSTACLES:
        return WARNING_OBSTACLES[class_id], "WARNING", (0, 165, 255)  # Orange
    elif class_id in CAUTION_OBSTACLES:
        return CAUTION_OBSTACLES[class_id], "CAUTION", (0, 255, 255)  # Yellow
    return None, None, None

def generate_alert_message(object_name: str, level: str) -> str:
    """Generate alert message based on object and danger level."""
    template = ALERT_TEMPLATES.get(level, "ALERT: {object} Detected!")
    return template.format(object=object_name)
