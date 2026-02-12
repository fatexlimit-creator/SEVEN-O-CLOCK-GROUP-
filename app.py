import streamlit as st
import pdfplumber
from openai import OpenAI
import os

# ================= 配置区 =================
# 页面基础设置
st.set_page_config(
    page_title="7-Trade 单证风控中台",
    page_icon="🚢",
    layout="wide"
)

# ================= 核心逻辑区 =================

def extract_text_from_pdf(uploaded_file):
    """从PDF提取文字"""
    text = ""
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
    except Exception as e:
        return f"读取错误: {e}"
    return text

def analyze_with_ai(doc_text, doc_type, api_key):
    """调用 AI 进行风控审查 (DeepSeek 专用版)"""
    
    # 1. 强制清洗 Key：去掉前后可能复制进去的空格
    clean_key = api_key.strip()
    
    # 2. 强制指定 DeepSeek 的地址 (绝对不能错)
    client = OpenAI(
        api_key=clean_key, 
        base_url="https://api.deepseek.com" 
    )

    # 核心指令：扮演老练的单证专家
    system_prompt = """
    你是一位拥有20年经验的国际贸易单证专家，服务于 'Seven O'Clock Resources'。
    请审查用户上传的贸易单据。
    
    请执行以下风控检查：
    1. **软条款陷阱**：查找是否有 'Receipt of Goods'、'Quality Certificate by Applicant' 等条款。
    2. **关键数据核对**：检查金额、最迟装运期、溢短装条款。
    3. **特殊风险**：孟加拉信用证的特殊扣费或中转行限制。
    4. **一致性检查**：检查单单一致。
    
    输出格式要求：使用 Markdown，包含【高危风险预警】、【需注意细节】、【操作建议】。
    """

    user_prompt = f"请审查以下 {doc_type} 文件的内容：\n\n{doc_text[:10000]}"

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",  # 强制指定 DeepSeek 模型名
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            stream=False
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ AI 连接失败: {e}\n\n请检查：\n1. DeepSeek 官网是否有余额？\n2. Key 是否复制完整？" f"AI 连接失败: {e} (请检查 API Key 是否正确)"

# ================= 界面 UI 区 =================

# 侧边栏
with st.sidebar:
    st.image("https://img.icons8.com/color/96/polyester.png", width=50) # 可以换成您的 Logo URL
    st.title("Seven O'Clock Resources")
    st.markdown("---")
    api_key_input = st.text_input("请输入 AI 密钥 (API Key)", type="password")
    st.info("💡 密钥仅保存在当前浏览器，刷新即消失，安全无忧。")
    st.markdown("---")
    st.markdown("**支持文件类型**：\n- 信用证 (LC)\n- 采购合同 (PO)\n- 形式发票 (PI)")

# 主界面
st.title("🛡️ 7-Trade 智能单证风控中心")
st.markdown("### Upload Documents & Detect Risks Instantly")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📂 步骤 1：上传文件")
    uploaded_file = st.file_uploader("拖拽 PDF 文件到这里", type=["pdf"])
    
    doc_type = st.selectbox(
        "这是什么文件？",
        ("信用证 (L/C)", "销售合同 (SC)", "银行托收指示 (Collection)")
    )

    if uploaded_file and api_key_input:
        if st.button("🚀 开始 AI 极速审单", type="primary"):
            with st.spinner("AI 正在逐字阅读条款，请寻找潜在陷阱..."):
                # 1. 提取文字
                file_text = extract_text_from_pdf(uploaded_file)
                # 2. AI 分析
                if len(file_text) > 50:
                    result = analyze_with_ai(file_text, doc_type, api_key_input)
                    st.session_state['result'] = result
                else:
                    st.error("文件内容为空或无法识别，请上传清晰的 PDF。")

with col2:
    st.subheader("📊 步骤 2：风控报告")
    if 'result' in st.session_state:
        st.success("分析完成！")
        st.markdown(st.session_state['result'])
        st.download_button(
            label="📥 下载风控报告",
            data=st.session_state['result'],
            file_name="Risk_Report.md",
            mime="text/markdown"
        )
    else:
        st.info("👈 请在左侧上传文件并点击开始按钮")

# 底部版权
st.markdown("---")
st.caption("© 2026 Seven O'Clock Resources | Internal Use Only | Powered by 7-Trade OS")

