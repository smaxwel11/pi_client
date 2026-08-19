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
        # ID of the specific Drive Folder (Root Folder: "Classroom_Recordings")
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

    def _get_or_create_folder(self, folder_name, parent_id):
        """Queries Drive for a folder by name and parent. Creates it if it doesn't exist."""
        # Escape single quotes in folder names to prevent Drive API query syntax errors
        safe_query_name = folder_name.replace("'", "\\'")
        # Strict query parameter to prevent creating duplicate folders
        query = f"name='{safe_query_name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        
        try:
            response = self.service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
            files = response.get('files', [])
            
            if files:
                logger.debug(f"Found existing folder '{folder_name}' with ID: {files[0].get('id')}")
                return files[0].get('id')
            else:
                logger.info(f"Creating new folder '{folder_name}' in parent '{parent_id}'...")
                folder_metadata = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [parent_id]
                }
                folder = self.service.files().create(body=folder_metadata, fields='id').execute()
                return folder.get('id')
        except Exception as e:
            logger.error(f"Error checking/creating folder '{folder_name}': {e}")
            return parent_id # Fallback to parent if query fails

    def upload_file(self, filepath):
        if not self.service or not self.folder_id:
            logger.error("Drive API not initialized or DRIVE_FOLDER_ID missing.")
            return False

        if not os.path.exists(filepath):
            logger.error(f"File {filepath} does not exist for upload.")
            return False

        filename = os.path.basename(filepath)
        
        # Route the file dynamically: Root -> Room -> Class
        # Expected format: [room_number]_[class_name]_[MM-DD]_Part[X].mp3
        target_parent_id = self.folder_id
        parts = filename.replace('.mp3', '').split('_')
        
        # Ensure it actually matches the format before trying to route it
        if len(parts) >= 4:
            room_name = parts[0]
            class_name = "_".join(parts[1:-2])
            
            # 1. Get/Create Room Folder
            room_folder_id = self._get_or_create_folder(room_name, self.folder_id)
            # 2. Get/Create Class Folder inside Room Folder
            class_folder_id = self._get_or_create_folder(class_name, room_folder_id)
            
            target_parent_id = class_folder_id
            
        file_metadata = {
            'name': filename,
            'parents': [target_parent_id]
        }
        
        # Use resumable uploads for large MP3 files to handle flaky Wi-Fi
        media = MediaFileUpload(filepath, mimetype='audio/mpeg', resumable=True)
        
        try:
            logger.info(f"Uploading {filename} to Google Drive folder {target_parent_id}...")
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
