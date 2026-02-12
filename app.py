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

# ================= 配置区 =================
st.set_page_config(
    page_title="7-Trade 交易中台 (归档版)",
    page_icon="🗂️",
    layout="wide"
)

# === 全局状态初始化 ===
# 1. 控制清空逻辑的 ID
if 'audit_session_id' not in st.session_state:
    st.session_state.audit_session_id = 0

# 2. 存储审核记录（管理员数据）
if 'audit_history' not in st.session_state:
    st.session_state.audit_history = []

# ================= 核心工具区 =================

def read_docx(file):
    try:
        doc = docx.Document(file)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except:
        return "Word 读取失败"

def read_pdf_with_ocr(file):
    text = ""
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted: text += extracted + "\n"
    except: pass

    if len(text) < 50: # 触发 OCR
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
        file.seek(0) # 确保从头读取
        fname = file.name.lower()
        content = ""
        try:
            if fname.endswith(".docx"): content = read_docx(file)
            elif fname.endswith(".pdf"): content = read_pdf_with_ocr(file)
            combined_text += f"\n=== 文件: {file.name} ===\n{content}\n"
        except Exception as e:
            combined_text += f"读取错误: {e}\n"
    return combined_text

def analyze_cross_check(po_text, req_text, docs_text, mode, api_key):
    client = OpenAI(api_key=api_key.strip(), base_url="https://api.deepseek.com")
    
    if mode == "信用证 (L/C)":
        focus = "比对【单据】是否符合【信用证】及【合同】。"
    elif mode == "托收 (CAD/DP)":
        focus = "比对【单据】是否符合【银行指示】。"
    else:
        focus = "比对【单据】是否符合【合同】。"

    prompt = f"""
    你是 Seven O'Clock Resources 的单证风控专家。
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
    except Exception as e:
        return f"AI 连接失败: {e}"

def create_archive_zip(contract_no, files_map):
    """生成归档压缩包"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for original_file, file_type in files_map:
            if original_file:
                # 重命名逻辑：合同号_文件类型_已审核.后缀
                ext = original_file.name.split('.')[-1]
                new_name = f"{contract_no}_{file_type}_已审核.{ext}"
                original_file.seek(0)
                zf.writestr(new_name, original_file.read())
    return zip_buffer.getvalue()

# ================= 界面 UI 区 =================

# 侧边栏设置
with st.sidebar:
    st.image("https://img.icons8.com/color/96/polyester.png", width=50)
    st.title("7-Trade")
    
    # API KEY
    api_key = st.text_input("DeepSeek Key", type="password")
    
    st.markdown("---")
    # 模式选择
    mode = st.radio("交易模式", ("信用证 (L/C)", "电汇 (T/T)", "托收 (CAD/DP)"))
    
    st.markdown("---")
    # 下一单按钮
    if st.button("🗑️ 清空/下一单", type="primary"):
        st.session_state.audit_session_id += 1
        st.rerun()

# 主界面：Tabs 分页（这里修改了名字）
tab1, tab2 = st.tabs(["🕵️‍♀️ 单证·审核台", "👨‍💼 管理员·数据台"])

# === Tab 1: 单证·审核台 ===
with tab1:
    st.caption(f"当前批次: #{st.session_state.audit_session_id}")
    
    # 1. 强制录入合同号
    col_input, col_info = st.columns([1, 2])
    with col_input:
        contract_no = st.text_input("📝 合同号 (必填)", placeholder="例如: PO-20260212")
    with col_info:
        if contract_no:
            st.success(f"当前归档文件将命名为：**{contract_no}_..._已审核**")
        else:
            st.warning("👈 请先输入合同号，否则无法开始审核。")

    # 2. 上传区 (动态 Key)
    s_key = str(st.session_state.audit_session_id)
    c1, c2, c3 = st.columns(3)
    
    with c1:
        f_po = st.file_uploader("1. 销售合同", type=["pdf","docx"], key=f"po_{s_key}")
    with c2:
        if mode == "电汇 (T/T)":
            st.info("T/T 无需要求文件")
            f_req = None
        else:
            f_req = st.file_uploader("2. 信用证/要求", type=["pdf","docx"], key=f"req_{s_key}")
    with c3:
        f_docs = st.file_uploader("3. 出口单据", type=["pdf","docx"], accept_multiple_files=True, key=f"doc_{s_key}")

    # 3. 执行审核
    st.markdown("---")
    if st.button("🚀 开始 AI 审核 & 归档", type="secondary"):
        if not api_key: st.error("缺 API Key")
        elif not contract_no: st.error("❌ 必须填写合同号才能归档！")
        elif not f_po or not f_docs: st.error("请上传完整文件")
        else:
            with st.spinner("AI 正在读取文件并进行交叉比对..."):
                # 提取文字
                t_po = extract_text_smart(f_po)
                t_req = extract_text_smart(f_req) if f_req else "无"
                t_docs = extract_text_smart(f_docs)
                
                # AI 分析
                result = analyze_cross_check(t_po, t_req, t_docs, mode, api_key)
                
                # 记录到历史
                risk_tag = "🔴 高危" if "致命" in result else "🟢 安全"
                
                st.session_state.audit_history.append({
                    "时间": time.strftime("%H:%M:%S"),
                    "合同号": contract_no,
                    "模式": mode,
                    "结果摘要": risk_tag
                })
                
                # 显示结果
                st.success(f"✅ 合同 {contract_no} 审核完成！")
                st.markdown(result)
                
                # 生成归档包
                files_to_zip = [(f_po, "合同")]
                if f_req: files_to_zip.append((f_req, "要求"))
                if f_docs:
                    for doc in f_docs: files_to_zip.append((doc, "单据"))
                
                zip_data = create_archive_zip(contract_no, files_to_zip)
                
                st.download_button(
                    label=f"📥 下载归档包 ({contract_no}_已审核.zip)",
                    data=zip_data,
                    file_name=f"{contract_no}_已审核.zip",
                    mime="application/zip",
                    help="文件会自动重命名并打包。"
                )

# === Tab 2: 管理员·数据台 ===
with tab2:
    st.subheader("📊 今日审核记录 (实时)")
    st.caption("注意：刷新网页后记录会清空，请及时查看。")
    
    if st.session_state.audit_history:
        df = pd.DataFrame(st.session_state.audit_history)
        st.dataframe(df, use_container_width=True)
        
        total = len(df)
        high_risk = len(df[df['结果摘要'] == "🔴 高危"])
        st.metric("今日审核总数", f"{total} 单", delta=f"{high_risk} 单高危风险", delta_color="inverse")
    else:
        st.info("📭 今日暂无审核记录")
