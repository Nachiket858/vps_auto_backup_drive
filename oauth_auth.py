from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_FILE = "/opt/mysql-backup/credentials/oauth-client.json"
TOKEN_FILE = "/opt/mysql-backup/credentials/token.json"

SCOPES = ["https://www.googleapis.com/auth/drive"]

flow = InstalledAppFlow.from_client_secrets_file(
    CLIENT_FILE,
    SCOPES
)

credentials = flow.run_console()

with open(TOKEN_FILE, "w") as token:
    token.write(credentials.to_json())

print("OAuth authentication successful!")
print(f"Token saved to: {TOKEN_FILE}")
