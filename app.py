import streamlit as st
import json
import os
import uuid
from datetime import datetime
from functools import lru_cache
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from textwrap import dedent
import pandas as pd
import smtplib, ssl
from email.message import EmailMessage
# -----------------------------
# Course Types & Faculty Catalogs

# -----------------------------
# -----------------------------
# Page & basic styles
# -----------------------------
st.set_page_config(page_title="MU Course Reviews — All-in-One", page_icon="⭐", layout="wide")
st.markdown(
    """
    <style>
      .star {font-size: 1.0rem; line-height: 1}
      .muted {color: rgba(0,0,0,0.6); font-size: 0.9rem}
      .codepill {display:inline-block; padding:0.2rem 0.45rem; border-radius:6px; background:#f0f2f6; font-weight:600}
      .box {padding:0.75rem 0.9rem; background:#f8fafc; border:1px solid #eef2f7; border-radius:8px}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("""
<style>
/* โหลดฟอนต์สำรอง (ถ้าเครื่องไม่มี Browallia New) */
@import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600;700&display=swap');

/* ตั้ง stack ฟอนต์ทั้งระบบ */
:root {
  --app-font: "Browallia New", "Sarabun",
              system-ui, -apple-system, "Segoe UI", Roboto,
              "Helvetica Neue", Arial, "Noto Sans Thai", "Noto Sans", sans-serif;
}

html, body { font-size: 16.5px; }

/* บังคับทั้งแอป (ตัวอักษรไทย/อังกฤษในคอมโพเนนต์เกือบทั้งหมด) */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stHeader"],
[data-testid="stSidebar"],
[data-testid="stToolbar"],
[class^="st-"], [class*=" st-"],
[data-testid="stMarkdownContainer"] * ,
[data-testid="stTable"] * {
  font-family: var(--app-font) !important;
}
</style>
""", unsafe_allow_html=True)


APP_TITLE = "เว็บไซต์รีวิวรายวิชามหาวิทยาลัยมหิดล MU Review Course"
DATA_FILE = os.path.join("data", "data.json")
MIN_PASSWORD_LEN = 8

# -----------------------------
# Course Types & Faculty Catalogs
# -----------------------------
COURSE_TYPES = {
    "GE": "รายวิชาศึกษาทั่วไป",
    "FE": "รายวิชาเสรี",
    "ME": "รายวิชาเฉพาะเลือก (SC - คณิตศาสตร์)",
}

FACULTIES_BY_TYPE = {
    # รายวิชาศึกษาทั่วไป
    "GE": {
        "SI": "คณะแพทยศาสตร์ศิริราชพยาบาล",
        "PY": "คณะเภสัชศาสตร์",
        "SC": "คณะวิทยาศาสตร์",
        "NS": "คณะพยาบาลศาสตร์",
        "RA": "คณะแพทยศาสตร์โรงพยาบาลรามาธิบดี",
        "EG": "คณะวิศวกรรมศาสตร์",
        "EN": "คณะสิ่งแวดล้อมและทรัพยากรศาสตร์",
        "SH": "คณะสังคมศาสตร์และมนุษย์ศาสตร์",
        "LA": "คณะศิลปศาสตร์",
        "SP": "วิทยาลัยวิทยาศาสตร์และเทคโนโลยีการกีฬา",
        "CF": "สถาบันแห่งชาติเพื่อการพัฒนาเด็กและครอบครัว",
        "HP": "โครงการจัดตั้งสถาบันสิทธิมนุษยชนและสันติศึกษา",
        "IL": "สถาบันนวัตกรรมการเรียนรู้",
        "LC": "สถาบันวิจัยภาษาและวัฒนธรรมเอเชีย",
        "MU": "มหาวิทยาลัยมหิดล (ศูนย์ส่งเสริมการเรียนรู้ฯ)",
        "PR": "สถาบันวิจัยประชากรและสังคม",
    },
    # รายวิชาเสรี
    "FE": {
        "SH": "คณะสังคมศาสตร์และมนุษยศาสตร์",
        "LA": "คณะศิลปศาสตร์",
        "CR": "วิทยาลัยศาสนศึกษา",
        "NW": "โครงการจัดตั้งวิทยาเขตนครสวรรค์",
    },
    # รายวิชาเฉพาะเลือก — ทำเฉพาะ SC (คณิตศาสตร์)
    "ME": {
        "SC": "คณะวิทยาศาสตร์",
    }
}

# ตัวอย่างรายวิชาให้เลือกต่อคณะ (ปรับเพิ่ม/แก้ไขได้)
# ===== Course catalog (new structure): ประเภท → คณะ → [รายวิชา] =====
# ฟอร์แมตของ 1 รายวิชา:
# {"code": "รหัสวิชา", "name": "ชื่อวิชา", "desc_th": "...", "desc_en": "...", "credit": 3, "prereq": "..."}

COURSE_CATALOG_BY_TYPE = {
    # -----------------------
    # 1) GE: รายวิชาศึกษาทั่วไป
    # -----------------------
    "GE": {
        "SI": [  # คณะแพทยศาสตร์ศิริราชพยาบาล
            {
                "code": "SIHE301",
                "name": "จิตวิทยาสังคมสำหรับบุคลากรในระบบสุขภาพ",
                "desc_th": "ภาษาและการสื่อสาร การรับรู้ทางสังคม การชักจูง อคติ คุณค่า อิทธิพลทางสังคม ตัวตนในสังคม และอัตลักษณ์ทางสังคม ความสัมพันธ์ระหว่างบุคคล พฤติกรรมกลุ่ม จิตวิทยาสังคมกับระบบสุขภาพ",
                "desc_en": "Language and communication, social perception, persuasion, prejudice, values, social influence, social self and social identities, personal relationship, behavior in groups, social psychology and healthcare",
                "credit": "2(2-0-4)",  # ← หน่วยกิต (แนะนำให้เก็บเป็นสตริงตาม format ที่มหาลัยใช้)
                "grading": "OSU",  # ← วิธีตัดเกรด: ABC หรือ OSU
                "updated_at": "7/9/2025"  # ← วันที่อัปเดตล่าสุด (รูปแบบ YYYY-MM-DD)
            },
        ],
        "PY": [  # คณะเภสัชศาสตร์
            # ตัวอย่าง:
            # {"code": "GE-PY101", "name": "เภสัชวิทยาสำหรับชีวิตประจำวัน", "credit": 3},
        ],
        "SC": [  # คณะวิทยาศาสตร์
            {"code": "GE-SC101", "name": "วิทยาศาสตร์ในชีวิตประจำวัน", "credit": 3},
            {"code": "GE-SC102", "name": "โลกและสิ่งแวดล้อม", "credit": 3},
        ],
        "NS": [],  # คณะพยาบาลศาสตร์
        "RA": [],  # รามาธิบดี
        "EG": [],  # วิศวกรรมศาสตร์
        "EN": [],  # สิ่งแวดล้อมและทรัพยากรศาสตร์
        "SH": [],  # สังคมศาสตร์และมนุษยศาสตร์
        "LA": [],  # ศิลปศาสตร์
        "SP": [],  # วิทยาศาสตร์และเทคโนโลยีการกีฬา
        "CF": [],  # สถาบันพัฒนาเด็กและครอบครัว
        "HP": [],  # สถาบันสิทธิมนุษยชนและสันติศึกษา
        "IL": [],  # สถาบันนวัตกรรมการเรียนรู้
        "LC": [],  # วิจัยภาษาและวัฒนธรรมเอเชีย
        "MU": [],  # ม.มหิดล (ศูนย์ส่งเสริมการเรียนรู้ฯ)
        "PR": [],  # วิจัยประชากรและสังคม
    },

    # -----------------------
    # 2) FE: รายวิชาเสรี
    # -----------------------
    "FE": {
        "SH": [
            {
                "code": "SHSS103",
                "name": "มนุษย์กับสังคม",
                "desc_th": "ไม่พบคำอธิบายรายวิชา",
                "desc_en": "Not Found",
                "credit": "2(2-0-4)",  # ← หน่วยกิต (แนะนำให้เก็บเป็นสตริงตาม format ที่มหาลัยใช้)
                "grading": "ABC",  # ← วิธีตัดเกรด: ABC หรือ OSU
                "updated_at": "7/23/2025"  # ← วันที่อัปเดตล่าสุด (รูปแบบ YYYY-MM-DD)
            },
            # สังคมศาสตร์และมนุษยศาสตร์
            # {"code": "FE-SH201", "name": "สังคมไทยร่วมสมัย", "credit": 3},
        ],
        "LA": [  # ศิลปศาสตร์
            # {"code": "FE-LA201", "name": "ภาษาและวัฒนธรรมอาเซียน", "credit": 3},
        ],
        "CR": [  # วิทยาลัยศาสนศึกษา
            # {"code": "FE-CR201", "name": "ศาสนาและสังคม", "credit": 3},
        ],
        "NW": [  # วิทยาเขตนครสวรรค์
            # {"code": "FE-NW201", "name": "นวัตกรรมท้องถิ่นศึกษา", "credit": 3},
        ],
    },

    # -----------------------
    # 3) ME: รายวิชาเฉพาะเลือก (ทำเฉพาะ SC - คณิตศาสตร์)
    # -----------------------
    "ME": {
        "SC": [
            {
                "code": "SCMA 349",
                "name": "Software Engineering",
                "prereq": "SCMA 247",
                "desc_th": "วิศวกรรมซอฟต์แวร์ขั้นแนะนํา ระบบสังคมเทคนิค ระบบวิกฤต กระบวนการซอฟต์แวร์ การจัดการโครงงาน ความต้องการซอฟต์แวร์การทวนสอบและการตรวจสอบ การทดสอบซอฟต์แวร",
                "desc_en": "Introduction to software engineering; socio-technical systems; critical systems; softwareprocesses; project management; software requirements; verification and validation;software testing",
                "credit": "3(3-0-6)"

            },
            {
                "code": "SCMA 371",
                "name": "Financial Mathematics",
                "prereq": "SCMA 212 and SCMA 280",
                "desc_th": "ตัวแบบทางการเงินแบบเวลาไมต่ ่อเนื่อง : การทําอาร์บทราจ ิ แบบจําลองไบโนเมียล อนุพันธ์ตราสารสิทธิเลือก การเทียบเท่าแบบมาร์ติงเกลเมเชอร์ อนุพันธราดอน ์ -นิโคดีม ตัวแบบประเมินสินทรัพย์ทุนตัวแบบอัตราดอกเบี้ย อนุพันธท์ ี่อ้างอิงกับตราสารหนี้กรณีศกษาจากนอกห ึ องเร ้ ียน",
                "desc_en": "Discrete time models in finance : arbitrage, binomial model, derivatives, options,equivalent martingale measures, Radon-Nikodym derivative, capital asset pricingmodel, interest rate models, fixed income derivatives; case studies from outside theclassroom",
                "credit": "3(3-0-6)"
             },
            {
                "code": "SCMA 243",
                "name": "Operating Systems",
                "prereq": "SCMA 240",
                "desc_th": "การพัฒนาของระบบปฏิบัติการ กระบวนการและสายโยงใย มัลติโปรแกรมมิงและการแบ่งเวลา การจัดการภาวะพร้อมกัน กําหนดการ อุปกรณ์แฟ้ม ตัวประสานผู้ใช้ระบบเสมือน การจัดสรรทรัพยากรระบบการประมวลผล แบบกระจายและระบบข่ายงาน สมรรถนะ การพัฒนาของระบบปฏิบัติการในอนาคต",
                "desc_en": "Development of operating systems; processes and threads; multiprogramming andtime sharing; concurrency management; scheduling; devices; files; user interface; virtualsystems; resource allocation; distributed computing and network based systems;performance; future development of the operating systems",
                "credit": "3(3-0-6)"
            },
        ],
    },
}


def list_faculties_by_type(course_type: str) -> dict:
    return FACULTIES_BY_TYPE.get(course_type, {})

def list_courses(course_type: str, faculty_code: str) -> list:
    return COURSE_CATALOG_BY_TYPE.get(course_type, {}).get(faculty_code, [])



# -----------------------------
# Auth (prototype)
# -----------------------------
USERS: Dict[str, Dict[str, str]] = {
    "student1": {"password": "1234", "role": "student", "display": "Student A"},
    "student2": {"password": "1234", "role": "student", "display": "Student B"},
    "admin": {"password": "admin", "role": "admin", "display": "Administrator"},
}

# ==============================================
# Faculty / Department / Course Catalog (Prototype)
# ==============================================
@lru_cache(maxsize=1)
# สร้างรายการคอร์สแบบ "แบน" จากคาแทล็อกใหม่ (ประเภท → คณะ → รายวิชา)
def flatten_catalog() -> list[dict]:
    rows: list[dict] = []
    for ctype, facs in COURSE_CATALOG_BY_TYPE.items():           # GE / FE / ME
        fac_map = FACULTIES_BY_TYPE.get(ctype, {})
        for fac_code, courses in facs.items():                   # SI / PY / SC / ...
            fac_name = fac_map.get(fac_code, fac_code)
            for c in courses:                                    # {"code": "...", "name": "...", ...}
                rows.append({
                    # ฟิลด์อ้างอิงตามโครงใหม่
                    "course_type": ctype,
                    "faculty": fac_code,
                    "faculty_name": fac_name,

                    # ฟิลด์ที่โค้ดบางส่วนเก่ายังเรียกใช้ — ให้เว้นไว้/เป็นค่าว่างเพื่อกันพัง
                    "department": "",
                    "department_name": "",
                    "year": 0,

                    # เมทาดาต้ารายวิชา (คงชื่อ key 'code','name' ตามเดิม)
                    "code": c["code"],
                    "name": c["name"],
                    "desc_th": c.get("desc_th", ""),
                    "desc_en": c.get("desc_en", ""),
                    "credit": c.get("credit"),
                    "prereq": c.get("prereq"),
                })
    rows.sort(key=lambda r: (r["course_type"], r["faculty"], r["code"]))
    return rows

ALL_COURSES = flatten_catalog()


# -----------------------------
# Storage helpers (Local JSON or Google Sheets via Streamlit Cloud)
# -----------------------------

# Columns schema used for cloud storage
try:
    HEADERS
except NameError:
    HEADERS = [
        "id",
        "course_type",
        "faculty", "faculty_name",
        "department", "department_name",
        "year",
        "course_code", "course_name",
        "rating", "text", "author", "created_at", "status",
    ]
try:
    USERS_HEADERS
except NameError:
    USERS_HEADERS = [
        "email", "display", "role",
        "password_salt", "password_hash",
        "is_verified", "created_at",
    ]
try:
    TOKENS_HEADERS
except NameError:
    TOKENS_HEADERS = [
        "token", "email", "kind", "payload", "created_at", "used_at",
    ]



class GoogleSheetsStorage:
    """
    ใช้ Google Sheets เป็น “คลาวด์ DB” อย่างง่าย
    - ต้องตั้ง secrets: SPREADSHEET_KEY และ gcp_service_account (JSON)
    - ต้องแชร์ชีตให้ service account (สิทธิ Editor)
    """

    def __init__(self):
        import gspread  # import แบบ lazy
        svc_info = dict(st.secrets.get("gcp_service_account", {}))
        if not svc_info:
            raise RuntimeError("Missing gcp_service_account in secrets")
        self.spreadsheet_key = st.secrets.get("SPREADSHEET_KEY")
        if not self.spreadsheet_key:
            raise RuntimeError("Missing SPREADSHEET_KEY in secrets")

        self.gc = gspread.service_account_from_dict(svc_info)
        self.ss = self.gc.open_by_key(self.spreadsheet_key)

        # worksheets ที่ต้องใช้
        self.ws_pending  = self._get_or_create_ws("pending_reviews",  cols=len(HEADERS))
        self.ws_approved = self._get_or_create_ws("approved_reviews", cols=len(HEADERS))
        self.ws_users    = self._get_or_create_ws("users",            cols=len(USERS_HEADERS))
        self.ws_tokens   = self._get_or_create_ws("tokens",           cols=len(TOKENS_HEADERS))

        # บังคับหัวตารางให้ครบ (เติมหัวที่ตกหล่น “ต่อท้าย” ไม่ลบของเดิม)
        self._ensure_headers(self.ws_pending,  HEADERS)
        self._ensure_headers(self.ws_approved, HEADERS)
        self._ensure_headers(self.ws_users,    USERS_HEADERS)
        self._ensure_headers(self.ws_tokens,   TOKENS_HEADERS)

    # ---------- internal helpers ----------

    def _get_or_create_ws(self, title: str, rows: int = 2000, cols: int = 20):
        try:
            return self.ss.worksheet(title)
        except Exception:
            return self.ss.add_worksheet(title=title, rows=rows, cols=cols)

    def _ensure_headers(self, ws, headers=None):
        """
        ให้แผ่น (worksheet) มีหัวตารางตาม headers
        - ถ้าแถวแรกว่าง: เขียน headers ทั้งแถว
        - ถ้าขาดหัวบางตัว: เติมต่อท้าย โดยไม่ล้างข้อมูลเดิม
        """
        if headers is None:
            headers = HEADERS

        hdr = ws.row_values(1)

        def _col_letter(n: int) -> str:
            s = ""
            while n:
                n, r = divmod(n - 1, 26)
                s = chr(65 + r) + s
            return s

        if not hdr:
            ws.update("A1", [headers])
            return

        missing = [h for h in headers if h not in hdr]
        if missing:
            new_hdr = hdr + missing
            last_col = _col_letter(len(new_hdr))
            ws.update(f"A1:{last_col}1", [new_hdr])

    def _read_all(self, ws) -> (List[str], List[List[str]]):
        """
        อ่านค่าทั้งชีตแล้วแยก (headers, rows)
        headers = แถวแรก
        rows    = ตั้งแต่แถวที่ 2 เป็นต้นไป (list of list)
        """
        vals = ws.get_all_values()
        if not vals:
            return [], []
        headers = vals[0]
        rows = vals[1:] if len(vals) > 1 else []
        return headers, rows

    def _rows_to_dicts(self, rows: List[List[str]], headers: List[str], default_headers: List[str]) -> List[Dict]:
        """
        map row -> dict ด้วยชื่อหัวคอลัมน์จริง
        ถ้าหัวจริงบางตัวไม่มี ให้เติมค่าว่าง; ถ้าหัวเกินจาก default_headers จะเก็บไว้ด้วย
        """
        # รวมคีย์ที่ต้องการ (default) + ที่มีอยู่จริง (กันหัวเพิ่ม)
        keys = list(dict.fromkeys(list(default_headers) + list(headers)))
        out: List[Dict] = []
        for r in rows:
            rec = {k: "" for k in keys}
            for i, v in enumerate(r):
                if i < len(headers):
                    rec[headers[i]] = v
            # normalize เฉพาะฟิลด์ที่เรารู้ชนิด
            if "year" in rec:
                try:
                    rec["year"] = int(rec.get("year") or 0)
                except Exception:
                    rec["year"] = 0
            if "rating" in rec:
                try:
                    rec["rating"] = int(rec.get("rating") or 0)
                except Exception:
                    rec["rating"] = 0
            out.append(rec)
        return out

    def _dicts_to_rows(self, dicts: List[Dict], headers: List[str]) -> List[List[str]]:
        """map dict -> row ตามลำดับ headers ที่กำหนด (เขียนแค่หัวที่สนใจ)"""
        rows: List[List[str]] = []
        for d in dicts:
            rows.append([str(d.get(k, "")) for k in headers])
        return rows

    # ---------- public: reviews ----------

    def load_data(self) -> Dict:
        # pending
        hdr_p, rows_p = self._read_all(self.ws_pending)
        if not hdr_p:
            self._ensure_headers(self.ws_pending, HEADERS)
            hdr_p, rows_p = HEADERS, []
        pending = self._rows_to_dicts(rows_p, hdr_p, HEADERS)

        # approved
        hdr_a, rows_a = self._read_all(self.ws_approved)
        if not hdr_a:
            self._ensure_headers(self.ws_approved, HEADERS)
            hdr_a, rows_a = HEADERS, []
        approved = self._rows_to_dicts(rows_a, hdr_a, HEADERS)

        return {"pending_reviews": pending, "approved_reviews": approved}

    def save_data(self, data: Dict) -> None:
        """
        เขียนทับทั้งชีตแบบง่าย (เหมาะกับโปรโตไทป์)
        ถ้าต้องการลดโควตา สามารถเปลี่ยนเป็น partial update ได้ภายหลัง
        """
        pending = data.get("pending_reviews", [])
        approved = data.get("approved_reviews", [])

        # pending
        self.ws_pending.clear()
        self.ws_pending.update("A1", [HEADERS] + self._dicts_to_rows(pending, HEADERS))

        # approved
        self.ws_approved.clear()
        self.ws_approved.update("A1", [HEADERS] + self._dicts_to_rows(approved, HEADERS))

    # ---------- public: users ----------

    def load_users(self) -> List[Dict]:
        hdr, rows = self._read_all(self.ws_users)
        if not hdr:
            self._ensure_headers(self.ws_users, USERS_HEADERS)
            return []
        return self._rows_to_dicts(rows, hdr, USERS_HEADERS)

    def upsert_user(self, user: Dict) -> None:
        """
        เพิ่ม/แก้ไขผู้ใช้ โดยใช้ email เป็นคีย์
        """
        users = self.load_users()
        email = (user.get("email") or "").strip().lower()
        idx = next((i for i, u in enumerate(users) if (u.get("email") or "").lower() == email), -1)
        if idx >= 0:
            users[idx].update(user)
        else:
            users.append(user)

        self.ws_users.clear()
        self.ws_users.update("A1", [USERS_HEADERS] + self._dicts_to_rows(users, USERS_HEADERS))

    # ---------- public: tokens (verify/reset) ----------

    def load_tokens(self) -> List[Dict]:
        hdr, rows = self._read_all(self.ws_tokens)
        if not hdr:
            self._ensure_headers(self.ws_tokens, TOKENS_HEADERS)
            return []
        return self._rows_to_dicts(rows, hdr, TOKENS_HEADERS)

    def write_tokens(self, tokens: List[Dict]) -> None:
        self.ws_tokens.clear()
        self.ws_tokens.update("A1", [TOKENS_HEADERS] + self._dicts_to_rows(tokens, TOKENS_HEADERS))

    def add_token(self, token_row: Dict) -> None:
        """
        เพิ่มโทเคนใหม่ 1 แถว (append) – ลดการอ่าน/เขียนทั้งชีต
        """
        # ให้แน่ใจว่าหัวครบก่อน
        self._ensure_headers(self.ws_tokens, TOKENS_HEADERS)
        row = [str(token_row.get(k, "")) for k in TOKENS_HEADERS]
        self.ws_tokens.append_row(row, value_input_option="USER_ENTERED")

    def mark_token_used(self, token: str) -> bool:
        """
        เซ็ต used_at ให้โทเคนที่ตรง (หาแบบอ่านทั้งหมดแล้วเขียนทับกลับไป)
        """
        tokens = self.load_tokens()
        found = False
        now = datetime.now().isoformat(timespec="seconds")
        for t in tokens:
            if t.get("token") == token and not t.get("used_at"):
                t["used_at"] = now
                found = True
                break
        if found:
            self.write_tokens(tokens)
        return found


# Select backend from secrets (default to local JSON)
BACKEND = st.secrets.get("STORAGE_BACKEND", "local").lower()


@st.cache_resource
def get_storage():
    # instantiate lazily to allow class overrides above to take effect
    if BACKEND == "gsheets":
        return GoogleSheetsStorage()
    return LocalJSONStorage(DATA_FILE)


@st.cache_data(ttl=10)
def _cached_load_data(data_version: int):
    return get_storage().load_data()


def load_data() -> Dict:
    ver = st.session_state.get("data_version", 0)
    try:
        data = _cached_load_data(ver)
        st.session_state["last_data"] = data
        return data
    except Exception as e:
        if any(x in str(e).lower() for x in ["quota exceeded", "429", "rate limit"]):
            st.warning("เกินโควต้าอ่าน Google Sheets ชั่วคราว — แสดงข้อมูลล่าสุดจากแคช")
            return st.session_state.get("last_data", {"approved_reviews": [], "pending_reviews": []})
        raise


def save_data(data: Dict) -> None:
    get_storage().save_data(data)
    st.session_state["data_version"] = st.session_state.get("data_version", 0) + 1
    try:
        _cached_load_data.clear()
    except Exception:
        pass


# -----------------------------
# Authentication utilities (Sign-up / Email verify / Forgot password)
# -----------------------------
import re, hashlib, secrets, smtplib, ssl
from email.message import EmailMessage

ALLOWED_EMAIL_DOMAIN = st.secrets.get("ALLOWED_EMAIL_DOMAIN", "student.mahidol.edu")
APP_BASE_URL = st.secrets.get("APP_BASE_URL", "")  # e.g. https://your-user-your-app.streamlit.app

USERS_HEADERS = ["email", "password_salt", "password_hash", "role", "display", "is_verified", "created_at"]
TOKENS_HEADERS = ["token", "email", "type", "expires_at", "used", "created_at"]


# ---- LocalJSONStorage (drop-in; supports reviews + users + tokens) ----


class LocalJSONStorage:
    def __init__(self, path: str):
        self.path = path
        self._ensure()

    def _ensure(self):
        # สร้างโฟลเดอร์/ไฟล์เริ่มต้น
        base_dir = os.path.dirname(self.path)
        if base_dir:
            os.makedirs(base_dir, exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "pending_reviews": [],
                        "approved_reviews": [],
                        "users": [],
                        "tokens": [],
                    },
                    f, ensure_ascii=False, indent=2
                )
        else:
            # ให้แน่ใจว่ามีคีย์หลักครบ
            with open(self.path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except Exception:
                    data = {}
            changed = False
            for k in ("pending_reviews", "approved_reviews", "users", "tokens"):
                if k not in data:
                    data[k] = []
                    changed = True
            if changed:
                with open(self.path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

    # ---------- file helpers ----------
    def _read(self) -> Dict:
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: Dict) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ---------- reviews ----------
    def load_data(self) -> Dict:
        d = self._read()
        # normalize type (กันกรณี rating/year เป็น string)
        for bucket in ("pending_reviews", "approved_reviews"):
            for r in d.get(bucket, []):
                try:
                    r["rating"] = int(r.get("rating", 0))
                except Exception:
                    r["rating"] = 0
                try:
                    r["year"] = int(r.get("year", 0)) if r.get("year") not in ("", None) else 0
                except Exception:
                    r["year"] = 0
        return {
            "pending_reviews": d.get("pending_reviews", []),
            "approved_reviews": d.get("approved_reviews", []),
        }

    def save_data(self, data: Dict) -> None:
        d = self._read()
        d["pending_reviews"]  = data.get("pending_reviews", [])
        d["approved_reviews"] = data.get("approved_reviews", [])
        self._write(d)

    # ---------- users ----------
    def load_users(self) -> List[Dict]:
        return self._read().get("users", [])

    def upsert_user(self, user: Dict) -> None:
        d = self._read()
        users = d.get("users", [])
        email = (user.get("email") or "").strip().lower()
        idx = next((i for i, u in enumerate(users) if (u.get("email","").lower() == email)), -1)
        if idx >= 0:
            users[idx].update(user)
        else:
            users.append(user)
        d["users"] = users
        self._write(d)

    # ---------- tokens (verify/reset) ----------
    def load_tokens(self) -> List[Dict]:
        return self._read().get("tokens", [])

    def write_tokens(self, tokens: List[Dict]) -> None:
        d = self._read()
        d["tokens"] = tokens
        self._write(d)

    def add_token(self, token_row: Dict) -> None:
        d = self._read()
        d.setdefault("tokens", []).append(token_row)
        self._write(d)

    def mark_token_used(self, token: str) -> bool:
        d = self._read()
        tokens = d.get("tokens", [])
        now = datetime.now().isoformat(timespec="seconds")
        found = False
        for t in tokens:
            if t.get("token") == token and not t.get("used_at"):
                t["used_at"] = now
                found = True
                break
        if found:
            d["tokens"] = tokens
            self._write(d)
        return found



class GoogleSheetsStorage(GoogleSheetsStorage):  # type: ignore[misc]
    def __init__(self):  # override to also ensure users/tokens worksheets
        import gspread
        svc_info = dict(st.secrets.get("gcp_service_account", {}))
        if not svc_info:
            raise RuntimeError("Missing gcp_service_account in secrets")
        self.spreadsheet_key = st.secrets.get("SPREADSHEET_KEY")
        if not self.spreadsheet_key:
            raise RuntimeError("Missing SPREADSHEET_KEY in secrets")
        self.gc = gspread.service_account_from_dict(svc_info)
        self.ss = self.gc.open_by_key(self.spreadsheet_key)
        # Ensure worksheets
        self.ws_pending = self._get_or_create_ws("pending_reviews")
        self.ws_approved = self._get_or_create_ws("approved_reviews")
        self.ws_users = self._get_or_create_ws("users")
        self.ws_tokens = self._get_or_create_ws("tokens")
        self._ensure_headers(self.ws_pending, HEADERS)
        self._ensure_headers(self.ws_approved, HEADERS)
        self._ensure_headers(self.ws_users, USERS_HEADERS)
        self._ensure_headers(self.ws_tokens, TOKENS_HEADERS)

    def _ensure_headers(self, ws, headers=None):
        """
        ให้แผ่น (worksheet) มีหัวตารางตาม headers
        - ถ้าแถวแรกว่าง: เขียน headers ทั้งแถว
        - ถ้าขาดหัวบางตัว: เติมต่อท้าย โดยไม่ล้างข้อมูลเดิม
        """
        if headers is None:
            headers = HEADERS  # ถ้าไม่ส่งมาก็ใช้ HEADERS ปกติ

        hdr = ws.row_values(1)

        # helper: เลขคอลัมน์ -> ตัวอักษร A1 (รองรับ > 26 คอลัมน์)
        def _col_letter(n: int) -> str:
            s = ""
            while n:
                n, r = divmod(n - 1, 26)
                s = chr(65 + r) + s
            return s

        if not hdr:
            ws.update("A1", [headers])
            return

        missing = [h for h in headers if h not in hdr]
        if missing:
            new_hdr = hdr + missing
            last_col = _col_letter(len(new_hdr))
            ws.update(f"A1:{last_col}1", [new_hdr])

    # keep existing review methods from base class; add users/tokens I/O
    def load_users(self) -> List[Dict]:
        rows = self.ws_users.get_all_values()
        data = []
        for r in rows[1:]:
            rec = {USERS_HEADERS[i]: (r[i] if i < len(r) else "") for i in range(len(USERS_HEADERS))}
            rec["is_verified"] = True if str(rec.get("is_verified", "")) in ("1", "true", "True", "yes") else False
            data.append(rec)
        return data

    def save_users(self, users: List[Dict]) -> None:
        rows = [[str(u.get(k, "")) for k in USERS_HEADERS] for u in users]
        self.ws_users.clear();
        self.ws_users.update("A1", [USERS_HEADERS] + rows)

    def load_tokens(self) -> List[Dict]:
        rows = self.ws_tokens.get_all_values()
        data = []
        for r in rows[1:]:
            rec = {TOKENS_HEADERS[i]: (r[i] if i < len(r) else "") for i in range(len(TOKENS_HEADERS))}
            rec["used"] = True if str(rec.get("used", "")) in ("1", "true", "True", "yes") else False
            data.append(rec)
        return data

    def save_tokens(self, tokens: List[Dict]) -> None:
        rows = [[str(t.get(k, "")) for k in TOKENS_HEADERS] for t in tokens]
        self.ws_tokens.clear();
        self.ws_tokens.update("A1", [TOKENS_HEADERS] + rows)


# simple wrappers
def load_users() -> List[Dict]:
    storage = get_storage()
    return storage.load_users() if hasattr(storage, 'load_users') else []


def save_users(users: List[Dict]) -> None:
    storage = get_storage()
    if hasattr(storage, 'save_users'):
        storage.save_users(users)


def load_tokens() -> List[Dict]:
    storage = get_storage()
    return storage.load_tokens() if hasattr(storage, 'load_tokens') else []


def save_tokens(tokens: List[Dict]) -> None:
    storage = get_storage()
    if hasattr(storage, 'save_tokens'):
        storage.save_tokens(tokens)


# ---- password hashing helpers ----

def make_salt() -> str:
    return secrets.token_hex(16)


def hash_password(pw: str, salt: str) -> str:
    return hashlib.sha256((salt + pw).encode("utf-8")).hexdigest()


def verify_password(pw: str, salt: str, pw_hash: str) -> bool:
    return secrets.compare_digest(hash_password(pw, salt), pw_hash)


# ---- token helpers ----

def generate_token() -> str:
    return secrets.token_urlsafe(24)


# ---- email sender ----
class Mailer:
    def __init__(self):
        self.host = st.secrets.get("SMTP_HOST")
        self.port = int(st.secrets.get("SMTP_PORT", 587))
        self.user = st.secrets.get("SMTP_USER")
        self.password = st.secrets.get("SMTP_PASS")
        self.sender = st.secrets.get("SMTP_SENDER", self.user)
        self.sender_name = st.secrets.get("SMTP_SENDER_NAME", "Uni Course Reviews")
        self.enabled = all([self.host, self.port, self.user, self.password, self.sender])

    def send(self, to_email: str, subject: str, body: str) -> bool:
        if not self.enabled:
            return False
        msg = EmailMessage()
        msg["From"] = f"{self.sender_name} <{self.sender}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(self.user, self.password)
                s.send_message(msg)
            return True
        except Exception as e:
            st.warning(f"ส่งอีเมลไม่สำเร็จ: {e}")
            return False


MAILER = Mailer()


# ---- auth data layer ----

def find_user_by_email(email: str) -> Optional[Dict]:
    users = load_users()
    for u in users:
        if u.get("email", "").lower() == email.lower():
            return u
    return None


def upsert_user(user: Dict) -> None:
    users = load_users()
    found = False
    for i, u in enumerate(users):
        if u.get("email", "").lower() == user.get("email", "").lower():
            users[i] = user;
            found = True;
            break
    if not found:
        users.append(user)
    save_users(users)


def add_token(email: str, type_: str, expires_at: str) -> Dict:
    tokens = load_tokens()
    tok = {"token": generate_token(), "email": email, "type": type_, "expires_at": expires_at, "used": False,
           "created_at": datetime.now().isoformat(timespec="seconds")}
    tokens.append(tok);
    save_tokens(tokens)
    return tok


def consume_token(token: str, type_: str) -> Optional[Dict]:
    tokens = load_tokens()
    for t in tokens:
        if t.get("token") == token and t.get("type") == type_ and not t.get("used"):
            # (ไม่ตรวจวันหมดอายุแบบเข้มงวดเพื่อความง่ายของ prototype)
            t["used"] = True
            save_tokens(tokens)
            return t
    return None


# ---- URL helpers ----

def make_link_with_param(param_key: str, token: str) -> str:
    if APP_BASE_URL:
        sep = '&' if '?' in APP_BASE_URL else '?'
        return f"{APP_BASE_URL}{sep}{param_key}={token}"
    # fallback: relative link (ใช้ได้ถ้าคลิกจากในแอป)
    return f"?{param_key}={token}"


def get_query_params() -> Dict[str, List[str]]:
    try:
        return dict(st.query_params)
    except Exception:
        return st.experimental_get_query_params()


# ---- auth UI ----

def do_login_form():
    from textwrap import dedent

    st.markdown("### เข้าสู่ระบบ / ลงทะเบียน")

    # อ่าน query params เพื่อดูว่าเป็น reset flow ไหม
    try:
        q = get_query_params()
    except Exception:
        try:
            q = st.query_params
        except Exception:
            q = {}
    reset_token = q.get("reset", [None])[0] if isinstance(q.get("reset"), list) else q.get("reset")

    # กำหนดโหมดเริ่มต้น
    default_mode = "Forgot password" if reset_token else "Login"
    if "auth_mode" not in st.session_state:
        st.session_state["auth_mode"] = default_mode

    # ใช้ radio (จำสถานะข้าม rerun ได้) แทน tabs
    mode = st.radio(
        "โหมด",
        ["Login", "Sign up", "Forgot password"],
        index=["Login", "Sign up", "Forgot password"].index(st.session_state["auth_mode"]),
        horizontal=True,
        key="auth_mode"
    )

    # =========================
    # LOGIN
    # =========================
    if mode == "Login":
        email_or_admin = st.text_input(f"อีเมลนักศึกษา (@{ALLOWED_EMAIL_DOMAIN}) หรือ admin",
                                       key="auth_login_email")
        pw = st.text_input("รหัสผ่าน", type="password", key="auth_login_pw")
        if st.button("เข้าสู่ระบบ", type="primary", key="auth_login_btn"):
            if email_or_admin == "admin":
                user = USERS.get("admin")
                if user and user.get("password") == pw:
                    st.session_state["auth"] = {
                        "email": "admin", "username": "admin", "role": "admin",
                        "display": user.get("display", "Administrator")
                    }
                    st.success("เข้าสู่ระบบสำเร็จ (admin)")
                    st.rerun()
                else:
                    st.error("admin หรือรหัสผ่านไม่ถูกต้อง")
            else:
                if not email_or_admin.lower().endswith("@" + ALLOWED_EMAIL_DOMAIN):
                    st.error(f"อีเมลต้องลงท้ายด้วย @{ALLOWED_EMAIL_DOMAIN}")
                else:
                    u = find_user_by_email(email_or_admin)
                    if not u:
                        st.error("ไม่พบบัญชีผู้ใช้ — โปรดสมัครสมาชิกก่อน")
                    elif not u.get("is_verified"):
                        st.warning("บัญชียังไม่ยืนยันอีเมล — โปรดตรวจกล่องจดหมายของคุณ")
                        if st.button("ส่งอีเมลยืนยันอีกครั้ง", key="auth_login_resend"):
                            tok = add_token(u["email"], "verify", "")
                            link = make_link_with_param("verify", tok["token"])
                            body = f"สวัสดี {u.get('display', u['email'])}\n\nกดยืนยันที่ลิงก์นี้:\n{link}\n\n— MU Course Reviews"
                            ok = send_email(u["email"], "ยืนยันอีเมลสำหรับลงทะเบียน (ส่งใหม่)", body)
                            if ok:
                                st.success("ส่งอีเมลยืนยันอีกครั้งแล้ว โปรดตรวจกล่องจดหมาย")
                            else:
                                st.warning("ส่งอีเมลไม่สำเร็จ — ใช้ลิงก์ชั่วคราวด้านล่าง")
                                st.markdown(f"[คลิกเพื่อยืนยันบัญชี]({link})")
                                st.code(link)
                    else:
                        if verify_password(pw, u.get("password_salt", ""), u.get("password_hash", "")):
                            st.session_state["auth"] = {
                                "email": u["email"], "username": u["email"],
                                "role": u.get("role", "student"),
                                "display": u.get("display", u["email"])
                            }
                            st.success("เข้าสู่ระบบสำเร็จ")
                            st.rerun()
                        else:
                            st.error("รหัสผ่านไม่ถูกต้อง")

    # =========================
    # SIGN UP
    # =========================
    elif mode == "Sign up":
        student_email = st.text_input(f"อีเมลนักศึกษา (@{ALLOWED_EMAIL_DOMAIN})", key="auth_signup_email")
        pw1 = st.text_input(
            "รหัสผ่าน (อย่างน้อย 8 ตัวอักษร)",
            type="password",
            key="auth_signup_pw1",
            help=f"รหัสผ่านต้องมีอย่างน้อย {MIN_PASSWORD_LEN} ตัวอักษร"
        )

        pw2 = st.text_input("ยืนยันรหัสผ่าน", type="password", key="auth_signup_pw2")
        display = st.text_input("ชื่อที่แสดง (ไม่บังคับ)", key="auth_signup_display")

        if st.button("สมัครสมาชิก", key="auth_signup_btn"):
            if not student_email or not student_email.lower().endswith("@" + ALLOWED_EMAIL_DOMAIN):
                st.error(f"ต้องใช้อีเมล @{ALLOWED_EMAIL_DOMAIN} เท่านั้น")
            elif not pw1 or len(pw1) < MIN_PASSWORD_LEN:
                st.error(f"รหัสผ่านต้องยาวอย่างน้อย {MIN_PASSWORD_LEN} ตัวอักษร")
            elif pw1 != pw2:
                st.error("รหัสผ่านยืนยันไม่ตรงกัน")
            else:
                existing = find_user_by_email(student_email)
                salt = make_salt()
                pw_hash = hash_password(pw1, salt)

                if existing and existing.get("is_verified"):
                    st.error("อีเมลนี้มีผู้ใช้งานแล้ว")
                elif existing and not existing.get("is_verified"):
                    existing["password_salt"] = salt
                    existing["password_hash"] = pw_hash
                    if display:
                        existing["display"] = display
                    upsert_user(existing)

                    tok = add_token(student_email, "verify", "")
                    link = make_link_with_param("verify", tok["token"])
                    body = dedent(f"""\
                    สวัสดี {existing.get('display', student_email)},

                    เราได้รับคำขอลงทะเบียนสำหรับอีเมลนี้ ซึ่งยังไม่ได้ยืนยัน
                    กรุณาคลิกลิงก์ด้านล่างเพื่อยืนยันอีเมล:
                    {link}

                    หากคุณไม่ได้ส่งคำขอนี้ โปรดละเว้นอีเมลฉบับนี้
                    — MU Course Reviews
                    """)
                    ok = send_email(student_email, "ยืนยันอีเมลสำหรับลงทะเบียน (ส่งใหม่)", body)
                    if ok:
                        st.success("บัญชีนี้ยังไม่ยืนยัน — เราได้ส่งอีเมลยืนยันใหม่ให้แล้ว โปรดตรวจกล่องจดหมาย")
                    else:
                        st.warning("ส่งอีเมลไม่สำเร็จ — ใช้ลิงก์ยืนยันชั่วคราวด้านล่างได้เลย")
                        st.markdown(f"[คลิกเพื่อยืนยันบัญชี]({link})")
                        st.code(link)
                else:
                    user = {
                        "email": student_email,
                        "password_salt": salt,
                        "password_hash": pw_hash,
                        "role": "student",
                        "display": (display or student_email),
                        "is_verified": False,
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                    }
                    upsert_user(user)

                    tok = add_token(student_email, "verify", "")
                    link = make_link_with_param("verify", tok["token"])
                    body = dedent(f"""\
                    สวัสดี {display or student_email},

                    กรุณาคลิกลิงก์ด้านล่างเพื่อยืนยันอีเมลสำหรับเข้าใช้งานระบบรีวิวรายวิชา:
                    {link}

                    หากคุณไม่ได้ส่งคำขอนี้ โปรดละเว้นอีเมลฉบับนี้
                    — MU Course Reviews
                    """)
                    ok = send_email(student_email, "ยืนยันอีเมลสำหรับลงทะเบียน", body)
                    if ok:
                        st.success("สมัครเสร็จแล้ว! โปรดตรวจอีเมลเพื่อกดยืนยันก่อนเข้าสู่ระบบ")
                    else:
                        st.warning("ส่งอีเมลไม่สำเร็จ — ใช้ลิงก์ยืนยันชั่วคราวด้านล่างได้เลย")
                        st.markdown(f"[คลิกเพื่อยืนยันบัญชี]({link})")
                        st.code(link)

    # =========================
    # FORGOT / RESET PASSWORD
    # =========================
    else:
        if reset_token:
            st.info("ตั้งรหัสผ่านใหม่สำหรับโทเคนรีเซ็ต")
            npw1 = st.text_input("รหัสผ่านใหม่ (อย่างน้อย 8 ตัวอักษร)", type="password", key="auth_reset_pw1")
            st.caption(f"รหัสผ่านต้องยาวอย่างน้อย {MIN_PASSWORD_LEN} ตัวอักษร")

            npw2 = st.text_input("ยืนยันรหัสผ่านใหม่", type="password", key="auth_reset_pw2")
            if st.button("ยืนยันการตั้งรหัสผ่านใหม่", key="auth_reset_submit"):
                if not npw1 or len(npw1) < MIN_PASSWORD_LEN:
                    st.error(f"รหัสผ่านต้องยาวอย่างน้อย {MIN_PASSWORD_LEN} ตัวอักษร")
                elif npw1 != npw2:
                    st.error("รหัสผ่านยืนยันไม่ตรงกัน")
                else:
                    tok = get_token_record(reset_token, "reset")
                    if not tok or tok.get("used"):
                        st.error("โทเคนไม่ถูกต้องหรือถูกใช้ไปแล้ว")
                    else:
                        u = find_user_by_email(tok["email"])
                        if not u:
                            st.error("ไม่พบบัญชีผู้ใช้ที่เกี่ยวข้องกับโทเคน")
                        else:
                            salt = make_salt()
                            pw_hash = hash_password(npw1, salt)
                            u["password_salt"] = salt
                            u["password_hash"] = pw_hash
                            upsert_user(u)
                            consume_token(reset_token, "reset")
                            st.success("ตั้งรหัสผ่านใหม่สำเร็จ! โปรดเข้าสู่ระบบอีกครั้ง")
                            try:
                                st.query_params.clear()
                            except Exception:
                                st.experimental_set_query_params()
                            st.rerun()
        else:
            reset_email = st.text_input(f"อีเมลนักศึกษา (@{ALLOWED_EMAIL_DOMAIN})", key="auth_reset_email")
            if st.button("ส่งลิงก์รีเซ็ตรหัสผ่าน", key="auth_reset_btn"):
                if not reset_email or not reset_email.lower().endswith("@" + ALLOWED_EMAIL_DOMAIN):
                    st.error(f"ต้องใช้อีเมล @{ALLOWED_EMAIL_DOMAIN} เท่านั้น")
                elif not find_user_by_email(reset_email):
                    st.error("ไม่พบบัญชีผู้ใช้สำหรับอีเมลนี้")
                else:
                    tok = add_token(reset_email, "reset", "")
                    link = make_link_with_param("reset", tok["token"])
                    body = dedent(f"""\
                    สวัสดี {reset_email},

                    ตั้งรหัสผ่านใหม่ได้ที่ลิงก์ต่อไปนี้:
                    {link}

                    หากคุณไม่ได้ร้องขอ โปรดละเว้นอีเมลฉบับนี้
                    — MU Course Reviews
                    """)
                    ok = send_email(reset_email, "ลิงก์รีเซ็ตรหัสผ่าน — MU Course Reviews", body)
                    if ok:
                        st.success("ส่งลิงก์รีเซ็ตไปที่อีเมลแล้ว โปรดตรวจกล่องจดหมาย")
                    else:
                        st.warning("ส่งอีเมลไม่สำเร็จ — ใช้ลิงก์ชั่วคราวด้านล่าง")
                        st.markdown(f"[คลิกเพื่อรีเซ็ตรหัสผ่าน]({link})")
                        st.code(link)

# -----------------------------
# Utilities
# -----------------------------

# ---- magic-link handler (verify/reset) ----

def handle_magic_links():
    q = get_query_params()
    verify_token = q.get("verify") if isinstance(q.get("verify"), str) else (
        q.get("verify", [None])[0] if q.get("verify") else None)
    if verify_token:
        t = consume_token(verify_token, "verify")
        if t:
            u = find_user_by_email(t.get("email", ""))
            if u:
                u["is_verified"] = True
                upsert_user(u)
                st.success("ยืนยันอีเมลสำเร็จ! กรุณาเข้าสู่ระบบด้วยอีเมลนักศึกษา")
        else:
            st.warning("ลิงก์ยืนยันหมดอายุหรือถูกใช้ไปแล้ว")


def star_str(n: int) -> str:
    n = int(n)
    return "★" * n + "☆" * (5 - n)


def compute_course_stats(approved_reviews: List[Dict]) -> Dict[Tuple[int, str], Dict[str, float]]:
    stats: Dict[Tuple[int, str], Dict[str, float]] = {}
    for r in approved_reviews:
        if r.get("status") != "approved":
            continue
        key = (int(r.get("year", 0)), r.get("course_name") or r.get("course", ""))
        stats.setdefault(key, {"sum": 0.0, "count": 0})
        stats[key]["sum"] += float(r.get("rating", 0))
        stats[key]["count"] += 1
    for k, v in stats.items():
        v["avg"] = v["sum"] / v["count"] if v["count"] else 0.0
    return stats


# -----------------------------
# Login / sidebar
# -----------------------------

def do_login_form_legacy():
    # Legacy simple login disabled; using new email sign-in with verification
    pass


def sidebar_user_box():
    auth = st.session_state.get("auth")
    if not auth:
        return
    with st.sidebar:
        st.markdown(f"**ผู้ใช้:** {auth['display']}")
        st.markdown(f"**บทบาท:** `{auth['role']}`")
        if st.button("ออกจากระบบ", use_container_width=True):
            st.session_state.pop("auth", None)
            st.rerun()


# -----------------------------
# Helpers for filters (frontend)
# -----------------------------
ALL_FACULTIES = ["ทั้งหมด"] + sorted({r["faculty_name"] for r in ALL_COURSES})


def faculty_options() -> List[str]:
    return ALL_FACULTIES


def department_options(selected_faculty_name: str) -> List[str]:
    if selected_faculty_name == "ทั้งหมด":
        depts = sorted({r["department_name"] for r in ALL_COURSES})
    else:
        depts = sorted({r["department_name"] for r in ALL_COURSES if r["faculty_name"] == selected_faculty_name})
    return ["ทั้งหมด"] + depts


def year_options(selected_faculty_name: str, selected_dept_name: str) -> List[str]:
    # show actual years available from catalog
    years = sorted({
        r["year"] for r in ALL_COURSES
        if (selected_faculty_name == "ทั้งหมด" or r["faculty_name"] == selected_faculty_name)
           and (selected_dept_name == "ทั้งหมด" or r["department_name"] == selected_dept_name)
    })
    return ["ทั้งหมด"] + [str(y) for y in years]


def filter_courses(fac_name: str, dept_name: str, year_str: str) -> List[Dict]:
    items = list(ALL_COURSES)
    if fac_name != "ทั้งหมด":
        items = [r for r in items if r["faculty_name"] == fac_name]
    if dept_name != "ทั้งหมด":
        items = [r for r in items if r["department_name"] == dept_name]
    if year_str != "ทั้งหมด":
        items = [r for r in items if r["year"] == int(year_str)]
    return items


# -----------------------------
# Student page
# -----------------------------

def page_student(data: Dict):
    approved = data["approved_reviews"]
    pending = data["pending_reviews"]

    t_submit, t_browse = st.tabs(["📝 ส่งรีวิวรายวิชา", "🔎 ดูรีวิวที่อนุมัติแล้ว"])

    # Submit tab
    with t_submit:
        # --- NEW: ตัวกรองแบบ ประเภท → คณะ → รายวิชา ---
        st.subheader("เลือกประเภท / คณะ / รายวิชา")

        # 1) ประเภทของรายวิชา
        type_keys = list(COURSE_TYPES.keys())
        type_ix = st.selectbox(
            "ประเภทของรายวิชา",
            options=list(range(len(type_keys))),
            format_func=lambda i: COURSE_TYPES[type_keys[i]],
            key="stu_type_ix",
        )
        sel_type = type_keys[type_ix]

        # 2) คณะที่เปิดสอน (ตามประเภท)
        fac_map = list_faculties_by_type(sel_type)
        fac_codes = list(fac_map.keys())
        fac_ix = st.selectbox(
            "คณะที่เปิดสอน",
            options=list(range(len(fac_codes))),
            format_func=lambda i: f"{fac_codes[i]} - {fac_map[fac_codes[i]]}",
            key="stu_fac_ix",
        )
        fac_code = fac_codes[fac_ix]
        fac_name = fac_map[fac_code]

        # 3) รายวิชา (ตามประเภท + คณะ)
        courses = list_courses(sel_type, fac_code)
        if not courses:
            st.info("คณะนี้ยังไม่มีรายวิชาในแค็ตตาล็อก (เพิ่มภายหลังได้)")
            st.stop()

        course_ix = st.selectbox(
            "เลือกรายวิชา",
            options=list(range(len(courses))),
            format_func=lambda i: f"{courses[i]['code']} {courses[i]['name']}",
            key="stu_course_ix",
        )
        course = courses[course_ix]

        # ✅ กล่องข้อมูลรายวิชา (รวม header + meta + คำอธิบาย ไว้ในกรอบเดียว)
        # ✅ เมตาเรียงลำดับ: credit → prereq → grading → updated_at
        meta_bits = []
        if course.get("credit"):
            meta_bits.append(f"หน่วยกิต: {course['credit']}")
        if course.get("prereq"):
            meta_bits.append(f"เงื่อนไขรายวิชา: {course['prereq']}")
        if course.get("grading"):
            label = {"ABC": "เกรด A–F", "OSU": "O/S/U"}.get(course["grading"], course["grading"])
            meta_bits.append(f"การตัดเกรด: {course['grading']} ({label})")
        if course.get("updated_at"):
            meta_bits.append(f"อัปเดตล่าสุด: {course['updated_at']}")

        box_html = f"""
        <div class='box'>
          <div style="margin-bottom:.4rem;">
            <span class='codepill'>{course['code']}</span> <b>{course['name']}</b>
          </div>
          <div class='muted' style="margin-bottom:.5rem;">
            ประเภท: {COURSE_TYPES[sel_type]} • คณะ: {fac_code} - {fac_name}
          </div>
          {f'<div style="margin-bottom:.75rem;">' + ' • '.join(meta_bits) + '</div>' if meta_bits else ''}

          {f'<div style="margin-bottom:.35rem;"><b>คำอธิบายรายวิชา (ภาษาไทย)</b></div>' if course.get('desc_th') else ''}
          {f'<div style="margin-bottom:.6rem;">{course["desc_th"]}</div>' if course.get('desc_th') else ''}

          {f'<div style="margin-bottom:.35rem;"><b>คำอธิบายรายวิชา (ภาษาอังกฤษ)</b></div>' if course.get('desc_en') else ''}
          {f'<div class="muted">{course["desc_en"]}</div>' if course.get('desc_en') else ''}
        </div>
        """
        st.markdown(box_html, unsafe_allow_html=True)

        st.markdown("---")
        col_rate, _ = st.columns([1, 2])
        with col_rate:
            rating = st.radio("ให้คะแนน (1-5 ดาว)", options=[1, 2, 3, 4, 5], horizontal=True, index=4)
        st.markdown(f"**ตัวอย่างดาว:** <span class='star'>{star_str(rating)}</span>", unsafe_allow_html=True)
        review_text = st.text_area("เขียนรีวิวเพิ่มเติม (ไม่บังคับ)", max_chars=1200, height=150,
                                   placeholder="เล่าประสบการณ์ เนื้อหา งาน/การบ้าน ความยาก-ง่าย คำแนะนำ ฯลฯ")

        if st.button("ส่งรีวิว (เข้าคิวรอตรวจ)", type="primary", use_container_width=True):
            auth = st.session_state.get("auth", {})
            new_r = {
                "id": str(uuid.uuid4()),
                "course_type": sel_type,  # <— ใหม่: ประเภทวิชา
                "faculty": fac_code, "faculty_name": fac_name,
                "department": "", "department_name": "",  # ไม่ใช้แล้ว
                "year": "",  # ไม่ใช้แล้ว
                "course_code": course["code"], "course_name": course["name"],
                "rating": int(rating),
                "text": (review_text or "").strip(),
                "author": (st.session_state.get("auth", {}).get("email")
                           or st.session_state.get("auth", {}).get("username", "anonymous")),
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "status": "pending",
            }

            pending.append(new_r)
            save_data(data)
            st.success("ส่งรีวิวเรียบร้อย! รอผู้ดูแลอนุมัติ")
            st.balloons()

    # Browse tab
    with t_browse:
        # ---- BROWSE: ดูรีวิวที่อนุมัติแล้ว (แทนทั้งก้อนเดิมนี้) ----
        st.subheader("ดูรีวิวที่อนุมัติแล้ว (กรองตาม ประเภท/คณะ/รายวิชา)")

        col1, col2, col3, col4 = st.columns([1, 1, 1, 1.2])

        # 1) ประเภท
        with col1:
            type_choices = ["ทั้งหมด"] + list(COURSE_TYPES.keys())
            t = st.selectbox("ประเภท", type_choices, key="b_type")
            sel_type = None if t == "ทั้งหมด" else t

        # 2) คณะ (ขึ้นกับประเภท)
        with col2:
            fac_map_b = list_faculties_by_type(sel_type) if sel_type else {}
            fac_codes_b = ["ทั้งหมด"] + (list(fac_map_b.keys()) if fac_map_b else [])
            f = st.selectbox("คณะ", fac_codes_b, key="b_fac2")
            sel_fac = None if f == "ทั้งหมด" else f

        # 3) รายวิชา (ขึ้นกับประเภท+คณะ)
        with col3:
            course_list_b = list_courses(sel_type, sel_fac) if (sel_type and sel_fac) else []
            course_opts_b = ["ทั้งหมด"] + [f"{c['code']} {c['name']}" for c in course_list_b]
            c = st.selectbox("รายวิชา", course_opts_b, key="b_course2")

        # 4) ค้นหา
        with col4:
            q = st.text_input("ค้นหาในข้อความรีวิว", key="b_q2")

        # ดึงเฉพาะอนุมัติแล้ว
        items = [r for r in approved if r.get("status") == "approved"]

        # กรองตามตัวเลือก
        if sel_type:
            items = [r for r in items if r.get("course_type") == sel_type]
        if sel_fac:
            items = [r for r in items if r.get("faculty") == sel_fac]
        if c != "ทั้งหมด":
            code = c.split(" ")[0]
            items = [r for r in items if r.get("course_code") == code]
        if q:
            ql = q.lower().strip()
            items = [r for r in items if ql in (r.get("text") or "").lower()
                     or ql in (r.get("course_name") or "").lower()]

        # สรุป/ตาราง (ถ้าอยากคงแบบ DataFrame ก็เพิ่มส่วนนี้ได้)
        # import pandas as pd
        # if items:
        #     df = pd.DataFrame([{
        #         "ประเภท": COURSE_TYPES.get(r.get("course_type",""), r.get("course_type","")),
        #         "คณะ": f"{r.get('faculty','-')} - {r.get('faculty_name','-')}",
        #         "รายวิชา": f"{r.get('course_code','')} — {r.get('course_name','')}",
        #         "คะแนน": r.get("rating"),
        #         "ผู้รีวิว": r.get("author"),
        #         "วันที่": r.get("created_at"),
        #         "รีวิว": r.get("text",""),
        #     } for r in items])
        #     st.dataframe(df, use_container_width=True)

        # แสดงรายการรีวิวแบบการ์ด (แนวเดิมของคุณ)
        if not items:
            if sel_type and sel_fac and not course_list_b:
                st.info("คณะนี้ยังไม่มีรายวิชาในแค็ตตาล็อก (เพิ่มได้ภายหลัง)")
            else:
                st.info("ยังไม่มีรีวิวที่ผ่านการอนุมัติตามเงื่อนไขที่เลือก")
        else:
            for r in sorted(items, key=lambda x: x.get("created_at", ""), reverse=True):
                with st.container(border=True):
                    # หัวการ์ด: รหัส + ชื่อวิชา
                    st.markdown(
                        f"<span class='codepill'>{r.get('course_code', '')}</span> "
                        f"<b>{r.get('course_name', '')}</b>",
                        unsafe_allow_html=True,
                    )

                    # แสดงประเภท/คณะ
                    st.markdown(
                        f"ประเภท: {COURSE_TYPES.get(r.get('course_type', ''), r.get('course_type', ''))} • "
                        f"คณะ: {r.get('faculty', '-')} - {r.get('faculty_name', '-')}"
                    )

                    # 🔹 เพิ่มบรรทัดหน่วยกิต/การตัดเกรด/อัปเดตล่าสุด (ใช้ COURSE_LUT)
                    info = COURSE_LUT.get(r.get("course_code", ""), {})
                    meta2 = []
                    if info.get("credit"):
                        meta2.append(f"หน่วยกิต: {info['credit']}")
                    if info.get("prereq"):
                        meta2.append(f"เงื่อนไขรายวิชา: {info['prereq']}")
                    if info.get("grading"):
                        label = {"ABC": "เกรด A–F", "OSU": "O/S/U"}.get(info["grading"], info["grading"])
                        meta2.append(f"การตัดเกรด: {info['grading']} ({label})")
                    if info.get("updated_at"):
                        meta2.append(f"อัปเดตล่าสุด: {info['updated_at']}")
                    if meta2:
                        st.caption(" • ".join(meta2))

                    # เพิ่มบรรทัด prerequisite และคำอธิบาย
                    if info.get("prereq"):
                        st.caption(f"เงื่อนไขก่อนลงทะเบียน: {info['prereq']}")
                    if info.get("desc_th") or info.get("desc_en"):
                        with st.container(border=True):
                            if info.get("desc_th"):
                                st.markdown("**คำอธิบายรายวิชา (ภาษาไทย)**")
                                st.write(info["desc_th"])
                            if info.get("desc_en"):
                                st.markdown("<span class='muted'><b>Course Description (English)</b></span>",
                                            unsafe_allow_html=True)
                                st.write(info["desc_en"])

                    # คะแนน + ผู้รีวิว + วันที่
                    st.markdown(
                        f"ให้คะแนน: <span class='star'>{star_str(int(r.get('rating', 0)))}</span>  "
                        f"<span class='muted'>โดย `{r.get('author', '?')}` • วันที่ {r.get('created_at', '')}</span>",
                        unsafe_allow_html=True,
                    )

                    # เนื้อหารีวิว
                    if r.get("text"):
                        st.markdown("—")
                        st.write(r["text"])

# -----------------------------
# -----------------------------
# Admin helpers (filters + grouping)  [REPLACED]
# -----------------------------

def admin_type_options(items: List[Dict]) -> List[str]:
    """คืนค่าเป็น list ของคีย์ประเภทที่มีอยู่จริงใน items เช่น ['GE','FE','ME']"""
    types = sorted({r.get("course_type") for r in items if r.get("course_type")})
    return ["ทั้งหมด"] + types

def admin_faculty_map(items: List[Dict], sel_type: Optional[str] = None) -> Dict[str, str]:
    """สร้าง mapping code -> name เฉพาะที่มีอยู่จริงใน items (ตามประเภทที่เลือก)"""
    rows = [r for r in items if r.get("faculty") and (not sel_type or r.get("course_type") == sel_type)]
    m = {}
    for r in rows:
        code = r.get("faculty")
        name = r.get("faculty_name") or code
        if code not in m:
            m[code] = name
    return m

def admin_course_options(items: List[Dict], sel_type: Optional[str], sel_fac: Optional[str]) -> List[str]:
    """คืนค่าเป็น ['ทั้งหมด', 'CODE NAME', ...] ตามตัวกรองประเภท/คณะ"""
    rows = [r for r in items if r.get("course_code")]
    if sel_type:
        rows = [r for r in rows if r.get("course_type") == sel_type]
    if sel_fac:
        rows = [r for r in rows if r.get("faculty") == sel_fac]
    names = sorted({f"{r['course_code']} {r.get('course_name','')}".strip() for r in rows})
    return ["ทั้งหมด"] + names

def admin_apply_filters(items: List[Dict],
                        sel_type: Optional[str],
                        sel_fac: Optional[str],
                        course_label: str,
                        q: str,
                        min_rating: int) -> List[Dict]:
    out = list(items)
    if sel_type:
        out = [r for r in out if r.get("course_type") == sel_type]
    if sel_fac:
        out = [r for r in out if r.get("faculty") == sel_fac]
    if course_label and course_label != "ทั้งหมด":
        code = course_label.split(" ")[0]
        out = [r for r in out if str(r.get("course_code", "")) == code]
    if q:
        ql = q.lower().strip()
        out = [r for r in out if ql in (r.get("text") or "").lower()
               or ql in (r.get("course_name") or "").lower()]
    if min_rating and min_rating > 1:
        out = [r for r in out if int(r.get("rating", 0)) >= min_rating]
    return out

def admin_sort_items(items: List[Dict], sort_key: str) -> List[Dict]:
    if sort_key == "วันที่ (ใหม่→เก่า)": return sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)
    if sort_key == "วันที่ (เก่า→ใหม่)": return sorted(items, key=lambda x: x.get("created_at", ""))
    if sort_key == "คะแนน (สูง→ต่ำ)": return sorted(items, key=lambda x: int(x.get("rating", 0)), reverse=True)
    if sort_key == "คะแนน (ต่ำ→สูง)": return sorted(items, key=lambda x: int(x.get("rating", 0)))
    return items

def bulk_bar(filtered_ids: List[str], data: Dict):
    pending = data["pending_reviews"]
    selected_ids = st.session_state.get("selected_ids", set())
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    with c1:
        if st.button("เลือกทั้งหมด(ตามตัวกรอง)"):
            st.session_state["selected_ids"] = set(filtered_ids)
            st.rerun()
    with c2:
        if st.button("ล้างการเลือก"):
            st.session_state["selected_ids"] = set()
            st.rerun()
    with c3:
        if st.button("✅ อนุมัติที่เลือก") and selected_ids:
            move, keep = [], []
            ids = set(selected_ids)
            for r in pending: (move if r["id"] in ids else keep).append(r)
            for r in move: r["status"] = "approved"
            data["approved_reviews"].extend(move)
            data["pending_reviews"] = keep
            save_data(data)
            st.success(f"อนุมัติ {len(move)} รายการ")
            st.session_state["selected_ids"] = set()
            st.rerun()
    with c4:
        if st.button("🗑️ ปฏิเสธที่เลือก") and selected_ids:
            keep = [r for r in pending if r["id"] not in selected_ids]
            removed = len(pending) - len(keep)
            data["pending_reviews"] = keep
            save_data(data)
            st.warning(f"ปฏิเสธ {removed} รายการ")
            st.session_state["selected_ids"] = set()
            st.rerun()

def render_grouped(items: List[Dict], data: Optional[Dict] = None, pending_mode: bool = False):
    """จัดกลุ่มเป็น ประเภท → คณะ → รายวิชา"""
    if not items:
        st.info("ไม่พบรายการตามตัวกรอง")
        return
    selected_ids = st.session_state.setdefault("selected_ids", set())
    groups: Dict[str, Dict[str, Dict[str, List[Dict]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in items:
        ctype = COURSE_TYPES.get(r.get("course_type",""), r.get("course_type","?"))
        fac = f"{r.get('faculty','?')} - {r.get('faculty_name','?')}"
        course_key = f"{r.get('course_code','')} {r.get('course_name','')}".strip()
        groups[ctype][fac][course_key].append(r)

    for ctype in sorted(groups.keys()):
        with st.expander(f"ประเภท: {ctype}", expanded=True):
            for fac in sorted(groups[ctype].keys()):
                st.markdown(f"### คณะ: {fac}")
                for course_key in sorted(groups[ctype][fac].keys()):
                    st.markdown(f"**รายวิชา: {course_key}**")
                    for r in groups[ctype][fac][course_key]:
                        with st.container(border=True):
                            left, right = st.columns([3, 1])
                            with left:
                                st.markdown(
                                    f"**{r.get('course_code','')} {r.get('course_name','')}**  \n"
                                    f"ให้คะแนน: {star_str(int(r.get('rating', 0)))}  \n"
                                    f"โดย `{r.get('author', '?')}` • วันที่ {r.get('created_at', '')}"
                                )
                                if txt := r.get("text"):
                                    st.markdown("—"); st.write(txt)
                            with right:
                                if pending_mode and data is not None:
                                    checked = r["id"] in selected_ids
                                    ck = st.checkbox("เลือก", key=f"sel_{r['id']}", value=checked)
                                    if ck and r["id"] not in selected_ids: selected_ids.add(r["id"])
                                    if not ck and r["id"] in selected_ids: selected_ids.remove(r["id"])
                                    a1, a2 = st.columns(2)
                                    with a1:
                                        if st.button("อนุมัติ", key=f"ap_{r['id']}"):
                                            r["status"] = "approved"
                                            data["approved_reviews"].append(r)
                                            data["pending_reviews"].remove(r)
                                            save_data(data)
                                            st.success("อนุมัติแล้ว"); st.rerun()
                                    with a2:
                                        if st.button("ปฏิเสธ", key=f"re_{r['id']}"):
                                            data["pending_reviews"].remove(r)
                                            save_data(data)
                                            st.warning("ปฏิเสธแล้ว"); st.rerun()


# -----------------------------
# Summary table (Admin)  [REPLACED]
# -----------------------------
def build_summary_rows(approved: List[Dict]) -> List[Dict]:
    """สรุปเป็นต่อรายวิชา: (ประเภท, คณะ, รหัส/ชื่อรายวิชา) → avg, count"""
    agg: Dict[Tuple[str, str, str, str, str], Dict[str, float]] = {}
    # key: (course_type, faculty_code, faculty_name, course_code, course_name)
    for r in approved:
        if r.get("status") != "approved":
            continue
        key = (
            r.get("course_type",""),
            r.get("faculty","-"),
            r.get("faculty_name","-"),
            r.get("course_code",""),
            r.get("course_name","-"),
        )
        obj = agg.setdefault(key, {"sum": 0.0, "count": 0.0})
        obj["sum"] += float(r.get("rating", 0))
        obj["count"] += 1

    rows: List[Dict] = []
    for (ctype, fac_code, fac_name, ccode, cname), v in agg.items():
        avg = v["sum"] / v["count"] if v["count"] else 0.0
        rows.append({
            "ประเภท": COURSE_TYPES.get(ctype, ctype),
            "คณะ": f"{fac_code} - {fac_name}",
            "รหัสวิชา": ccode,
            "รายวิชา": cname,
            "ค่าเฉลี่ย": round(avg, 2),
            "ดาว": star_str(int(round(avg))),
            "จำนวนรีวิว": int(v["count"]),
            "เฉลี่ย/5": avg / 5.0,
        })
    rows.sort(key=lambda r: (r["ประเภท"], r["คณะ"], r["รหัสวิชา"]))
    return rows

def summary_table_panel(data: Dict):
    st.subheader("📊 สรุปภาพรวม (ตาราง)")
    approved = [r for r in data.get("approved_reviews", []) if r.get("status") == "approved"]
    all_rows = build_summary_rows(approved)

    if not all_rows:
        st.info("ยังไม่มีข้อมูลสรุป"); return

    # Filters
    c1, c2, c3 = st.columns(3)
    with c1:
        types = ["ทั้งหมด"] + sorted({r["ประเภท"] for r in all_rows})
        ftype = st.selectbox("ประเภท", types, index=0, key="sum_type")
    with c2:
        facs = ["ทั้งหมด"] + sorted({r["คณะ"] for r in all_rows if ftype == "ทั้งหมด" or r["ประเภท"] == ftype})
        ffac = st.selectbox("คณะ", facs, index=0, key="sum_fac2")
    with c3:
        courses = ["ทั้งหมด"] + sorted({r["รหัสวิชา"] for r in all_rows
                                        if (ftype == "ทั้งหมด" or r["ประเภท"] == ftype) and
                                           (ffac == "ทั้งหมด" or r["คณะ"] == ffac)})
        fc = st.selectbox("รายวิชา", courses, index=0, key="sum_course2")

    rows = [r for r in all_rows
            if (ftype == "ทั้งหมด" or r["ประเภท"] == ftype)
            and (ffac == "ทั้งหมด" or r["คณะ"] == ffac)
            and (fc == "ทั้งหมด" or r["รหัสวิชา"] == fc)]

    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        use_container_width=True,
        column_config={
            "ค่าเฉลี่ย": st.column_config.NumberColumn(format="%.2f"),
            "จำนวนรีวิว": st.column_config.NumberColumn(format="%d"),
            "เฉลี่ย/5": st.column_config.ProgressColumn("เฉลี่ย/5", min_value=0.0, max_value=1.0),
        },
    )



# -----------------------------
# Admin page
# -----------------------------

def page_admin(data: Dict):
    st.markdown("### หลังบ้าน (Admin)")
    pending = data.get("pending_reviews", [])
    approved = [r for r in data.get("approved_reviews", []) if r.get("status") == "approved"]

    t_pend, t_appr, t_sum = st.tabs(["🕒 คิวรออนุมัติ", "✅ รีวิวที่อนุมัติแล้ว", "📊 สรุปตาราง"])

    with t_pend:
        st.subheader("กรองคิวรีวิว")
        # ตัวกรอง: ประเภท → คณะ → รายวิชา
        col1, col2, col3, col4 = st.columns([1,1,1,1.2])

        with col1:
            t_opts = admin_type_options(pending)
            p_type = st.selectbox("ประเภท", t_opts, index=0, key="adm_p_type",
                                  format_func=lambda v: "ทั้งหมด" if v=="ทั้งหมด" else COURSE_TYPES.get(v, v))
            sel_type = None if p_type == "ทั้งหมด" else p_type

        with col2:
            fac_map = admin_faculty_map(pending, sel_type)
            f_opts = ["ทั้งหมด"] + list(sorted(fac_map.keys()))
            p_fac = st.selectbox("คณะ", f_opts, index=0, key="adm_p_fac2",
                                 format_func=lambda code: "ทั้งหมด" if code=="ทั้งหมด" else f"{code} - {fac_map.get(code, code)}")
            sel_fac = None if p_fac == "ทั้งหมด" else p_fac

        with col3:
            c_opts = admin_course_options(pending, sel_type, sel_fac)
            p_course = st.selectbox("รายวิชา", c_opts, index=0, key="adm_p_course2")

        with col4:
            p_q = st.text_input("ค้นหาในข้อความรีวิว/ชื่อวิชา", key="adm_p_q2")

        p_minr = st.slider("คะแนนขั้นต่ำ", 1, 5, 1, step=1, key="adm_p_minr2")
        sort1 = st.selectbox("จัดเรียงโดย",
                             ["วันที่ (ใหม่→เก่า)", "วันที่ (เก่า→ใหม่)", "คะแนน (สูง→ต่ำ)", "คะแนน (ต่ำ→สูง)"],
                             index=0, key="adm_p_sort2")

        pf = admin_apply_filters(pending, sel_type, sel_fac, p_course, p_q, p_minr)
        pf = admin_sort_items(pf, sort1)
        ids = [r["id"] for r in pf]
        bulk_bar(ids, data)
        render_grouped(pf, data=data, pending_mode=True)

    with t_appr:
        st.subheader("กรองรีวิวที่อนุมัติแล้ว")
        col1, col2, col3, col4 = st.columns([1,1,1,1.2])

        with col1:
            t_opts = admin_type_options(approved)
            a_type = st.selectbox("ประเภท", t_opts, index=0, key="adm_a_type",
                                  format_func=lambda v: "ทั้งหมด" if v=="ทั้งหมด" else COURSE_TYPES.get(v, v))
            sel_type2 = None if a_type == "ทั้งหมด" else a_type

        with col2:
            fac_map2 = admin_faculty_map(approved, sel_type2)
            f_opts2 = ["ทั้งหมด"] + list(sorted(fac_map2.keys()))
            a_fac = st.selectbox("คณะ", f_opts2, index=0, key="adm_a_fac2",
                                 format_func=lambda code: "ทั้งหมด" if code=="ทั้งหมด" else f"{code} - {fac_map2.get(code, code)}")
            sel_fac2 = None if a_fac == "ทั้งหมด" else a_fac

        with col3:
            c_opts2 = admin_course_options(approved, sel_type2, sel_fac2)
            a_course = st.selectbox("รายวิชา", c_opts2, index=0, key="adm_a_course2")

        with col4:
            a_q = st.text_input("ค้นหาในข้อความรีวิว/ชื่อวิชา", key="adm_a_q2")

        a_minr = st.slider("คะแนนขั้นต่ำ", 1, 5, 1, step=1, key="adm_a_minr2")
        sort2 = st.selectbox("จัดเรียงโดย",
                             ["วันที่ (ใหม่→เก่า)", "วันที่ (เก่า→ใหม่)", "คะแนน (สูง→ต่ำ)", "คะแนน (ต่ำ→สูง)"],
                             index=0, key="adm_a_sort2")

        af = admin_apply_filters(approved, sel_type2, sel_fac2, a_course, a_q, a_minr)
        af = admin_sort_items(af, sort2)
        render_grouped(af, pending_mode=False)

    with t_sum:
        summary_table_panel(data)

    st.divider()
    # Exports
    from io import StringIO
    import csv
    colx, coly = st.columns(2)
    with colx:
        if st.button("⬇️ ดาวน์โหลด Approved (CSV)"):
            rows = approved
            if not rows:
                st.info("ยังไม่มีข้อมูลที่อนุมัติ")
            else:
                buf = StringIO()
                writer = csv.DictWriter(
                    buf,
                    fieldnames=[
                        "id", "course_type",
                        "faculty", "faculty_name",
                        "department", "department_name", "year",   # ยัง export ไว้เผื่อข้อมูลเก่า
                        "course_code", "course_name",
                        "rating", "text", "author", "created_at", "status",
                    ],
                )
                writer.writeheader()
                for r in rows:
                    writer.writerow({k: r.get(k, "") for k in writer.fieldnames})
                st.download_button("Download approved_reviews.csv", buf.getvalue(), "approved_reviews.csv", "text/csv")
    with coly:
        if st.button("⬇️ ดาวน์โหลดฐานข้อมูลทั้งหมด (JSON)"):
            payload = json.dumps(data, ensure_ascii=False, indent=2)
            st.download_button("Download data.json", payload, "data.json", "application/json")


# สร้าง lookup จาก catalog: code → {credit, grading, updated_at}
def build_course_lookup():
    lut = {}
    for ctype, facs in COURSE_CATALOG_BY_TYPE.items():
        for fac, items in facs.items():
            for c in items:
                lut[c["code"]] = {
                    "credit":     c.get("credit"),
                    "grading":    c.get("grading"),
                    "updated_at": c.get("updated_at"),
                    "prereq":     c.get("prereq"),
                    "desc_th":    c.get("desc_th"),
                    "desc_en":    c.get("desc_en"),
                    "type":       ctype,
                    "faculty":    fac,
                }
    return lut


COURSE_LUT = build_course_lookup()

# -----------------------------
# Main
# -----------------------------

def header_bar():
    data = load_data()
    approved_cnt = len([r for r in data.get('approved_reviews', []) if r.get('status') == 'approved'])
    st.title(APP_TITLE)
    st.caption(
        f"คิวรอตรวจ: {len(data.get('pending_reviews', []))} | อนุมัติแล้วสะสม: {approved_cnt} — จัดเก็บด้วย {BACKEND.upper()}")
    st.divider()

# ===== Email helper (วางไว้ส่วน Utilities ก่อน do_login_form) =====


def send_email(to: str, subject: str, body: str) -> bool:
    host = st.secrets.get("SMTP_HOST")
    port = st.secrets.get("SMTP_PORT")
    user = st.secrets.get("SMTP_USER")
    pwd  = st.secrets.get("SMTP_PASS")
    sender = st.secrets.get("SMTP_SENDER") or user
    sender_name = st.secrets.get("SMTP_SENDER_NAME", "MU Course Reviews")
    use_ssl = str(st.secrets.get("SMTP_SSL", "false")).lower() in ("1","true","yes")

    # ชี้ชัดว่าคีย์ไหนหาย
    missing = [k for k,v in {
        "SMTP_HOST": host, "SMTP_PORT": port, "SMTP_USER": user,
        "SMTP_PASS": pwd, "SMTP_SENDER": sender
    }.items() if not v]
    if missing:
        st.error("SMTP secrets ไม่ครบ: " + ", ".join(missing))
        return False

    port = int(port)  # แปลงตรงนี้หลังเช็กครบ
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{sender}>"
    msg["To"] = to
    reply_to = st.secrets.get("REPLY_TO")
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=20) as s:
                s.login(user, pwd)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(user, pwd)
                s.send_message(msg)
        return True
    except Exception as e:
        st.error(f"SMTP error: {e}")
        return False




def main():
    # handle magic links (verify/reset) before painting header
    handle_magic_links()
    header_bar()
    if "auth" not in st.session_state:
        do_login_form();
        return
    sidebar_user_box()
    data = load_data()
    role = st.session_state["auth"]["role"]
    if role == "admin":
        page_admin(data)
    else:
        page_student(data)


if __name__ == "__main__":
    main()
