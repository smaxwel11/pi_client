import subprocess
import logging
import os
import time

logger = logging.getLogger(__name__)

class AudioRecorder:
    def __init__(self):
        self.process = None
        # Default to hw:1,0 (common for USB mics) but allow override via .env
        self.device = os.getenv('ALSA_DEVICE', 'hw:1,0')
        self.output_dir = os.getenv('RECORDING_DIR', './recordings')
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def start_recording(self, class_name, part_number=1):
        """Spawns an FFmpeg subprocess to record audio."""
        if self.process and self.process.poll() is None:
            # FAILSAFE #1: Overlapping Event Lock
            logger.error("ALSA DEVICE LOCK: A recording is already in progress! Ignoring overlapping trigger to prevent ALSA crash.")
            return None

        # Sanitize class name for safe filenames
        room_number = os.getenv('DEVICE_ID', 'UnknownRoom')
        safe_room_number = "".join([c for c in room_number if c.isalpha() or c.isdigit() or c==' ']).rstrip().replace(" ", "_")
        safe_class_name = "".join([c for c in class_name if c.isalpha() or c.isdigit() or c==' ']).rstrip().replace(" ", "_")
        date_str = time.strftime("%m-%d")
        filename = f"{safe_room_number}_{safe_class_name}_{date_str}_Part{part_number}.mp3"
        filepath = os.path.join(self.output_dir, filename)
        self.current_filepath = filepath

        # Native FFmpeg command using ALSA input, applying filters, and real-time MP3 encoding
        cmd = [
            'ffmpeg',
            '-y',                      # Overwrite output files if they exist
            '-f', 'alsa',              # Input format
            '-i', self.device,         # Input device (USB Mic)
            '-af', 'acompressor,loudnorm', # Audio filters for dictation clarity
            '-c:a', 'libmp3lame',      # MP3 encoder (streamable/safe for power loss)
            '-b:a', '128k',            # Bitrate
            filepath
        ]

        logger.info(f"Starting recording via FFmpeg: {filepath}")
        try:
            # We use subprocess.Popen to run it in the background without blocking Python
            self.process = subprocess.Popen(
                cmd, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            return filepath
        except Exception as e:
            logger.error(f"Failed to start FFmpeg: {e}")
            return None

    def stop_recording(self):
        """Terminates the FFmpeg subprocess and returns the filepath."""
        if self.process and self.process.poll() is None:
            logger.info("Stopping recording (terminating FFmpeg)...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("FFmpeg did not terminate gracefully, killing it.")
                self.process.kill()
            self.process = None
            return getattr(self, 'current_filepath', None)
        else:
            logger.info("No active recording to stop.")
            return None
