import streamlit as st
import json
import os
import uuid
from datetime import datetime
from functools import lru_cache
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

"""
All-in-One Streamlit App (Student + Admin)
- Auth (prototype): student1/1234, student2/1234, admin/admin
- Frontend (Student):
  • เลือกวิชาจากแค็ตตาล็อกที่จัดหมวดหมู่: คณะ → สาขา → ชั้นปี → รายวิชา (แสดงทั้งหมดก่อนแล้วค่อยกรอง)
  • แสดงคำอธิบายรายวิชา + ข้อมูลคณะ/สาขา + หน่วยกิต + Prerequisite
  • ส่งรีวิว (1–5 ดาว + ข้อความ) → เข้าคิวรออนุมัติ
  • ดูรีวิวอนุมัติแล้ว พร้อมตัวกรองคณะ/สาขา/ปี/รายวิชา + ค้นหา
- Backend (Admin):
  • ตัวกรองครบ: คณะ → สาขา → ชั้นปี (1–4) → รายวิชา + คีย์เวิร์ด + คะแนนขั้นต่ำ + จัดเรียง
  • มุมมองแบบ Grouped: คณะ > สาขา > ชั้นปี พร้อมอนุมัติ/ปฏิเสธรายรายการ และ Bulk approve/reject
  • แท็บสรุปภาพรวม (ตาราง) กรองคณะ/สาขา/ชั้นปีได้
  • ส่งออก CSV/JSON

Storage: local JSON (./data/data.json)
Requires: streamlit>=1.31
Run: streamlit run app_all_in_one.py
"""

# -----------------------------
# Page & basic styles
# -----------------------------
st.set_page_config(page_title="Uni Course Reviews — All-in-One", page_icon="⭐", layout="wide")
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

APP_TITLE = "ระบบรีวิวรายวิชามหาวิทยาลัย (Prototype) — รวมหน้า Student/Admin"
DATA_FILE = os.path.join("data", "data.json")

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
FACULTIES: Dict[str, Dict] = {
    "SCI": {
        "name": "คณะวิทยาศาสตร์",
        "departments": {
            "SCMA": "สาขาวิชาคณิตศาสตร์",
            "SCPL": "สาขาวิชาพฤกษศาสตร์",
            "SCPY": "สาขาวิชาฟิสิกส์",
            "SCCH": "สาขาวิชาเคมี",
            "SCBT": "สาขาวิชาเทคโนโลยีชีวภาพ",
            "SCBI": "สาขาวิชาชีววิทยา",
            "SCIM": "สาขาวิชาคณิตศาสตร์อุตสาหการ (นานาชาติ)",
            "SCAS": "สาขาวิชาคณิตศาสตร์ประกันภัย (นานาชาติ)",
        },
    },
    # ภายหลังเพิ่มคณะอื่น ๆ ได้เช่น "ENG": {"name": "คณะวิศวกรรมศาสตร์", ...}
}

# COURSE_CATALOG[faculty_code][dept_code][year] = list of course dicts
COURSE_CATALOG: Dict[str, Dict[str, Dict[int, List[Dict]]]] = {
    "SCI": {
        "SCMA": {
            1: [
                {"code": "2101101", "name": "Calculus I", "desc_th": "ลิมิต อนุพันธ์ ฟังก์ชันตัวแปรเดียว", "desc_en": "Limits and derivatives of single-variable functions.", "credit": 3, "prereq": None},
            ],
            2: [
                {"code": "2101201", "name": "Calculus II", "desc_th": "อินทิกรัล อนุกรมอนันต์ เทคนิคการอินทิเกรต", "desc_en": "Integration techniques and infinite series.", "credit": 3, "prereq": "2101101"},
                {"code": "2102201", "name": "ELECT ENG MATH I", "desc_th": "สมการเชิงอนุพันธ์อันดับหนึ่งและสูงกว่า อนุกรมผลต่าง สมการเชิงอนุพันธ์ย่อย ฟูริเยร์ซีรีส์/ทรานส์ฟอร์ม ลาปลาซทรานส์ฟอร์ม Z-transform ปัญหาค่าเริ่มต้น/ขอบเขต ประยุกต์ในวิศวกรรมไฟฟ้า", "desc_en": "First- and higher-order ODEs; difference equations; Fourier series/transform; Laplace; Z-transform; PDEs; boundary-value problems; EE applications.", "credit": 3, "prereq": "2301108"},
            ],
            3: [
                {"code": "2102301", "name": "Linear Algebra", "desc_th": "เวกเตอร์ เมทริกซ์ พีชคณิตเชิงเส้นประยุกต์", "desc_en": "Vectors, matrices, eigenvalues/eigenvectors; applications.", "credit": 3, "prereq": None},
            ],
            4: [
                {"code": "2102401", "name": "Numerical Methods", "desc_th": "วิธีเชิงตัวเลขสำหรับสมการ อนุกรม และอินทิกรัล", "desc_en": "Numerical solutions for equations/ODEs/integration.", "credit": 3, "prereq": "2102301"},
            ],
        },
        "SCPL": {
            1: [{"code": "2103101", "name": "Introduction to Botany", "desc_th": "พื้นฐานพฤกษศาสตร์ อนุกรมวิธาน โครงสร้างพืช", "desc_en": "Plant biology fundamentals.", "credit": 3, "prereq": None}],
            2: [{"code": "2103201", "name": "Plant Physiology", "desc_th": "สรีรวิทยาพืช การสังเคราะห์แสง การลำเลียง", "desc_en": "Photosynthesis, transport, plant hormones.", "credit": 3, "prereq": "2103101"}],
            3: [{"code": "2103301", "name": "Plant Ecology", "desc_th": "นิเวศวิทยาพืช ระบบนิเวศ", "desc_en": "Plant ecology and ecosystems.", "credit": 3, "prereq": None}],
            4: [{"code": "2103401", "name": "Plant Biotechnology", "desc_th": "เทคโนโลยีชีวภาพพืชและการประยุกต์", "desc_en": "Plant tissue culture and biotech applications.", "credit": 3, "prereq": "2103201"}],
        },
        "SCPY": {
            1: [{"code": "2104101", "name": "Mechanics I", "desc_th": "การเคลื่อนที่ กฎของนิวตัน งานและพลังงาน", "desc_en": "Kinematics, Newton's laws, energy.", "credit": 3, "prereq": None}],
            2: [{"code": "2104201", "name": "Electromagnetism", "desc_th": "สนามไฟฟ้า สนามแม่เหล็ก สมการแมกซ์เวลล์", "desc_en": "E&M and Maxwell's equations.", "credit": 3, "prereq": "2104101"}],
            3: [{"code": "2104301", "name": "Quantum Physics", "desc_th": "พื้นฐานกลศาสตร์ควอนตัม", "desc_en": "Intro to quantum mechanics.", "credit": 3, "prereq": None}],
            4: [{"code": "2104401", "name": "Statistical Physics", "desc_th": "ฟิสิกส์สถิติและอุณหพลศาสตร์", "desc_en": "Statistical mechanics and thermodynamics.", "credit": 3, "prereq": None}],
        },
        "SCCH": {
            1: [{"code": "2105101", "name": "General Chemistry", "desc_th": "โครงสร้างอะตอม ตารางธาตุ พันธะเคมี", "desc_en": "Atomic structure, bonding.", "credit": 3, "prereq": None}],
            2: [{"code": "2105201", "name": "Organic Chemistry", "desc_th": "โครงสร้าง/การเรียกชื่อ/ปฏิกิริยาของสารอินทรีย์", "desc_en": "Organic molecules and reactions.", "credit": 3, "prereq": "2105101"}],
            3: [{"code": "2105301", "name": "Physical Chemistry", "desc_th": "จลนพลศาสตร์เคมี อุณหพลศาสตร์", "desc_en": "Kinetics and thermodynamics.", "credit": 3, "prereq": None}],
            4: [{"code": "2105401", "name": "Analytical Chemistry", "desc_th": "การวิเคราะห์เชิงปริมาณ/เชิงคุณภาพ", "desc_en": "Quantitative/qualitative analysis.", "credit": 3, "prereq": None}],
        },
        "SCBT": {
            1: [{"code": "2106101", "name": "Cell Biology for Biotech", "desc_th": "โครงสร้างเซลล์ เมแทบอลิซึม ชีววิทยาระดับโมเลกุล", "desc_en": "Cell structure & molecular basics.", "credit": 3, "prereq": None}],
            2: [{"code": "2106201", "name": "Biochemistry", "desc_th": "โปรตีน เอนไซม์ วิถีเมแทบอลิซึม", "desc_en": "Proteins, enzymes, metabolism.", "credit": 3, "prereq": "2105101"}],
            3: [{"code": "2106301", "name": "Microbiology", "desc_th": "จุลชีววิทยาและเทคนิคห้องปฏิบัติการ", "desc_en": "Microbiology & lab techniques.", "credit": 3, "prereq": None}],
            4: [{"code": "2106401", "name": "Bioinformatics", "desc_th": "ชีวสารสนเทศและการประมวลผลข้อมูลชีวภาพ", "desc_en": "Bioinformatics fundamentals.", "credit": 3, "prereq": None}],
        },
        "SCBI": {
            1: [{"code": "2107101", "name": "General Biology", "desc_th": "พื้นฐานชีววิทยาของเซลล์และสิ่งมีชีวิต", "desc_en": "Cell/organismal biology.", "credit": 3, "prereq": None}],
            2: [{"code": "2107201", "name": "Genetics", "desc_th": "หลักการถ่ายทอดพันธุกรรมและพันธุศาสตร์โมเลกุล", "desc_en": "Genetics principles.", "credit": 3, "prereq": "2107101"}],
            3: [{"code": "2107301", "name": "Ecology", "desc_th": "นิเวศวิทยาและสิ่งแวดล้อม", "desc_en": "Ecology and environment.", "credit": 3, "prereq": None}],
            4: [{"code": "2107401", "name": "Molecular Biology", "desc_th": "ชีววิทยาระดับโมเลกุลขั้นสูง", "desc_en": "Advanced molecular biology.", "credit": 3, "prereq": None}],
        },
        "SCIM": {
            1: [{"code": "2108101", "name": "Programming I", "desc_th": "พื้นฐานการเขียนโปรแกรม", "desc_en": "Intro to programming.", "credit": 3, "prereq": None}],
            2: [{"code": "2108201", "name": "Probability & Statistics", "desc_th": "ทฤษฎีความน่าจะเป็นและสถิติ", "desc_en": "Probability and statistics.", "credit": 3, "prereq": None}],
            3: [{"code": "2109301", "name": "Operations Research", "desc_th": "การโปรแกรมเชิงเส้นและวิธีเหมาะที่สุด", "desc_en": "Linear programming & optimization.", "credit": 3, "prereq": "2101201"}],
            4: [{"code": "2109401", "name": "Industrial Mathematics", "desc_th": "คณิตศาสตร์ประยุกต์ในอุตสาหกรรมและวิศวกรรม", "desc_en": "Applied math in industry.", "credit": 3, "prereq": "2109301"}],
        },
        "SCAS": {
            1: [{"code": "2108001", "name": "Intro to Actuarial Science", "desc_th": "แนะนำวิชาชีพนักคณิตศาสตร์ประกันภัย", "desc_en": "Actuarial profession overview.", "credit": 3, "prereq": None}],
            2: [{"code": "2108202", "name": "Financial Mathematics", "desc_th": "ดอกเบี้ย เงินงวด มูลค่าปัจจุบัน", "desc_en": "Interest theory and annuities.", "credit": 3, "prereq": None}],
            3: [{"code": "2108301", "name": "Actuarial Mathematics I", "desc_th": "ตารางมรณะ การประเมินความเสี่ยง", "desc_en": "Life tables and risk.", "credit": 3, "prereq": "2108202"}],
            4: [{"code": "2108401", "name": "Risk Modeling", "desc_th": "แบบจำลองความเสี่ยงและการประกันภัย", "desc_en": "Risk models in insurance.", "credit": 3, "prereq": "2108301"}],
        },
    }
}

@lru_cache(maxsize=1)
def flatten_catalog() -> List[Dict]:
    rows: List[Dict] = []
    for fac, fac_data in COURSE_CATALOG.items():
        fac_name = FACULTIES.get(fac, {}).get("name", fac)
        dept_map = FACULTIES.get(fac, {}).get("departments", {})
        for dept, years in fac_data.items():
            dept_name = dept_map.get(dept, dept)
            for year, courses in years.items():
                for c in courses:
                    rows.append({
                        "faculty": fac,
                        "faculty_name": fac_name,
                        "department": dept,
                        "department_name": dept_name,
                        "year": int(year),
                        "code": c["code"],
                        "name": c["name"],
                        "desc_th": c.get("desc_th", ""),
                        "desc_en": c.get("desc_en", ""),
                        "credit": c.get("credit", None),
                        "prereq": c.get("prereq", None),
                    })
    rows.sort(key=lambda r: (r["faculty"], r["department"], r["year"], r["code"]))
    return rows

ALL_COURSES = flatten_catalog()

# -----------------------------
# Storage helpers
# -----------------------------

def ensure_data_file() -> None:
    if not os.path.exists(DATA_FILE):
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"approved_reviews": [], "pending_reviews": []}, f, ensure_ascii=False, indent=2)


def load_data() -> Dict:
    ensure_data_file()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: Dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# -----------------------------
# Utilities
# -----------------------------

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

def do_login_form():
    st.markdown("### เข้าสู่ระบบ")
    u = st.text_input("Username", placeholder="student1 / admin")
    p = st.text_input("Password", type="password")
    if st.button("เข้าสู่ระบบ", type="primary"):
        user = USERS.get(u)
        if user and user.get("password") == p:
            st.session_state["auth"] = {"username": u, "role": user["role"], "display": user["display"]}
            st.success("เข้าสู่ระบบสำเร็จ")
            st.rerun()
        else:
            st.error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    st.info("บัญชีตัวอย่าง: student1/1234, student2/1234, admin/admin")


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
        st.subheader("เลือกวิชาเพื่อรีวิว (แสดงทั้งหมดก่อนแล้วค่อยกรอง)")
        colA, colB, colC = st.columns(3)
        with colA:
            sel_fac = st.selectbox("คณะ", faculty_options(), index=0, key="stu_fac")
        with colB:
            sel_dept = st.selectbox("สาขา", department_options(sel_fac), index=0, key="stu_dept")
        with colC:
            sel_year = st.selectbox("ชั้นปี", year_options(sel_fac, sel_dept), index=0, key="stu_year")

        filtered_courses = filter_courses(sel_fac, sel_dept, sel_year)
        if not filtered_courses:
            st.info("ยังไม่พบวิชาตามเงื่อนไขที่เลือก — โปรดลองเปลี่ยนตัวกรอง")
            return

        labels = [f"[{r['faculty']}/{r['department']}] ปี {r['year']} — {r['code']} {r['name']}" for r in filtered_courses]
        idx = st.selectbox("เลือกรายวิชา", range(len(filtered_courses)), format_func=lambda i: labels[i], key="stu_course")
        course = filtered_courses[idx]

        # Course meta box
        st.markdown(
            f"<div class='box'>"
            f"<div><span class='codepill'>{course['code']}</span> <b>{course['name']}</b></div>"
            f"<div class='muted'>คณะ: {course['faculty_name']} • สาขา: {course['department_name']} • ชั้นปี: {course['year']} • หน่วยกิต: {course.get('credit','-')}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if course.get("prereq"): st.caption(f"เงื่อนไขรายวิชา: {course['prereq']}")
        if course.get("desc_th"): st.write(course["desc_th"])
        if course.get("desc_en"): st.markdown(f"<span class='muted'>{course['desc_en']}</span>", unsafe_allow_html=True)

        st.markdown("---")
        col_rate, _ = st.columns([1, 2])
        with col_rate:
            rating = st.radio("ให้คะแนน (1-5 ดาว)", options=[1,2,3,4,5], horizontal=True, index=4)
        st.markdown(f"**ตัวอย่างดาว:** <span class='star'>{star_str(rating)}</span>", unsafe_allow_html=True)
        review_text = st.text_area("เขียนรีวิวเพิ่มเติม (ไม่บังคับ)", max_chars=1200, height=150, placeholder="เล่าประสบการณ์ เนื้อหา งาน/การบ้าน ความยาก-ง่าย คำแนะนำ ฯลฯ")

        if st.button("ส่งรีวิว (เข้าคิวรอตรวจ)", type="primary", use_container_width=True):
            auth = st.session_state.get("auth", {})
            new_r = {
                "id": str(uuid.uuid4()),
                "faculty": course["faculty"], "faculty_name": course["faculty_name"],
                "department": course["department"], "department_name": course["department_name"],
                "year": int(course["year"]),
                "course_code": course["code"], "course_name": course["name"],
                "rating": int(rating), "text": (review_text or "").strip(),
                "author": auth.get("username", "anonymous"),
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "status": "pending",
            }
            pending.append(new_r)
            save_data(data)
            st.success("ส่งรีวิวเรียบร้อย! รอผู้ดูแลอนุมัติ")
            st.balloons()

    # Browse tab
    with t_browse:
        st.subheader("ดูรีวิวที่อนุมัติแล้ว (กรองคณะ/สาขา/ชั้นปี/รายวิชา)")
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1: f_fac = st.selectbox("คณะ", faculty_options(), index=0, key="b_fac")
        with col2: f_dept = st.selectbox("สาขา", department_options(f_fac), index=0, key="b_dept")
        with col3: f_year = st.selectbox("ชั้นปี", year_options(f_fac, f_dept), index=0, key="b_year")
        master_courses = filter_courses(f_fac, f_dept, f_year)
        course_names = ["ทั้งหมด"] + [f"{r['code']} {r['name']}" for r in master_courses]
        with col4: f_course = st.selectbox("รายวิชา", course_names, index=0, key="b_course")
        with col5: q = st.text_input("ค้นหาในข้อความรีวิว", key="b_q")

        items = [r for r in approved if r.get("status") == "approved"]
        if f_fac != "ทั้งหมด": items = [r for r in items if r.get("faculty_name") == f_fac]
        if f_dept != "ทั้งหมด": items = [r for r in items if r.get("department_name") == f_dept]
        if f_year != "ทั้งหมด": items = [r for r in items if int(r.get("year", 0)) == int(f_year)]
        if f_course != "ทั้งหมด":
            code = f_course.split(" ")[0]
            items = [r for r in items if r.get("course_code") == code]
        if q:
            ql = q.lower().strip()
            items = [r for r in items if ql in (r.get("text") or "").lower()]

        stats = compute_course_stats(items)
        if stats:
            st.markdown("#### สรุปคะแนนเฉลี่ย (ผลจากตัวกรอง)")
            cols = st.columns(3); i = 0
            for (y, cname), s in sorted(stats.items(), key=lambda x: (x[0][0], x[0][1])):
                with cols[i % 3]:
                    st.markdown(f"**ปี {y}: {cname}**")
                    st.markdown(f"ค่าเฉลี่ย: **{s['avg']:.2f}** / 5")
                    st.progress(min(1.0, s['avg']/5.0))
                i += 1
            st.divider()

        if not items:
            st.info("ยังไม่มีรีวิวที่ผ่านการอนุมัติในเงื่อนไขที่เลือก")
        else:
            for r in sorted(items, key=lambda x: x["created_at"], reverse=True):
                with st.container(border=True):
                    st.markdown(f"<span class='codepill'>{r.get('course_code','')}</span> <b>{r.get('course_name','')}</b>", unsafe_allow_html=True)
                    st.markdown(f"คณะ: {r.get('faculty_name','-')} • สาขา: {r.get('department_name','-')} • ปี: {r.get('year','-')}")
                    st.markdown(
                        f"ให้คะแนน: <span class='star'>{star_str(int(r.get('rating',0)))}</span>  "
                        f"<span class='muted'>โดย `{r.get('author','?')}` • วันที่ {r.get('created_at','')}</span>",
                        unsafe_allow_html=True,
                    )
                    if r.get("text"):
                        st.markdown("—")
                        st.write(r["text"])

# -----------------------------
# Admin helpers (filters + grouping)
# -----------------------------

def admin_faculty_options(items: List[Dict]) -> List[str]:
    names = sorted({r.get("faculty_name", r.get("faculty", "")) for r in items if r.get("faculty")})
    return ["ทั้งหมด"] + names

def admin_department_options(items: List[Dict], fac_name: str) -> List[str]:
    if fac_name == "ทั้งหมด":
        names = sorted({r.get("department_name", r.get("department", "")) for r in items if r.get("department")})
    else:
        names = sorted({r.get("department_name", r.get("department", "")) for r in items if r.get("faculty_name") == fac_name})
    return ["ทั้งหมด"] + names

def admin_year_options() -> List[str]:
    return ["ทั้งหมด", "1", "2", "3", "4"]

def admin_course_options(items: List[Dict], fac: str, dept: str, year: str) -> List[str]:
    filtered = list(items)
    if fac != "ทั้งหมด": filtered = [r for r in filtered if r.get("faculty_name") == fac]
    if dept != "ทั้งหมด": filtered = [r for r in filtered if r.get("department_name") == dept]
    if year != "ทั้งหมด": filtered = [r for r in filtered if str(r.get("year", "")) == year]
    names = sorted({f"{r.get('course_code','')} {r.get('course_name','')}" for r in filtered if r.get("course_code")})
    return ["ทั้งหมด"] + names

def admin_apply_filters(items: List[Dict], fac: str, dept: str, year: str, course_label: str, q: str, min_rating: int) -> List[Dict]:
    out = list(items)
    if fac != "ทั้งหมด": out = [r for r in out if r.get("faculty_name") == fac]
    if dept != "ทั้งหมด": out = [r for r in out if r.get("department_name") == dept]
    if year != "ทั้งหมด": out = [r for r in out if str(r.get("year","")) == year]
    if course_label and course_label != "ทั้งหมด":
        code = course_label.split(" ")[0]
        out = [r for r in out if str(r.get("course_code","")) == code]
    if q:
        ql = q.lower().strip(); out = [r for r in out if ql in (r.get("text") or "").lower()]
    if min_rating and min_rating > 1:
        out = [r for r in out if int(r.get("rating", 0)) >= min_rating]
    return out

def admin_sort_items(items: List[Dict], sort_key: str) -> List[Dict]:
    if sort_key == "วันที่ (ใหม่→เก่า)": return sorted(items, key=lambda x: x.get("created_at",""), reverse=True)
    if sort_key == "วันที่ (เก่า→ใหม่)": return sorted(items, key=lambda x: x.get("created_at",""))
    if sort_key == "คะแนน (สูง→ต่ำ)": return sorted(items, key=lambda x: int(x.get("rating",0)), reverse=True)
    if sort_key == "คะแนน (ต่ำ→สูง)": return sorted(items, key=lambda x: int(x.get("rating",0)))
    return items

def bulk_bar(filtered_ids: List[str], data: Dict):
    pending = data["pending_reviews"]
    selected_ids = st.session_state.get("selected_ids", set())
    c1, c2, c3, c4 = st.columns([1,1,1,2])
    with c1:
        if st.button("เลือกทั้งหมด(ตามตัวกรอง)"): st.session_state["selected_ids"] = set(filtered_ids); st.rerun()
    with c2:
        if st.button("ล้างการเลือก"): st.session_state["selected_ids"] = set(); st.rerun()
    with c3:
        if st.button("✅ อนุมัติที่เลือก") and selected_ids:
            move, keep = [], []
            ids = set(selected_ids)
            for r in pending: (move if r["id"] in ids else keep).append(r)
            for r in move: r["status"] = "approved"
            data["approved_reviews"].extend(move); data["pending_reviews"] = keep; save_data(data)
            st.success(f"อนุมัติ {len(move)} รายการ"); st.session_state["selected_ids"] = set(); st.rerun()
    with c4:
        if st.button("🗑️ ปฏิเสธที่เลือก") and selected_ids:
            keep = [r for r in pending if r["id"] not in selected_ids]; removed = len(pending) - len(keep)
            data["pending_reviews"] = keep; save_data(data)
            st.warning(f"ปฏิเสธ {removed} รายการ"); st.session_state["selected_ids"] = set(); st.rerun()

def render_grouped(items: List[Dict], data: Optional[Dict] = None, pending_mode: bool = False):
    if not items: st.info("ไม่พบรายการตามตัวกรอง"); return
    selected_ids = st.session_state.setdefault("selected_ids", set())
    groups: Dict[str, Dict[str, Dict[str, List[Dict]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in items:
        fac = r.get("faculty_name", r.get("faculty","?")); dep = r.get("department_name", r.get("department","?")); yr = str(r.get("year","?"))
        groups[fac][dep][yr].append(r)
    for fac in sorted(groups.keys()):
        with st.expander(f"คณะ: {fac}", expanded=True):
            for dep in sorted(groups[fac].keys()):
                st.markdown(f"### สาขา: {dep}")
                for yr in sorted(groups[fac][dep].keys(), key=lambda v: (len(v), v)):
                    st.markdown(f"**ชั้นปีที่ {yr}**")
                    for r in groups[fac][dep][yr]:
                        with st.container(border=True):
                            left, right = st.columns([3,1])
                            with left:
                                st.markdown(
                                    f"**{r.get('course_code','')} {r.get('course_name','')}**  \n"
                                    f"ให้คะแนน: {star_str(int(r.get('rating',0)))}  \n"
                                    f"โดย `{r.get('author','?')}` • วันที่ {r.get('created_at','')}"
                                )
                                if txt := r.get("text"): st.markdown("—"); st.write(txt)
                            with right:
                                if pending_mode and data is not None:
                                    checked = r["id"] in selected_ids
                                    ck = st.checkbox("เลือก", key=f"sel_{r['id']}", value=checked)
                                    if ck and r["id"] not in selected_ids: selected_ids.add(r["id"])
                                    if not ck and r["id"] in selected_ids: selected_ids.remove(r["id"])
                                    a1, a2 = st.columns(2)
                                    with a1:
                                        if st.button("อนุมัติ", key=f"ap_{r['id']}"):
                                            r["status"] = "approved"; data["approved_reviews"].append(r); data["pending_reviews"].remove(r); save_data(data); st.success("อนุมัติแล้ว"); st.rerun()
                                    with a2:
                                        if st.button("ปฏิเสธ", key=f"re_{r['id']}"):
                                            data["pending_reviews"].remove(r); save_data(data); st.warning("ปฏิเสธแล้ว"); st.rerun()

# -----------------------------
# Summary table (Admin)
# -----------------------------

def build_summary_rows(approved: List[Dict]) -> List[Dict]:
    agg: Dict[Tuple[str,str,int,str], Dict[str,float]] = {}
    # key: (faculty_name, department_name, year, course_name)
    for r in approved:
        if r.get("status") != "approved": continue
        key = (r.get("faculty_name","-"), r.get("department_name","-"), int(r.get("year",0)), r.get("course_name","-"))
        obj = agg.setdefault(key, {"sum":0.0, "count":0.0}); obj["sum"] += float(r.get("rating",0)); obj["count"] += 1
    rows: List[Dict] = []
    for (fac,dep,yr,cname), v in agg.items():
        avg = v["sum"]/v["count"] if v["count"] else 0.0
        rows.append({"คณะ": fac, "สาขา": dep, "ชั้นปี": yr, "รายวิชา": cname, "ค่าเฉลี่ย": round(avg,2), "ดาว": star_str(int(round(avg))), "จำนวนรีวิว": int(v["count"]), "เฉลี่ย/5": avg/5.0})
    rows.sort(key=lambda r: (r["คณะ"], r["สาขา"], r["ชั้นปี"], r["รายวิชา"]))
    return rows

def summary_table_panel(data: Dict):
    st.subheader("📊 สรุปภาพรวม (ตาราง)")
    approved = [r for r in data.get("approved_reviews", []) if r.get("status") == "approved"]
    rows = build_summary_rows(approved)
    # Filters
    c1, c2, c3 = st.columns(3)
    with c1:
        facs = ["ทั้งหมด"] + sorted({r["คณะ"] for r in rows}); f = st.selectbox("คณะ", facs, index=0, key="sum_fac")
    with c2:
        deps = ["ทั้งหมด"] + sorted({r["สาขา"] for r in rows if f=="ทั้งหมด" or r["คณะ"]==f}); d = st.selectbox("สาขา", deps, index=0, key="sum_dep")
    with c3:
        yrs = ["ทั้งหมด", "1","2","3","4"]; y = st.selectbox("ชั้นปี", yrs, index=0, key="sum_year")
    if f != "ทั้งหมด": rows = [r for r in rows if r["คณะ"] == f]
    if d != "ทั้งหมด": rows = [r for r in rows if r["สาขา"] == d]
    if y != "ทั้งหมด": rows = [r for r in rows if str(r["ชั้นปี"]) == y]

    if not rows:
        st.info("ยังไม่มีข้อมูลสรุปสำหรับเงื่อนไขนี้"); return

    st.dataframe(
        rows,
        hide_index=True,
        use_container_width=True,
        column_config={
            "ชั้นปี": st.column_config.NumberColumn(format="%d"),
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
        col1, col2, col3, col4 = st.columns(4)
        p_fac = st.selectbox("คณะ", admin_faculty_options(pending), index=0, key="adm_p_fac")
        p_dep = st.selectbox("สาขา", admin_department_options(pending, p_fac), index=0, key="adm_p_dep")
        p_year = st.selectbox("ชั้นปี", admin_year_options(), index=0, key="adm_p_year")
        p_minr = st.slider("คะแนนขั้นต่ำ", 1, 5, 1, step=1, key="adm_p_minr")
        col5, col6 = st.columns([2,2])
        p_course = st.selectbox("รายวิชา", admin_course_options(pending, p_fac, p_dep, p_year), index=0, key="adm_p_course")
        p_q = st.text_input("ค้นหาในข้อความรีวิว", key="adm_p_q")
        sort1 = st.selectbox("จัดเรียงโดย", ["วันที่ (ใหม่→เก่า)", "วันที่ (เก่า→ใหม่)", "คะแนน (สูง→ต่ำ)", "คะแนน (ต่ำ→สูง)"], index=0, key="adm_p_sort")
        pf = admin_apply_filters(pending, p_fac, p_dep, p_year, p_course, p_q, p_minr)
        pf = admin_sort_items(pf, sort1)
        ids = [r["id"] for r in pf]
        bulk_bar(ids, data)
        render_grouped(pf, data=data, pending_mode=True)

    with t_appr:
        st.subheader("กรองรีวิวที่อนุมัติแล้ว")
        a_fac = st.selectbox("คณะ", admin_faculty_options(approved), index=0, key="a_fac")
        a_dep = st.selectbox("สาขา", admin_department_options(approved, a_fac), index=0, key="a_dep")
        a_year = st.selectbox("ชั้นปี", admin_year_options(), index=0, key="a_year")
        a_minr = st.slider("คะแนนขั้นต่ำ", 1, 5, 1, step=1, key="a_minr")
        col7, col8 = st.columns([2,2])
        a_course = st.selectbox("รายวิชา", admin_course_options(approved, a_fac, a_dep, a_year), index=0, key="a_course")
        a_q = st.text_input("ค้นหาในข้อความรีวิว", key="a_q")
        sort2 = st.selectbox("จัดเรียงโดย", ["วันที่ (ใหม่→เก่า)", "วันที่ (เก่า→ใหม่)", "คะแนน (สูง→ต่ำ)", "คะแนน (ต่ำ→สูง)"], index=0, key="a_sort")
        af = admin_apply_filters(approved, a_fac, a_dep, a_year, a_course, a_q, a_minr)
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
                    fieldnames=["id","faculty","faculty_name","department","department_name","year","course_code","course_name","rating","text","author","created_at","status"],
                ); writer.writeheader()
                for r in rows: writer.writerow({k: r.get(k, "") for k in writer.fieldnames})
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
    st.title(APP_TITLE)
    st.caption(f"คิวรอตรวจ: {len(data.get('pending_reviews', []))} | อนุมัติแล้วสะสม: {len(data.get('approved_reviews', []))} — เก็บในไฟล์ data/data.json")
    st.divider()


def main():
    header_bar()
    if "auth" not in st.session_state:
        do_login_form(); return
    sidebar_user_box()
    data = load_data()
    role = st.session_state["auth"]["role"]
    if role == "admin":
        page_admin(data)
    else:
        page_student(data)

if __name__ == "__main__":
    main()
