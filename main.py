#!/usr/bin/env python3
"""
Smart Cane Vision System with BLE GATT Server
Using multiprocessing to isolate BLE (GLib) from OpenCV (Qt)
"""

import os
import sys
import time
import signal
import multiprocessing as mp
from multiprocessing import Process, Queue, Event
from typing import Optional

# Must set before importing cv2
os.environ['QT_LOGGING_RULES'] = '*=false'
os.environ['QT_DEBUG_PLUGINS'] = '0'

import cv2

from config import (
    MODEL_NAME, VIDEO_PATH, CONFIDENCE_THRESHOLD,
    ALERT_COOLDOWN, WINDOW_TITLE
)
from detector import ObstacleDetector, FrameAnnotator

# BLE UUIDs
BLE_SERVICE_UUID = '12345678-1234-5678-1234-56789abcdef0'
BLE_ALERT_CHAR_UUID = '12345678-1234-5678-1234-56789abcdef1'


# ============================================================================
# BLE Server Process (completely isolated from OpenCV/Qt)
# ============================================================================

def ble_server_process(alert_queue: Queue, connected_event: Event, shutdown_event: Event):
    """
    Run BLE GATT server in separate process.
    Receives alerts via Queue and sends via BLE notifications.
    """
    import dbus
    import dbus.mainloop.glib
    import dbus.service
    from gi.repository import GLib
    
    # BLE Constants
    BLUEZ_SERVICE_NAME = 'org.bluez'
    LE_ADVERTISING_MANAGER_IFACE = 'org.bluez.LEAdvertisingManager1'
    DBUS_OM_IFACE = 'org.freedesktop.DBus.ObjectManager'
    DBUS_PROP_IFACE = 'org.freedesktop.DBus.Properties'
    LE_ADVERTISEMENT_IFACE = 'org.bluez.LEAdvertisement1'
    GATT_MANAGER_IFACE = 'org.bluez.GattManager1'
    GATT_SERVICE_IFACE = 'org.bluez.GattService1'
    GATT_CHRC_IFACE = 'org.bluez.GattCharacteristic1'
    
    class Advertisement(dbus.service.Object):
        PATH_BASE = '/org/bluez/example/advertisement'
        
        def __init__(self, bus, index, advertising_type):
            self.path = self.PATH_BASE + str(index)
            self.bus = bus
            self.ad_type = advertising_type
            self.service_uuids = None
            self.local_name = None
            self.include_tx_power = False
            dbus.service.Object.__init__(self, bus, self.path)
        
        def get_properties(self):
            properties = {'Type': self.ad_type}
            if self.service_uuids:
                properties['ServiceUUIDs'] = dbus.Array(self.service_uuids, signature='s')
            if self.local_name:
                properties['LocalName'] = dbus.String(self.local_name)
            if self.include_tx_power:
                properties['Includes'] = dbus.Array(["tx-power"], signature='s')
            return {LE_ADVERTISEMENT_IFACE: properties}
        
        def get_path(self):
            return dbus.ObjectPath(self.path)
        
        @dbus.service.method(DBUS_PROP_IFACE, in_signature='s', out_signature='a{sv}')
        def GetAll(self, interface):
            if interface != LE_ADVERTISEMENT_IFACE:
                raise dbus.exceptions.DBusException('org.bluez.Error.InvalidArguments')
            return self.get_properties()[LE_ADVERTISEMENT_IFACE]
        
        @dbus.service.method(LE_ADVERTISEMENT_IFACE)
        def Release(self):
            pass
    
    class SmartCaneAdvertisement(Advertisement):
        def __init__(self, bus, index):
            Advertisement.__init__(self, bus, index, 'peripheral')
            self.local_name = 'SmartCane'
            self.service_uuids = [BLE_SERVICE_UUID]
            self.include_tx_power = True
    
    class Service(dbus.service.Object):
        PATH_BASE = '/org/bluez/example/service'
        
        def __init__(self, bus, index, uuid, primary):
            self.path = self.PATH_BASE + str(index)
            self.bus = bus
            self.uuid = uuid
            self.primary = primary
            self.characteristics = []
            dbus.service.Object.__init__(self, bus, self.path)
        
        def get_properties(self):
            return {
                GATT_SERVICE_IFACE: {
                    'UUID': self.uuid,
                    'Primary': self.primary,
                    'Characteristics': dbus.Array([c.get_path() for c in self.characteristics], signature='o')
                }
            }
        
        def get_path(self):
            return dbus.ObjectPath(self.path)
        
        def add_characteristic(self, characteristic):
            self.characteristics.append(characteristic)
        
        @dbus.service.method(DBUS_PROP_IFACE, in_signature='s', out_signature='a{sv}')
        def GetAll(self, interface):
            if interface != GATT_SERVICE_IFACE:
                raise dbus.exceptions.DBusException('org.bluez.Error.InvalidArguments')
            return self.get_properties()[GATT_SERVICE_IFACE]
    
    class Characteristic(dbus.service.Object):
        def __init__(self, bus, index, uuid, flags, service):
            self.path = service.path + '/char' + str(index)
            self.bus = bus
            self.uuid = uuid
            self.service = service
            self.flags = flags
            self.descriptors = []
            dbus.service.Object.__init__(self, bus, self.path)
        
        def get_properties(self):
            return {
                GATT_CHRC_IFACE: {
                    'Service': self.service.get_path(),
                    'UUID': self.uuid,
                    'Flags': self.flags,
                    'Descriptors': dbus.Array([d.get_path() for d in self.descriptors], signature='o')
                }
            }
        
        def get_path(self):
            return dbus.ObjectPath(self.path)
        
        @dbus.service.method(DBUS_PROP_IFACE, in_signature='s', out_signature='a{sv}')
        def GetAll(self, interface):
            if interface != GATT_CHRC_IFACE:
                raise dbus.exceptions.DBusException('org.bluez.Error.InvalidArguments')
            return self.get_properties()[GATT_CHRC_IFACE]
        
        @dbus.service.method(GATT_CHRC_IFACE, in_signature='a{sv}', out_signature='ay')
        def ReadValue(self, options):
            return []
        
        @dbus.service.method(GATT_CHRC_IFACE, in_signature='aya{sv}')
        def WriteValue(self, value, options):
            pass
        
        @dbus.service.method(GATT_CHRC_IFACE)
        def StartNotify(self):
            pass
        
        @dbus.service.method(GATT_CHRC_IFACE)
        def StopNotify(self):
            pass
        
        @dbus.service.signal(DBUS_PROP_IFACE, signature='sa{sv}as')
        def PropertiesChanged(self, interface, changed, invalidated):
            pass
    
    class AlertCharacteristic(Characteristic):
        def __init__(self, bus, index, service, connected_event):
            Characteristic.__init__(self, bus, index, BLE_ALERT_CHAR_UUID, ['notify', 'read'], service)
            self.connected_event = connected_event
            self.notifying = False
            self.current_value = b'No obstacles'
            print(f'[BLE] Alert Characteristic UUID: {BLE_ALERT_CHAR_UUID}')
        
        def ReadValue(self, options):
            print(f'[BLE] ReadValue called - returning: {self.current_value}')
            return dbus.Array(self.current_value, signature='y')
        
        def StartNotify(self):
            print('[BLE] >>> StartNotify called!')
            if self.notifying:
                print('[BLE] Already notifying')
                return
            self.notifying = True
            self.connected_event.set()
            print('[BLE] ✓ Client connected and subscribed to notifications!')
        
        def StopNotify(self):
            print('[BLE] >>> StopNotify called!')
            if not self.notifying:
                return
            self.notifying = False
            self.connected_event.clear()
            print('[BLE] Client unsubscribed from notifications')
        
        def send_notification(self, message: str):
            if not self.notifying:
                return False
            self.current_value = message.encode('utf-8')
            print(f'[BLE] Sending notification: {message}')
            self.PropertiesChanged(GATT_CHRC_IFACE, {'Value': dbus.Array(self.current_value, signature='y')}, [])
            return True
    
    class SmartCaneService(Service):
        def __init__(self, bus, index, connected_event):
            Service.__init__(self, bus, index, BLE_SERVICE_UUID, True)
            print(f'[BLE] Service UUID: {BLE_SERVICE_UUID}')
            self.alert_char = AlertCharacteristic(bus, 0, self, connected_event)
            self.add_characteristic(self.alert_char)
    
    class Application(dbus.service.Object):
        def __init__(self, bus, connected_event):
            self.path = '/'
            self.services = []
            dbus.service.Object.__init__(self, bus, self.path)
            self.add_service(SmartCaneService(bus, 0, connected_event))
        
        def get_path(self):
            return dbus.ObjectPath(self.path)
        
        def add_service(self, service):
            self.services.append(service)
        
        @dbus.service.method(DBUS_OM_IFACE, out_signature='a{oa{sa{sv}}}')
        def GetManagedObjects(self):
            response = {}
            for service in self.services:
                response[service.get_path()] = service.get_properties()
                for chrc in service.characteristics:
                    response[chrc.get_path()] = chrc.get_properties()
            return response
    
    def find_adapter(bus):
        remote_om = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, '/'), DBUS_OM_IFACE)
        objects = remote_om.GetManagedObjects()
        for o, props in objects.items():
            if GATT_MANAGER_IFACE in props.keys():
                return o
        return None
    
    # Main BLE setup
    try:
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SystemBus()
        
        adapter_path = find_adapter(bus)
        if not adapter_path:
            print('[BLE] ERROR: No Bluetooth adapter found!')
            return
        
        service_manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter_path), GATT_MANAGER_IFACE)
        ad_manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter_path), LE_ADVERTISING_MANAGER_IFACE)
        
        # Power on adapter
        adapter_props = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter_path), DBUS_PROP_IFACE)
        adapter_props.Set('org.bluez.Adapter1', 'Powered', dbus.Boolean(1))
        
        # Create app and advertisement
        app = Application(bus, connected_event)
        adv = SmartCaneAdvertisement(bus, 0)
        alert_char = app.services[0].alert_char
        
        # Unregister any previous application/advertisement first (cleanup from previous runs)
        try:
            service_manager.UnregisterApplication(app.get_path())
            print('[BLE] Cleaned up previous GATT application')
        except dbus.exceptions.DBusException:
            pass  # No previous registration, that's fine
        
        try:
            ad_manager.UnregisterAdvertisement(adv.get_path())
            print('[BLE] Cleaned up previous advertisement')
        except dbus.exceptions.DBusException:
            pass  # No previous advertisement, that's fine
        
        # Register GATT application (only once!)
        registration_complete = {'gatt': False, 'adv': False}
        
        def on_gatt_registered():
            registration_complete['gatt'] = True
            print('[BLE] ✓ GATT registered (single instance)')
        
        def on_gatt_error(error):
            print(f'[BLE] GATT error: {error}')
        
        def on_adv_registered():
            registration_complete['adv'] = True
            print('[BLE] ✓ Advertising as "SmartCane"')
        
        def on_adv_error(error):
            print(f'[BLE] Advertising error: {error}')
        
        service_manager.RegisterApplication(app.get_path(), {},
            reply_handler=on_gatt_registered,
            error_handler=on_gatt_error)
        
        ad_manager.RegisterAdvertisement(adv.get_path(), {},
            reply_handler=on_adv_registered,
            error_handler=on_adv_error)
        
        print('[BLE] ✓ Server started')
        
        # Create mainloop
        mainloop = GLib.MainLoop()
        
        # Check for alerts from queue periodically
        def check_queue():
            if shutdown_event.is_set():
                mainloop.quit()
                return False
            
            try:
                while not alert_queue.empty():
                    msg = alert_queue.get_nowait()
                    if alert_char.send_notification(msg):
                        print(f'[BLE] Sent: {msg}')
            except:
                pass
            return True  # Continue checking
        
        # Check queue every 100ms
        GLib.timeout_add(100, check_queue)
        
        # Run mainloop
        mainloop.run()
        
    except Exception as e:
        print(f'[BLE] ERROR: {e}')


# ============================================================================
# Vision Process (runs OpenCV with Qt in isolation)
# ============================================================================

def run_vision(alert_queue: Queue, connected_event: Event, shutdown_event: Event):
    """Main vision processing - runs in main process"""
    
    print('[DETECTOR] Loading YOLO model...')
    detector = ObstacleDetector(MODEL_NAME)
    detector.load_model()
    
    print(f'\n[INIT] Opening video: {VIDEO_PATH}')
    cap = cv2.VideoCapture(VIDEO_PATH)
    
    if not cap.isOpened():
        print(f'[ERROR] Cannot open video: {VIDEO_PATH}')
        return
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f'[INIT] ✓ Video: {width}x{height} @ {fps:.1f}fps ({total_frames} frames)')
    
    # Create window
    cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_TITLE, 960, 540)
    
    annotator = FrameAnnotator()
    last_alert_time = 0
    frame_delay = max(1, int(1000 / fps))
    
    print('\n' + '=' * 65)
    print('  SMART CANE VISION SYSTEM - RUNNING')
    print('  Controls: [Q] Quit | [R] Restart | [T] Test Alert')
    print('=' * 65 + '\n')
    
    frame_count = 0
    start_time = time.time()
    
    while not shutdown_event.is_set():
        ret, frame = cap.read()
        
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        
        frame_count += 1
        current_time = time.time()
        
        # Detect obstacles - first detect, then check
        results = detector.detect(frame)
        obstacles = detector.check_for_obstacles(results)
        critical = obstacles[0] if obstacles else None
        
        # Get annotated frame from YOLO
        annotated = detector.get_annotated_frame(results)
        
        # Draw all obstacles with custom overlays
        annotator.draw_all_obstacles(annotated, obstacles)
        
        # Calculate FPS
        elapsed = current_time - start_time
        current_fps = frame_count / elapsed if elapsed > 0 else 0
        
        # Draw status bar
        cooldown_remaining = max(0, ALERT_COOLDOWN - (current_time - last_alert_time))
        annotator.draw_status_bar(
            annotated, 
            current_fps, 
            frame_count, 
            len(obstacles),
            cooldown_remaining,
            critical['name'] if critical else None
        )
        
        # BLE status overlay
        is_connected = connected_event.is_set()
        status_color = (0, 255, 0) if is_connected else (0, 165, 255)
        status_text = "BLE: Connected" if is_connected else "BLE: Waiting..."
        cv2.putText(annotated, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        
        # Send alert if needed
        if critical and (current_time - last_alert_time) >= ALERT_COOLDOWN:
            # Calculate position (left/center/right)
            x1, y1, x2, y2 = critical['bbox']
            cx = (x1 + x2) // 2
            frame_width = annotated.shape[1]
            if cx < frame_width // 3:
                position = "left"
            elif cx > 2 * frame_width // 3:
                position = "right"
            else:
                position = "center"
            
            msg = f"{critical['level']}:{critical['name']}:{critical['confidence']:.0%}:{position}"
            alert_queue.put(msg)
            
            # Draw alert banner
            annotator.draw_alert_banner(annotated, f"ALERT: {critical['name']} detected!", critical['level'])
            
            if is_connected:
                print(f'[ALERT] {msg}')
            else:
                print(f'[ALERT] (queued) {msg}')
            
            last_alert_time = current_time
        
        # Show frame
        cv2.imshow(WINDOW_TITLE, annotated)
        
        # Handle keys
        key = cv2.waitKey(frame_delay) & 0xFF
        if key == ord('q') or key == 27:
            break
        elif key == ord('r'):
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            print('[INFO] Video restarted')
        elif key == ord('t'):
            test_msg = "TEST:manual:100%:center"
            alert_queue.put(test_msg)
            print(f'[TEST] Sent: {test_msg}')
    
    cap.release()
    cv2.destroyAllWindows()
    shutdown_event.set()


# ============================================================================
# Main
# ============================================================================

def main():
    # Use 'spawn' for clean process separation
    mp.set_start_method('spawn', force=True)
    
    # Shared state
    alert_queue = Queue()
    connected_event = Event()
    shutdown_event = Event()
    
    def signal_handler(sig, frame):
        print('\n[INFO] Shutting down...')
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start BLE server in separate process
    print('[MAIN] Starting BLE server process...')
    ble_proc = Process(target=ble_server_process, args=(alert_queue, connected_event, shutdown_event), daemon=True)
    ble_proc.start()
    
    # Give BLE time to start
    time.sleep(2.0)
    
    try:
        # Run vision in main process
        run_vision(alert_queue, connected_event, shutdown_event)
    except Exception as e:
        print(f'[ERROR] {e}')
    finally:
        shutdown_event.set()
        ble_proc.terminate()
        ble_proc.join(timeout=2.0)
        print('[INFO] Goodbye!')


if __name__ == '__main__':
    main()
