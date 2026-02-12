import streamlit as st
import pdfplumber
from openai import OpenAI

# ================= 配置区 =================
st.set_page_config(
    page_title="7-Trade 智能单证风控 Pro",
    page_icon="⚖️",
    layout="wide"
)

# ================= 核心逻辑区 =================

def extract_text_from_files(uploaded_files):
    """从多个PDF提取文字，并合并"""
    combined_text = ""
    if not uploaded_files:
        return "（未上传）"
    
    # 如果是单个文件，转为列表处理
    if not isinstance(uploaded_files, list):
        uploaded_files = [uploaded_files]

    for file in uploaded_files:
        try:
            with pdfplumber.open(file) as pdf:
                file_content = ""
                for page in pdf.pages:
                    file_content += page.extract_text() + "\n"
                combined_text += f"\n--- 文件名: {file.name} ---\n{file_content}\n"
        except Exception as e:
            return f"读取错误 {file.name}: {e}"
    return combined_text

def analyze_cross_check(po_text, requirement_text, docs_text, mode, api_key):
    """调用 DeepSeek 进行交叉比对"""
    
    clean_key = api_key.strip()
    client = OpenAI(api_key=clean_key, base_url="https://api.deepseek.com")

    # 根据不同模式，定制不同的 Prompt
    if mode == "信用证 (L/C)":
        check_focus = "重点比对：1.【单据】是否完全符合【信用证】的所有条款（特别是46A/47A条款）。2.【单据】金额和数量是否在【合同】允许范围内。"
    elif mode == "托收 (CAD/DP)":
        check_focus = "重点比对：1.【单据】是否符合【银行托收指示】的要求。2. 提单收货人（Consignee）是否按指示填写（防止无单放货）。"
    else: # TT
        check_focus = "重点比对：【单据】内容（品名、金额、收货人）是否与【销售合同】完全一致。"

    system_prompt = f"""
    你亦是 Seven O'Clock Resources 的首席单证专家。现在的任务是进行【多方单据交叉审核】。
    
    当前业务模式：{mode}
    {check_focus}
    
    请严格检查以下三个维度的逻辑一致性：
    1. **销售合同 (PO)**：这是我们就答应给客户的东西。
    2. **要求文件 (L/C 或 托收指示)**：这是客户或银行要求我们必须怎么做。
    3. **出口单据 (Docs)**：这是单证员实际做出来的文件（发票、箱单、提单等）。
    
    请找出“单证不符”、“单单不符”的错误，例如：
    - 信用证要求 Latest Shipment 是 15号，但提单是 20号。
    - 合同是 CIF 条款，但发票上没写保险费。
    - 毛重在箱单上是 1000kg，提单上却是 1005kg。
    
    输出格式：
    🚨 **致命错误** (影响收款的硬伤)
    ⚠️ **一般疑点** (可能是笔误)
    ✅ **一致性确认** (主要信息核对无误)
    """

    user_prompt = f"""
    【1. 我们的销售合同 PO】:
    {po_text[:5000]}
    
    【2. 客户/银行要求 (L/C 或 指示)】:
    {requirement_text[:5000]}
    
    【3. 我们做的出口单据 (发票/箱单/提单)】:
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
    st.markdown("## ⚙️ 设置")
    api_key_input = st.text_input("DeepSeek API Key", type="password")
    
    st.markdown("---")
    st.markdown("### 🛠️ 业务模式选择")
    mode = st.radio(
        "请选择本次交易方式：",
        ("信用证 (L/C)", "电汇 (T/T)", "托收 (CAD/DP)")
    )

st.title(f"🛡️ 智能单证风控 Pro - {mode} 模式")
st.info("💡 请分别上传对应的文件，AI 将自动进行【三单匹配】找茬。")

# 根据选择的模式，显示不同的上传框
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("1️⃣ 销售合同 (PO)")
    file_po = st.file_uploader("上传发给客户的合同", type="pdf", key="po")

with col2:
    if mode == "电汇 (T/T)":
        st.subheader("🚫 (T/T 无需此项)")
        file_req = None
        st.caption("电汇模式主要比对合同和单据。")
    else:
        title = "2️⃣ 信用证 (L/C)" if mode == "信用证 (L/C)" else "2️⃣ 托收指示/银行信息"
        st.subheader(title)
        file_req = st.file_uploader("上传客户/银行发来的要求", type="pdf", key="req")

with col3:
    st.subheader("3️⃣ 出口全套单据")
    # accept_multiple_files=True 允许一次把发票、箱单、提单全拖进去
    files_docs = st.file_uploader("上传做好的发票/箱单/提单", type="pdf", accept_multiple_files=True, key="docs")

# 开始按钮
st.markdown("---")
if st.button("🚀 开始 AI 交叉稽核", type="primary"):
    if not api_key_input:
        st.error("请先在左侧输入 API Key")
    elif not file_po:
        st.error("请至少上传销售合同！")
    elif not files_docs:
        st.error("请上传出口单据！")
    else:
        with st.spinner("AI 正在同时阅读多份文件，进行逻辑碰撞..."):
            # 1. 提取文字
            text_po = extract_text_from_files(file_po)
            text_req = extract_text_from_files(file_req) if file_req else "（无额外要求，以合同为准）"
            text_docs = extract_text_from_files(files_docs)
            
            # 2. 发送给 AI
            result = analyze_cross_check(text_po, text_req, text_docs, mode, api_key_input)
            
            # 3. 显示结果
            st.success("审核完成！")
            st.markdown(result)
