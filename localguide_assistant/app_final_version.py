import streamlit as st
import base64
from pathlib import Path
from Hybridsearch import rag, log_feedback


st.set_page_config(page_title="Da Nang Tour Guide", layout="wide")

CATEGORY_CAPTION = {
    "eat": "🍜 Welcome to Da Nang! There are a lot of amazing foods here, from street food to famous local restaurants. Just ask me about location, price, opening time, or signature dishes – I’ll guide you like a true local! 😋",
    "see": "🏞️ Explore Da Nang's Sights! From beautiful beaches, bridges, museums to cozy cafés. Ask me about where to go, what to see, opening hours, and secret spots you shouldn't miss!",
    "stay": "🏨 Find your perfect stay in Da Nang! From budget hostels to luxury hotels. Ask me for locations, prices, amenities, or recommendations for your travel style!"
}

# === CUSTOM CSS ===
_bg_data = base64.b64encode(Path("localguide_assistant/Images/background.jpg").read_bytes()).decode()
st.markdown(f"""
    <style>
    .stApp {{
        background: url('data:image/jpg;base64,{_bg_data}') no-repeat center center fixed;
        background-size: cover;
    }}
    .centered-block {{
        background: rgba(10, 22, 40, 0.44);
        border-radius: 1.5rem;
        padding: 2rem 3rem 2.5rem 3rem;
        margin-top: 4vh;
        margin-bottom: 2vh;
        box-shadow: 0 4px 32px 0 rgba(0,0,0,0.19);
        max-width: 800px;
        margin-left: auto;
        margin-right: auto;
        text-align: center;
    }}
    .button-container {{
        display: flex;
        justify-content: center;
        gap: 36px;
        margin: 2.7rem 0 2.2rem 0;
        flex-wrap: wrap;
    }}
    div.stButton > button {{
        border-radius: 999px;
        padding: 0.85rem 2.6rem;
        background: rgba(255,255,255,0.93);
        color: #242c36;
        font-weight: 800;
        font-size: 1.21rem;
        border: none;
        box-shadow: 0 1px 8px 0 rgba(0,0,0,0.13);
        transition: background 0.18s, color 0.18s;
        margin: 0;
        flex: 0 0 auto;
    }}
    div.stButton > button:hover {{
        background: #FFDB70;
        color: #232b2b;
    }}
    .contact-me {{
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
    }}
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

# ==== MENU PAGE ====
if st.session_state.page == "menu":
    st.markdown("""
        <div class="centered-block">
            <h2 style="color:white; font-family: 'Comic Sans MS', cursive, sans-serif; font-size: 2.25rem; margin-bottom:0.2em;">
                Welcome to Da Nang Tour Guide
            </h2>
            <p style="color:#f7f7f7; font-size:1.25rem;">
                I'm your smart local guide for food, fun, and stay in Da Nang.<br>Let's start!
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Modified button container
    st.markdown('<div class="button-container">', unsafe_allow_html=True)
    buff, col, buff2 = st.columns([1,3.5,0.27])
    with col:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.button("Eat", on_click=go_to_chat, args=("eat",))
        with col2:
            st.button("See", on_click=go_to_chat, args=("see",))
        with col3:
            st.button("Stay", on_click=go_to_chat, args=("stay",))
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("""
        <div class="contact-me">
            Contact me on github: Koshiroquoc</span>
        </div>
    """, unsafe_allow_html=True)

# ==== CHAT PAGE ====

elif st.session_state.page == "chat":
    category = st.session_state.category
    caption = CATEGORY_CAPTION.get(category, "")
    st.markdown(f"""
        <div class="centered-block">
            <h3  <span style="color:#FFDB70">{category.title()}</span></h3>
            <div style="color:#fff; background:rgba(255,255,255,0.07); border-radius:1em; padding:1.05em 1.4em 1.05em 1.4em; margin-bottom:1.25em; font-size:1.12em; text-align:center;">
                {caption}
            </div>
            <p style="color:#fafafa; margin-bottom:0.5em;">💬 Ask me anything about local places!</p>
    """, unsafe_allow_html=True)
    
    # Adjust the box chat
    st.markdown("""
        <style>
        .chat-input-box {max-width: 320px; margin-left:auto; margin-right:auto;}
        div.stTextInput > div > input {
            font-size: 1.13em;
            padding: 0.95em 1.1em;
            border-radius: 1.4em;
        }
        </style>
        <div class="chat-input-box">
    """, unsafe_allow_html=True)
    buff, col, buff2 = st.columns([1,3.1,1])
    with col:
        user_input = st.text_input("Your question:", label_visibility="collapsed")

    #user_input = st.text_input("Your question:", label_visibility="collapsed")
    st.markdown("</div></div>", unsafe_allow_html=True)  
    if user_input:
        from Hybridsearch import rag
        response = rag(user_input, type_filter=category)
        with col:
            st.markdown("""
          <div style="
                margin-top:1.2em;
                margin-bottom:1em;
                background: rgba(10,22,40,0.70);
                border-radius: 1.15em;
                padding: 1.25em 1.6em;
                color: #fff;
                font-size: 1.13em;
                box-shadow: 0 2px 16px 0 rgba(0,0,0,0.14);
                ">
        """ + response + "</div>",
        unsafe_allow_html=True)
    
    # Center 3 button
        buff, like_col, dislike_col, buff2 = st.columns([1.5,1,1,1])
    
    # Check if feedback sent are not 
        if "feedback_sent" not in st.session_state:
            st.session_state.feedback_sent = False

        if not st.session_state.feedback_sent:
            with like_col:
                if st.button("👍 Like", key="like_button"):
                    log_feedback(user_input, response, "like")
                    st.session_state.feedback_msg = "Thanks for your feedback!"
                    st.session_state.feedback_sent = True
            with dislike_col:
                if st.button("👎 Dislike", key="dislike_button"):
                    log_feedback(user_input, response, "dislike")
                    st.session_state.feedback_msg = "Thanks for your feedback!"
                    st.session_state.feedback_sent = True
        else:
            st.markdown(
                '<div style="text-align:center; color:#fafafa; font-weight:600; margin-top:1em; margin-bottom:1.2em;">'
                + st.session_state.get("feedback_msg", "Thanks for your feedback!")
                + '</div>', unsafe_allow_html=True
            )
            st.markdown(
                f"""
                <div style="
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
                    font-weight: 600;
                ">
                    {st.session_state.get("feedback_msg", "Thanks for your feedback!")}
                </div>
                """,
                unsafe_allow_html=True
            )


    # Back button appear after send feedback
        if st.session_state.feedback_sent:
            st.markdown("""
                <div style="display:flex; justify-content:center; margin-top:1.3em;">
                    <form>
                        <button style="border-radius: 999px; padding: 0.85rem 2.8rem; background: rgba(255,255,255,0.93); color: #232b2b; font-size: 1.18rem; font-weight: 600; border:none; box-shadow:0 1px 8px 0 rgba(0,0,0,0.13); cursor:pointer;" onclick="window.location.reload(); return false;">⬅️ Back</button>
                    </form>
                </div>
            """, unsafe_allow_html=True)














    