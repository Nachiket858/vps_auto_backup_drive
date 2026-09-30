from google.oauth2 import service_account
from googleapiclient.discovery import build

CREDENTIALS_FILE = "/opt/mysql-backup/credentials/google-service-account.json"

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

response = service.files().list(
    pageSize=10,
    fields="files(id,name,mimeType)"
).execute()

print("\nGoogle Drive authentication successful!\n")

files = response.get("files", [])

if not files:
    print("No files/folders visible to the service account.")
else:
    print("Files/Folders accessible to the service account:")

    for file in files:
        print(
            f"- {file['name']} "
            f"({file['mimeType']}) "
            f"[ID: {file['id']}]"
        )
