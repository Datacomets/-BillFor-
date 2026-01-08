# bill.py
# -*- coding: utf-8 -*-

import io
import pandas as pd
import streamlit as st
import numpy as np

# ========== PAGE CONFIG ==========
st.set_page_config(
    page_title="Sales Bill Converter",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ========== CUSTOM CSS ==========
st.markdown("""
<style>
    /* Main container styling */
    .main {
        padding: 2rem;
    }
    
    /* Header styling */
    .header-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2.5rem 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .header-title {
        color: white;
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
        text-align: center;
    }
    
    .header-subtitle {
        color: rgba(255, 255, 255, 0.9);
        font-size: 1.1rem;
        text-align: center;
        margin-top: 0.5rem;
    }
    
    /* Upload section */
    .upload-section {
        background: white;
        padding: 2rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        margin-bottom: 2rem;
        border: 2px dashed #e0e0e0;
        transition: all 0.3s ease;
    }
    
    .upload-section:hover {
        border-color: #667eea;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
    }
    
    /* Info cards */
    .info-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 4px solid #667eea;
    }
    
    /* Success card */
    .success-card {
        background: linear-gradient(135deg, #d4f1d4 0%, #b8e6b8 100%);
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 4px solid #28a745;
    }
    
    /* Stats container */
    .stats-container {
        display: flex;
        gap: 1rem;
        margin: 2rem 0;
    }
    
    .stat-box {
        flex: 1;
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        text-align: center;
        border-top: 3px solid #667eea;
    }
    
    .stat-number {
        font-size: 2rem;
        font-weight: 700;
        color: #667eea;
        margin: 0;
    }
    
    .stat-label {
        color: #666;
        font-size: 0.9rem;
        margin-top: 0.5rem;
    }
    
    /* Download buttons styling */
    .stDownloadButton button {
        width: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stDownloadButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }
    
    /* Dataframe styling */
    .dataframe-container {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        margin: 1.5rem 0;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background: #f8f9fa;
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ========== UTILITIES ==========
def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="sales")
    return bio.getvalue()

def _norm_cell(x) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip()

def detect_skiprows(file_like, max_scan_rows: int = 60) -> int:
    """Auto-detect header row by scanning first N rows"""
    try:
        preview = pd.read_excel(file_like, header=None, nrows=max_scan_rows)
    except Exception:
        return 0

    must_have = {"วันที่", "เลขที่", "ลูกค้า"}
    nice_to_have = {"พนักงานขาย", "เก็บเงิน", "ใบสั่งขาย", "ครบกำหนด", "ส่วนลด"}

    best_i = None
    best_score = -1

    for i in range(len(preview)):
        row = preview.iloc[i].tolist()
        cells = [_norm_cell(c) for c in row]
        cell_set = set(cells)

        score = 0
        score += 5 * sum(k in cell_set for k in must_have)
        score += 1 * sum(any(k in c for c in cells) for k in nice_to_have)

        if sum(k in cell_set for k in must_have) >= 2:
            if score > best_score:
                best_score = score
                best_i = i

    return best_i if best_i is not None else 5

def read_excel_autoskip(uploaded_file) -> tuple[pd.DataFrame, int]:
    """Read Excel with auto-detected skiprows"""
    uploaded_file.seek(0)
    sk = detect_skiprows(uploaded_file)

    uploaded_file.seek(0)
    df = pd.read_excel(uploaded_file, skiprows=sk)

    new_cols = []
    for c in df.columns:
        if isinstance(c, str) and not c.startswith("Unnamed:"):
            new_cols.append(c.strip())
        else:
            new_cols.append(c)
    df.columns = new_cols

    return df, sk

def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Transform dataframe according to business logic"""
    def col_exists(name: str) -> bool:
        return name in df.columns

    df["new_col"] = np.where(
        df["Unnamed: 6"].astype(str).str.contains("IN", na=False),
        "-",
        df["ใบสั่งขาย"]
            .astype(str)
            .str.split("-", n=1)
            .str[0],
        ),
    )

    mask_dp = df["V"] == "ตัดใบรับมัดจำ#"
    df.loc[mask_dp, "Unnamed: 6"] = "ตัดใบรับมัดจำ#"
    df.loc[mask_dp, "Unnamed: 7"] = df.loc[mask_dp, "ส่วนลด"]
    df.loc[mask_dp, "รวมทั้งสิ้น"] = df.loc[mask_dp, "มูลค่าสินค้า"]

    due_col = "ครบกำหนด" if col_exists("ครบกำหนด") else ("ครบกำหนด " if col_exists("ครบกำหนด ") else None)

    cols = ["วันที่", "เลขที่", "ลูกค้า", "พนักงานขาย", "เก็บเงิน", "new_col"]
    if due_col:
        cols.append(due_col)

    cols_exist = [c for c in cols if c in df.columns]
    if cols_exist:
        df[cols_exist] = df[cols_exist].ffill()

    df = df[df["Unnamed: 6"].notna()]
    df = df.iloc[1:].copy()

    df = df.rename(
        columns={
            "V": "รายการที่",
            "Unnamed: 6": "เลขที่สินค้า",
            "Unnamed: 7": "รายละเอียด",
            "Unnamed: 9": "หน่วยนับ",
            "new_col": "เลขที่ใบสั่งขาย",
            "ครบกำหนด": "ครบกำหนด",
            "มูลค่าสินค้า":"ราคาต่อหน่วย"
        }
    )

    if "Unnamed: 1" in df.columns:
        df = df.drop(columns=["Unnamed: 1"])

    return df

# ========== UI ==========

# Header
st.markdown("""
<div class="header-container">
    <h1 class="header-title">🧾 Sales Bill Converter</h1>
    <p class="header-subtitle">ระบบแปลงไฟล์ยอดขายตามฟอร์แมตรายงานใบกำกับสินค้า</p>
</div>
""", unsafe_allow_html=True)

# Instructions
with st.expander("📖 วิธีการใช้งาน", expanded=False):
    st.markdown("""
    ### ขั้นตอนการใช้งาน
    1. **อัปโหลดไฟล์** - เลือกไฟล์ Excel (.xlsx) ที่ต้องการแปลง (สามารถเลือกหลายไฟล์พร้อมกันได้)
    2. **ตรวจสอบข้อมูล** - ระบบจะประมวลผลและแสดงผลลัพธ์โดยอัตโนมัติ
    3. **ดาวน์โหลด** - เลือกดาวน์โหลดไฟล์ในรูปแบบ CSV หรือ Excel
    
    ### คุณสมบัติ
    - ✅ รองรับการอัปโหลดหลายไฟล์พร้อมกัน
    - ✅ ตรวจจับ Header อัตโนมัติ
    - ✅ รวมข้อมูลจากทุกไฟล์เป็นไฟล์เดียว
    - ✅ Export เป็น CSV และ Excel
    """)

# Upload section
st.markdown('<div class="upload-section">', unsafe_allow_html=True)
st.markdown("### 📁 อัปโหลดไฟล์")

uploaded_files = st.file_uploader(
    "เลือกไฟล์ Excel (.xlsx) ที่ต้องการแปลง",
    type=["xlsx"],
    accept_multiple_files=True,
    help="คุณสามารถเลือกหลายไฟล์พร้อมกันได้"
)
st.markdown('</div>', unsafe_allow_html=True)

if not uploaded_files:
    st.markdown("""
    <div class="info-card">
        <h4 style="margin-top: 0;">ℹ️ เริ่มต้นใช้งาน</h4>
        <p style="margin-bottom: 0;">กรุณาอัปโหลดไฟล์ Excel เพื่อเริ่มการแปลงข้อมูล</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# Processing
with st.spinner("🔄 กำลังประมวลผลไฟล์..."):
    dfs = []
    errors = []
    detected_info = []

    for uf in uploaded_files:
        try:
            df_raw, sk = read_excel_autoskip(uf)
            detected_info.append((uf.name, sk))

            df_out = transform(df_raw)
            df_out["__source_file__"] = uf.name
            dfs.append(df_out)
        except Exception as e:
            errors.append((uf.name, str(e)))

# Show detected skiprows info
if detected_info:
    with st.expander("🔍 ข้อมูลการตรวจจับ Header อัตโนมัติ", expanded=False):
        for name, sk in detected_info:
            st.markdown(f"- **{name}**: Header ที่แถว {sk + 1} (skiprows = {sk})")

# Show errors if any
if errors:
    st.error("⚠️ พบข้อผิดพลาดในการประมวลผลบางไฟล์")
    for name, msg in errors:
        st.markdown(f"- **{name}**: `{msg}`")

if not dfs:
    st.stop()

# Combine all dataframes
df_all = pd.concat(dfs, ignore_index=True)

# Success message with stats
st.markdown("""
<div class="success-card">
    <h3 style="margin-top: 0; color: #28a745;">✅ ประมวลผลสำเร็จ</h3>
    <p style="margin-bottom: 0;">แปลงไฟล์เรียบร้อยแล้ว พร้อมดาวน์โหลด</p>
</div>
""", unsafe_allow_html=True)

# Statistics
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f"""
    <div class="stat-box">
        <p class="stat-number">{len(uploaded_files):,}</p>
        <p class="stat-label">ไฟล์ที่อัปโหลด</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="stat-box">
        <p class="stat-number">{len(df_all):,}</p>
        <p class="stat-label">รายการทั้งหมด</p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="stat-box">
        <p class="stat-number">{len(df_all.columns):,}</p>
        <p class="stat-label">คอลัมน์ข้อมูล</p>
    </div>
    """, unsafe_allow_html=True)

# Preview data
st.markdown("### 📊 ตัวอย่างข้อมูลที่แปลงแล้ว")
st.markdown('<div class="dataframe-container">', unsafe_allow_html=True)
st.dataframe(df_all.head(100), use_container_width=True, height=400)
st.markdown('</div>', unsafe_allow_html=True)

if len(df_all) > 100:
    st.info(f"📌 แสดง 100 แถวแรก จากทั้งหมด {len(df_all):,} แถว")

# Download section
st.markdown("### 💾 ดาวน์โหลดผลลัพธ์")

csv_bytes = df_all.to_csv(index=False).encode("utf-8-sig")
xlsx_bytes = df_to_excel_bytes(df_all)

col_a, col_b = st.columns(2)

with col_a:
    st.download_button(
        label="📥 ดาวน์โหลด CSV",
        data=csv_bytes,
        file_name="sales_clean_all.csv",
        mime="text/csv",
        use_container_width=True
    )

with col_b:
    st.download_button(
        label="📥 ดาวน์โหลด Excel",
        data=xlsx_bytes,
        file_name="sales_clean_all.xlsx",
        mime="application/vnd.openxmlformats-officedocedocument.spreadsheetml.sheet",
        use_container_width=True
    )

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 1rem;">
    <p style="margin: 0;">Sales Bill Converter v2.0 | Made with ❤️ using Streamlit</p>
</div>
""", unsafe_allow_html=True)
