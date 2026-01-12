# bill.py
# -*- coding: utf-8 -*-

import io
import pandas as pd
import streamlit as st
import numpy as np

# ================= PAGE CONFIG =================
st.set_page_config(
    page_title="Sales & Payment Converter",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ================= CUSTOM CSS =================
st.markdown(
    """
<style>
.main { padding: 2rem; }
.header-container {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 2.5rem 2rem;
    border-radius: 15px;
    margin-bottom: 2rem;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
.header-title {
    color: white; font-size: 2.5rem; font-weight: 700; margin: 0; text-align: center;
}
.header-subtitle {
    color: rgba(255,255,255,0.9); font-size: 1.1rem; text-align: center; margin-top: .5rem;
}
.upload-section {
    background: white; padding: 2rem; border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    margin-bottom: 2rem; border: 2px dashed #e0e0e0;
}
.success-card {
    background: linear-gradient(135deg, #d4f1d4 0%, #b8e6b8 100%);
    padding: 1.5rem; border-radius: 10px; margin: 1rem 0; border-left: 4px solid #28a745;
}
.dataframe-container {
    background: white; padding: 1.5rem; border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin: 1.5rem 0;
}
.stDownloadButton button {
    width: 100%;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white; border: none; padding: .75rem 1.5rem; border-radius: 8px; font-weight: 600;
}
</style>
""",
    unsafe_allow_html=True,
)

# ================= UTILITIES =================
def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="data")
    return bio.getvalue()


def _norm_cell(x) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip()


def detect_skiprows(file_like, max_scan_rows: int = 60) -> int:
    """Auto-detect header row"""
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


def read_excel_autoskip(uploaded_file):
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


# ================= TRANSFORM: SALES =================
def transform_sales(df: pd.DataFrame) -> pd.DataFrame:

    df["new_col"] = np.where(
        df["Unnamed: 6"].astype(str).str.contains("IN", na=False),
        "-",
        np.where(
            ~df["ใบสั่งขาย"].astype(str).str.contains("-", na=False),
            df["ใบสั่งขาย"],
            df["ใบสั่งขาย"].astype(str).str.split("-", n=1).str[0],
        ),
    )

    mask_dp = df["V"] == "ตัดใบรับมัดจำ#"
    df.loc[mask_dp, "Unnamed: 6"] = "ตัดใบรับมัดจำ#"
    df.loc[mask_dp, "Unnamed: 7"] = df.loc[mask_dp, "ส่วนลด"]
    df.loc[mask_dp, "รวมทั้งสิ้น"] = df.loc[mask_dp, "มูลค่าสินค้า"]

    cols = ["วันที่", "เลขที่", "ลูกค้า", "พนักงานขาย", "เก็บเงิน", "new_col"]
    cols_exist = [c for c in cols if c in df.columns]
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
            "มูลค่าสินค้า": "ราคาต่อหน่วย",
        }
    )

    if "Unnamed: 1" in df.columns:
        df = df.drop(columns=["Unnamed: 1"])

    return df


# ================= TRANSFORM: PAYMENT =================
def transform_payment(df: pd.DataFrame) -> pd.DataFrame:

    mask_re = df["เลขที่ใบเสร็จ"].astype(str).str.contains("RE", na=False)

    df["new_col"] = np.where(mask_re, df["พนักงานขาย"], np.nan)

    df["จำนวนเงินรวมตามใบเสร็จ"] = np.where(mask_re, df["ยอดตามใบกำกับ"], np.nan)

    fill_cols = [
        "วันที่รับชำระ",
        "เลขที่ใบเสร็จ",
        "วันที่",
        "ชื่อลูกค้า",
        "new_col",
        "จำนวนเงินรวมตามใบเสร็จ",
    ]
    df[fill_cols] = df[fill_cols].ffill()

    df = df[df["ตัดเงินมัดจำ"].notna()]

    cols = [
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

    df_result = df.loc[
        df["พนักงานขาย"].astype(str).str.contains("I", na=False),
        cols,
    ]

    return df_result


# ================= HEADER =================
st.markdown(
    """
<div class="header-container">
    <h1 class="header-title">🧾 Sales & Payment Converter</h1>
    <p class="header-subtitle">แปลงไฟล์ใบกำกับสินค้า และ รายงานการรับชำระหนี้</p>
</div>
""",
    unsafe_allow_html=True,
)

# ================= TABS =================
tab1, tab2 = st.tabs(["🧾 รายงานใบกำกับสินค้า", "💰 รายงานการรับชำระหนี้"])


# ================= TAB 1: SALES =================
with tab1:

    st.markdown("### 📁 อัปโหลดไฟล์ใบกำกับสินค้า")

    uploaded_files = st.file_uploader(
        "เลือกไฟล์ Excel (.xlsx)",
        type=["xlsx"],
        accept_multiple_files=True,
        key="sales_upload",
    )

    if not uploaded_files:
        st.info("กรุณาอัปโหลดไฟล์เพื่อเริ่มการแปลงข้อมูล")
        st.stop()

    with st.spinner("กำลังประมวลผล..."):
        dfs = []
        errors = []

        for uf in uploaded_files:
            try:
                df_raw, sk = read_excel_autoskip(uf)
                df_out = transform_sales(df_raw)
                df_out["__source_file__"] = uf.name
                dfs.append(df_out)
            except Exception as e:
                errors.append((uf.name, str(e)))

    if errors:
        st.error("พบข้อผิดพลาดบางไฟล์")
        for n, m in errors:
            st.write(f"- {n}: {m}")

    if not dfs:
        st.stop()

    df_all = pd.concat(dfs, ignore_index=True)

    st.markdown(
        """
    <div class="success-card">
        <h4 style="margin:0;">✅ แปลงข้อมูลใบกำกับสำเร็จ</h4>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.dataframe(df_all.head(100), use_container_width=True, height=400)

    csv_bytes = df_all.to_csv(index=False).encode("utf-8-sig")
    xlsx_bytes = df_to_excel_bytes(df_all)

    c1, c2 = st.columns(2)
    with c1:
        st.download_button("📥 ดาวน์โหลด CSV", csv_bytes, "sales_clean_all.csv", "text/csv", use_container_width=True)
    with c2:
        st.download_button(
            "📥 ดาวน์โหลด Excel",
            xlsx_bytes,
            "sales_clean_all.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


# ================= TAB 2: PAYMENT =================
with tab2:

    st.markdown("### 📁 อัปโหลดไฟล์รายงานการรับชำระ")

    uploaded_files2 = st.file_uploader(
        "เลือกไฟล์ Excel (.xlsx)",
        type=["xlsx"],
        accept_multiple_files=True,
        key="payment_upload",
    )

    if not uploaded_files2:
        st.info("กรุณาอัปโหลดไฟล์เพื่อเริ่มการแปลงข้อมูล")
        st.stop()

    with st.spinner("กำลังประมวลผล..."):
        dfs2 = []
        errors2 = []

        for uf in uploaded_files2:
            try:
                uf.seek(0)
                df_raw = pd.read_excel(uf, skiprows=4)
                df_out = transform_payment(df_raw)
                df_out["__source_file__"] = uf.name
                dfs2.append(df_out)
            except Exception as e:
                errors2.append((uf.name, str(e)))

    if errors2:
        st.error("พบข้อผิดพลาดบางไฟล์")
        for n, m in errors2:
            st.write(f"- {n}: {m}")

    if not dfs2:
        st.stop()

    df_pay_all = pd.concat(dfs2, ignore_index=True)

    st.markdown(
        """
    <div class="success-card">
        <h4 style="margin:0;">✅ แปลงข้อมูลรายการรับชำระสำเร็จ</h4>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.dataframe(df_pay_all.head(100), use_container_width=True, height=400)

    csv_bytes = df_pay_all.to_csv(index=False).encode("utf-8-sig")
    xlsx_bytes = df_to_excel_bytes(df_pay_all)

    c1, c2 = st.columns(2)
    with c1:
        st.download_button("📥 ดาวน์โหลด CSV", csv_bytes, "payment_clean_all.csv", "text/csv", use_container_width=True)
    with c2:
        st.download_button(
            "📥 ดาวน์โหลด Excel",
            xlsx_bytes,
            "payment_clean_all.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


# ================= FOOTER =================
st.markdown("---")
st.markdown(
    '<div style="text-align:center;color:#666;">Sales & Payment Converter v3.0 | Made with ❤️ using Streamlit</div>',
    unsafe_allow_html=True,
)
