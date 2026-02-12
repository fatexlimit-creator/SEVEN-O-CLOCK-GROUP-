import streamlit as st
import pdfplumber
from openai import OpenAI
import docx
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import io

# ================= 配置区 =================
st.set_page_config(
    page_title="7-Trade 智能单证风控 Pro (OCR版)",
    page_icon="👁️",
    layout="wide"
)

# ================= 核心工具区 =================

def read_docx(file):
    """读取 Word 文档 (.docx)"""
    try:
        doc = docx.Document(file)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception as e:
        return f"Word 读取失败: {e} (请确保是 .docx 格式，不是老版 .doc)"

def read_pdf_with_ocr(file):
    """读取 PDF (包含扫描件 OCR)"""
    text = ""
    # 1. 尝试直接提取文本 (针对电子版 PDF)
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except:
        pass

    # 2. 如果提取的字数太少（<50字），说明可能是扫描件，启动 OCR
    if len(text) < 50:
        file.seek(0) # 重置指针
        try:
            # 将 PDF 每一页转为图片
            images = convert_from_bytes(file.read())
            ocr_text = ""
            for i, image in enumerate(images):
                # 调用 OCR 引擎识别图片中的文字
                page_content = pytesseract.image_to_string(image, lang='eng') # 默认识别英文
                ocr_text += f"\n--- 第 {i+1} 页 (OCR识别) ---\n{page_content}\n"
            
            # 如果 OCR 识别出了内容，就用 OCR 的结果
            if len(ocr_text) > len(text):
                text = ocr_text
        except Exception as e:
            return f"OCR 识别失败: {e} (请检查 packages.txt 是否配置正确)"
            
    return text

def extract_text_smart(uploaded_files):
    """智能识别文件类型并提取文字"""
    combined_text = ""
    if not uploaded_files:
        return "（未上传）"
    
    if not isinstance(uploaded_files, list):
        uploaded_files = [uploaded_files]

    for file in uploaded_files:
        file_name = file.name.lower()
        content = ""
        
        try:
            if file_name.endswith(".docx"):
                content = read_docx(file)
            elif file_name.endswith(".pdf"):
                content = read_pdf_with_ocr(file)
            else:
                content = "不支持的文件格式 (仅支持 PDF 或 DOCX)"
                
            combined_text += f"\n=== 文件: {file.name} ===\n{content}\n"
        except Exception as e:
            combined_text += f"\n读取错误 {file.name}: {e}\n"
            
    return combined_text

def analyze_cross_check(po_text, requirement_text, docs_text, mode, api_key):
    """DeepSeek 交叉比对"""
    clean_key = api_key.strip()
    client = OpenAI(api_key=clean_key, base_url="https://api.deepseek.com")

    if mode == "信用证 (L/C)":
        check_focus = "重点比对：1.【单据】是否完全符合【信用证】扫描件的所有条款。2. 扫描件可能存在识别误差，请结合上下文判断。"
    elif mode == "托收 (CAD/DP)":
        check_focus = "重点比对：【单据】是否符合【银行托收指示】的要求。"
    else: 
        check_focus = "重点比对：【单据】与【销售合同】的一致性。"

    system_prompt = f"""
    你是 Seven O'Clock Resources 的单证风控专家。
    当前任务：{mode} 模式下的多方单据交叉审核。
    
    注意：部分内容可能来自 OCR 识别（扫描件），可能会有乱码或拼写错误（如 '0' 被识别为 'O'），请利用上下文智能纠错并理解。
    
    请严格检查逻辑一致性：
    1. **销售合同 (PO)**
    2. **要求文件 (L/C 或 托收指示)**
    3. **出口单据 (Docs)**
    
    请找出“单证不符”、“单单不符”的错误。
    输出格式：🚨 **致命错误**、⚠️ **一般疑点**、✅ **一致性确认**。
    """

    user_prompt = f"""
    【1. 销售合同 PO】:
    {po_text[:6000]}
    
    【2. 客户/银行要求】:
    {requirement_text[:6000]}
    
    【3. 出口单据】:
    {docs_text[:8000]}
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            stream=False
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI 连接失败: {e}"

# ================= 界面 UI 区 =================

with st.sidebar:
    st.title("Seven O'Clock")
    st.markdown("### ⚙️ 核心设置")
    api_key_input = st.text_input("DeepSeek API Key", type="password")
    
    st.markdown("---")
    st.markdown("### 🛠️ 业务模式")
    mode = st.radio("选择交易方式：", ("信用证 (L/C)", "电汇 (T/T)", "托收 (CAD/DP)"))
    st.info("💡 已支持：\n- Word 合同 (.docx)\n- 扫描件 PDF (自动OCR)")

st.title(f"🛡️ 智能单证风控 Pro (OCR增强版)")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("1️⃣ 销售合同 (PO)")
    # 增加 docx 支持
    file_po = st.file_uploader("上传合同 (PDF/Word)", type=["pdf", "docx"], key="po")

with col2:
    if mode == "电汇 (T/T)":
        st.subheader("🚫 (T/T 无需此项)")
        file_req = None
    else:
        title = "2️⃣ 信用证 (L/C)" if mode == "信用证 (L/C)" else "2️⃣ 托收指示"
        st.subheader(title)
        # 增加 docx 支持 (虽然LC一般是PDF)
        file_req = st.file_uploader("上传扫描件/要求", type=["pdf", "docx"], key="req")

with col3:
    st.subheader("3️⃣ 出口全套单据")
    files_docs = st.file_uploader("上传单据", type=["pdf", "docx"], accept_multiple_files=True, key="docs")

st.markdown("---")
if st.button("🚀 开始 AI 交叉稽核 (含OCR)", type="primary"):
    if not api_key_input:
        st.error("请先输入 API Key")
    elif not file_po:
        st.error("请至少上传销售合同！")
    elif not files_docs:
        st.error("请上传出口单据！")
    else:
        with st.spinner("正在启动 OCR 引擎识别扫描件，并进行交叉比对... (扫描件处理较慢，请稍候)"):
            text_po = extract_text_smart(file_po)
            text_req = extract_text_smart(file_req) if file_req else "（无要求）"
            text_docs = extract_text_smart(files_docs)
            
            result = analyze_cross_check(text_po, text_req, text_docs, mode, api_key_input)
            
            st.success("审核完成！")
            st.markdown(result)
