# bill.py
# -*- coding: utf-8 -*-

import io
import pandas as pd
import numpy as np
import streamlit as st

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="Sales Bill Converter",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =====================================================
# UTILITIES
# =====================================================
def df_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "data") -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return bio.getvalue()


def detect_skiprows(file_like, max_scan_rows: int = 60) -> int:
    """ตรวจจับแถว header อัตโนมัติ"""
    preview = pd.read_excel(file_like, header=None, nrows=max_scan_rows)
    must_have = {"วันที่", "เลขที่", "ลูกค้า"}

    for i in range(len(preview)):
        row_vals = set(preview.iloc[i].astype(str))
        if len(must_have & row_vals) >= 2:
            return i
    return 5


def read_excel_autoskip(uploaded_file):
    uploaded_file.seek(0)
    skip = detect_skiprows(uploaded_file)
    uploaded_file.seek(0)

    df = pd.read_excel(uploaded_file, skiprows=skip)
    df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]
    return df, skip


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Business logic หลัก"""

    # สร้างเลขที่ใบสั่งขาย
    df["new_col"] = np.where(
        df["Unnamed: 6"].astype(str).str.contains("IN", na=False),
        "-",
        df["ใบสั่งขาย"]
        .astype(str)
        .str.split("-", n=1)
        .str[0]
    )

    # กรณีตัดใบรับมัดจำ
    mask_dp = df["V"] == "ตัดใบรับมัดจำ#"
    df.loc[mask_dp, "Unnamed: 6"] = "ตัดใบรับมัดจำ#"
    df.loc[mask_dp, "Unnamed: 7"] = df.loc[mask_dp, "ส่วนลด"]
    df.loc[mask_dp, "รวมทั้งสิ้น"] = df.loc[mask_dp, "มูลค่าสินค้า"]

    # Fill down ข้อมูลหัวบิล
    fill_cols = [
        "วันที่",
        "เลขที่",
        "ลูกค้า",
        "พนักงานขาย",
        "เก็บเงิน",
        "new_col",
    ]
    fill_cols = [c for c in fill_cols if c in df.columns]
    df[fill_cols] = df[fill_cols].ffill()

    # ตัดเฉพาะรายการสินค้า
    df = df[df["Unnamed: 6"].notna()].iloc[1:].copy()

    # Rename columns
    df = df.rename(columns={
        "V": "รายการที่",
        "Unnamed: 6": "เลขที่สินค้า",
        "Unnamed: 7": "รายละเอียด",
        "new_col": "เลขที่ใบสั่งขาย",
        "มูลค่าสินค้า": "ราคาต่อหน่วย",
    })

    # ลบคอลัมน์ไม่จำเป็น
    if "Unnamed: 1" in df.columns:
        df = df.drop(columns=["Unnamed: 1"])

    return df


# =====================================================
# HEADER
# =====================================================
st.markdown("""
<h1 style="text-align:center;">🧾 Sales Bill Converter</h1>
<p style="text-align:center; color:gray;">
ระบบแปลงข้อมูลขาย และรายงานการรับชำระหนี้
</p>
<hr>
""", unsafe_allow_html=True)

# =====================================================
# UPLOAD
# =====================================================
uploaded_files = st.file_uploader(
    "อัปโหลดไฟล์ Excel (.xlsx)",
    type=["xlsx"],
    accept_multiple_files=True
)

if not uploaded_files:
    st.info("กรุณาอัปโหลดไฟล์เพื่อเริ่มการประมวลผล")
    st.stop()

# =====================================================
# PROCESS FILES
# =====================================================
dfs = []

with st.spinner("กำลังประมวลผลไฟล์..."):
    for uf in uploaded_files:
        df_raw, skip = read_excel_autoskip(uf)
        df_out = transform(df_raw)
        df_out["__source_file__"] = uf.name
        dfs.append(df_out)

df_all = pd.concat(dfs, ignore_index=True)

# =====================================================
# REPORT : รายงานการรับชำระหนี้
# =====================================================
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
].copy()

# =====================================================
# TABS (สำคัญ: ต้องอยู่นอก IF และ LOOP)
# =====================================================
tab_all, tab_payment = st.tabs([
    "📄 ข้อมูลขายทั้งหมด",
    "🧾 รายงานการรับชำระหนี้"
])

# ---------------- TAB 1 ----------------
with tab_all:
    st.subheader("ข้อมูลขายทั้งหมด")
    st.dataframe(df_all, use_container_width=True)
    st.download_button(
        "📥 ดาวน์โหลดข้อมูลขายทั้งหมด (Excel)",
        data=df_to_excel_bytes(df_all, "sales"),
        file_name="sales_all.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ---------------- TAB 2 ----------------
with tab_payment:
    st.subheader("รายงานการรับชำระหนี้")
    st.dataframe(df_payment, use_container_width=True)

    st.success(f"พบข้อมูล {len(df_payment):,} รายการ")

    st.download_button(
        "📥 ดาวน์โหลดรายงานการรับชำระหนี้ (Excel)",
        data=df_to_excel_bytes(df_payment, "payment"),
        file_name="payment_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# =====================================================
# FOOTER
# =====================================================
st.markdown("---")
st.markdown(
    "<p style='text-align:center; color:gray;'>Sales Bill Converter | Streamlit</p>",
    unsafe_allow_html=True
)
