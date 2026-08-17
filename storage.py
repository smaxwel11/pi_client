import os
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

# Scopes for Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive.file']

class DriveUploader:
    def __init__(self):
        self.credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'credentials.json')
        # ID of the specific Drive Folder you shared with the Service Account
        self.folder_id = os.getenv('DRIVE_FOLDER_ID')
        self.service = self._authenticate_drive()

    def _authenticate_drive(self):
        try:
            if not os.path.exists(self.credentials_path):
                logger.warning(f"Credentials file not found at {self.credentials_path}. Drive API won't initialize.")
                return None
            creds = service_account.Credentials.from_service_account_file(
                self.credentials_path, scopes=SCOPES)
            service = build('drive', 'v3', credentials=creds, cache_discovery=False)
            logger.info("Successfully authenticated with Google Drive API.")
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
