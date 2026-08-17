import os
import time
import requests
import logging
import threading
from dotenv import load_dotenv
from fault_tolerance import StateManager

logger = logging.getLogger(__name__)

class TelemetryClient:
    def __init__(self, state_manager: StateManager):
        load_dotenv()
        self.hub_url = os.getenv('CENTRAL_HUB_URL', 'http://localhost:3000')
        self.device_id = os.getenv('DEVICE_ID', 'Pi_Room_Unknown')
        self.state_manager = state_manager
        self._stop_event = threading.Event()
        self.thread = None

    def _ping_hub(self):
        while not self._stop_event.is_set():
            try:
                state = self.state_manager.get_state()
                payload = {
                    'device_id': self.device_id,
                    'status': 'recording' if state and state.get('is_recording') else 'idle',
                    'class_name': state.get('class_name') if state else None,
                    'timestamp': time.time()
                }
                
                # Send to Central Hub
                response = requests.post(f"{self.hub_url}/api/telemetry", json=payload, timeout=5)
                
                if response.status_code == 200:
                    logger.debug("Telemetry heartbeat sent successfully.")
                else:
                    logger.warning(f"Telemetry heartbeat failed with status {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Failed to reach Central Hub for telemetry: {e}")
                
            # Ping every 10 minutes (600 seconds) to conserve Vercel DB free limits
            self._stop_event.wait(600)

    def start(self):
        logger.info(f"Starting Telemetry thread for device: {self.device_id}")
        self.thread = threading.Thread(target=self._ping_hub, daemon=True)
        self.thread.start()

    def stop(self):
        logger.info("Stopping Telemetry thread...")
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
