import os
import subprocess
import tempfile
import zipfile
import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = "/opt/mysql-backup"

BACKUP_DIR = os.path.join(BASE_DIR, "backups")
LOG_DIR = os.path.join(BASE_DIR, "logs")

TOKEN_FILE = os.path.join(
    BASE_DIR,
    "credentials",
    "token.json"
)

EMAIL_ENV_FILE = os.path.join(
    BASE_DIR,
    "credentials",
    "email.env"
)

GOOGLE_DRIVE_FOLDER_ID = (
    "1mkHo7YCkMqSlcIANaHustdmc5PBy-Q9o"
)

SCOPES = [
    "https://www.googleapis.com/auth/drive"
]

EXCLUDED_DATABASES = {
    "information_schema",
    "mysql",
    "performance_schema",
    "sys",
}


# ============================================================
# DIRECTORIES
# ============================================================

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


# ============================================================
# LOGGING
# ============================================================

log_file = os.path.join(
    LOG_DIR,
    f"backup_{datetime.now().strftime('%Y-%m-%d')}.log"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# ============================================================
# LOAD EMAIL CONFIGURATION
# ============================================================

def load_email_config():

    values = {}

    with open(EMAIL_ENV_FILE, "r") as file:

        for line in file:

            line = line.strip()

            if not line or line.startswith("#"):
                continue

            key, value = line.split("=", 1)

            values[key.strip()] = value.strip()

    return values


# ============================================================
# SEND EMAIL
# ============================================================

def send_email(
    subject,
    body
):

    try:

        config = load_email_config()

        smtp_host = config["SMTP_HOST"]
        smtp_port = int(config["SMTP_PORT"])
        smtp_username = config["SMTP_USERNAME"]
        smtp_password = config["SMTP_PASSWORD"]
        smtp_from = config["SMTP_FROM"]
        smtp_to = config["SMTP_TO"]

        message = EmailMessage()

        message["Subject"] = subject
        message["From"] = smtp_from
        message["To"] = smtp_to

        message.set_content(body)

        with smtplib.SMTP(
            smtp_host,
            smtp_port,
            timeout=30
        ) as smtp:

            smtp.ehlo()

            smtp.starttls()

            smtp.ehlo()

            smtp.login(
                smtp_username,
                smtp_password
            )

            smtp.send_message(message)

        logger.info(
            "Email notification sent successfully."
        )

        return True

    except Exception as error:

        logger.error(
            "Email notification failed: %s",
            error
        )

        return False


# ============================================================
# FIND DATABASES
# ============================================================

def get_databases():

    logger.info(
        "Detecting MySQL databases..."
    )

    result = subprocess.run(
        [
            "sudo",
            "mysql",
            "-N",
            "-B",
            "-e",
            "SHOW DATABASES;"
        ],
        capture_output=True,
        text=True,
        check=True
    )

    databases = []

    for database in result.stdout.splitlines():

        database = database.strip()

        if (
            database
            and database not in EXCLUDED_DATABASES
        ):

            databases.append(database)

    databases.sort()

    logger.info(
        "Databases detected: %s",
        ", ".join(databases)
    )

    return databases


# ============================================================
# BACKUP DATABASE
# ============================================================

def backup_database(
    database,
    backup_directory
):

    output_file = os.path.join(
        backup_directory,
        f"{database}.sql"
    )

    logger.info(
        "Starting backup: %s",
        database
    )

    command = [
        "sudo",
        "mysqldump",
        "--single-transaction",
        "--routines",
        "--triggers",
        "--events",
        database
    ]

    try:

        with open(
            output_file,
            "w",
            encoding="utf-8"
        ) as sql_file:

            result = subprocess.run(
                command,
                stdout=sql_file,
                stderr=subprocess.PIPE,
                text=True
            )

        if result.returncode != 0:

            logger.error(
                "Backup failed for %s: %s",
                database,
                result.stderr.strip()
            )

            if os.path.exists(output_file):
                os.remove(output_file)

            return False

        size = os.path.getsize(
            output_file
        )

        logger.info(
            "Backup completed: %s (%.2f MB)",
            database,
            size / (1024 * 1024)
        )

        return True

    except Exception as error:

        logger.error(
            "Unexpected error backing up %s: %s",
            database,
            error
        )

        if os.path.exists(output_file):
            os.remove(output_file)

        return False


# ============================================================
# CREATE ZIP
# ============================================================

def create_zip(
    backup_directory,
    zip_file
):

    logger.info(
        "Creating ZIP archive..."
    )

    sql_files = []

    for filename in os.listdir(
        backup_directory
    ):

        if filename.endswith(".sql"):

            sql_files.append(
                os.path.join(
                    backup_directory,
                    filename
                )
            )

    if not sql_files:

        raise RuntimeError(
            "No SQL backup files were created."
        )

    with zipfile.ZipFile(
        zip_file,
        "w",
        compression=zipfile.ZIP_DEFLATED
    ) as zipf:

        for sql_file in sql_files:

            zipf.write(
                sql_file,
                arcname=os.path.basename(sql_file)
            )

    size = os.path.getsize(
        zip_file
    )

    logger.info(
        "ZIP created: %s (%.2f MB)",
        zip_file,
        size / (1024 * 1024)
    )


# ============================================================
# GOOGLE DRIVE AUTHENTICATION
# ============================================================

def get_drive_service():

    logger.info(
        "Authenticating with Google Drive..."
    )

    credentials = (
        Credentials.from_authorized_user_file(
            TOKEN_FILE,
            SCOPES
        )
    )

    if (
        credentials.expired
        and credentials.refresh_token
    ):

        logger.info(
            "Refreshing Google Drive token..."
        )

        credentials.refresh(
            Request()
        )

    if not credentials.valid:

        raise RuntimeError(
            "Google Drive credentials are invalid."
        )

    drive = build(
        "drive",
        "v3",
        credentials=credentials
    )

    logger.info(
        "Google Drive authentication successful."
    )

    return drive


# ============================================================
# GOOGLE DRIVE UPLOAD
# ============================================================

def upload_to_google_drive(
    drive,
    zip_file
):

    filename = os.path.basename(
        zip_file
    )

    logger.info(
        "Uploading %s to Google Drive...",
        filename
    )

    metadata = {
        "name": filename,
        "parents": [
            GOOGLE_DRIVE_FOLDER_ID
        ]
    }

    media = MediaFileUpload(
        zip_file,
        mimetype="application/zip",
        resumable=True
    )

    uploaded_file = (
        drive.files()
        .create(
            body=metadata,
            media_body=media,
            fields="id,name,size,webViewLink"
        )
        .execute()
    )

    logger.info(
        "Google Drive upload successful."
    )

    logger.info(
        "Google Drive File ID: %s",
        uploaded_file.get("id")
    )

    logger.info(
        "Google Drive File Name: %s",
        uploaded_file.get("name")
    )

    logger.info(
        "Google Drive Link: %s",
        uploaded_file.get("webViewLink")
    )

    return uploaded_file


# ============================================================
# DELETE OLD LOCAL ZIP FILES
# ============================================================

def delete_old_local_zips(
    current_zip
):

    logger.info(
        "Checking for old local ZIP backups..."
    )

    deleted_count = 0

    for filename in os.listdir(
        BACKUP_DIR
    ):

        if (
            filename.startswith("mysql-backup-")
            and filename.endswith(".zip")
        ):

            old_zip = os.path.join(
                BACKUP_DIR,
                filename
            )

            if (
                os.path.abspath(old_zip)
                == os.path.abspath(current_zip)
            ):
                continue

            try:

                os.remove(old_zip)

                deleted_count += 1

                logger.info(
                    "Deleted old local ZIP: %s",
                    filename
                )

            except Exception as error:

                logger.warning(
                    "Could not delete old ZIP %s: %s",
                    filename,
                    error
                )

    logger.info(
        "Old local ZIPs deleted: %d",
        deleted_count
    )


# ============================================================
# CLEAN TEMPORARY SQL FILES
# ============================================================

def cleanup_temp_directory(
    backup_directory
):

    if not os.path.exists(
        backup_directory
    ):
        return

    for filename in os.listdir(
        backup_directory
    ):

        file_path = os.path.join(
            backup_directory,
            filename
        )

        if os.path.isfile(file_path):

            os.remove(file_path)

    try:

        os.rmdir(
            backup_directory
        )

    except OSError:

        pass


# ============================================================
# MAIN BACKUP PROCESS
# ============================================================

def main():

    start_time = datetime.now()

    logger.info("=" * 70)

    logger.info(
        "MYSQL AUTOMATIC BACKUP STARTED"
    )

    logger.info("=" * 70)

    timestamp = start_time.strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    backup_directory = tempfile.mkdtemp(
        prefix="mysql_backup_",
        dir=BACKUP_DIR
    )

    zip_file = os.path.join(
        BACKUP_DIR,
        f"mysql-backup-{timestamp}.zip"
    )

    successful_databases = []

    failed_databases = []

    google_drive_uploaded = False

    uploaded_file = None

    try:

        # ----------------------------------------------------
        # 1. Detect databases
        # ----------------------------------------------------

        databases = get_databases()

        if not databases:

            raise RuntimeError(
                "No application databases found."
            )

        # ----------------------------------------------------
        # 2. Backup databases
        # ----------------------------------------------------

        for database in databases:

            success = backup_database(
                database,
                backup_directory
            )

            if success:

                successful_databases.append(
                    database
                )

            else:

                failed_databases.append(
                    database
                )

        logger.info(
            "Successful databases: %s",
            ", ".join(successful_databases)
            if successful_databases
            else "None"
        )

        logger.info(
            "Failed databases: %s",
            ", ".join(failed_databases)
            if failed_databases
            else "None"
        )

        if not successful_databases:

            raise RuntimeError(
                "All database backups failed."
            )

        # ----------------------------------------------------
        # 3. Create ZIP
        # ----------------------------------------------------

        create_zip(
            backup_directory,
            zip_file
        )

        # ----------------------------------------------------
        # 4. Upload to Google Drive
        # ----------------------------------------------------

        drive = get_drive_service()

        uploaded_file = upload_to_google_drive(
            drive,
            zip_file
        )

        google_drive_uploaded = True

        # ----------------------------------------------------
        # 5. Delete temporary SQL files
        # ----------------------------------------------------

        cleanup_temp_directory(
            backup_directory
        )

        logger.info(
            "Temporary SQL files deleted."
        )

        # ----------------------------------------------------
        # 6. Delete OLD local ZIP files
        # ----------------------------------------------------

        delete_old_local_zips(
            zip_file
        )

        # ----------------------------------------------------
        # 7. Keep NEW ZIP
        # ----------------------------------------------------

        logger.info(
            "Latest ZIP retained on server: %s",
            zip_file
        )

        # ----------------------------------------------------
        # 8. SUCCESS / PARTIAL SUCCESS EMAIL
        # ----------------------------------------------------

        if failed_databases:

            subject = (
                "⚠️ MySQL Backup Partially Failed - EC2"
            )

            status = "PARTIAL FAILURE"

        else:

            subject = (
                "✅ MySQL Backup Successful - EC2"
            )

            status = "SUCCESS"

        email_body = f"""
MySQL Backup Report

Status: {status}

Server:
EC2 Production Server

Backup Date:
{start_time.strftime("%Y-%m-%d %H:%M:%S")} UTC

Total Databases Detected:
{len(databases)}

Successfully Backed Up:
{len(successful_databases)}

Failed:
{len(failed_databases)}

Successful Databases:
{chr(10).join("✓ " + db for db in successful_databases) if successful_databases else "None"}

Failed Databases:
{chr(10).join("✗ " + db for db in failed_databases) if failed_databases else "None"}

Local ZIP:
{os.path.basename(zip_file)}

Google Drive Upload:
{"SUCCESS" if google_drive_uploaded else "FAILED"}

Google Drive File:
{uploaded_file.get("name") if uploaded_file else "Not uploaded"}

Google Drive File ID:
{uploaded_file.get("id") if uploaded_file else "N/A"}

No backup file is attached to this email.

Regards,
EC2 MySQL Backup System
"""

        send_email(
            subject,
            email_body
        )

        # ----------------------------------------------------
        # 9. FINAL LOG
        # ----------------------------------------------------

        logger.info("=" * 70)

        logger.info(
            "MYSQL BACKUP COMPLETED"
        )

        logger.info(
            "Databases backed up: %d",
            len(successful_databases)
        )

        logger.info(
            "Databases failed: %d",
            len(failed_databases)
        )

        logger.info("=" * 70)

    except Exception as error:

        logger.exception(
            "BACKUP FAILED: %s",
            error
        )

        # Keep the ZIP if it was already created.
        # This protects the local backup if Google Drive
        # or another later step fails.

        cleanup_temp_directory(
            backup_directory
        )

        # ----------------------------------------------------
        # FAILURE EMAIL
        # ----------------------------------------------------

        failed_list = (
            "\n".join(
                "✗ " + db
                for db in failed_databases
            )
            if failed_databases
            else "No database-specific failure recorded."
        )

        successful_list = (
            "\n".join(
                "✓ " + db
                for db in successful_databases
            )
            if successful_databases
            else "None"
        )

        email_body = f"""
MySQL Backup Failure Report

Status:
FAILED

Server:
EC2 Production Server

Backup Date:
{start_time.strftime("%Y-%m-%d %H:%M:%S")} UTC

Successfully Backed Up:
{successful_list}

Failed Databases:
{failed_list}

Error:
{error}

Local ZIP:
{os.path.basename(zip_file) if os.path.exists(zip_file) else "ZIP was not created"}

Google Drive Upload:
{"SUCCESS" if google_drive_uploaded else "FAILED / NOT COMPLETED"}

Please check the backup log:

{log_file}

No backup file is attached to this email.

Regards,
EC2 MySQL Backup System
"""

        send_email(
            "🚨 MySQL Backup FAILED - EC2",
            email_body
        )

        raise


if __name__ == "__main__":
    main()
