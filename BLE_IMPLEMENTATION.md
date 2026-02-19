# Smart Cane - Raspberry Pi BLE GATT Server Implementation

## Overview
The Raspberry Pi 5 runs a BLE GATT server that sends obstacle detection alerts to a Flutter mobile app. The system uses YOLOv8 for real-time object detection and BlueZ D-Bus API for BLE communication.

---

## BLE Configuration

### Device Name
```
SmartCane
```

### Service UUID
```
12345678-1234-5678-1234-56789abcdef0
```

### Alert Characteristic UUID
```
12345678-1234-5678-1234-56789abcdef1
```

### Characteristic Properties
- **Read** - Returns current obstacle status
- **Notify** - Sends real-time obstacle alerts (must subscribe!)

---

## Alert Message Format

Alerts are sent as UTF-8 encoded strings in this format:
```
LEVEL:OBJECT_NAME:CONFIDENCE:POSITION
```

### Examples:
```
CRITICAL:Person:87%:center
WARNING:Bicycle:65%:left
CAUTION:Chair:52%:right
```

### Fields:
| Field | Values | Description |
|-------|--------|-------------|
| `LEVEL` | `CRITICAL`, `WARNING`, `CAUTION`, `TEST` | Danger level |
| `OBJECT_NAME` | `Person`, `Car`, `Bicycle`, `Dog`, `Chair`, etc. | Detected obstacle |
| `CONFIDENCE` | `0%` - `100%` | Detection confidence |
| `POSITION` | `left`, `center`, `right` | Position in frame |

---

## Flutter App Requirements

### 1. Connect to Device
- Scan for BLE devices
- Connect to device named **"SmartCane"**

### 2. Discover Services
- After connection, discover GATT services
- Find service with UUID: `12345678-1234-5678-1234-56789abcdef0`

### 3. Subscribe to Notifications (CRITICAL!)
- Find characteristic with UUID: `12345678-1234-5678-1234-56789abcdef1`
- **Call `setNotifyValue(true)` on the characteristic**
- This triggers `StartNotify` on the Pi and enables alert delivery

### 4. Handle Incoming Data
- Listen to characteristic value changes
- Parse the string format: `LEVEL:NAME:CONFIDENCE:POSITION`
- Display appropriate UI/alerts based on danger level

---

## Sample Flutter Code (flutter_blue_plus)

```dart
import 'package:flutter_blue_plus/flutter_blue_plus.dart';

// UUIDs
final serviceUuid = Guid('12345678-1234-5678-1234-56789abcdef0');
final alertCharUuid = Guid('12345678-1234-5678-1234-56789abcdef1');

class BleService {
  BluetoothDevice? _device;
  BluetoothCharacteristic? _alertChar;

  Future<void> connectToSmartCane() async {
    // Scan for SmartCane
    await FlutterBluePlus.startScan(timeout: Duration(seconds: 10));
    
    FlutterBluePlus.scanResults.listen((results) async {
      for (var r in results) {
        if (r.device.platformName == 'SmartCane') {
          await FlutterBluePlus.stopScan();
          _device = r.device;
          await _device!.connect();
          await _discoverAndSubscribe();
          break;
        }
      }
    });
  }

  Future<void> _discoverAndSubscribe() async {
    List<BluetoothService> services = await _device!.discoverServices();
    
    for (var service in services) {
      if (service.uuid == serviceUuid) {
        for (var char in service.characteristics) {
          if (char.uuid == alertCharUuid) {
            _alertChar = char;
            
            // IMPORTANT: Subscribe to notifications!
            await char.setNotifyValue(true);
            
            // Listen for alerts
            char.onValueReceived.listen((value) {
              String alert = String.fromCharCodes(value);
              _handleAlert(alert);
            });
          }
        }
      }
    }
  }

  void _handleAlert(String alert) {
    // Parse: "CRITICAL:Person:87%:center"
    List<String> parts = alert.split(':');
    if (parts.length >= 4) {
      String level = parts[0];      // CRITICAL, WARNING, CAUTION
      String object = parts[1];     // Person, Car, etc.
      String confidence = parts[2]; // 87%
      String position = parts[3];   // left, center, right
      
      // Update UI, show notification, trigger TTS, etc.
      print('Alert: $level $object at $position ($confidence)');
    }
  }
}
```

---

## Danger Levels & Suggested UI

| Level | Color | Action |
|-------|-------|--------|
| `CRITICAL` | 🔴 Red | Immediate alert, vibration, urgent TTS |
| `WARNING` | 🟠 Orange | Standard alert, warning sound |
| `CAUTION` | 🟡 Yellow | Informational, subtle notification |
| `TEST` | 🔵 Blue | Test message (press 'T' on Pi) |

---

## Detected Obstacle Types

### CRITICAL (Immediate Danger)
- Person
- Bicycle
- Car
- Motorcycle
- Bus
- Truck

### WARNING (Potential Obstacles)
- Bench
- Bird
- Cat
- Dog
- Backpack
- Umbrella
- Handbag
- Suitcase

### CAUTION (Path Obstacles)
- Traffic Light
- Fire Hydrant
- Stop Sign
- Parking Meter
- Chair
- Couch
- Potted Plant
- Bed
- Dining Table
- Toilet
- TV
- Laptop
- Refrigerator
- Book
- Clock
- Vase
- Scissors
- Toothbrush

---

## Running the Pi Server

```bash
cd /home/pi/Thesis
sudo python main.py
```

### Controls (when video window is focused):
- **Q** - Quit
- **R** - Restart video
- **T** - Send test alert

---

## Testing

1. Run on Pi: `sudo python main.py`
2. Connect Flutter app to "SmartCane"
3. **Must call `setNotifyValue(true)` to receive alerts**
4. Press **'T'** on Pi keyboard to send test alert: `TEST:manual:100%:center`

---

## Troubleshooting

### App connects but no alerts received
- Ensure `setNotifyValue(true)` is called on the alert characteristic
- Check Pi terminal for `[BLE] >>> StartNotify called!` message
- If you don't see this, the app is not subscribing to notifications

### Connection issues
- Restart Bluetooth on Pi: `sudo systemctl restart bluetooth`
- Make sure only one device is connected at a time
- Kill any existing Python processes: `sudo pkill -f "python main.py"`

### Pi terminal shows "(queued)" instead of "Sent"
- This means no client has subscribed to notifications yet
- The Flutter app must call `setNotifyValue(true)` after connecting

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Raspberry Pi 5                           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐         ┌─────────────────────────┐   │
│  │  Vision Process │         │    BLE Process          │   │
│  │  (Main Thread)  │         │    (Separate Process)   │   │
│  ├─────────────────┤         ├─────────────────────────┤   │
│  │ • OpenCV/Qt     │  Queue  │ • D-Bus/GLib MainLoop   │   │
│  │ • YOLOv8        │ ──────► │ • BlueZ GATT Server     │   │
│  │ • Frame Display │ alerts  │ • BLE Notifications     │   │
│  └─────────────────┘         └─────────────────────────┘   │
│                                        │                    │
│                                        │ BLE               │
│                                        ▼                    │
└─────────────────────────────────────────────────────────────┘
                                         │
                                         │ Wireless
                                         ▼
                              ┌─────────────────────┐
                              │   Flutter App       │
                              │   (SmartCane)       │
                              ├─────────────────────┤
                              │ • BLE Client        │
                              │ • Alert Display     │
                              │ • TTS / Vibration   │
                              └─────────────────────┘
```

---

## Files

| File | Description |
|------|-------------|
| `main.py` | Main application with BLE server and vision loop |
| `config.py` | Configuration (thresholds, UUIDs, obstacle types) |
| `detector.py` | YOLOv8 obstacle detection module |
| `yolov8n.pt` | YOLOv8 Nano model weights |

---

## Contact

For issues with the Pi implementation, check the terminal output for debug messages prefixed with `[BLE]`, `[DETECTOR]`, `[ALERT]`, etc.
