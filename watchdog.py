import time
import logging
import requests
import threading
import os

logger = logging.getLogger(__name__)

class ConnectivityWatchdog(threading.Thread):
    def __init__(self, state_manager):
        super().__init__(daemon=True)
        self.state_manager = state_manager
        self.failure_counter = 0

    def run(self):
        logger.info("Starting Internal Wi-Fi Watchdog Timer...")
        while True:
            time.sleep(300) # Sleep for 5 minutes

            try:
                # Use Google's lightweight 204 endpoint to avoid ICMP blocks
                response = requests.get('http://connectivitycheck.gstatic.com/generate_204', timeout=5)
                if response.status_code in (200, 204):
                    if self.failure_counter > 0:
                        logger.info("Wi-Fi connection is healthy. Resetting watchdog counter.")
                    self.failure_counter = 0
                else:
                    self.failure_counter += 1
                    logger.warning(f"Watchdog HTTP ping failed (Status {response.status_code}). Counter: {self.failure_counter}/2")
            except requests.exceptions.RequestException as e:
                self.failure_counter += 1
                logger.warning(f"Watchdog HTTP ping exception (Network dead): {e}. Counter: {self.failure_counter}/2")

            # The Trigger
            if self.failure_counter >= 2:
                logger.error("Watchdog triggered: 10+ minutes of dead Wi-Fi detected.")
                state = self.state_manager.get_state()
                
                if state and state.get('is_recording'):
                    # We are in the middle of a class! Do NOT kill FFmpeg. Let it save to the SD card.
                    logger.warning("Active recording in progress. Postponing hardware reboot to protect FFmpeg process.")
                else:
                    # Wi-Fi is dead and we are idle. Power-cycle the hardware!
                    logger.critical("No active recording. Executing hardware power-cycle to recover Wi-Fi...")
                    os.system('sudo reboot')
                    time.sleep(60) # Pause thread while waiting for OS shutdown
