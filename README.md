# MU Review Course

MU Review Course is a Streamlit web application for Mahidol University course reviews. Students can browse courses by category, faculty, and course, submit star-rated reviews, and view approved reviews. Admin users can moderate submissions, filter review queues, summarize ratings, and export review data.

The latest application entry point is:

```text
app_2.py
```

## Live Demo

[https://review-test-2.streamlit.app/](https://review-test-2.streamlit.app/)

## Screenshot

![MU Review Course student review form](docs/images/mu-course-review.png)

## Key Features

- Student login, sign-up, email verification, and password reset flows
- Role-based access for student and admin users
- Course selection by course type, faculty, and course
- Review submission with 1-5 star ratings
- Approved-review browsing with search, filtering, sorting, and rating summaries
- Admin moderation for pending reviews, including approve and reject actions
- Bulk moderation for filtered pending reviews
- Summary table with average rating and review count by course
- CSV export for approved reviews
- JSON export for the full review database
- Local JSON storage for development
- Optional Google Sheets storage for deployment

## Tech Stack

- Python
- Streamlit
- Pandas
- gspread
- Google Auth
- SMTP email integration

## Repository Structure

```text
.
|-- app_2.py                 # Latest Streamlit app version
|-- app.py                   # Previous app version
|-- requirements.txt         # Python dependencies
|-- data/
|   `-- data.json            # Local JSON database for development
`-- docs/
    `-- images/
        `-- mu-course-review.png
```

## Getting Started

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the latest app:

```bash
streamlit run app_2.py
```

Streamlit will show a local URL in the terminal, usually:

```text
http://localhost:8501
```

## Local Storage

By default, the app uses local JSON storage when no Streamlit secrets are configured.

```text
data/data.json
```

This mode is useful for local development and quick demos.

## Google Sheets Storage

For a deployed app, set Streamlit secrets to use Google Sheets as the database:

```toml
STORAGE_BACKEND = "gsheets"
SPREADSHEET_KEY = "your_google_sheet_id"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

Make sure the Google Sheet is shared with the service account `client_email` as an editor.

The app creates or uses worksheets for pending reviews, approved reviews, users, and tokens.

## Email Configuration

To enable email verification and password reset emails, add SMTP settings to Streamlit secrets:

```toml
SMTP_HOST = "smtp.example.com"
SMTP_PORT = 587
SMTP_USER = "your_email@example.com"
SMTP_PASS = "your_password"
SMTP_SENDER = "your_email@example.com"
SMTP_SENDER_NAME = "MU Course Reviews"
SMTP_SSL = false
```

## Demo Accounts

The local prototype accounts in `app_2.py` are:

```text
student1 / 1234
student2 / 1234
admin / admin
```

Replace these accounts or move account management fully into your storage backend before production use.

## Deployment

When deploying to Streamlit Community Cloud, set the app file to:

```text
app_2.py
```

Then add the required secrets for Google Sheets and SMTP in the app settings.
