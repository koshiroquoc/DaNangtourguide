import streamlit as st

# ---- PAGE CONFIG ----
st.set_page_config(page_title="Da Nang Tour Guide", layout="wide")

# ---- CUSTOM CSS (bổ sung invisible button + pretty button) ----
st.markdown("""
    <style>
    .stApp {
        background: url('http://127.0.0.1:8888/localguide_assistant/Images/background.jpg') no-repeat center center fixed;
        background-size: cover;
    }
    .centered-block {
        background: rgba(10, 22, 40, 0.44);
        border-radius: 1.5rem;
        padding: 2rem 3rem;
        margin-top: 4vh;
        margin-bottom: 2vh;
        box-shadow: 0 4px 32px 0 rgba(0,0,0,0.19);
        max-width: 600px;
        margin-left: auto;
        margin-right: auto;
        position: relative;
    }
    .custom-btn-row {
        position: relative;
        width: 440px;
        margin: 0 auto 1.5em auto;
        height: 64px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .invisible-btn > button {
        background: transparent !important;
        color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        width: 132px; height: 60px;
        margin: 0;
        padding: 0;
        position: absolute;
        z-index: 2;
        cursor: pointer;
        left: 0; top: 0;
    }
    .invisible-btn.btn2 > button { left: 154px;}
    .invisible-btn.btn3 > button { left: 308px;}
    .pretty-btn {
        position: absolute;
        z-index: 1;
        width: 132px; height: 60px;
        border-radius: 999px;
        background: rgba(255,255,255,0.93);
        color: #232b2b;
        font-size: 1.23rem;
        font-weight: 800;
        border: none;
        left: 0; top: 0;
        text-align: center;
        line-height: 60px;
        pointer-events: none;
        box-shadow: 0 1px 8px 0 rgba(0,0,0,0.12);
        transition: background 0.18s;
    }
    .pretty-btn.btn2 { left: 154px;}
    .pretty-btn.btn3 { left: 308px;}
    .contact-me {
        background: rgba(10, 22, 40, 0.33);
        border-radius: 2rem;
        color: #fff;
        padding: 0.75rem 2rem;
        margin-top: 9vh;
        margin-left: auto;
        margin-right: auto;
        text-align: center;
        max-width: 400px;
        font-size: 1.12rem;
    }
    </style>
""", unsafe_allow_html=True)

if "page" not in st.session_state:
    st.session_state.page = "menu"
if "category" not in st.session_state:
    st.session_state.category = None

def go_to_chat(category):
    st.session_state.category = category
    st.session_state.page = "chat"

def go_back():
    st.session_state.page = "menu"

# ==== TRANG MENU ====
if st.session_state.page == "menu":
    st.markdown("""
        <div class="centered-block">
            <h2 style="color:white; font-family: 'Comic Sans MS', cursive, sans-serif; font-size: 2.25rem; margin-bottom:0.2em; text-align:center">
                Welcome to Da Nang Tour Guide
            </h2>
            <p style="color:#f7f7f7; text-align:center; font-size:1.25rem;">
                I'm your smart local guide for food, fun, and stay in Da Nang.<br>Let's start!
            </p>
            <div class="custom-btn-row" style="margin-top:2.6em; margin-bottom:2.5em;">
                <!-- Invisible button + overlay pretty-btn -->
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Nút invisible + overlay viên thuốc bằng markdown
    # Sử dụng st.markdown để chèn vào .custom-btn-row
    st.markdown("""
        <div class="custom-btn-row">
            <div class="invisible-btn btn1">
                {}
            </div>
            <div class="invisible-btn btn2">
                {}
            </div>
            <div class="invisible-btn btn3">
                {}
            </div>
            <div class="pretty-btn btn1">Eat</div>
            <div class="pretty-btn btn2">See</div>
            <div class="pretty-btn btn3">Stay</div>
        </div>
    """.format(
        st.button("", key="eat"),
        st.button("", key="see"),
        st.button("", key="stay")
    ), unsafe_allow_html=True)

    # Xử lý sự kiện
    if st.session_state.get("eat"):
        go_to_chat("eat")
    if st.session_state.get("see"):
        go_to_chat("see")
    if st.session_state.get("stay"):
        go_to_chat("stay")

    # Contact dưới cùng
    st.markdown("""
        <div class="contact-me">
            Contact me: <span style="letter-spacing:0.25em;">..........</span>
        </div>
    """, unsafe_allow_html=True)

# ==== TRANG CHAT ====
elif st.session_state.page == "chat":
    st.markdown(f"""
        <div class="centered-block">
            <h3 style="color:white;">You selected: <span style="color:#FFDB70">{st.session_state.category.title()}</span></h3>
            <p style="color:#fafafa">💬 Ask me anything about local places!</p>
        </div>
    """, unsafe_allow_html=True)
    user_input = st.text_input("Your question:")
    if user_input:
        from Hybridsearch import rag
        response = rag(user_input, type_filter=st.session_state.category)
        st.success(response)
    st.button("🔙 Back", on_click=go_back)
