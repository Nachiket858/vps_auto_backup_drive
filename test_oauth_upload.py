from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

TOKEN_FILE = "/opt/mysql-backup/credentials/token.json"

FOLDER_ID = "1mkHo7YCkMqSlcIANaHustdmc5PBy-Q9o"

TEST_FILE = "/opt/mysql-backup/test-upload.txt"

SCOPES = ["https://www.googleapis.com/auth/drive"]

credentials = Credentials.from_authorized_user_file(
    TOKEN_FILE,
    SCOPES
)

drive = build("drive", "v3", credentials=credentials)

file_metadata = {
    "name": "server-backup-oauth-test.txt",
    "parents": [FOLDER_ID]
}

media = MediaFileUpload(
    TEST_FILE,
    mimetype="text/plain"
)

uploaded_file = drive.files().create(
    body=file_metadata,
    media_body=media,
    fields="id,name,webViewLink"
).execute()

print("Upload successful!")
print("File ID:", uploaded_file["id"])
print("File Name:", uploaded_file["name"])
print("Link:", uploaded_file.get("webViewLink"))
