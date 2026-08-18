import os
import logging
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

# Scopes for Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive.file']

class DriveUploader:
    def __init__(self):
        self.token_path = os.getenv('GOOGLE_OAUTH_TOKEN', 'token.json')
        # ID of the specific Drive Folder you shared
        self.folder_id = os.getenv('DRIVE_FOLDER_ID')
        self.service = self._authenticate_drive()

    def _authenticate_drive(self):
        creds = None
        try:
            if os.path.exists(self.token_path):
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    logger.error(f"Missing or invalid {self.token_path}. Run get_token.py on your PC first.")
                    return None
            service = build('drive', 'v3', credentials=creds, cache_discovery=False)
            logger.info("Successfully authenticated with Google Drive API via OAuth Token.")
            return service
        except Exception as e:
            logger.error(f"Failed to authenticate with Google Drive: {e}")
            return None

    def upload_file(self, filepath):
        if not self.service or not self.folder_id:
            logger.error("Drive API not initialized or DRIVE_FOLDER_ID missing.")
            return False

        if not os.path.exists(filepath):
            logger.error(f"File {filepath} does not exist for upload.")
            return False

        filename = os.path.basename(filepath)
        file_metadata = {
            'name': filename,
            'parents': [self.folder_id]
        }
        
        # Use resumable uploads for large MP3 files to handle flaky Wi-Fi
        media = MediaFileUpload(filepath, mimetype='audio/mpeg', resumable=True)
        
        try:
            logger.info(f"Uploading {filename} to Google Drive...")
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            logger.info(f"Successfully uploaded {filename}. File ID: {file.get('id')}")
            
            # Clean up the local SD card cache after a successful upload
            os.remove(filepath)
            logger.info(f"Deleted local cache: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload {filename} to Google Drive: {e}")
            return False
