# MySQL Automated Backup to Google Drive + Email Notification

## 1. Overview

This document explains the complete setup of the automated MySQL backup system created on the AWS EC2 production server.

The system:

1. Automatically discovers all application MySQL databases.
2. Excludes MySQL system databases.
3. Creates a separate `.sql` dump for every application database.
4. Packages all SQL dumps into one timestamped ZIP file.
5. Uploads the ZIP backup to a Google Drive folder.
6. Deletes temporary SQL files after a successful upload.
7. Keeps the newest local ZIP backup and removes older local ZIP files.
8. Sends a success/failure email through Zoho SMTP.
9. Runs automatically every day at **6:50 PM IST** using cron.
10. Keeps the backup system isolated from application code, Python environments, Nginx, Gunicorn, and existing application dependencies.

---

# 2. Architecture

```text
                         AWS EC2 SERVER
                              |
                              |
                    /opt/mysql-backup/
                              |
          +-------------------+-------------------+
          |                   |                   |
       venv/             credentials/         backups/
          |                   |                   |
 Google libraries       OAuth token         Temporary SQL
 Google Drive API       OAuth client         + ZIP backup
 Email dependencies     email.env
          |
          |
 backup_mysql_to_drive.py
          |
          +--------------------+
          |                    |
          v                    v
       MySQL              Google Drive
   Dynamic DB discovery       |
   mysqldump                  |
                               v
                    Server-Database-Backups
                               |
                               v
                     Timestamped ZIP backup

          |
          v
       Zoho SMTP
          |
          v
   Email notification
```

---

# 3. Current Production Configuration

## Server

- Server type: AWS EC2
- Linux user: `ubuntu`
- Server timezone: `UTC`
- Application backup timezone: IST
- IST schedule: **6:50 PM**
- Equivalent UTC schedule: **1:20 PM UTC**

## Backup application directory

```text
/opt/mysql-backup/
```

Directory structure:

```text
/opt/mysql-backup/
├── venv/
├── credentials/
│   ├── google-service-account.json
│   ├── oauth-client.json
│   ├── token.json
│   └── email.env
├── backups/
├── logs/
├── backup_mysql_to_drive.py
└── test_*.py
```

The backup system is deliberately separated from application directories such as:

```text
/var/www/
```

This prevents the backup Python environment from interfering with deployed applications.

---

# 4. Current Application Databases

The system dynamically discovers databases.

At the time of deployment, the application databases were:

```text
ecubebuild
idyllicgifting_db
idyllictechnology_db
ispl_db
kidsfunzone
saluja_db
vapeshacks_db
```

The following MySQL system databases are excluded:

```text
information_schema
mysql
performance_schema
sys
```

### Important

Do NOT hard-code the application database names in the backup script.

The script uses:

```bash
sudo mysql -N -B -e "SHOW DATABASES;"
```

Therefore, if a new application database is created later, it is automatically discovered and included in the next backup.

---

# 5. Why the Backup System Uses `sudo mysql`

The server's MySQL configuration allows administrative MySQL access through:

```bash
sudo mysql
```

For example:

```bash
sudo mysql -e "SHOW DATABASES;"
```

and:

```bash
sudo mysqldump ...
```

This means the backup system does not require storing a MySQL root password inside a script.

This is preferable to putting a database password directly into:

```text
backup_mysql_to_drive.py
```

or:

```text
.env
```

for this server setup.

---

# 6. Google Drive Configuration

## Google Cloud Project

Project:

```text
Server Database Backup
```

Google Drive API was enabled.

## Service Account

A service account named:

```text
server-database-backup
```

was created.

The service account JSON is stored at:

```text
/opt/mysql-backup/credentials/google-service-account.json
```

Permissions:

```text
600
```

The service account was granted access to the backup folder.

## Important service-account limitation

The initial service-account upload attempt failed because the personal Google Drive storage quota was not available to the service account.

Error:

```text
Service Accounts do not have storage quota
```

Because the account uses personal Google Drive rather than Google Workspace Shared Drives, OAuth authentication was used instead.

The service account JSON is retained for reference, but the production upload currently uses OAuth.

---

# 7. Google Drive Folder

The backup folder is:

```text
Server-Database-Backups
```

Current folder ID:

```text
1mkHo7YCkMqSlcIANaHustdmc5PBy-Q9o
```

The folder is used as the destination for all backup ZIP files.

---

# 8. OAuth Authentication

A Google OAuth Desktop application was created.

OAuth client file:

```text
/opt/mysql-backup/credentials/oauth-client.json
```

OAuth access/refresh token:

```text
/opt/mysql-backup/credentials/token.json
```

Permissions:

```text
600
```

The OAuth token was generated on a Windows machine because the EC2 server does not have a browser.

The authentication flow was:

```text
Windows PC
    |
    v
Google OAuth login
    |
    v
token.json
    |
    v
SCP to EC2
    |
    v
/opt/mysql-backup/credentials/token.json
```

## Important long-term consideration

The OAuth application was configured as a Testing application during setup.

Before relying on this system indefinitely, review Google's current OAuth application/testing-token requirements and move to an appropriate long-term configuration.

If the OAuth refresh token becomes invalid, Google Drive uploads will fail even though MySQL backups continue to be created locally.

---

# 9. OAuth Authentication on a New Server

If a new server needs to use the same Google Drive account:

### Option A — Reuse an existing valid token

Copy:

```text
token.json
```

to:

```text
/opt/mysql-backup/credentials/token.json
```

with:

```bash
chmod 600 /opt/mysql-backup/credentials/token.json
```

The token must be valid for the Google account and OAuth client being used.

### Option B — Generate a new token

On a Windows/Linux machine with a browser:

```bash
pip install google-api-python-client google-auth google-auth-httplib2 google-auth-oauthlib
```

Create an OAuth authentication script similar to:

```python
from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_FILE = "oauth-client.json"
TOKEN_FILE = "token.json"

SCOPES = ["https://www.googleapis.com/auth/drive"]

flow = InstalledAppFlow.from_client_secrets_file(
    CLIENT_FILE,
    SCOPES
)

credentials = flow.run_local_server(
    host="127.0.0.1",
    bind_addr="127.0.0.1",
    port=0,
    access_type="offline",
    prompt="consent"
)

with open(TOKEN_FILE, "w") as token:
    token.write(credentials.to_json())

print("OAuth authentication successful!")
```

After successful authentication, copy the resulting:

```text
token.json
```

to the server.

---

# 10. Python Virtual Environment

The backup system uses its own isolated Python environment:

```text
/opt/mysql-backup/venv
```

This is important because the production applications may have different Python dependencies.

Activate it with:

```bash
cd /opt/mysql-backup
source venv/bin/activate
```

Installed Google-related packages:

```text
google-api-python-client
google-auth
google-auth-httplib2
google-auth-oauthlib
```

The backup system does not install packages into the system Python environment or application virtual environments.

---

# 11. Email Configuration

Email is sent through Zoho SMTP.

Configuration file:

```text
/opt/mysql-backup/credentials/email.env
```

Expected structure:

```text
SMTP_HOST=smtp.zoho.com
SMTP_PORT=587
SMTP_USERNAME=YOUR_ZOHO_EMAIL
SMTP_PASSWORD=YOUR_ZOHO_APP_PASSWORD
SMTP_FROM=YOUR_ZOHO_EMAIL
SMTP_TO=YOUR_NOTIFICATION_EMAIL
```

Example structure:

```text
SMTP_HOST=smtp.zoho.com
SMTP_PORT=587
SMTP_USERNAME=backup@example.com
SMTP_PASSWORD=APP_SPECIFIC_PASSWORD
SMTP_FROM=backup@example.com
SMTP_TO=admin@example.com
```

Permissions:

```bash
chmod 600 /opt/mysql-backup/credentials/email.env
```

Do not commit this file to GitHub.

Do not put the SMTP password directly inside:

```text
backup_mysql_to_drive.py
```

Use a Zoho app-specific password rather than the normal account password.

---

# 12. Backup Script

Main script:

```text
/opt/mysql-backup/backup_mysql_to_drive.py
```

The script performs the following workflow.

## Step 1 — Discover databases

It executes:

```bash
sudo mysql -N -B -e "SHOW DATABASES;"
```

System databases are excluded.

---

## Step 2 — Create temporary SQL dumps

Each application database gets its own SQL file.

Example:

```text
ecubebuild.sql
idyllicgifting_db.sql
idyllictechnology_db.sql
ispl_db.sql
kidsfunzone.sql
saluja_db.sql
vapeshacks_db.sql
```

The dump uses:

```bash
sudo mysqldump --single-transaction --routines --triggers --events DATABASE_NAME
```

### Meaning

`--single-transaction`

Creates a consistent dump for transactional tables without requiring a long table lock.

`--routines`

Includes stored procedures and functions.

`--triggers`

Includes database triggers.

`--events`

Includes MySQL scheduled events.

---

# 13. ZIP Creation

After all databases are dumped, the SQL files are packaged into:

```text
mysql-backup-YYYY-MM-DD_HH-MM-SS.zip
```

Example:

```text
mysql-backup-2026-09-30_12-52-51.zip
```

The ZIP is stored temporarily in:

```text
/opt/mysql-backup/backups/
```

---

# 14. Google Drive Upload

The ZIP is uploaded to:

```text
Server-Database-Backups
```

using the Google Drive API and OAuth token.

The backup file remains in Google Drive after successful upload.

The script does NOT automatically delete old Google Drive backups.

This provides historical backup retention in Drive.

---

# 15. Local Cleanup

After a successful upload:

1. Temporary `.sql` files are deleted.
2. Older local ZIP backups are deleted.
3. The newest ZIP remains locally.

Therefore the server does not continuously accumulate large local backup files.

Example:

```text
/opt/mysql-backup/backups/
└── mysql-backup-2026-09-30_12-52-51.zip
```

---

# 16. Email Notification

The script sends an email after the backup process.

A successful email includes information such as:

```text
Backup Status: SUCCESS

Databases detected: 7
Successful backups: 7
Failed backups: 0

ZIP:
mysql-backup-2026-09-30_12-52-51.zip

Google Drive upload: SUCCESS
```

The email does not contain the ZIP attachment.

The backup itself remains in Google Drive.

This avoids sending a large database ZIP through email.

---

# 17. Logs

Application logs are stored in:

```text
/opt/mysql-backup/logs/
```

Daily backup log:

```text
/opt/mysql-backup/logs/backup_YYYY-MM-DD.log
```

Cron output:

```text
/opt/mysql-backup/logs/cron.log
```

A manual cron test may create:

```text
/opt/mysql-backup/logs/cron-test.log
```

---

# 18. Cron Scheduling

The EC2 server uses:

```text
UTC
```

The required backup time is:

```text
6:50 PM IST
```

IST is UTC+5:30.

Therefore:

```text
6:50 PM IST
= 13:20 UTC
```

Current cron entry:

```cron
20 13 * * * /usr/bin/sudo /opt/mysql-backup/venv/bin/python /opt/mysql-backup/backup_mysql_to_drive.py >> /opt/mysql-backup/logs/cron.log 2>&1
```

This means:

```text
Minute: 20
Hour: 13
Every day
Every month
Every weekday
```

Therefore it runs every day at:

```text
13:20 UTC
18:50 IST
```

---

# 19. Check Cron

Run:

```bash
crontab -l
```

Expected line:

```cron
20 13 * * * /usr/bin/sudo /opt/mysql-backup/venv/bin/python /opt/mysql-backup/backup_mysql_to_drive.py >> /opt/mysql-backup/logs/cron.log 2>&1
```

Check cron service:

```bash
sudo systemctl status cron --no-pager
```

Expected:

```text
Active: active (running)
```

---

# 20. Manual Backup

To manually execute the backup:

```bash
/usr/bin/sudo /opt/mysql-backup/venv/bin/python /opt/mysql-backup/backup_mysql_to_drive.py
```

This is useful when:

- testing a new configuration
- testing Google Drive authentication
- testing SMTP
- testing a new database
- troubleshooting scheduled backups

---

# 21. Check Backup Logs

List logs:

```bash
ls -lah /opt/mysql-backup/logs/
```

View the latest backup log:

```bash
tail -100 /opt/mysql-backup/logs/backup_$(date +%Y-%m-%d).log
```

View cron output:

```bash
tail -100 /opt/mysql-backup/logs/cron.log
```

---

# 22. Check Local Backup

Run:

```bash
ls -lah /opt/mysql-backup/backups/
```

A successful run should leave the newest ZIP.

Example:

```text
mysql-backup-2026-09-30_12-52-51.zip
```

---

# 23. Check Databases Manually

To see all MySQL databases:

```bash
sudo mysql -e "SHOW DATABASES;"
```

To check database sizes:

```bash
sudo mysql -e "
SELECT
    table_schema AS database_name,
    ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_mb
FROM information_schema.tables
GROUP BY table_schema
ORDER BY size_mb DESC;
"
```

---

# 24. Test Google Drive Upload

The production script itself should normally be used instead of test scripts.

If Google Drive authentication fails, first verify:

```bash
ls -lh /opt/mysql-backup/credentials/token.json
```

Check permissions:

```bash
stat -c "%a %U:%G %n" /opt/mysql-backup/credentials/token.json
```

Expected:

```text
600 ubuntu:ubuntu
```

Do not print the contents of `token.json`.

---

# 25. Test Email Configuration

Email credentials are stored in:

```text
/opt/mysql-backup/credentials/email.env
```

Do not display the file using:

```bash
cat /opt/mysql-backup/credentials/email.env
```

because it contains the SMTP password.

Instead, verify that the file exists:

```bash
ls -l /opt/mysql-backup/credentials/email.env
```

Expected permission:

```text
-rw------- 
```

---

# 26. Security Rules

Never commit these files to GitHub:

```text
google-service-account.json
oauth-client.json
token.json
email.env
```

Never paste their contents into:

- GitHub
- Slack
- WhatsApp
- public documentation
- tickets
- screenshots
- public repositories

If an SMTP app password is exposed, revoke it and generate a new one.

If the Google OAuth token is exposed, revoke the associated authorization/token and authenticate again.

---

# 27. What the Backup System DOES NOT Modify

The backup system does not modify:

```text
/var/www/ecube
```

or other application directories.

It does not modify:

```text
Nginx
Gunicorn
systemd application services
application virtual environments
application source code
application requirements.txt
MySQL table structure
MySQL data
application configuration
```

The backup operation is read-oriented:

```text
MySQL
  |
  | read/dump
  v
SQL file
  |
  v
ZIP
  |
  v
Google Drive
```

It does not execute:

```text
DROP DATABASE
DROP TABLE
DELETE
ALTER TABLE
UPDATE
INSERT
```

as part of the backup workflow.

---

# 28. How to Add the Same Automation to Another Server

This section describes the complete migration/setup procedure for applying the same backup automation to another EC2/VPS server.

---

## Phase 1 — Check the New Server

SSH into the new server.

Example:

```bash
ssh -i "YOUR_KEY.pem" ubuntu@SERVER_IP
```

Check OS:

```bash
cat /etc/os-release
```

Check Python:

```bash
python3 --version
```

Check MySQL:

```bash
mysql --version
```

Check sudo MySQL:

```bash
sudo mysql -e "SHOW DATABASES;"
```

If the last command works, the backup script can use the same MySQL authentication approach.

---

# 29. Create the Isolated Backup Directory

Run:

```bash
sudo mkdir -p /opt/mysql-backup/{credentials,backups,logs}
```

Give ownership to the backup user:

```bash
sudo chown -R ubuntu:ubuntu /opt/mysql-backup
```

Set directory permissions:

```bash
sudo chmod 700 /opt/mysql-backup
sudo chmod 700 /opt/mysql-backup/credentials
sudo chmod 700 /opt/mysql-backup/backups
sudo chmod 700 /opt/mysql-backup/logs
```

---

# 30. Create a Dedicated Virtual Environment

Run:

```bash
cd /opt/mysql-backup
python3 -m venv venv
```

If `venv` is unavailable:

```bash
sudo apt update
sudo apt install -y python3-venv
```

Then:

```bash
python3 -m venv /opt/mysql-backup/venv
```

Activate:

```bash
source /opt/mysql-backup/venv/bin/activate
```

---

# 31. Install Backup Dependencies

Inside the backup venv:

```bash
pip install --upgrade pip
```

Then:

```bash
pip install google-api-python-client google-auth google-auth-httplib2 google-auth-oauthlib
```

Verify:

```bash
python -c "import google.oauth2.service_account; print('Google auth library available')"
```

Expected:

```text
Google auth library available
```

Do NOT run these installations inside an application's virtual environment.

---

# 32. Copy the Backup Script

Copy:

```text
backup_mysql_to_drive.py
```

to:

```text
/opt/mysql-backup/backup_mysql_to_drive.py
```

Then:

```bash
chmod 700 /opt/mysql-backup/backup_mysql_to_drive.py
```

Test syntax:

```bash
python -m py_compile /opt/mysql-backup/backup_mysql_to_drive.py
```

No output means the syntax check passed.

---

# 33. Copy Google OAuth Configuration

Copy the OAuth client:

```text
oauth-client.json
```

to:

```text
/opt/mysql-backup/credentials/oauth-client.json
```

Then:

```bash
chmod 600 /opt/mysql-backup/credentials/oauth-client.json
```

Generate or copy the OAuth token:

```text
token.json
```

to:

```text
/opt/mysql-backup/credentials/token.json
```

Then:

```bash
chmod 600 /opt/mysql-backup/credentials/token.json
```

---

# 34. Configure Google Drive Destination

The backup script contains the Google Drive folder ID.

For a new server using the same backup folder, use the existing folder ID.

For a completely separate backup folder:

1. Create a new Google Drive folder.
2. Obtain its folder ID.
3. Replace the folder ID in the backup script/configuration.
4. Authenticate the Google account if required.
5. Test upload.

Do not create a new Google Cloud project for every server unless there is a business/security reason to do so.

---

# 35. Configure Email

Create:

```bash
nano /opt/mysql-backup/credentials/email.env
```

Add:

```text
SMTP_HOST=smtp.zoho.com
SMTP_PORT=587
SMTP_USERNAME=YOUR_ZOHO_EMAIL
SMTP_PASSWORD=YOUR_ZOHO_APP_PASSWORD
SMTP_FROM=YOUR_ZOHO_EMAIL
SMTP_TO=YOUR_NOTIFICATION_EMAIL
```

Save the file.

Set permissions:

```bash
chmod 600 /opt/mysql-backup/credentials/email.env
```

---

# 36. Verify Database Discovery

Run:

```bash
sudo mysql -N -B -e "SHOW DATABASES;"
```

Confirm that the expected application databases are visible.

The script will automatically exclude:

```text
information_schema
mysql
performance_schema
sys
```

---

# 37. Run a Manual Backup on the New Server

Run:

```bash
/usr/bin/sudo /opt/mysql-backup/venv/bin/python /opt/mysql-backup/backup_mysql_to_drive.py
```

Wait for completion.

Check:

```bash
ls -lah /opt/mysql-backup/backups/
```

Check logs:

```bash
ls -lah /opt/mysql-backup/logs/
```

Then verify the ZIP appears in Google Drive.

Also verify the success email.

Do not configure cron until this manual test succeeds.

---

# 38. Configure Cron on the New Server

Check server timezone:

```bash
timedatectl
```

If the server uses UTC and the desired time is 6:50 PM IST:

```text
IST 18:50
UTC 13:20
```

Edit cron:

```bash
crontab -e
```

Add:

```cron
20 13 * * * /usr/bin/sudo /opt/mysql-backup/venv/bin/python /opt/mysql-backup/backup_mysql_to_drive.py >> /opt/mysql-backup/logs/cron.log 2>&1
```

Save and exit.

Verify:

```bash
crontab -l
```

---

# 39. Verify Cron Service on New Server

Run:

```bash
sudo systemctl status cron --no-pager
```

Expected:

```text
Active: active (running)
```

If cron is not installed:

```bash
sudo apt update
sudo apt install -y cron
```

Enable and start:

```bash
sudo systemctl enable --now cron
```

---

# 40. Test the Exact Scheduled Command

Before waiting for the scheduled time, manually execute the exact command:

```bash
/usr/bin/sudo /opt/mysql-backup/venv/bin/python /opt/mysql-backup/backup_mysql_to_drive.py >> /opt/mysql-backup/logs/cron-test.log 2>&1
```

Then:

```bash
tail -100 /opt/mysql-backup/logs/cron-test.log
```

Confirm:

```text
Database discovery successful
All expected databases backed up
ZIP created
Google Drive upload successful
Email notification sent
```

---

# 41. New Server Migration Checklist

Use this checklist when deploying the automation elsewhere.

```text
[ ] SSH access verified
[ ] MySQL installed
[ ] sudo mysql works
[ ] Database list verified
[ ] /opt/mysql-backup created
[ ] Directory permissions configured
[ ] Dedicated Python venv created
[ ] Google libraries installed
[ ] backup_mysql_to_drive.py copied
[ ] Script syntax verified
[ ] oauth-client.json copied
[ ] token.json copied/generated
[ ] Google Drive folder configured
[ ] email.env created
[ ] email.env permissions set to 600
[ ] Manual database dump tested
[ ] ZIP creation tested
[ ] Google Drive upload tested
[ ] Email notification tested
[ ] Local cleanup verified
[ ] Cron installed
[ ] Cron service running
[ ] Exact cron command tested
[ ] Scheduled time verified
[ ] Existing applications checked and unaffected
```

---

# 42. Troubleshooting

## Problem: MySQL access denied

Test:

```bash
sudo mysql -e "SHOW DATABASES;"
```

If this fails, fix MySQL administrative access first.

Do not modify application database credentials without understanding the application's configuration.

---

## Problem: Google Drive upload fails

Check:

```bash
ls -l /opt/mysql-backup/credentials/token.json
```

Check the backup log:

```bash
tail -100 /opt/mysql-backup/logs/backup_$(date +%Y-%m-%d).log
```

Common causes:

- OAuth token expired/revoked
- Google account authorization changed
- Drive folder deleted
- Drive folder ID changed
- OAuth client changed
- API disabled
- Google quota/authentication issue

---

## Problem: Email fails

Check:

```bash
ls -l /opt/mysql-backup/credentials/email.env
```

Do not print the password.

Verify:

- Zoho SMTP hostname
- SMTP port
- username
- app-specific password
- sender address
- destination address
- SMTP authentication

---

## Problem: Cron does not run

Check:

```bash
sudo systemctl status cron --no-pager
```

Then:

```bash
crontab -l
```

Then:

```bash
tail -100 /opt/mysql-backup/logs/cron.log
```

Check system cron messages:

```bash
sudo journalctl -u cron --since "24 hours ago" --no-pager
```

---

## Problem: Backup works manually but not through cron

Cron has a limited environment.

Use absolute paths.

The current cron entry intentionally uses:

```text
/usr/bin/sudo
/opt/mysql-backup/venv/bin/python
/opt/mysql-backup/backup_mysql_to_drive.py
```

The script also uses absolute paths for credentials, backups, and logs.

If cron still fails, check:

```bash
tail -100 /opt/mysql-backup/logs/cron.log
```

---

# 43. Application Safety

Before making changes on a production server:

Do NOT:

```bash
pip install ... 
```

inside an application's venv just for the backup system.

Do NOT modify:

```text
/var/www/<application>
```

Do NOT modify application:

```text
requirements.txt
```

Do NOT restart application services unnecessarily.

Do NOT modify Nginx configuration for the backup system.

Do NOT change MySQL schemas merely to support the backup.

The backup system should remain under:

```text
/opt/mysql-backup/
```

---

# 44. Recommended Production Directory Layout

For a server containing multiple applications:

```text
/var/www/
├── ecube/
├── saluja/
├── kidsfunzone/
├── vapecrown/
├── idyllictechnology/
└── ...

/opt/
└── mysql-backup/
    ├── venv/
    ├── credentials/
    ├── backups/
    ├── logs/
    └── backup_mysql_to_drive.py
```

This separation should be maintained.

---

# 45. Backup Retention

## Local server

Only the newest successful local ZIP is retained.

This prevents the EC2 disk from filling up.

## Google Drive

The script does not delete old Drive backups.

Therefore Drive acts as the historical backup store.

Administrators should periodically review Google Drive storage usage and establish a retention policy appropriate for the organization.

---

# 46. Recovery / Restore Procedure

A backup is useful only if it can be restored.

To restore a database:

### Step 1 — Download the ZIP

Download the required ZIP from Google Drive.

### Step 2 — Extract it

On Linux:

```bash
unzip mysql-backup-YYYY-MM-DD_HH-MM-SS.zip
```

### Step 3 — Create the database if necessary

Example:

```bash
sudo mysql -e "CREATE DATABASE database_name;"
```

### Step 4 — Import the SQL file

```bash
sudo mysql database_name < database_name.sql
```

### Step 5 — Verify

```bash
sudo mysql -e "SHOW TABLES FROM database_name;"
```

### Important

Do not restore over a production database without first confirming:

- correct backup date
- correct database name
- application compatibility
- current production data status
- whether a fresh backup should be taken first

---

# 47. Disaster Recovery Recommendation

For important production systems, maintain backups in more than one location.

Current architecture:

```text
Production MySQL
       |
       v
EC2 local ZIP
       |
       v
Google Drive
```

A stronger disaster-recovery architecture can later add:

```text
Production MySQL
       |
       +----> Google Drive
       |
       +----> S3 / another independent storage location
```

The second storage location protects against loss or account-level problems affecting the primary backup destination.

---

# 48. Files That Should Remain Secret

The following files contain sensitive credentials or authorization material:

```text
credentials/google-service-account.json
credentials/oauth-client.json
credentials/token.json
credentials/email.env
```

Never upload them to a public GitHub repository.

A recommended `.gitignore` for a repository containing this project would be:

```gitignore
credentials/
*.env
token.json
google-service-account.json
oauth-client.json
__pycache__/
*.pyc
backups/
logs/
```

---

# 49. Operational Commands Quick Reference

## Start working directory

```bash
cd /opt/mysql-backup
```

## Activate venv

```bash
source /opt/mysql-backup/venv/bin/activate
```

## Manual backup

```bash
/usr/bin/sudo /opt/mysql-backup/venv/bin/python /opt/mysql-backup/backup_mysql_to_drive.py
```

## List databases

```bash
sudo mysql -e "SHOW DATABASES;"
```

## Check cron

```bash
crontab -l
```

## Check cron service

```bash
sudo systemctl status cron --no-pager
```

## Check backup files

```bash
ls -lah /opt/mysql-backup/backups/
```

## Check logs

```bash
ls -lah /opt/mysql-backup/logs/
```

## Follow cron log

```bash
tail -f /opt/mysql-backup/logs/cron.log
```

## Check today's backup log

```bash
tail -100 /opt/mysql-backup/logs/backup_$(date +%Y-%m-%d).log
```

## Check backup directory permissions

```bash
ls -ld /opt/mysql-backup /opt/mysql-backup/credentials /opt/mysql-backup/backups /opt/mysql-backup/logs
```

---

# 50. Change Schedule

If the backup time needs to be changed, edit:

```bash
crontab -e
```

Cron format:

```text
minute hour day month weekday command
```

Current:

```cron
20 13 * * * ...
```

This means:

```text
13:20 UTC
18:50 IST
```

Always convert the desired IST time to UTC when the server timezone is UTC.

After changing:

```bash
crontab -l
```

Then verify the new schedule.

---

# 51. Changing the Google Drive Folder

If the backup destination changes:

1. Create/select the new Google Drive folder.
2. Obtain the folder ID.
3. Update the destination folder ID used by the backup script.
4. Ensure the authenticated Google account has access.
5. Run a manual backup.
6. Verify the ZIP appears in the new folder.
7. Verify email notification.
8. Only then wait for the scheduled cron run.

---

# 52. Changing the Notification Email

Edit:

```bash
nano /opt/mysql-backup/credentials/email.env
```

Change:

```text
SMTP_TO=NEW_EMAIL@example.com
```

Save.

Do not modify the SMTP password unless necessary.

Run a manual backup to verify notification delivery.

---

# 53. Adding a New Database

No script modification is required.

For example, if a new database:

```text
new_project_db
```

is created:

```bash
sudo mysql -e "SHOW DATABASES;"
```

The backup script will discover it automatically.

The next scheduled backup will include:

```text
new_project_db.sql
```

No change to the cron job is required.

---

# 54. Final Production Status

Current system successfully demonstrated:

```text
7 databases detected
7 databases backed up
0 database failures
ZIP created
ZIP uploaded to Google Drive
Email notification sent
Old local ZIP cleaned up
Cron service active
Daily cron configured
```

Example successful backup:

```text
mysql-backup-2026-09-30_12-52-51.zip
```

Example local location:

```text
/opt/mysql-backup/backups/mysql-backup-2026-09-30_12-52-51.zip
```

Google Drive upload was successfully tested.

---

# 55. Important Maintenance Note

Before treating this as a permanent unattended production system, verify the long-term Google OAuth configuration.

The current OAuth application was created in Testing mode during initial setup.

The MySQL backup mechanism, local ZIP creation, cron scheduling, and email notification are independent of this issue, but Google Drive authentication must remain valid for unattended uploads.

If Google authentication expires/revokes the token:

```text
MySQL dump
   |
   v
ZIP creation
   |
   v
SUCCESS locally
   |
   v
Google Drive upload FAILED
```

The email notification should be used to detect this failure.

---

# 56. Change Management Procedure

When modifying the backup system:

1. Read this document first.
2. Do not modify application directories.
3. Make one change at a time.
4. Run Python syntax validation.
5. Run a manual backup.
6. Verify all databases.
7. Verify Google Drive.
8. Verify email.
9. Check logs.
10. Verify cron.
11. Document the change.

Syntax test:

```bash
python -m py_compile /opt/mysql-backup/backup_mysql_to_drive.py
```

Manual test:

```bash
/usr/bin/sudo /opt/mysql-backup/venv/bin/python /opt/mysql-backup/backup_mysql_to_drive.py
```

Log check:

```bash
tail -100 /opt/mysql-backup/logs/backup_$(date +%Y-%m-%d).log
```

---

# 57. Summary for Interns

The important concept is:

```text
DO NOT TOUCH APPLICATIONS.
```

The backup system is isolated:

```text
/opt/mysql-backup/
```

Applications remain under:

```text
/var/www/
```

The backup process:

```text
Discover DBs
     ↓
Exclude system DBs
     ↓
mysqldump each DB
     ↓
Create ZIP
     ↓
Upload ZIP to Google Drive
     ↓
Delete temporary SQL files
     ↓
Keep newest local ZIP
     ↓
Send email report
```

Schedule:

```text
Every day
6:50 PM IST
13:20 UTC
```

Main script:

```text
/opt/mysql-backup/backup_mysql_to_drive.py
```

Main cron:

```cron
20 13 * * * /usr/bin/sudo /opt/mysql-backup/venv/bin/python /opt/mysql-backup/backup_mysql_to_drive.py >> /opt/mysql-backup/logs/cron.log 2>&1
```

This is the standard procedure to reproduce the same backup automation on another Linux/EC2 server.
