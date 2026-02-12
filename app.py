import streamlit as st
import pdfplumber
from openai import OpenAI
import docx
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import io
import time
import pandas as pd
import zipfile
import base64

# ================= 配置区 =================
st.set_page_config(
    page_title="Seven O'Clock Group - 智能交易中台",
    page_icon="🏢",
    layout="wide"
)

# === 视觉优化：注入专业的行业背景图 ===
page_bg_img = """
<style>
[data-testid="stAppViewContainer"] {
    background-image: url("https://images.unsplash.com/photo-1555697723-55f8974e093d?q=80&w=2070&auto=format&fit=crop");
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    background-attachment: fixed;
}
[data-testid="stAppViewContainer"]::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.7);
    z-index: -1;
}
[data-testid="stSidebar"] {
    background-color: rgba(28, 31, 45, 0.85) !important;
    backdrop-filter: blur(10px);
    border-right: 1px solid rgba(255, 255, 255, 0.1);
}
header[data-testid="stHeader"] {
    background-color: transparent !important;
}
[data-testid="stExpander"], [data-testid="stForm"] {
    background-color: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
}
</style>
"""
st.markdown(page_bg_img, unsafe_allow_html=True)

# === 嵌入公司 LOGO (Base64编码) ===
LOGO_BASE64 = "data:image/png;base64,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"

with st.sidebar:
    col_logo, col_text = st.columns([1, 3])
    with col_logo:
        st.image(LOGO_BASE64, width=60)
    with col_text:
        st.markdown(
            """
            <div style="
                display: flex; 
                align-items: center; 
                height: 60px; 
                color: white; 
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                font-weight: 600;
            ">
                <span style="font-size: 1.2rem; line-height: 1.2;">SEVEN O'CLOCK<br>GROUP</span>
            </div>
            """, 
            unsafe_allow_html=True
        )
    
    api_key = st.text_input("DeepSeek Key", type="password")
    st.markdown("---")
    mode = st.radio("交易模式", ("信用证 (L/C)", "电汇 (T/T)", "托收 (CAD/DP)"))
    st.markdown("---")
    if st.button("🗑️ 清空/下一单", type="primary"):
        st.session_state.audit_session_id += 1
        st.rerun()

# === 全局状态初始化 ===
if 'audit_session_id' not in st.session_state:
    st.session_state.audit_session_id = 0
if 'audit_history' not in st.session_state:
    st.session_state.audit_history = []

# ================= 核心工具区 =================
def read_docx(file):
    try:
        doc = docx.Document(file)
        return "\n".join([para.text for para in doc.paragraphs])
    except: return "Word 读取失败"

def read_pdf_with_ocr(file):
    text = ""
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted: text += extracted + "\n"
    except: pass
    if len(text) < 50:
        file.seek(0)
        try:
            images = convert_from_bytes(file.read())
            ocr_text = ""
            for i, image in enumerate(images):
                page_content = pytesseract.image_to_string(image, lang='eng')
                ocr_text += f"\n[OCR Page {i+1}]\n{page_content}\n"
            if len(ocr_text) > len(text): text = ocr_text
        except: pass
    return text

def extract_text_smart(uploaded_files):
    combined_text = ""
    if not uploaded_files: return "（未上传）"
    if not isinstance(uploaded_files, list): uploaded_files = [uploaded_files]
    for file in uploaded_files:
        file.seek(0)
        fname = file.name.lower()
        content = ""
        try:
            if fname.endswith(".docx"): content = read_docx(file)
            elif fname.endswith(".pdf"): content = read_pdf_with_ocr(file)
            combined_text += f"\n=== 文件: {file.name} ===\n{content}\n"
        except Exception as e: combined_text += f"读取错误: {e}\n"
    return combined_text

def analyze_cross_check(po_text, req_text, docs_text, mode, api_key):
    client = OpenAI(api_key=api_key.strip(), base_url="https://api.deepseek.com")
    prompt = f"""
    你是 Seven O'Clock Group 的单证风控专家。
    任务：{mode} 模式下的多方交叉审核。
    
    请严格检查以下文件的逻辑一致性，找出“单证不符”或“单单不符”。
    
    1. **合同**: {po_text[:4000]}
    2. **要求**: {req_text[:4000]}
    3. **单据**: {docs_text[:6000]}
    
    输出要求：
    - 请先给出一个总体评分（满分100，越高越安全）。
    - 🚨 **致命错误** (影响收款的)
    - ⚠️ **一般疑点** (需确认的)
    - ✅ **通过项**
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e: return f"AI 连接失败: {e}"

def create_archive_zip(contract_no, files_map):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for original_file, file_type in files_map:
            if original_file:
                ext = original_file.name.split('.')[-1]
                new_name = f"{contract_no}_{file_type}_已审核.{ext}"
                original_file.seek(0)
                zf.writestr(new_name, original_file.read())
    return zip_buffer.getvalue()

# ================= 主界面 =================
tab1, tab2 = st.tabs(["🕵️‍♀️ 单证·审核台", "👨‍💼 管理员·数据台"])

with tab1:
    with st.container():
        st.caption(f"当前批次: #{st.session_state.audit_session_id}")
        col_input, col_info = st.columns([1, 2])
        with col_input:
            contract_no = st.text_input("📝 合同号 (必填)", placeholder="例如: PO-20260212")
        with col_info:
            if contract_no: st.success(f"归档命名预览：**{contract_no}_..._已审核.zip**")
            else: st.warning("👈 请输入合同号以启动 AI 审核引擎。")

        s_key = str(st.session_state.audit_session_id)
        c1, c2, c3 = st.columns(3)
        with c1:
            f_po = st.file_uploader("1. 销售合同 (PO)", type=["pdf","docx"], key=f"po_{s_key}")
        with c2:
            if mode == "电汇 (T/T)":
                st.info("T/T 模式：无需上传要求文件。")
                f_req = None
            else:
                title = "2. 信用证(L/C) / 要求" if mode == "信用证 (L/C)" else "2. 银行托收指示"
                f_req = st.file_uploader(title, type=["pdf","docx"], key=f"req_{s_key}")
        with c3:
            f_docs = st.file_uploader("3. 出口全套单据", type=["pdf","docx"], accept_multiple_files=True, key=f"doc_{s_key}")

        st.markdown("---")
        if st.button("🚀 启动 AI 交叉风控引擎", type="secondary"):
            if not api_key: st.error("请在左侧侧边栏输入 DeepSeek API Key")
            elif not contract_no: st.error("❌ 无法归档：请填写合同号")
            elif not f_po or not f_docs: st.error("文件不全：请至少上传销售合同和出口单据")
            else:
                with st.spinner("AI 引擎正在读取文件、识别扫描件并进行逻辑碰撞..."):
                    t_po = extract_text_smart(f_po)
                    t_req = extract_text_smart(f_req) if f_req else "无要求"
                    t_docs = extract_text_smart(f_docs)
                    result = analyze_cross_check(t_po, t_req, t_docs, mode, api_key)
                    risk_tag = "🔴 高危" if "致命" in result else "🟢 安全"
                    st.session_state.audit_history.append({
                        "时间": time.strftime("%H:%M:%S"),
                        "合同号": contract_no,
                        "模式": mode,
                        "结果摘要": risk_tag
                    })
                    st.success(f"✅ 合同 {contract_no} 风控扫描完成！")
                    with st.expander("📄 点击查看详细风控报告", expanded=True):
                        st.markdown(result)
                    files_to_zip = [(f_po, "合同")]
                    if f_req: files_to_zip.append((f_req, "要求"))
                    if f_docs:
                        for doc in f_docs: files_to_zip.append((doc, "单据"))
                    zip_data = create_archive_zip(contract_no, files_to_zip)
                    st.download_button(
                        label=f"📥 下载归档包 ({contract_no}_已审核.zip)",
                        data=zip_data,
                        file_name=f"{contract_no}_已审核.zip",
                        mime="application/zip"
                    )

with tab2:
    with st.container():
        st.subheader("📊 今日风控数据看板 (实时)")
        if st.session_state.audit_history:
            df = pd.DataFrame(st.session_state.audit_history)
            def highlight_risk(val):
                color = '#ff4b4b' if val == '🔴 高危' else '#09ab3b'
                return f'color: {color}; font-weight: bold;'
            st.dataframe(df.style.map(highlight_risk, subset=['结果摘要']), use_container_width=True)
            total = len(df)
            high_risk = len(df[df['结果摘要'] == "🔴 高危"])
            st.metric("今日审核总量", f"{total} 单", delta=f"{high_risk} 单存在高危风险", delta_color="inverse")
        else:
            st.info("📭 今日暂无审核记录，请前往「单证·审核台」开始工作。")
