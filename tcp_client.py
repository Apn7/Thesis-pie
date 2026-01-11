"""
=============================================================================
  AUTONOMOUS SMART CANE - TCP CLIENT MODULE
  Handles IoT transmission to Flutter companion app
  Implements persistent connection with auto-reconnect
=============================================================================
"""

import socket
import time
from config import CONNECTION_TIMEOUT


class TCPClient:
    """
    TCP Client for sending alerts to the Flutter companion app.
    Maintains a persistent connection with automatic reconnection.
    """
    
    def __init__(self, host: str, port: int):
        """
        Initialize TCP Client.
        
        Args:
            host: IP address of the receiving device
            port: TCP port number
        """
        self.host = host
        self.port = port
        self.timeout = CONNECTION_TIMEOUT
        self.socket = None
        self.is_connected = False
        self.reconnect_delay = 1.0  # Seconds between reconnect attempts
        self.last_reconnect_attempt = 0.0
    
    def connect(self) -> bool:
        """
        Establish persistent connection to Flutter app.
        
        Returns:
            True if connected successfully, False otherwise
        """
        if self.is_connected:
            return True
        
        try:
            # Create new socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            
            # Enable TCP keepalive to detect dead connections
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            
            # Connect to Flutter app
            self.socket.connect((self.host, self.port))
            
            # Set socket to non-blocking for sends (with timeout)
            self.socket.setblocking(True)
            self.socket.settimeout(self.timeout)
            
            self.is_connected = True
            print(f"[TCP] ✓ Connected to {self.host}:{self.port}")
            return True
            
        except socket.timeout:
            print(f"[TCP] ✗ Connection timeout - Is the Flutter app running?")
            self._cleanup_socket()
            return False
        except ConnectionRefusedError:
            print(f"[TCP] ✗ Connection refused - Check if app is listening on port {self.port}")
            self._cleanup_socket()
            return False
        except OSError as e:
            print(f"[TCP] ✗ Network error: {e}")
            self._cleanup_socket()
            return False
        except Exception as e:
            print(f"[TCP] ✗ Unexpected error: {e}")
            self._cleanup_socket()
            return False
    
    def disconnect(self):
        """
        Gracefully close the connection.
        """
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except:
                pass
            self._cleanup_socket()
        print("[TCP] Disconnected")
    
    def _cleanup_socket(self):
        """Clean up socket resources."""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.socket = None
        self.is_connected = False
    
    def _try_reconnect(self) -> bool:
        """
        Attempt to reconnect with rate limiting.
        
        Returns:
            True if reconnected, False otherwise
        """
        current_time = time.time()
        
        # Rate limit reconnection attempts
        if current_time - self.last_reconnect_attempt < self.reconnect_delay:
            return False
        
        self.last_reconnect_attempt = current_time
        print("[TCP] Attempting to reconnect...")
        return self.connect()
    
    def send_alert(self, message: str) -> bool:
        """
        Send a TCP message through the persistent connection.
        Automatically reconnects if connection was lost.
        
        Args:
            message: Alert text to transmit
        
        Returns:
            True if message sent successfully, False otherwise
        """
        # Ensure we're connected (reconnect if needed)
        if not self.is_connected:
            if not self._try_reconnect():
                return False
        
        try:
            # Send alert message with newline delimiter for Flutter parsing
            data = (message + "\n").encode('utf-8')
            self.socket.sendall(data)
            
            print(f"[TCP] ✓ Alert sent: {message[:40]}...")
            return True
            
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            print("[TCP] ✗ Connection lost - will reconnect on next alert")
            self._cleanup_socket()
            return False
        except socket.timeout:
            print("[TCP] ✗ Send timeout")
            self._cleanup_socket()
            return False
        except OSError as e:
            print(f"[TCP] ✗ Send error: {e}")
            self._cleanup_socket()
            return False
        except Exception as e:
            print(f"[TCP] ✗ Unexpected send error: {e}")
            self._cleanup_socket()
            return False
    
    def test_connection(self) -> bool:
        """
        Test if the Flutter app is reachable by attempting to connect.
        
        Returns:
            True if connection successful, False otherwise
        """
        return self.connect()
    
    @property
    def status(self) -> str:
        """Get human-readable connection status."""
        return "Connected" if self.is_connected else "Disconnected"
    
    def __enter__(self):
        """Context manager entry - connect."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - disconnect."""
        self.disconnect()
        return False


# Standalone test
if __name__ == "__main__":
    from config import LAPTOP_IP, LAPTOP_PORT, ALERT_MESSAGE
    
    print("=" * 50)
    print("  TCP CLIENT MODULE TEST (Persistent Connection)")
    print("=" * 50)
    print(f"\nTarget: {LAPTOP_IP}:{LAPTOP_PORT}")
    print(f"Message: {ALERT_MESSAGE}")
    print("-" * 50)
    
    # Test with context manager (auto connect/disconnect)
    with TCPClient(LAPTOP_IP, LAPTOP_PORT) as client:
        print(f"\n[STATUS] {client.status}")
        
        if client.is_connected:
            print("\n[TEST] Sending 3 test alerts...")
            for i in range(3):
                success = client.send_alert(f"Test alert #{i+1}")
                time.sleep(1)
            
            print("\n✓ Test complete!")
        else:
            print("\n✗ Could not connect.")
            print("  Make sure the Flutter app is running and listening.")
