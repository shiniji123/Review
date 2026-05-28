# MU Review Course

เว็บไซต์รีวิวรายวิชามหาวิทยาลัยมหิดล สร้างด้วย Streamlit สำหรับให้นักศึกษาเลือกหมวดรายวิชา คณะ และรายวิชา แล้วส่งรีวิวพร้อมคะแนน ส่วนผู้ดูแลระบบสามารถตรวจสอบ อนุมัติ ปฏิเสธ กรองข้อมูล และส่งออกข้อมูลรีวิวได้

> เวอร์ชันล่าสุดของแอปอยู่ที่ `app_2.py`

## Live Demo

[https://review-test-2.streamlit.app/](https://review-test-2.streamlit.app/)

## Screenshot

![MU Review Course screenshot](docs/images/mu-course-review.png)

## Features

- ระบบเข้าสู่ระบบ สมัครสมาชิก ยืนยันอีเมล และลืมรหัสผ่าน
- แยกบทบาทผู้ใช้เป็น `student` และ `admin`
- นักศึกษาส่งรีวิวรายวิชาพร้อมคะแนน 1-5 ดาว
- เลือกรายวิชาตามโครงสร้าง ประเภทวิชา -> คณะ -> รายวิชา
- แสดงรีวิวที่ผ่านการอนุมัติ พร้อมตัวกรองและการจัดเรียง
- ผู้ดูแลระบบตรวจคิวรีวิว อนุมัติหรือปฏิเสธเป็นรายรายการหรือหลายรายการ
- ตารางสรุปภาพรวม เช่น ค่าเฉลี่ยคะแนนและจำนวนรีวิวต่อรายวิชา
- ส่งออกข้อมูลรีวิวเป็น CSV และ JSON
- รองรับการเก็บข้อมูลแบบ local JSON หรือ Google Sheets

## Tech Stack

- Python
- Streamlit
- Pandas
- Google Sheets API ผ่าน `gspread`
- Google Auth
- SMTP สำหรับอีเมลยืนยันบัญชีและรีเซ็ตรหัสผ่าน

## Project Structure

```text
.
├── app_2.py                 # เวอร์ชันล่าสุดของแอป
├── app.py                   # เวอร์ชันก่อนหน้า
├── requirements.txt         # Python dependencies
├── data/
│   └── data.json            # local JSON storage สำหรับทดลองรัน
└── docs/
    └── images/
        └── mu-course-review.png
```

## Getting Started

ติดตั้ง dependencies:

```bash
pip install -r requirements.txt
```

รันแอปเวอร์ชันล่าสุด:

```bash
streamlit run app_2.py
```

จากนั้นเปิดเว็บที่ Streamlit แสดงใน terminal โดยปกติคือ:

```text
http://localhost:8501
```

## Local Storage Mode

ถ้าไม่ได้ตั้งค่า secrets ระบบจะใช้ local JSON เป็นค่าเริ่มต้น โดยอ่านและเขียนข้อมูลที่:

```text
data/data.json
```

เหมาะสำหรับการทดสอบในเครื่องหรือ demo แบบง่าย

## Google Sheets Mode

สำหรับใช้งานจริง สามารถตั้งค่า Streamlit secrets เพื่อให้ Google Sheets เป็นฐานข้อมูลได้:

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

ใน Google Sheet ควรแชร์สิทธิ์ Editor ให้ `client_email` ของ service account ด้วย

## Email / SMTP Secrets

ถ้าต้องการเปิดใช้การส่งอีเมลสำหรับยืนยันบัญชีและรีเซ็ตรหัสผ่าน ให้ตั้งค่าเพิ่ม:

```toml
SMTP_HOST = "smtp.example.com"
SMTP_PORT = 587
SMTP_USER = "your_email@example.com"
SMTP_PASS = "your_password"
SMTP_SENDER = "your_email@example.com"
SMTP_SENDER_NAME = "MU Course Reviews"
SMTP_SSL = false
```

## Example Local Accounts

สำหรับโหมดทดลองใน `app_2.py` มีบัญชีเริ่มต้น:

```text
student1 / 1234
student2 / 1234
admin / admin
```

ควรเปลี่ยนระบบบัญชีและรหัสผ่านก่อนใช้งานจริง

## Deployment

ถ้า deploy บน Streamlit Community Cloud ให้ตั้งค่า entry point เป็น:

```text
app_2.py
```

แล้วเพิ่ม secrets ตามโหมดที่ต้องการใช้งานในหน้า Settings ของแอป
