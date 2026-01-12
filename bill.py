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
.main { padding: 2rem; }
.header-container {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 2.5rem 2rem;
    border-radius: 15px;
    margin-bottom: 2rem;
}
.header-title {
    color: white; font-size: 2.5rem; font-weight: 700; text-align: center;
}
.header-subtitle {
    color: rgba(255,255,255,.9); text-align: center;
}
.upload-section {
    background: white; padding: 2rem; border-radius: 12px;
    border: 2px dashed #e0e0e0; margin-bottom: 2rem;
}
.dataframe-container {
    background: white; padding: 1.5rem;
    border-radius: 12px; margin: 1.5rem 0;
}
</style>
""", unsafe_allow_html=True)

# ========== UTILITIES ==========
def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="data")
    return bio.getvalue()

def detect_skiprows(file_like, max_scan_rows: int = 60) -> int:
    preview = pd.read_excel(file_like, header=None, nrows=max_scan_rows)
    must_have = {"วันที่", "เลขที่", "ลูกค้า"}
    for i in range(len(preview)):
        if len(must_have & set(preview.iloc[i].astype(str))) >= 2:
            return i
    return 5

def read_excel_autoskip(uploaded_file):
    uploaded_file.seek(0)
    sk = detect_skiprows(uploaded_file)
    uploaded_file.seek(0)
    df = pd.read_excel(uploaded_file, skiprows=sk)
    df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]
    return df, sk

def transform(df: pd.DataFrame) -> pd.DataFrame:
    df["new_col"] = np.where(
        df["Unnamed: 6"].astype(str).str.contains("IN", na=False),
        "-",
        df["ใบสั่งขาย"].astype(str).str.split("-", n=1).str[0]
    )

    mask_dp = df["V"] == "ตัดใบรับมัดจำ#"
    df.loc[mask_dp, "Unnamed: 6"] = "ตัดใบรับมัดจำ#"
    df.loc[mask_dp, "Unnamed: 7"] = df.loc[mask_dp, "ส่วนลด"]
    df.loc[mask_dp, "รวมทั้งสิ้น"] = df.loc[mask_dp, "มูลค่าสินค้า"]

    fill_cols = [
        "วันที่", "เลขที่", "ลูกค้า",
        "พนักงานขาย", "เก็บเงิน", "new_col"
    ]
    df[fill_cols] = df[fill_cols].ffill()

    df = df[df["Unnamed: 6"].notna()].iloc[1:].copy()

    df = df.rename(columns={
        "V": "รายการที่",
        "Unnamed: 6": "เลขที่สินค้า",
        "Unnamed: 7": "รายละเอียด",
        "new_col": "เลขที่ใบสั่งขาย",
        "มูลค่าสินค้า": "ราคาต่อหน่วย"
    })

    df = df.drop(columns=[c for c in ["Unnamed: 1"] if c in df.columns])
    return df

# ========== HEADER ==========
st.markdown("""
<div class="header-container">
    <h1 class="header-title">🧾 Sales Bill Converter</h1>
    <p class="header-subtitle">ระบบแปลงไฟล์รายงานขายและรายงานการรับชำระหนี้</p>
</div>
""", unsafe_allow_html=True)

# ========== UPLOAD ==========
st.markdown('<div class="upload-section">', unsafe_allow_html=True)
uploaded_files = st.file_uploader(
    "อัปโหลดไฟล์ Excel",
    type=["xlsx"],
    accept_multiple_files=True
)
st.markdown('</div>', unsafe_allow_html=True)

if not uploaded_files:
    st.stop()

# ========== PROCESS ==========
dfs = []
for uf in uploaded_files:
    df_raw, _ = read_excel_autoskip(uf)
    df_out = transform(df_raw)
    df_out["__source_file__"] = uf.name
    dfs.append(df_out)

df_all = pd.concat(dfs, ignore_index=True)

# ===== รายงานการรับชำระหนี้ =====
payment_cols = [
    "วันที่รับชำระ",
    "เลขที่ใบเสร็จ",
    "วันที่",
    "ชื่อลูกค้า",
    "พนักงานขาย",
    "new_col",
    "ตัดเงินมัดจำ",
    "ยอดตามใบกำกับ",
    "จำนวนเงินรวมตามใบเสร็จ",
]

payment_cols = [c for c in payment_cols if c in df_all.columns]

df_payment = df_all.loc[
    df_all["พนักงานขาย"].astype(str).str.contains("I", na=False)
    & df_all["ตัดเงินมัดจำ"].notna(),
    payment_cols
]

# ========== TABS ==========
tab1, tab2 = st.tabs([
    "📄 ข้อมูลขายทั้งหมด",
    "🧾 รายงานการรับชำระหนี้"
])

with tab1:
    st.markdown('<div class="dataframe-container">', unsafe_allow_html=True)
    st.dataframe(df_all.head(100), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="dataframe-container">', unsafe_allow_html=True)
    st.dataframe(df_payment, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.success(f"พบข้อมูล {len(df_payment):,} รายการ")

# ========== DOWNLOAD ==========
st.markdown("### 💾 ดาวน์โหลดไฟล์")

st.download_button(
    "📥 ดาวน์โหลดทั้งหมด (Excel)",
    data=df_to_excel_bytes(df_all),
    file_name="sales_all.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

st.download_button(
    "📥 ดาวน์โหลดรายงานการรับชำระหนี้ (Excel)",
    data=df_to_excel_bytes(df_payment),
    file_name="payment_report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
