import os
import datetime
import logging
import pytz
import threading
from dateutil import parser
from google.oauth2 import service_account
from googleapiclient.discovery import build
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# Import our assemblies
from audio import AudioRecorder
from storage import DriveUploader

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

class CalendarScheduler:
    def __init__(self, state_manager):
        load_dotenv()
        self.state_manager = state_manager
        self.calendar_id = os.getenv('CALENDAR_ID')
        self.credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'credentials.json')
        
        self.timezone_str = os.getenv('TIMEZONE', 'America/New_York')
        self.tz = pytz.timezone(self.timezone_str)
        
        self.scheduler = BackgroundScheduler(timezone=self.tz)
        self.service = self._authenticate_google_calendar()
        self.audio_recorder = AudioRecorder()
        self.uploader = DriveUploader()

    def _authenticate_google_calendar(self):
        try:
            if not os.path.exists(self.credentials_path):
                logger.warning(f"Credentials file not found at {self.credentials_path}. Calendar API won't initialize.")
                return None
            creds = service_account.Credentials.from_service_account_file(
                self.credentials_path, scopes=SCOPES)
            service = build('calendar', 'v3', credentials=creds, cache_discovery=False)
            logger.info("Successfully authenticated with Google Calendar API.")
            return service
        except Exception as e:
            logger.error(f"Failed to authenticate with Google Calendar: {e}")
            return None

    def fetch_upcoming_events(self):
        if not self.service or not self.calendar_id:
            logger.error("Google Calendar API not initialized properly. Cannot fetch events.")
            return []
            
        now_dt = datetime.datetime.now(self.tz)
        tomorrow_dt = now_dt + datetime.timedelta(days=1)
        
        now = now_dt.isoformat()
        tomorrow = tomorrow_dt.isoformat()
        
        try:
            logger.info(f"Fetching calendar events from {now} to {tomorrow}...")
            events_result = self.service.events().list(
                calendarId=self.calendar_id, 
                timeMin=now,
                timeMax=tomorrow,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])
            return events
        except Exception as e:
            logger.error(f"Error fetching events: {e}")
            return []
            
    def execute_start_recording(self, summary, part_number):
        logger.info(f"Triggering start recording for {summary} Part {part_number}")
        filepath = self.audio_recorder.start_recording(summary, part_number)
        if filepath:
            self.state_manager.set_recording(summary, part_number)

    def execute_stop_recording(self):
        logger.info("Triggering stop recording")
        filepath = self.audio_recorder.stop_recording()
        if filepath:
            self.state_manager.clear_recording()
            threading.Thread(target=self.uploader.upload_file, args=(filepath,), daemon=True).start()

    def start(self):
        logger.info("Starting background scheduler...")
        self.scheduler.start()
        self.scheduler.add_job(self.sync_schedule, 'interval', minutes=15, id='sync_job', replace_existing=True)
        self.sync_schedule()
        
    def sync_schedule(self):
        events = self.fetch_upcoming_events()
        if not events:
            logger.info("No upcoming events found for the next 24 hours.")
            return
            
        existing_job_ids = [job.id for job in self.scheduler.get_jobs()]
        now = datetime.datetime.now(self.tz)
            
        for event in events:
            event_id = event['id']
            summary = event.get('summary', 'Unknown_Class')
            
            start_str = event['start'].get('dateTime')
            end_str = event['end'].get('dateTime')
            if not start_str or not end_str:
                continue
                
            start_dt = parser.parse(start_str).astimezone(self.tz)
            end_dt = parser.parse(end_str).astimezone(self.tz)
            
            record_start_dt = start_dt - datetime.timedelta(minutes=5)
            record_end_dt = end_dt + datetime.timedelta(minutes=5)
            
            start_job_id = f"start_{event_id}"
            end_job_id = f"stop_{event_id}"
            
            # If we are currently INSIDE the recording window (e.g. rebooted mid-class)
            if record_start_dt <= now < record_end_dt:
                state = self.state_manager.get_state()
                part_num = 1
                if state and state.get('class_name') == summary and state.get('is_recording'):
                    part_num = state.get('part_number', 1) + 1
                    logger.warning(f"Resuming interrupted class '{summary}' as Part {part_num}...")
                else:
                    logger.info(f"Class '{summary}' is currently active! Starting late recording...")
                
                # Start immediately since we missed the scheduled start_date
                self.execute_start_recording(summary, part_num)
                
                # Still schedule the stop job
                if record_end_dt > now:
                    self.scheduler.add_job(
                        self.execute_stop_recording, 
                        'date', 
                        run_date=record_end_dt, 
                        id=end_job_id,
                        replace_existing=True
                    )
            
            # Future event, schedule normally
            elif record_start_dt > now:
                self.scheduler.add_job(
                    self.execute_start_recording, 
                    'date', 
                    run_date=record_start_dt, 
                    args=[summary, 1],
                    id=start_job_id,
                    replace_existing=True
                )
                if start_job_id not in existing_job_ids:
                    logger.info(f"Scheduled START for '{summary}' at {record_start_dt}")
                    
                if record_end_dt > now:
                    self.scheduler.add_job(
                        self.execute_stop_recording, 
                        'date', 
                        run_date=record_end_dt, 
                        id=end_job_id,
                        replace_existing=True
                    )
                    if end_job_id not in existing_job_ids:
                        logger.info(f"Scheduled STOP for '{summary}' at {record_end_dt}")
                    
    def shutdown(self):
        logger.info("Shutting down scheduler...")
        self.scheduler.shutdown()
