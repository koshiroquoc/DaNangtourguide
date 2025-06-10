import streamlit as st
#from Hybridsearch import rag


st.set_page_config(page_title="TourBot <3", layout="centered")

# Khởi tạo session state
if "page" not in st.session_state:
    st.session_state.page = "menu"

def go_to_chat(category):
    st.session_state.category = category
    st.session_state.page = "chat"

def go_back():
    st.session_state.page = "menu"

# ==== TRANG MENU ====
if st.session_state.page == "menu":
    st.markdown("## 🥚 Local Guide <3")
    st.markdown("### What are you looking for today?")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🍜 Eat"):
            go_to_chat("eat")
    with col2:
        if st.button("☕ See"):
            go_to_chat("see")
    with col3:
        if st.button("🏨 Stay"):
            go_to_chat("stay")


# ==== TRANG CHAT ====
elif st.session_state.page == "chat":
    st.markdown(f"### You selected: **{st.session_state.category.title()}**")
    st.markdown("#### 💬 Ask me anything about local places!")
    
    user_input = st.text_input("Your question:")
   # if user_input:
     #   response = rag(user_input, type_filter=st.session_state.category)
     #   st.success(response)
    st.button("🔙 Back", on_click=go_back)
