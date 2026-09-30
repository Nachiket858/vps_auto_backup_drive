import os
import smtplib
from email.message import EmailMessage


ENV_FILE = "/opt/mysql-backup/credentials/email.env"


def load_env_file(path):
    values = {}

    with open(path, "r") as file:
        for line in file:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()

    return values


config = load_env_file(ENV_FILE)

SMTP_HOST = config["SMTP_HOST"]
SMTP_PORT = int(config["SMTP_PORT"])
SMTP_USERNAME = config["SMTP_USERNAME"]
SMTP_PASSWORD = config["SMTP_PASSWORD"]
SMTP_FROM = config["SMTP_FROM"]
SMTP_TO = config["SMTP_TO"]


message = EmailMessage()

message["Subject"] = "✅ MySQL Backup Email Test - EC2"
message["From"] = SMTP_FROM
message["To"] = SMTP_TO

message.set_content(
    """Hello,

This is a test email from the EC2 MySQL backup system.

SMTP configuration is working successfully.

No attachment is included in this email.

Regards,
EC2 MySQL Backup System
"""
)


try:

    with smtplib.SMTP(
        SMTP_HOST,
        SMTP_PORT,
        timeout=30
    ) as smtp:

        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()

        smtp.login(
            SMTP_USERNAME,
            SMTP_PASSWORD
        )

        smtp.send_message(message)

    print("Email sent successfully!")
    print("From:", SMTP_FROM)
    print("To:", SMTP_TO)

except Exception as error:

    print("Email sending failed!")
    print("Error:", error)
