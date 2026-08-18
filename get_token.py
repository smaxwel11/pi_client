import os
from google_auth_oauthlib.flow import InstalledAppFlow

# Scopes for BOTH Google Drive and Google Calendar
SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/calendar.readonly'
]

def main():
    print("==================================================")
    print("  OAuth 2.0 Token Generator for Pi Recorders      ")
    print("==================================================\n")
    
    if not os.path.exists('client_secret.json'):
        print("ERROR: 'client_secret.json' not found in the current directory.")
        print("Please download your OAuth 2.0 Client ID JSON file from Google Cloud Console,")
        print("rename it to 'client_secret.json', and place it next to this script.")
        return

    print("Opening your web browser to authenticate with Google...")
    
    # Initialize the OAuth flow
    flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
    creds = flow.run_local_server(port=0)

    # Save the credentials for the next run
    with open('token.json', 'w') as token:
        token.write(creds.to_json())

    print("\nSUCCESS! 'token.json' has been generated.")
    print("You can now transfer 'token.json' to your Raspberry Pis.")

if __name__ == '__main__':
    main()
