import streamlit as st

# ---- PAGE CONFIG ----
st.set_page_config(page_title="Da Nang Tour Guide", layout="wide")

# ---- CUSTOM CSS ----
st.markdown("""
    <style>
    .stApp {
        background: url('http://127.0.0.1:8888/localguide_assistant/Images/background.jpg') no-repeat center center fixed;
        background-size: cover;
    }
    .centered-block {
        background: rgba(10, 22, 40, 0.44);  /* mờ nền */
        border-radius: 1.5rem;
        padding: 2rem 3rem;
        margin-top: 4vh;
        margin-bottom: 2vh;
        box-shadow: 0 4px 32px 0 rgba(0,0,0,0.19);
        max-width: 600px;
        margin-left: auto;
        margin-right: auto;
    }
    .pill-btn {
        display: inline-block;
        padding: 0.75rem 2.5rem;
        border-radius: 999px;
        border: none;
        background: rgba(255,255,255,0.85);
        color: #242c36;
        font-weight: 700;
        font-size: 1.25rem;
        margin: 0 18px;
        box-shadow: 0 1px 8px 0 rgba(0,0,0,0.13);
        transition: background 0.2s;
        cursor: pointer;
        text-align: center;
    }
    .pill-btn:hover {
        background: #FFDB70;
        color: #2e2e2e;
    }
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

# ---- MAIN UI ----
if "page" not in st.session_state:
    st.session_state.page = "menu"

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
            <div style="text-align:center; margin:2rem 0 2rem 0;">
                <form action="" method="post">
                    <button class="pill-btn" name="eat" type="submit" formmethod="post">Eat</button>
                    <button class="pill-btn" name="see" type="submit" formmethod="post">See</button>
                    <button class="pill-btn" name="stay" type="submit" formmethod="post">Stay</button>
                </form>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Xử lý click
    if st.session_state.get('form_submitted', False):
        st.session_state.form_submitted = False  # reset
    else:
        # Hack để detect click từng nút bằng query param, hoặc dùng st.form nhưng custom button đẹp hơn với HTML
        import streamlit.components.v1 as components
        clicked = st.query_params.get("eat") or st.query_params.get("see") or st.query_params.get("stay")
        if clicked:
            if st.query_params.get("eat"):
                go_to_chat("eat")
            elif st.query_params.get("see"):
                go_to_chat("see")
            elif st.query_params.get("stay"):
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
