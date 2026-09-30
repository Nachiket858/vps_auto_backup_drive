from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

CREDENTIALS_FILE = "/opt/mysql-backup/credentials/google-service-account.json"

FOLDER_ID = "1mkHo7YCkMqSlcIANaHustdmc5PBy-Q9o"

TEST_FILE = "/opt/mysql-backup/test-upload.txt"

SCOPES = [
    "https://www.googleapis.com/auth/drive"
]

credentials = service_account.Credentials.from_service_account_file(
    CREDENTIALS_FILE,
    scopes=SCOPES
)

service = build(
    "drive",
    "v3",
    credentials=credentials
)

file_metadata = {
    "name": "test-upload.txt",
    "parents": [FOLDER_ID]
}

media = MediaFileUpload(
    TEST_FILE,
    mimetype="text/plain"
)

uploaded_file = service.files().create(
    body=file_metadata,
    media_body=media,
    fields="id,name,webViewLink"
).execute()

print("\nUpload successful!")
print("File name:", uploaded_file.get("name"))
print("File ID:", uploaded_file.get("id"))
print("Drive link:", uploaded_file.get("webViewLink"))
