# app.py  (หรือชื่อไฟล์ที่คุณใช้รัน Streamlit)
import streamlit as st
import json
import os
import uuid
from datetime import datetime
from functools import lru_cache
from typing import Dict, List, Tuple, Optional
from collections import defaultdict, Counter
from textwrap import dedent
import smtplib, ssl
# สำหรับกราฟ: ใช้ Altair ถ้ามี ไม่มีก็ fallback เป็น st.bar_chart
try:
    import altair as alt
    ALTAIR_AVAILABLE = True
except Exception:
    ALTAIR_AVAILABLE = False

import pandas as pd  # ให้แน่ใจว่ามี pandas ใช้สร้าง DataFrame สำหรับกราฟ
from email.message import EmailMessage

# =============================
# Page config & global styles
# =============================
st.set_page_config(page_title="MU Course Reviews — All-in-One", page_icon="⭐", layout="wide")

st.markdown(
    """
    <style>
      /* Base styles */
      .star {font-size: 1.0rem; line-height: 1}
      .muted {color: rgba(0,0,0,0.6); font-size: 0.9rem}
      .codepill {display:inline-block; padding:0.2rem 0.45rem; border-radius:6px; background:#f0f2f6; font-weight:600}
      .box {padding:0.75rem 0.9rem; background:#f8fafc; border:1px solid #eef2f7; border-radius:8px}
    </style>
    """,
    unsafe_allow_html=True,
)

# Material Icons (แก้ ghost text keyboard_arrow_down)
st.markdown("""
<link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">

<style>
/* ใช้ Browallia New ทั้งแอป */
.stApp, .stApp p, .stApp div, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
.stApp li, .stApp label, .stApp input, .stApp button, .stApp textarea {
  font-family: "Browallia New", "Noto Sans Thai", Tahoma, sans-serif !important;
}
/* ขยายขนาดฟอนต์ทั้งหน้าตามที่ต้องการ */
html, body { font-size: 20px; }

/* คงฟอนต์ของไอคอนไว้ให้ถูกต้อง */
.material-icons, .material-icons-outlined,
.material-symbols-outlined, .material-symbols-rounded {
  font-family: 'Material Icons', 'Material Symbols Outlined', 'Material Symbols Rounded' !important;
  font-weight: normal !important;
  font-style: normal !important;
  text-transform: none !important;
  letter-spacing: normal !important;
  -webkit-font-feature-settings: 'liga' !important;
  -webkit-font-smoothing: antialiased !important;
}
</style>
""", unsafe_allow_html=True)

APP_TITLE = "เว็บไซต์รีวิวรายวิชามหาวิทยาลัยมหิดล MU Review Course"
DATA_FILE = os.path.join("data", "data.json")
MIN_PASSWORD_LEN = 8

# =====================================================
# Course catalog loader — from Google Sheets
# คอลัมน์ที่ต้องมี: code_en, title_th, category, faculty_init, faculty_name,
#                    credit, grading, detail_th, detail_en, prereq_en
# Secrets:
#   - gcp_service_account (JSON)
#   - COURSE_SHEET_KEY (optional; fallback ไป SPREADSHEET_KEY)
#   - COURSE_SHEET_WS  (optional; ดีฟอลต์ "courses")
# =====================================================

COURSE_SHEET_KEY = st.secrets.get("COURSE_SHEET_KEY", st.secrets.get("SPREADSHEET_KEY", ""))
COURSE_SHEET_WS  = st.secrets.get("COURSE_SHEET_WS", "courses")

# Fallback sample (กรณีโหลดชีตไม่ได้)
FALLBACK_ROWS = [
    {
        "code_en": "SIHE301",
        "title_th": "จิตวิทยาสังคมสำหรับบุคลากรในระบบสุขภาพ",
        "category": "รายวิชาศึกษาทั่วไป",
        "faculty_init": "SI",
        "faculty_name": "คณะแพทยศาสตร์ศิริราชพยาบาล",
        "credit": "2(2-0-4)",
        "grading": "OSU",
        "detail_th": "ภาษาและการสื่อสาร การรับรู้ทางสังคม ... จิตวิทยาสังคมกับระบบสุขภาพ",
        "detail_en": "Language and communication ... social psychology and healthcare",
        "prereq_en": "",
        "updated_at": "2025-09-03",
    },
    {
        "code_en": "SCMA 349",
        "title_th": "Software Engineering",
        "category": "รายวิชาเฉพาะเลือก (SC - คณิตศาสตร์)",
        "faculty_init": "SC",
        "faculty_name": "คณะวิทยาศาสตร์",
        "credit": "3(3-0-6)",
        "grading": "ABC",
        "detail_th": "วิศวกรรมซอฟต์แวร์เบื้องต้น ...",
        "detail_en": "Introduction to software engineering ...",
        "prereq_en": "SCMA 247",
        "updated_at": "2025-09-03",
    },
]

def _normalize_course_row(r: Dict) -> Dict:
    return {
        "code": (r.get("code_en") or "").strip(),
        "name": (r.get("title_th") or "").strip(),
        "course_type": (r.get("category") or "").strip(),      # ใช้ชื่อหมวดภาษาไทยเป็น key เลย
        "faculty": (r.get("faculty_init") or "").strip(),      # เช่น SI
        "faculty_name": (r.get("faculty_name") or "").strip(),
        "credit": (r.get("credit") or "").strip(),
        "grading": (r.get("grading") or "").strip(),
        "desc_th": (r.get("detail_th") or "").strip(),
        "desc_en": (r.get("detail_en") or "").strip(),
        "prereq_en": (r.get("prereq_en") or "").strip(),
        "updated_at": (r.get("updated_at") or "").strip(),
    }

@st.cache_data(ttl=300)
def load_courses_from_gsheets() -> List[Dict]:
    rows: List[Dict] = []
    try:
        import gspread
        svc_info = dict(st.secrets.get("gcp_service_account", {}))
        if not svc_info:
            raise RuntimeError("Missing gcp_service_account in secrets")
        if not COURSE_SHEET_KEY:
            raise RuntimeError("Missing COURSE_SHEET_KEY or SPREADSHEET_KEY in secrets")
        gc = gspread.service_account_from_dict(svc_info)
        ss = gc.open_by_key(COURSE_SHEET_KEY)
        ws = ss.worksheet(COURSE_SHEET_WS)
        raw = ws.get_all_records()
        for r in raw:
            rows.append(_normalize_course_row(r))
        if not rows:
            raise RuntimeError("Course sheet is empty")
        return rows
    except Exception as e:
        st.warning(f"ไม่สามารถโหลดคาแทล็อกจาก Google Sheets ได้ ใช้ข้อมูลตัวอย่างแทน — {e}")
        return [_normalize_course_row(r) for r in FALLBACK_ROWS]

@st.cache_data(ttl=300)
def build_catalog_struct(course_rows: List[Dict]):
    """
    คืนค่า:
      - COURSE_TYPES: dict[str,str] (ใช้ label เป็น key และ value)
      - FACULTIES_BY_TYPE: {category: {fac_code: fac_name}}
      - COURSE_CATALOG_BY_TYPE: {category: {fac_code: [course,...]}}
      - COURSE_LUT: {course_code: meta}
      - ALL_COURSES: flat list (บางส่วนของโค้ดเก่าอาจยังใช้)
    """
    cats = sorted({r["course_type"] for r in course_rows if r.get("course_type")})
    COURSE_TYPES = {c: c for c in cats}

    FACULTIES_BY_TYPE: Dict[str, Dict[str, str]] = defaultdict(dict)
    COURSE_CATALOG_BY_TYPE: Dict[str, Dict[str, List[Dict]]] = defaultdict(lambda: defaultdict(list))
    for r in course_rows:
        ctype = r["course_type"]
        fac_code = r["faculty"]
        fac_name = r["faculty_name"] or fac_code
        FACULTIES_BY_TYPE[ctype][fac_code] = fac_name
        COURSE_CATALOG_BY_TYPE[ctype][fac_code].append({
            "code": r["code"],
            "name": r["name"],
            "desc_th": r.get("desc_th",""),
            "desc_en": r.get("desc_en",""),
            "credit": r.get("credit"),
            "grading": r.get("grading"),
            "updated_at": r.get("updated_at"),
            "prereq_en": r.get("prereq_en",""),
        })

    # sort by code
    for ctype in COURSE_CATALOG_BY_TYPE:
        for fac in COURSE_CATALOG_BY_TYPE[ctype]:
            COURSE_CATALOG_BY_TYPE[ctype][fac].sort(key=lambda x: x.get("code",""))

    ALL_COURSES: List[Dict] = []
    for ctype, facs in COURSE_CATALOG_BY_TYPE.items():
        for fac_code, items in facs.items():
            fac_name = FACULTIES_BY_TYPE[ctype].get(fac_code, fac_code)
            for c in items:
                ALL_COURSES.append({
                    "course_type": ctype,
                    "faculty": fac_code,
                    "faculty_name": fac_name,
                    "department": "",
                    "department_name": "",
                    "year": 0,
                    "code": c["code"],
                    "name": c["name"],
                    "desc_th": c.get("desc_th",""),
                    "desc_en": c.get("desc_en",""),
                    "credit": c.get("credit"),
                    "prereq_en": c.get("prereq_en"),
                })
    ALL_COURSES.sort(key=lambda r: (r["course_type"], r["faculty"], r["code"]))

    COURSE_LUT: Dict[str, Dict] = {}
    for r in course_rows:
        COURSE_LUT[r["code"]] = {
            "credit": r.get("credit"),
            "grading": r.get("grading"),
            "updated_at": r.get("updated_at"),
            "prereq_en": r.get("prereq_en"),
            "desc_th": r.get("desc_th"),
            "desc_en": r.get("desc_en"),
            "type": r.get("course_type"),
            "faculty": r.get("faculty"),
            "faculty_name": r.get("faculty_name"),
            "name": r.get("name"),
        }

    return COURSE_TYPES, dict(FACULTIES_BY_TYPE), {k: dict(v) for k,v in COURSE_CATALOG_BY_TYPE.items()}, ALL_COURSES, COURSE_LUT

# Build catalog structures (from Sheets)
_COURSE_ROWS = load_courses_from_gsheets()
COURSE_TYPES, FACULTIES_BY_TYPE, COURSE_CATALOG_BY_TYPE, ALL_COURSES, COURSE_LUT = build_catalog_struct(_COURSE_ROWS)

# convenience helpers
def list_faculties_by_type(course_type: str) -> dict:
    return FACULTIES_BY_TYPE.get(course_type, {})

def list_courses(course_type: str, faculty_code: str) -> list:
    return COURSE_CATALOG_BY_TYPE.get(course_type, {}).get(faculty_code, [])

# -----------------------------
# Auth (prototype admin fallback)
# -----------------------------
USERS: Dict[str, Dict[str, str]] = {
    "admin": {"password": "admin", "role": "admin", "display": "Administrator"},
}

# -----------------------------
# Storage (Local JSON or Google Sheets)
# -----------------------------
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
    """ใช้ Google Sheets เป็น DB: pending_reviews, approved_reviews, users, tokens"""
    def __init__(self):
        import gspread
        svc_info = dict(st.secrets.get("gcp_service_account", {}))
        if not svc_info:
            raise RuntimeError("Missing gcp_service_account in secrets")
        self.spreadsheet_key = st.secrets.get("SPREADSHEET_KEY")
        if not self.spreadsheet_key:
            raise RuntimeError("Missing SPREADSHEET_KEY in secrets")

        self.gc = gspread.service_account_from_dict(svc_info)
        self.ss = self.gc.open_by_key(self.spreadsheet_key)

        self.ws_pending  = self._get_or_create_ws("pending_reviews",  cols=len(HEADERS))
        self.ws_approved = self._get_or_create_ws("approved_reviews", cols=len(HEADERS))
        self.ws_users    = self._get_or_create_ws("users",            cols=len(USERS_HEADERS))
        self.ws_tokens   = self._get_or_create_ws("tokens",           cols=len(TOKENS_HEADERS))

        self._ensure_headers(self.ws_pending,  HEADERS)
        self._ensure_headers(self.ws_approved, HEADERS)
        self._ensure_headers(self.ws_users,    USERS_HEADERS)
        self._ensure_headers(self.ws_tokens,   TOKENS_HEADERS)

    def _get_or_create_ws(self, title: str, rows: int = 2000, cols: int = 20):
        try:
            return self.ss.worksheet(title)
        except Exception:
            return self.ss.add_worksheet(title=title, rows=rows, cols=cols)

    def _ensure_headers(self, ws, headers=None):
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
        vals = ws.get_all_values()
        if not vals: return [], []
        headers = vals[0]
        rows = vals[1:] if len(vals) > 1 else []
        return headers, rows

    def _rows_to_dicts(self, rows: List[List[str]], headers: List[str], default_headers: List[str]) -> List[Dict]:
        keys = list(dict.fromkeys(list(default_headers) + list(headers)))
        out: List[Dict] = []
        for r in rows:
            rec = {k: "" for k in keys}
            for i, v in enumerate(r):
                if i < len(headers):
                    rec[headers[i]] = v
            if "year" in rec:
                try: rec["year"] = int(rec.get("year") or 0)
                except Exception: rec["year"] = 0
            if "rating" in rec:
                try: rec["rating"] = int(rec.get("rating") or 0)
                except Exception: rec["rating"] = 0
            out.append(rec)
        return out

    def _dicts_to_rows(self, dicts: List[Dict], headers: List[str]) -> List[List[str]]:
        rows: List[List[str]] = []
        for d in dicts:
            rows.append([str(d.get(k, "")) for k in headers])
        return rows

    def load_data(self) -> Dict:
        hdr_p, rows_p = self._read_all(self.ws_pending)
        if not hdr_p:
            self._ensure_headers(self.ws_pending, HEADERS)
            hdr_p, rows_p = HEADERS, []
        pending = self._rows_to_dicts(rows_p, hdr_p, HEADERS)

        hdr_a, rows_a = self._read_all(self.ws_approved)
        if not hdr_a:
            self._ensure_headers(self.ws_approved, HEADERS)
            hdr_a, rows_a = HEADERS, []
        approved = self._rows_to_dicts(rows_a, hdr_a, HEADERS)

        return {"pending_reviews": pending, "approved_reviews": approved}

    def save_data(self, data: Dict) -> None:
        pending = data.get("pending_reviews", [])
        approved = data.get("approved_reviews", [])
        self.ws_pending.clear()
        self.ws_pending.update("A1", [HEADERS] + self._dicts_to_rows(pending, HEADERS))
        self.ws_approved.clear()
        self.ws_approved.update("A1", [HEADERS] + self._dicts_to_rows(approved, HEADERS))

    # users
    def load_users(self) -> List[Dict]:
        hdr, rows = self._read_all(self.ws_users)
        if not hdr:
            self._ensure_headers(self.ws_users, USERS_HEADERS)
            return []
        return self._rows_to_dicts(rows, hdr, USERS_HEADERS)

    def upsert_user(self, user: Dict) -> None:
        users = self.load_users()
        email = (user.get("email") or "").strip().lower()
        idx = next((i for i, u in enumerate(users) if (u.get("email") or "").lower() == email), -1)
        if idx >= 0: users[idx].update(user)
        else: users.append(user)
        self.ws_users.clear()
        self.ws_users.update("A1", [USERS_HEADERS] + self._dicts_to_rows(users, USERS_HEADERS))

    # tokens
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
        self._ensure_headers(self.ws_tokens, TOKENS_HEADERS)
        row = [str(token_row.get(k, "")) for k in TOKENS_HEADERS]
        self.ws_tokens.append_row(row, value_input_option="USER_ENTERED")

    def mark_token_used(self, token: str) -> bool:
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

# เลือก backend
BACKEND = st.secrets.get("STORAGE_BACKEND", "local").lower()

# Local JSON storage
class LocalJSONStorage:
    def __init__(self, path: str):
        self.path = path; self._ensure()

    def _ensure(self):
        base_dir = os.path.dirname(self.path)
        if base_dir: os.makedirs(base_dir, exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"pending_reviews": [], "approved_reviews": [], "users": [], "tokens": []},
                          f, ensure_ascii=False, indent=2)
        else:
            with open(self.path, "r", encoding="utf-8") as f:
                try: data = json.load(f)
                except Exception: data = {}
            changed = False
            for k in ("pending_reviews","approved_reviews","users","tokens"):
                if k not in data: data[k] = []; changed = True
            if changed:
                with open(self.path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

    def _read(self) -> Dict:
        with open(self.path, "r", encoding="utf-8") as f: return json.load(f)
    def _write(self, data: Dict) -> None:
        with open(self.path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

    def load_data(self) -> Dict:
        d = self._read()
        for bucket in ("pending_reviews","approved_reviews"):
            for r in d.get(bucket, []):
                try: r["rating"] = int(r.get("rating", 0))
                except Exception: r["rating"] = 0
                try: r["year"] = int(r.get("year", 0)) if r.get("year") not in ("", None) else 0
                except Exception: r["year"] = 0
        return {"pending_reviews": d.get("pending_reviews", []),
                "approved_reviews": d.get("approved_reviews", [])}

    def save_data(self, data: Dict) -> None:
        d = self._read()
        d["pending_reviews"]  = data.get("pending_reviews", [])
        d["approved_reviews"] = data.get("approved_reviews", [])
        self._write(d)

    # users
    def load_users(self) -> List[Dict]: return self._read().get("users", [])
    def upsert_user(self, user: Dict) -> None:
        d = self._read(); users = d.get("users", [])
        email = (user.get("email") or "").strip().lower()
        idx = next((i for i,u in enumerate(users) if u.get("email","").lower()==email), -1)
        if idx >= 0: users[idx].update(user)
        else: users.append(user)
        d["users"] = users; self._write(d)

    # tokens
    def load_tokens(self) -> List[Dict]: return self._read().get("tokens", [])
    def write_tokens(self, tokens: List[Dict]) -> None:
        d = self._read(); d["tokens"] = tokens; self._write(d)
    def add_token(self, token_row: Dict) -> None:
        d = self._read(); d.setdefault("tokens", []).append(token_row); self._write(d)
    def mark_token_used(self, token: str) -> bool:
        d = self._read(); tokens = d.get("tokens", [])
        now = datetime.now().isoformat(timespec="seconds"); found = False
        for t in tokens:
            if t.get("token")==token and not t.get("used_at"):
                t["used_at"] = now; found = True; break
        if found: d["tokens"] = tokens; self._write(d)
        return found

# Storage instance
@st.cache_resource
def get_storage():
    if BACKEND == "gsheets": return GoogleSheetsStorage()
    return LocalJSONStorage(DATA_FILE)

@st.cache_data(ttl=10)
def _cached_load_data(data_version: int):
    return get_storage().load_data()

def load_data() -> Dict:
    ver = st.session_state.get("data_version", 0)
    try:
        data = _cached_load_data(ver); st.session_state["last_data"] = data; return data
    except Exception as e:
        if any(x in str(e).lower() for x in ["quota exceeded","429","rate limit"]):
            st.warning("เกินโควต้าอ่าน Google Sheets ชั่วคราว — แสดงข้อมูลล่าสุดจากแคช")
            return st.session_state.get("last_data", {"approved_reviews": [], "pending_reviews": []})
        raise

def save_data(data: Dict) -> None:
    get_storage().save_data(data)
    st.session_state["data_version"] = st.session_state.get("data_version", 0) + 1
    try: _cached_load_data.clear()
    except Exception: pass

# -----------------------------
# Authentication utilities
# -----------------------------
import re, hashlib, secrets
ALLOWED_EMAIL_DOMAIN = st.secrets.get("ALLOWED_EMAIL_DOMAIN", "student.mahidol.edu")
APP_BASE_URL = st.secrets.get("APP_BASE_URL", "")

USERS_HEADERS = ["email", "password_salt", "password_hash", "role", "display", "is_verified", "created_at"]
TOKENS_HEADERS = ["token", "email", "type", "expires_at", "used", "created_at"]

# ========= Star histogram helpers =========
from typing import Tuple


def find_user_by_email(email: str) -> Optional[Dict]:
    users = load_users()
    for u in users:
        if u.get("email", "").lower() == email.lower(): return u
    return None

def upsert_user(user: Dict) -> None:
    users = load_users(); found = False
    for i,u in enumerate(users):
        if u.get("email","").lower()==user.get("email","").lower():
            users[i] = user; found = True; break
    if not found: users.append(user)
    save_users(users)

def load_users() -> List[Dict]:
    storage = get_storage()
    return storage.load_users() if hasattr(storage,'load_users') else []

def save_users(users: List[Dict]) -> None:
    storage = get_storage()
    if hasattr(storage,'upsert_user'):
        if isinstance(storage, LocalJSONStorage):
            d = storage._read(); d["users"] = users; storage._write(d)
        else:
            for u in users: storage.upsert_user(u)

def load_tokens() -> List[Dict]:
    storage = get_storage()
    return storage.load_tokens() if hasattr(storage,'load_tokens') else []

def save_tokens(tokens: List[Dict]) -> None:
    storage = get_storage()
    if hasattr(storage,'write_tokens'): storage.write_tokens(tokens)

def generate_token() -> str: return secrets.token_urlsafe(24)
def make_salt() -> str: return secrets.token_hex(16)
def hash_password(pw: str, salt: str) -> str: return hashlib.sha256((salt+pw).encode("utf-8")).hexdigest()
def verify_password(pw: str, salt: str, pw_hash: str) -> bool:
    import secrets as _secrets
    return _secrets.compare_digest(hash_password(pw, salt), pw_hash)

def add_token(email: str, type_: str, expires_at: str) -> Dict:
    tokens = load_tokens()
    tok = {"token": generate_token(), "email": email, "type": type_, "expires_at": expires_at, "used": False,
           "created_at": datetime.now().isoformat(timespec="seconds")}
    tokens.append(tok); save_tokens(tokens); return tok

def consume_token(token: str, type_: str) -> Optional[Dict]:
    tokens = load_tokens()
    for t in tokens:
        if t.get("token")==token and t.get("type")==type_ and not t.get("used"):
            t["used"] = True; save_tokens(tokens); return t
    return None

def get_token_record(token: str, type_: str) -> Optional[Dict]:
    tokens = load_tokens()
    for t in tokens:
        if t.get("token")==token and t.get("type")==type_: return t
    return None

def make_link_with_param(param_key: str, token: str) -> str:
    if APP_BASE_URL:
        sep = '&' if '?' in APP_BASE_URL else '?'
        return f"{APP_BASE_URL}{sep}{param_key}={token}"
    return f"?{param_key}={token}"

def get_query_params() -> Dict[str, List[str]]:
    try: return dict(st.query_params)
    except Exception: return st.experimental_get_query_params()

# Email helper
def send_email(to: str, subject: str, body: str) -> bool:
    host = st.secrets.get("SMTP_HOST"); port = st.secrets.get("SMTP_PORT")
    user = st.secrets.get("SMTP_USER"); pwd = st.secrets.get("SMTP_PASS")
    sender = st.secrets.get("SMTP_SENDER") or user
    sender_name = st.secrets.get("SMTP_SENDER_NAME", "MU Course Reviews")
    use_ssl = str(st.secrets.get("SMTP_SSL","false")).lower() in ("1","true","yes")

    missing = [k for k,v in {"SMTP_HOST":host,"SMTP_PORT":port,"SMTP_USER":user,"SMTP_PASS":pwd,"SMTP_SENDER":sender}.items() if not v]
    if missing:
        st.error("SMTP secrets ไม่ครบ: " + ", ".join(missing)); return False
    port = int(port)
    msg = EmailMessage(); msg["Subject"]=subject; msg["From"]=f"{sender_name} <{sender}>"; msg["To"]=to
    reply_to = st.secrets.get("REPLY_TO");
    if reply_to: msg["Reply-To"]=reply_to
    msg.set_content(body)
    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=20) as s:
                s.login(user, pwd); s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(user, pwd); s.send_message(msg)
        return True
    except Exception as e:
        st.error(f"SMTP error: {e}"); return False

# -----------------------------
# UI helpers
# -----------------------------
def handle_magic_links():
    q = get_query_params()
    verify_token = q.get("verify") if isinstance(q.get("verify"), str) else (q.get("verify",[None])[0] if q.get("verify") else None)
    if verify_token:
        t = consume_token(verify_token, "verify")
        if t:
            u = find_user_by_email(t.get("email",""))
            if u: u["is_verified"]=True; upsert_user(u); st.success("ยืนยันอีเมลสำเร็จ! กรุณาเข้าสู่ระบบด้วยอีเมลนักศึกษา")
        else:
            st.warning("ลิงก์ยืนยันหมดอายุหรือถูกใช้ไปแล้ว")

def star_str(n: int) -> str:
    n = int(n); return "★"*n + "☆"*(5-n)

# =======================
# Star-rating chart utils
# =======================

def build_star_hist(reviews: List[Dict]):
    """คืนค่า (hist, total, avg)
       hist: list ของ (ดาว, จำนวน) โดยเรียง 5→1
       total: จำนวนรีวิวทั้งหมด
       avg: ค่าเฉลี่ย 1–5
    """
    c = Counter()
    for r in reviews:
        try:
            k = int(r.get("rating", 0))
        except Exception:
            k = 0
        if 1 <= k <= 5:
            c[k] += 1
    hist = [(s, c.get(s, 0)) for s in range(5, 1-1, -1)]
    total = sum(cnt for _, cnt in hist)
    avg = (sum(s * c.get(s, 0) for s in range(1, 6)) / total) if total else 0.0
    return hist, total, avg


def render_star_histogram(hist, total: int, avg: float, title: str = ""):
    """
    วาดกราฟแท่งแนวนอนแบบ Play Store/IMDb (Altair)
    - แกน Y: 5★ → 1★
    - แกน X: เปอร์เซ็นต์
    - แสดง tooltip และตัวเลขเปอร์เซ็นต์ตรงแท่ง
    """
    df = pd.DataFrame({
        "stars": [s for s, _ in hist],           # 5..1
        "count": [cnt for _, cnt in hist],
    })
    if total == 0:
        st.info("ยังไม่มีรีวิวเพียงพอสำหรับแสดงกราฟ")
        return
    df["percent"] = (df["count"] / total) * 100.0

    base = alt.Chart(df).properties(title=title)
    bars = base.mark_bar().encode(
        y=alt.Y("stars:O", sort="descending", title="คะแนน"),
        x=alt.X("percent:Q", title="เปอร์เซ็นต์"),
        tooltip=[
            alt.Tooltip("stars:O", title="ดาว"),
            alt.Tooltip("count:Q", title="จำนวนรีวิว"),
            alt.Tooltip("percent:Q", title="เปอร์เซ็นต์", format=".1f")
        ]
    )
    texts = base.mark_text(align="left", dx=4).encode(
        y=alt.Y("stars:O", sort="descending"),
        x=alt.X("percent:Q"),
        text=alt.Text("percent:Q", format=".1f")
    )

    st.markdown(f"**ค่าเฉลี่ย:** {avg:.2f} / 5  •  **ทั้งหมด:** {total} รีวิว")
    st.altair_chart(bars + texts, use_container_width=True)



# ========= Star histogram helpers (Play Store/IMDb style) =========
def build_star_hist_df(reviews: List[Dict]):
    """
    แปลงรายการรีวิว -> DataFrame ฮิสโตแกรมดาว + รวม + ค่าเฉลี่ย
    คืนค่า: (df[ดาว,จำนวน] เรียง 5..1, total, avg)
    """
    hist = {i: 0 for i in range(1, 6)}
    for r in reviews:
        try:
            rating = int(r.get("rating", 0))
        except Exception:
            rating = 0
        if rating in hist:
            hist[rating] += 1

    total = sum(hist.values())
    avg = (sum(k * v for k, v in hist.items()) / total) if total else 0.0
    df = pd.DataFrame({
        "ดาว": [5, 4, 3, 2, 1],
        "จำนวน": [hist[i] for i in (5, 4, 3, 2, 1)]
    })
    return df, total, avg


def render_star_histogram_altair(reviews: List[Dict], title: str):
    """
    วาดกราฟแท่งแนวนอน 5→1 ดาว + แสดงค่าเฉลี่ย/จำนวนรีวิว
    """
    df, total, avg = build_star_hist_df(reviews)

    st.markdown(f"#### {title}")
    left, right = st.columns([1, 2])

    with left:
        st.metric("คะแนนเฉลี่ย", f"{avg:.2f} / 5")
        st.caption(f"จำนวนรีวิวทั้งหมด: {total}")
        st.markdown(f"<span class='star'>{star_str(int(round(avg)))}</span>", unsafe_allow_html=True)

    with right:
        chart = (
            alt.Chart(df)
               .mark_bar()
               .encode(
                   y=alt.Y("ดาว:O", sort="descending", title="จำนวนดาว"),
                   x=alt.X("จำนวน:Q", title="จำนวนรีวิว"),
                   tooltip=["ดาว", "จำนวน"]
               )
               .properties(height=160)
        )
        st.altair_chart(chart, use_container_width=True)


def sidebar_user_box():
    auth = st.session_state.get("auth")
    if not auth: return
    with st.sidebar:
        st.markdown(f"**ผู้ใช้:** {auth['display']}")
        st.markdown(f"**บทบาท:** `{auth['role']}`")
        if st.button("ออกจากระบบ", use_container_width=True):
            st.session_state.pop("auth", None); st.rerun()

def do_login_form():
    st.markdown("### เข้าสู่ระบบ / ลงทะเบียน")
    try: q = get_query_params()
    except Exception:
        try: q = st.query_params
        except Exception: q = {}
    reset_token = q.get("reset", [None])[0] if isinstance(q.get("reset"), list) else q.get("reset")

    default_mode = "Forgot password" if reset_token else "Login"
    if "auth_mode" not in st.session_state: st.session_state["auth_mode"] = default_mode

    mode = st.radio(
        "",
        ["Login", "Sign up", "Forgot password"],
        index=["Login","Sign up","Forgot password"].index(st.session_state["auth_mode"]),
        horizontal=True, key="auth_mode", label_visibility="collapsed"
    )

    if mode == "Login":
        email_or_admin = st.text_input(f"อีเมลนักศึกษา (@{ALLOWED_EMAIL_DOMAIN})", key="auth_login_email")
        pw = st.text_input("รหัสผ่าน", type="password", key="auth_login_pw")
        if st.button("เข้าสู่ระบบ", type="primary", key="auth_login_btn"):
            if email_or_admin == "admin":
                user = USERS.get("admin")
                if user and user.get("password")==pw:
                    st.session_state["auth"] = {"email":"admin","username":"admin","role":"admin","display":user.get("display","Administrator")}
                    st.success("เข้าสู่ระบบสำเร็จ (admin)"); st.rerun()
                else:
                    st.error("admin หรือรหัสผ่านไม่ถูกต้อง")
            else:
                if not email_or_admin.lower().endswith("@"+ALLOWED_EMAIL_DOMAIN):
                    st.error(f"อีเมลต้องลงท้ายด้วย @{ALLOWED_EMAIL_DOMAIN}")
                else:
                    u = find_user_by_email(email_or_admin)
                    if not u:
                        st.error("ไม่พบบัญชีผู้ใช้ — โปรดลงทะเบียนก่อน")
                    elif not u.get("is_verified"):
                        st.warning("บัญชียังไม่ยืนยันอีเมล — โปรดตรวจกล่องจดหมายของคุณ")
                        if st.button("ส่งอีเมลยืนยันอีกครั้ง", key="auth_login_resend"):
                            tok = add_token(u["email"], "verify", "")
                            link = make_link_with_param("verify", tok["token"])
                            body = f"สวัสดี {u.get('display', u['email'])}\n\nกดยืนยันที่ลิงก์นี้:\n{link}\n\n— MU Course Reviews"
                            ok = send_email(u["email"], "ยืนยันอีเมลสำหรับลงทะเบียน (ส่งใหม่)", body)
                            if ok: st.success("ส่งอีเมลยืนยันอีกครั้งแล้ว โปรดตรวจกล่องจดหมาย")
                            else:
                                st.warning("ส่งอีเมลไม่สำเร็จ — ใช้ลิงก์ชั่วคราว")
                                st.markdown(f"[คลิกเพื่อยืนยันบัญชี]({link})"); st.code(link)
                    else:
                        if verify_password(pw, u.get("password_salt",""), u.get("password_hash","")):
                            st.session_state["auth"] = {"email":u["email"],"username":u["email"],
                                                        "role":u.get("role","student"),
                                                        "display":u.get("display",u["email"])}
                            st.success("เข้าสู่ระบบสำเร็จ"); st.rerun()
                        else:
                            st.error("รหัสผ่านไม่ถูกต้อง")

    elif mode == "Sign up":
        student_email = st.text_input(f"อีเมลนักศึกษา (@{ALLOWED_EMAIL_DOMAIN})", key="auth_signup_email")
        pw1 = st.text_input("รหัสผ่าน (อย่างน้อย 8 ตัวอักษร)", type="password", key="auth_signup_pw1",
                            help=f"รหัสผ่านต้องมีอย่างน้อย {MIN_PASSWORD_LEN} ตัวอักษร")
        pw2 = st.text_input("ยืนยันรหัสผ่าน", type="password", key="auth_signup_pw2")
        display = st.text_input("ชื่อที่แสดง (ไม่บังคับ)", key="auth_signup_display")
        if st.button("ลงทะเบียน", key="auth_signup_btn"):
            if not student_email or not student_email.lower().endswith("@"+ALLOWED_EMAIL_DOMAIN):
                st.error(f"ต้องใช้อีเมล @{ALLOWED_EMAIL_DOMAIN} เท่านั้น")
            elif not pw1 or len(pw1) < MIN_PASSWORD_LEN:
                st.error(f"รหัสผ่านต้องยาวอย่างน้อย {MIN_PASSWORD_LEN} ตัวอักษร")
            elif pw1 != pw2:
                st.error("รหัสผ่านยืนยันไม่ตรงกัน")
            else:
                existing = find_user_by_email(student_email)
                salt = make_salt(); pw_hash = hash_password(pw1, salt)
                if existing and existing.get("is_verified"):
                    st.error("อีเมลนี้มีผู้ใช้งานแล้ว")
                elif existing and not existing.get("is_verified"):
                    existing["password_salt"]=salt; existing["password_hash"]=pw_hash
                    if display: existing["display"]=display
                    upsert_user(existing)
                    tok = add_token(student_email, "verify", ""); link = make_link_with_param("verify", tok["token"])
                    body = dedent(f"""สวัสดี {existing.get('display', student_email)},

เราได้รับคำขอลงทะเบียนสำหรับอีเมลนี้ ซึ่งยังไม่ได้ยืนยัน
กรุณาคลิกลิงก์ด้านล่างเพื่อยืนยันอีเมล:
{link}

หากคุณไม่ได้ส่งคำขอนี้ โปรดละเว้นอีเมลฉบับนี้
— MU Course Reviews""")
                    ok = send_email(student_email, "ยืนยันอีเมลสำหรับลงทะเบียน (ส่งใหม่)", body)
                    if ok: st.success("บัญชีนี้ยังไม่ยืนยัน — เราได้ส่งอีเมลยืนยันใหม่ให้แล้ว โปรดตรวจกล่องจดหมาย")
                    else:
                        st.warning("ส่งอีเมลไม่สำเร็จ — ใช้ลิงก์ยืนยันชั่วคราวด้านล่างได้เลย")
                        st.markdown(f"[คลิกเพื่อยืนยันบัญชี]({link})"); st.code(link)
                else:
                    user = {
                        "email": student_email,
                        "password_salt": salt, "password_hash": pw_hash,
                        "role": "student", "display": (display or student_email),
                        "is_verified": False, "created_at": datetime.now().isoformat(timespec="seconds"),
                    }
                    upsert_user(user)
                    tok = add_token(student_email, "verify", ""); link = make_link_with_param("verify", tok["token"])
                    body = dedent(f"""สวัสดี {display or student_email},

กรุณาคลิกลิงก์ด้านล่างเพื่อยืนยันอีเมลสำหรับเข้าใช้งานระบบรีวิวรายวิชา:
{link}

หากคุณไม่ได้ส่งคำขอนี้ โปรดละเว้นอีเมลฉบับนี้
— MU Course Reviews""")
                    ok = send_email(student_email, "ยืนยันอีเมลสำหรับลงทะเบียน", body)
                    if ok: st.success("สมัครเสร็จแล้ว! โปรดตรวจอีเมลเพื่อกดยืนยันก่อนเข้าสู่ระบบ")
                    else:
                        st.warning("ส่งอีเมลไม่สำเร็จ — ใช้ลิงก์ยืนยันชั่วคราวด้านล่างได้เลย")
                        st.markdown(f"[คลิกเพื่อยืนยันบัญชี]({link})"); st.code(link)

    else:
        reset_token = q.get("reset", [None])[0] if isinstance(q.get("reset"), list) else q.get("reset")
        if reset_token:
            st.info("ตั้งรหัสผ่านใหม่สำหรับโทเคนรีเซ็ต")
            npw1 = st.text_input("รหัสผ่านใหม่ (อย่างน้อย 8 ตัวอักษร)", type="password", key="auth_reset_pw1")
            st.caption(f"รหัสผ่านต้องยาวอย่างน้อย {MIN_PASSWORD_LEN} ตัวอักษร")
            npw2 = st.text_input("ยืนยันรหัสผ่านใหม่", type="password", key="auth_reset_pw2")
            if st.button("ยืนยันการตั้งรหัสผ่านใหม่", key="auth_reset_submit"):
                if not npw1 or len(npw1) < MIN_PASSWORD_LEN: st.error(f"รหัสผ่านต้องยาวอย่างน้อย {MIN_PASSWORD_LEN} ตัวอักษร")
                elif npw1 != npw2: st.error("รหัสผ่านยืนยันไม่ตรงกัน")
                else:
                    tok = get_token_record(reset_token, "reset")
                    if not tok or tok.get("used"): st.error("โทเคนไม่ถูกต้องหรือถูกใช้ไปแล้ว")
                    else:
                        u = find_user_by_email(tok["email"])
                        if not u: st.error("ไม่พบบัญชีผู้ใช้ที่เกี่ยวข้องกับโทเคน")
                        else:
                            salt = make_salt(); pw_hash = hash_password(npw1, salt)
                            u["password_salt"]=salt; u["password_hash"]=pw_hash; upsert_user(u)
                            consume_token(reset_token, "reset")
                            st.success("ตั้งรหัสผ่านใหม่สำเร็จ! โปรดเข้าสู่ระบบอีกครั้ง")
                            try: st.query_params.clear()
                            except Exception: st.experimental_set_query_params()
                            st.rerun()
        else:
            reset_email = st.text_input(f"อีเมลนักศึกษา (@{ALLOWED_EMAIL_DOMAIN})", key="auth_reset_email")
            if st.button("ส่งลิงก์รีเซ็ตรหัสผ่าน", key="auth_reset_btn"):
                if not reset_email or not reset_email.lower().endswith("@"+ALLOWED_EMAIL_DOMAIN):
                    st.error(f"ต้องใช้อีเมล @{ALLOWED_EMAIL_DOMAIN} เท่านั้น")
                elif not find_user_by_email(reset_email):
                    st.error("ไม่พบบัญชีผู้ใช้สำหรับอีเมลนี้")
                else:
                    tok = add_token(reset_email, "reset", ""); link = make_link_with_param("reset", tok["token"])
                    body = dedent(f"""สวัสดี {reset_email},

ตั้งรหัสผ่านใหม่ได้ที่ลิงก์ต่อไปนี้:
{link}

หากคุณไม่ได้ร้องขอ โปรดละเว้นอีเมลฉบับนี้
— MU Course Reviews""")
                    ok = send_email(reset_email, "ลิงก์รีเซ็ตรหัสผ่าน — MU Course Reviews", body)
                    if ok: st.success("ส่งลิงก์รีเซ็ตไปที่อีเมลแล้ว โปรดตรวจกล่องจดหมาย")
                    else:
                        st.warning("ส่งอีเมลไม่สำเร็จ — ใช้ลิงก์ชั่วคราว")
                        st.markdown(f"[คลิกเพื่อรีเซ็ตรหัสผ่าน]({link})"); st.code(link)

# -------------
# Filters (shared)
# -------------
def admin_type_options(items: List[Dict]) -> List[str]:
    types = sorted({r.get("course_type") for r in items if r.get("course_type")})
    return ["ทั้งหมด"] + types

def admin_faculty_map(items: List[Dict], sel_type: Optional[str] = None) -> Dict[str, str]:
    rows = [r for r in items if r.get("faculty") and (not sel_type or r.get("course_type")==sel_type)]
    m: Dict[str,str] = {}
    for r in rows:
        code = r.get("faculty"); name = r.get("faculty_name") or code
        if code not in m: m[code] = name
    return m

def admin_course_options(items: List[Dict], sel_type: Optional[str], sel_fac: Optional[str]) -> List[str]:
    rows = [r for r in items if r.get("course_code")]
    if sel_type: rows = [r for r in rows if r.get("course_type")==sel_type]
    if sel_fac: rows = [r for r in rows if r.get("faculty")==sel_fac]
    names = sorted({f"{r['course_code']} {r.get('course_name','')}".strip() for r in rows})
    return ["ทั้งหมด"] + names

def admin_apply_filters(items: List[Dict], sel_type: Optional[str], sel_fac: Optional[str],
                        course_label: str, q: str, min_rating: int) -> List[Dict]:
    out = list(items)
    if sel_type: out = [r for r in out if r.get("course_type")==sel_type]
    if sel_fac: out = [r for r in out if r.get("faculty")==sel_fac]
    if course_label and course_label != "ทั้งหมด":
        code = course_label.split(" ")[0]
        out = [r for r in out if str(r.get("course_code",""))==code]
    if q:
        ql = q.lower().strip()
        out = [r for r in out if ql in (r.get("text") or "").lower() or ql in (r.get("course_name") or "").lower()]
    if min_rating and min_rating > 1:
        out = [r for r in out if int(r.get("rating", 0)) >= min_rating]
    return out

def admin_sort_items(items: List[Dict], sort_key: str) -> List[Dict]:
    if sort_key == "วันที่ (ใหม่→เก่า)": return sorted(items, key=lambda x: x.get("created_at",""), reverse=True)
    if sort_key == "วันที่ (เก่า→ใหม่)": return sorted(items, key=lambda x: x.get("created_at",""))
    if sort_key == "คะแนน (สูง→ต่ำ)": return sorted(items, key=lambda x: int(x.get("rating",0)), reverse=True)
    if sort_key == "คะแนน (ต่ำ→สูง)": return sorted(items, key=lambda x: int(x.get("rating",0)))
    return items

# -------- Rendering helpers
@lru_cache(maxsize=512)
def _email_to_display(email: str) -> str:
    u = find_user_by_email(email)
    return (u.get("display") if u and u.get("display") else email)

def review_author(row: Dict) -> str:
    if row.get("author_display"): return row["author_display"]
    name = (row.get("author") or "").strip()
    if "@" in name: return _email_to_display(name)
    if row.get("author_email"): return _email_to_display(row["author_email"])
    return name or "ผู้ใช้"

def render_grouped(items: List[Dict], data: Optional[Dict] = None, pending_mode: bool = False):
    """Admin-style (โชว์ผู้เขียน)"""
    if not items: st.info("ไม่พบรายการตามตัวกรอง"); return
    selected_ids = st.session_state.setdefault("selected_ids", set())
    groups: Dict[str, Dict[str, Dict[str, List[Dict]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in items:
        ctype = r.get("course_type","?")
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
                                author = review_author(r)
                                st.markdown(
                                    f"**{r.get('course_code','')} {r.get('course_name','')}**  \n"
                                    f"ให้คะแนน: {star_str(int(r.get('rating', 0)))}  \n"
                                    f"โดย `{author}` • วันที่ {r.get('created_at', '')}"
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
                                            r["status"]="approved"
                                            data["approved_reviews"].append(r)
                                            data["pending_reviews"].remove(r)
                                            save_data(data); st.success("อนุมัติแล้ว"); st.rerun()
                                    with a2:
                                        if st.button("ปฏิเสธ", key=f"re_{r['id']}"):
                                            data["pending_reviews"].remove(r)
                                            save_data(data); st.warning("ปฏิเสธแล้ว"); st.rerun()

def render_grouped_public(items: List[Dict]):
    """มุมมองนักศึกษา (ไม่โชว์ผู้เขียน)"""
    if not items: st.info("ไม่พบรายการตามตัวกรอง"); return
    groups: Dict[str, Dict[str, Dict[str, List[Dict]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in items:
        ctype = r.get("course_type","?")
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
                            st.markdown(
                                f"**{r.get('course_code','')} {r.get('course_name','')}**  \n"
                                f"ให้คะแนน: {star_str(int(r.get('rating', 0)))}  \n"
                                f"<span class='muted'>วันที่ {r.get('created_at','')}</span>",
                                unsafe_allow_html=True,
                            )
                            if txt := r.get("text"):
                                st.markdown("—"); st.write(txt)

# -------------
# Stats helpers
# -------------
def star_histogram(reviews: List[Dict]) -> pd.DataFrame:
    """DataFrame index 5..1 / col 'จำนวน' ใช้ทำ bar chart"""
    cnt = Counter(int(r.get("rating",0)) for r in reviews if r.get("status")=="approved")
    data = {"ดาว": [5,4,3,2,1], "จำนวน": [cnt.get(5,0), cnt.get(4,0), cnt.get(3,0), cnt.get(2,0), cnt.get(1,0)]}
    return pd.DataFrame(data).set_index("ดาว")

def build_summary_rows(approved: List[Dict]) -> List[Dict]:
    agg: Dict[Tuple[str,str,str,str,str], Dict[str,float]] = {}
    for r in approved:
        if r.get("status") != "approved": continue
        key = (r.get("course_type",""), r.get("faculty","-"), r.get("faculty_name","-"),
               r.get("course_code",""), r.get("course_name","-"))
        obj = agg.setdefault(key, {"sum":0.0, "count":0.0})
        obj["sum"] += float(r.get("rating",0)); obj["count"] += 1
    rows: List[Dict] = []
    for (ctype, code, name, ccode, cname), v in agg.items():
        avg = v["sum"]/v["count"] if v["count"] else 0.0
        rows.append({
            "ประเภท": ctype,
            "คณะ": f"{code} - {name}",
            "รหัสวิชา": ccode,
            "รายวิชา": cname,
            "ค่าเฉลี่ย": round(avg,2),
            "ดาว": star_str(int(round(avg))),
            "จำนวนรีวิว": int(v["count"]),
            "เฉลี่ย/5": avg/5.0,
        })
    rows.sort(key=lambda r: (r["ประเภท"], r["คณะ"], r["รหัสวิชา"]))
    return rows

# -----------------------------
# Student page
# -----------------------------
def page_student(data: Dict):
    approved = data["approved_reviews"]
    pending = data["pending_reviews"]

    t_submit, t_browse = st.tabs(["📝 ส่งรีวิวรายวิชา", "🔎 ดูรีวิวที่อนุมัติแล้ว"])

    # Submit
    with t_submit:
        st.subheader("เลือกประเภท / คณะ / รายวิชา")

        # ประเภท (dynamic จากชีต)
        type_keys = list(COURSE_TYPES.keys())
        if not type_keys:
            st.error("ยังไม่มีหมวดรายวิชาใน Google Sheet"); st.stop()
        type_ix = st.selectbox("ประเภทของรายวิชา", options=list(range(len(type_keys))),
                               format_func=lambda i: COURSE_TYPES[type_keys[i]], key="stu_type_ix")
        sel_type = type_keys[type_ix]

        # คณะ (ตามประเภท)
        fac_map = list_faculties_by_type(sel_type)
        fac_codes = list(fac_map.keys())
        if not fac_codes:
            st.info("หมวดนี้ยังไม่มีรายวิชาในคณะใดเลย"); st.stop()
        fac_ix = st.selectbox("คณะที่เปิดสอน", options=list(range(len(fac_codes))),
                              format_func=lambda i: f"{fac_codes[i]} - {fac_map[fac_codes[i]]}", key="stu_fac_ix")
        fac_code = fac_codes[fac_ix]; fac_name = fac_map[fac_code]

        # รายวิชา
        courses = list_courses(sel_type, fac_code)
        if not courses:
            st.info("คณะนี้ยังไม่มีรายวิชาในคาแทล็อก"); st.stop()
        course_ix = st.selectbox("เลือกรายวิชา", options=list(range(len(courses))),
                                 format_func=lambda i: f"{courses[i]['code']} {courses[i]['name']}", key="stu_course_ix")
        course = courses[course_ix]

        # กล่องข้อมูลวิชา: credit → prereq → grading → updated_at
        meta_bits = []
        if course.get("credit"): meta_bits.append(f"หน่วยกิต: {course['credit']}")
        if course.get("prereq_en"): meta_bits.append(f"เงื่อนไขรายวิชา: {course['prereq_en']}")
        if course.get("grading"):
            label = {"ABC": "เกรด A–F", "OSU": "O/S/U"}.get(course["grading"], course["grading"])
            meta_bits.append(f"การตัดเกรด: {course['grading']} ({label})")
        if course.get("updated_at"): meta_bits.append(f"อัปเดตล่าสุด: {course['updated_at']}")

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
          {f'<div style="margin-bottom:.6rem;">{course.get("desc_th","")}</div>' if course.get('desc_th') else ''}

          {f'<div style="margin-bottom:.35rem;"><b>คำอธิบายรายวิชา (ภาษาอังกฤษ)</b></div>' if course.get('desc_en') else ''}
          {f'<div class="muted">{course.get("desc_en","")}</div>' if course.get('desc_en') else ''}
        </div>
        """
        st.markdown(box_html, unsafe_allow_html=True)

        st.markdown("---")
        col_rate, _ = st.columns([1,2])
        with col_rate:
            rating = st.radio("ให้คะแนน (1-5 ดาว)", options=[1,2,3,4,5], horizontal=True, index=4)
        st.markdown(f"**ตัวอย่างดาว:** <span class='star'>{star_str(rating)}</span>", unsafe_allow_html=True)
        review_text = st.text_area("เขียนรีวิวเพิ่มเติม (ไม่บังคับ)", max_chars=1200, height=150,
                                   placeholder="เล่าประสบการณ์ เนื้อหา งาน/การบ้าน ความยาก-ง่าย คำแนะนำ ฯลฯ")

        if st.button("ส่งรีวิว (เข้าคิวรอตรวจ)", type="primary", use_container_width=True):
            auth = st.session_state.get("auth", {})
            author_display = auth.get("display") or auth.get("email") or auth.get("username","anonymous")
            new_r = {
                "id": str(uuid.uuid4()),
                "course_type": sel_type,
                "faculty": fac_code, "faculty_name": fac_name,
                "department": "", "department_name": "", "year": "",
                "course_code": course["code"], "course_name": course["name"],
                "rating": int(rating), "text": (review_text or "").strip(),
                "author": author_display,  # เก็บชื่อที่แสดงไว้ตั้งแต่ตอนบันทึก
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "status": "pending",
            }
            pending.append(new_r); save_data(data)
            st.success("ส่งรีวิวเรียบร้อย! รอผู้ดูแลอนุมัติ"); st.balloons()

    # Browse (public) — ซ่อนผู้เขียน
    with t_browse:
        st.subheader("ดูรีวิวที่อนุมัติแล้ว (มุมมองผู้ใช้)")

        approved_only = [r for r in approved if r.get("status") == "approved"]
        col1, col2, col3, col4 = st.columns([1,1,1,1.2])

        with col1:
            t_opts = admin_type_options(approved_only)
            s_type = st.selectbox("ประเภท", t_opts, index=0, key="stu_a_type",
                                  format_func=lambda v: "ทั้งหมด" if v=="ทั้งหมด" else v)
            sel_type2 = None if s_type == "ทั้งหมด" else s_type

        with col2:
            fac_map2 = admin_faculty_map(approved_only, sel_type2)
            f_opts2 = ["ทั้งหมด"] + list(sorted(fac_map2.keys()))
            s_fac = st.selectbox("คณะ", f_opts2, index=0, key="stu_a_fac",
                                 format_func=lambda code: "ทั้งหมด" if code=="ทั้งหมด" else f"{code} - {fac_map2.get(code, code)}")
            sel_fac2 = None if s_fac == "ทั้งหมด" else s_fac

        with col3:
            c_opts2 = admin_course_options(approved_only, sel_type2, sel_fac2)
            s_course = st.selectbox("รายวิชา", c_opts2, index=0, key="stu_a_course")

        with col4:
            s_q = st.text_input("ค้นหาในข้อความรีวิว/ชื่อวิชา", key="stu_a_q")

        s_minr = st.slider("คะแนนขั้นต่ำ", 1, 5, 1, step=1, key="stu_a_minr")
        s_sort = st.selectbox("จัดเรียงโดย",
                              ["วันที่ (ใหม่→เก่า)","วันที่ (เก่า→ใหม่)","คะแนน (สูง→ต่ำ)","คะแนน (ต่ำ→สูง)"],
                              index=0, key="stu_a_sort")

        sf = admin_apply_filters(approved_only, sel_type2, sel_fac2, s_course, s_q, s_minr)
        sf = admin_sort_items(sf, s_sort)

        # ----- วางบล็อกกราฟตรงนี้ -----
        # ----- แสดงกราฟสรุปดาว -----
        # ถ้าเลือกวิชาเฉพาะ จะสรุปเฉพาะวิชานั้น
        # ถ้า "ทั้งหมด" จะสรุปภาพรวมตามตัวกรองปัจจุบัน
        if s_course != "ทั้งหมด":
            code = s_course.split(" ")[0]
            dataset = [r for r in sf if r.get("course_code") == code]
            title = f"สรุปแนวโน้มรีวิว — {s_course}"
        else:
            dataset = list(sf)
            title = "สรุปแนวโน้มรีวิว — ตามตัวกรองปัจจุบัน"

        hist, total, avg = build_star_hist(dataset)
        if total > 0:
            render_star_histogram(hist, total, avg, title=title)
        else:
            st.info("ยังไม่มีรีวิวสำหรับแสดงกราฟในเงื่อนไขนี้")

        # แล้วค่อยแสดงการ์ด
        render_grouped_public(sf)

# -----------------------------
# Summary table (Admin)
# -----------------------------
def build_summary_rows(approved: List[Dict]) -> List[Dict]:
    agg: Dict[Tuple[str,str,str,str,str], Dict[str,float]] = {}
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
            "ประเภท": ctype,
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

    c1,c2,c3 = st.columns(3)
    with c1:
        types = ["ทั้งหมด"] + sorted({r["ประเภท"] for r in all_rows})
        ftype = st.selectbox("ประเภท", types, index=0, key="sum_type")
    with c2:
        facs = ["ทั้งหมด"] + sorted({r["คณะ"] for r in all_rows if ftype=="ทั้งหมด" or r["ประเภท"]==ftype})
        ffac = st.selectbox("คณะ", facs, index=0, key="sum_fac2")
    with c3:
        courses = ["ทั้งหมด"] + sorted({r["รหัสวิชา"] for r in all_rows
                                        if (ftype=="ทั้งหมด" or r["ประเภท"]==ftype)
                                           and (ffac=="ทั้งหมด" or r["คณะ"]==ffac)})
        fc = st.selectbox("รายวิชา", courses, index=0, key="sum_course2")

    rows = [r for r in all_rows
            if (ftype=="ทั้งหมด" or r["ประเภท"]==ftype)
            and (ffac=="ทั้งหมด" or r["คณะ"]==ffac)
            and (fc=="ทั้งหมด" or r["รหัสวิชา"]==fc)]

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
def bulk_bar(filtered_ids: List[str], data: Dict):
    pending = data["pending_reviews"]
    selected_ids = st.session_state.get("selected_ids", set())
    c1,c2,c3,c4 = st.columns([1,1,1,2])
    with c1:
        if st.button("เลือกทั้งหมด(ตามตัวกรอง)"):
            st.session_state["selected_ids"] = set(filtered_ids); st.rerun()
    with c2:
        if st.button("ล้างการเลือก"):
            st.session_state["selected_ids"] = set(); st.rerun()
    with c3:
        if st.button("✅ อนุมัติที่เลือก") and selected_ids:
            move, keep = [], []
            ids = set(selected_ids)
            for r in pending: (move if r["id"] in ids else keep).append(r)
            for r in move: r["status"]="approved"
            data["approved_reviews"].extend(move); data["pending_reviews"]=keep
            save_data(data); st.success(f"อนุมัติ {len(move)} รายการ"); st.session_state["selected_ids"]=set(); st.rerun()
    with c4:
        if st.button("🗑️ ปฏิเสธที่เลือก") and selected_ids:
            keep = [r for r in pending if r["id"] not in selected_ids]
            removed = len(pending) - len(keep)
            data["pending_reviews"] = keep; save_data(data)
            st.warning(f"ปฏิเสธ {removed} รายการ"); st.session_state["selected_ids"]=set(); st.rerun()

def page_admin(data: Dict):
    st.markdown("### หลังบ้าน (Admin)")
    pending = data.get("pending_reviews", [])
    approved = [r for r in data.get("approved_reviews", []) if r.get("status") == "approved"]

    t_pend, t_appr, t_sum = st.tabs(["🕒 คิวรออนุมัติ", "✅ รีวิวที่อนุมัติแล้ว", "📊 สรุปตาราง"])

    with t_pend:
        st.subheader("กรองคิวรีวิว")
        col1,col2,col3,col4 = st.columns([1,1,1,1.2])
        with col1:
            t_opts = admin_type_options(pending)
            p_type = st.selectbox("ประเภท", t_opts, index=0, key="stu_a_type",
                      format_func=lambda v: "ทั้งหมด" if v=="ทั้งหมด" else COURSE_TYPES.get(v, v))
            sel_type = None if p_type=="ทั้งหมด" else p_type
        with col2:
            fac_map = admin_faculty_map(pending, sel_type)
            f_opts = ["ทั้งหมด"] + list(sorted(fac_map.keys()))
            p_fac = st.selectbox("คณะ", f_opts, index=0, key="adm_p_fac2",
                                 format_func=lambda code: "ทั้งหมด" if code=="ทั้งหมด" else f"{code} - {fac_map.get(code, code)}")
            sel_fac = None if p_fac=="ทั้งหมด" else p_fac
        with col3:
            c_opts = admin_course_options(pending, sel_type, sel_fac)
            p_course = st.selectbox("รายวิชา", c_opts, index=0, key="adm_p_course2")
        with col4:
            p_q = st.text_input("ค้นหาในข้อความรีวิว/ชื่อวิชา", key="adm_p_q2")

        p_minr = st.slider("คะแนนขั้นต่ำ", 1, 5, 1, step=1, key="adm_p_minr2")
        sort1 = st.selectbox("จัดเรียงโดย", ["วันที่ (ใหม่→เก่า)","วันที่ (เก่า→ใหม่)","คะแนน (สูง→ต่ำ)","คะแนน (ต่ำ→สูง)"], index=0, key="adm_p_sort2")

        pf = admin_apply_filters(pending, sel_type, sel_fac, p_course, p_q, p_minr)
        pf = admin_sort_items(pf, sort1)
        ids = [r["id"] for r in pf]
        bulk_bar(ids, data)
        render_grouped(pf, data=data, pending_mode=True)

    with t_appr:
        st.subheader("กรองรีวิวที่อนุมัติแล้ว")
        col1,col2,col3,col4 = st.columns([1,1,1,1.2])
        with col1:
            t_opts = admin_type_options(approved)
            a_type = st.selectbox("ประเภท", t_opts, index=0, key="adm_a_type",
                                  format_func=lambda v: "ทั้งหมด" if v=="ทั้งหมด" else v)
            sel_type2 = None if a_type=="ทั้งหมด" else a_type
        with col2:
            fac_map2 = admin_faculty_map(approved, sel_type2)
            f_opts2 = ["ทั้งหมด"] + list(sorted(fac_map2.keys()))
            a_fac = st.selectbox("คณะ", f_opts2, index=0, key="adm_a_fac2",
                                 format_func=lambda code: "ทั้งหมด" if code=="ทั้งหมด" else f"{code} - {fac_map2.get(code, code)}")
            sel_fac2 = None if a_fac=="ทั้งหมด" else a_fac
        with col3:
            c_opts2 = admin_course_options(approved, sel_type2, sel_fac2)
            a_course = st.selectbox("รายวิชา", c_opts2, index=0, key="adm_a_course2")
        with col4:
            a_q = st.text_input("ค้นหาในข้อความรีวิว/ชื่อวิชา", key="adm_a_q2")

        a_minr = st.slider("คะแนนขั้นต่ำ", 1, 5, 1, step=1, key="adm_a_minr2")
        sort2 = st.selectbox("จัดเรียงโดย", ["วันที่ (ใหม่→เก่า)","วันที่ (เก่า→ใหม่)","คะแนน (สูง→ต่ำ)","คะแนน (ต่ำ→สูง)"], index=0, key="adm_a_sort2")

        af = admin_apply_filters(approved, sel_type2, sel_fac2, a_course, a_q, a_minr)
        af = admin_sort_items(af, sort2)

        # ----- แสดงกราฟแนวโน้มรีวิว เมื่อเลือกวิชาเฉพาะ -----
        if a_course != "ทั้งหมด":
            code = a_course.split(" ")[0]
            course_reviews = [r for r in af if r.get("course_code") == code]
            if course_reviews:
                render_star_histogram_altair(course_reviews, title=f"สรุปแนวโน้มรีวิว — {a_course}")

        # โชว์ meta รายวิชา (จาก COURSE_LUT) + กราฟสรุปดาว
        if a_course != "ทั้งหมด":
            code = a_course.split(" ")[0]
            info = COURSE_LUT.get(code, {})
            meta2 = []
            if info.get("credit"): meta2.append(f"หน่วยกิต: {info['credit']}")
            if info.get("prereq_en"): meta2.append(f"เงื่อนไขรายวิชา: {info['prereq_en']}")
            if info.get("grading"):
                label = {"ABC":"เกรด A–F","OSU":"O/S/U"}.get(info["grading"], info["grading"])
                meta2.append(f"การตัดเกรด: {info['grading']} ({label})")
            if info.get("updated_at"): meta2.append(f"อัปเดตล่าสุด: {info['updated_at']}")
            if meta2: st.caption(" • ".join(meta2))

            course_reviews = [r for r in af if r.get("course_code")==code]
            if course_reviews:
                st.markdown("#### สรุปคะแนนรีวิว (รายวิชาที่เลือก)")
                df_hist = star_histogram(course_reviews)
                avg = sum(int(r.get("rating",0)) for r in course_reviews)/len(course_reviews)
                st.metric("ค่าเฉลี่ย", f"{avg:.2f} / 5")
                st.bar_chart(df_hist, use_container_width=True)

        render_grouped(af, pending_mode=False)

    with t_sum:
        summary_table_panel(data)

    st.divider()
    # Export
    from io import StringIO
    import csv
    colx, coly = st.columns(2)
    with colx:
        if st.button("⬇️ ดาวน์โหลด Approved (CSV)"):
            rows = approved
            if not rows: st.info("ยังไม่มีข้อมูลที่อนุมัติ")
            else:
                buf = StringIO()
                writer = csv.DictWriter(buf, fieldnames=[
                    "id","course_type",
                    "faculty","faculty_name",
                    "department","department_name","year",
                    "course_code","course_name",
                    "rating","text","author","created_at","status",
                ])
                writer.writeheader()
                for r in rows: writer.writerow({k:r.get(k,"") for k in writer.fieldnames})
                st.download_button("Download approved_reviews.csv", buf.getvalue(), "approved_reviews.csv", "text/csv")
    with coly:
        if st.button("⬇️ ดาวน์โหลดฐานข้อมูลทั้งหมด (JSON)"):
            payload = json.dumps(data, ensure_ascii=False, indent=2)
            st.download_button("Download data.json", payload, "data.json", "application/json")

# -----------------------------
# Main
# -----------------------------
def header_bar():
    data = load_data()
    approved_cnt = len([r for r in data.get('approved_reviews', []) if r.get('status') == 'approved'])
    st.title(APP_TITLE)
    st.caption(f"คิวรอตรวจ: {len(data.get('pending_reviews', []))} | อนุมัติแล้ว: {approved_cnt} — คอร์สโหลดจาก Google Sheets")
    st.divider()

def main():
    handle_magic_links()
    header_bar()
    if "auth" not in st.session_state:
        do_login_form(); return
    sidebar_user_box()
    data = load_data()
    role = st.session_state["auth"]["role"]
    if role == "admin": page_admin(data)
    else: page_student(data)

if __name__ == "__main__":
    main()
