import time
import datetime
import logging
import sys
import socket
import os

from fault_tolerance import StateManager
from telemetry import TelemetryClient
from scheduler import CalendarScheduler
from storage import DriveUploader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def wait_for_ntp_sync():
    """Wait until the system clock is reasonable (sync'd via NTP)."""
    logger.info("Checking system clock for NTP sync...")
    while True:
        current_year = datetime.datetime.now().year
        if current_year >= 2024:
            logger.info(f"System clock is successfully synced! Current time: {datetime.datetime.now()}")
            break
        logger.warning(f"System clock NOT synced (Year is {current_year}). Waiting for network time...")
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
        except OSError:
            pass
        time.sleep(5)

def recover_orphaned_files():
    """Uploads any files left on the SD card due to a sudden power loss."""
    uploader = DriveUploader()
    rec_dir = os.getenv('RECORDING_DIR', './recordings')
    if os.path.exists(rec_dir):
        for file in os.listdir(rec_dir):
            if file.endswith('.mp3'):
                filepath = os.path.join(rec_dir, file)
                logger.warning(f"Found orphaned recording from crash: {filepath}. Uploading immediately...")
                uploader.upload_file(filepath)

def main():
    logger.info("Starting Pi Classroom Recorder Daemon")
    
    wait_for_ntp_sync()

    logger.info("Initializing fault tolerance DB...")
    state_manager = StateManager()
    
    logger.info("Checking for orphaned files to upload...")
    recover_orphaned_files()

    last_state = state_manager.get_state()
    if last_state and last_state.get('is_recording'):
        class_name = last_state.get('class_name')
        part_number = last_state.get('part_number', 1)
        logger.warning(f"Power loss detected during '{class_name}' (Part {part_number})!")
        logger.warning(f"Pre-crash file is uploading as Part {part_number}. Leaving state active so scheduler starts Part {part_number + 1}...")

    logger.info("Starting Telemetry heartbeat...")
    telemetry_client = TelemetryClient(state_manager)
    telemetry_client.start()

    logger.info("Initializing Google Calendar scheduler...")
    scheduler = CalendarScheduler(state_manager=state_manager)
    scheduler.start()

    logger.info("Initialization complete. Entering main loop.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Daemon stopping...")
        scheduler.shutdown()
        telemetry_client.stop()

if __name__ == "__main__":
    main()
