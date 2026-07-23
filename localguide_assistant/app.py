"""Streamlit interface for the Da Nang Tour Guide."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import streamlit as st

from localguide_assistant.logging_db import get_feedback_store
from localguide_assistant.service import get_rag_service


CATEGORY_CAPTION = {
    "eat": "Find local dishes by area, price, or serving time.",
    "see": "Discover beaches, landmarks, museums, and local experiences.",
    "stay": "Compare places to stay by budget, area, and travel style.",
}


@st.cache_resource
def load_service():
    return get_rag_service()


def _apply_theme() -> None:
    image_path = Path(__file__).parent / "Images/background.jpg"
    background = base64.b64encode(image_path.read_bytes()).decode()
    st.markdown(
        f"""
        <style>
        .stApp {{
            background: linear-gradient(rgba(5,18,35,.66), rgba(5,18,35,.76)),
                        url('data:image/jpg;base64,{background}') center/cover fixed;
        }}
        [data-testid="stMainBlockContainer"] {{ max-width: 860px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _initialize_state() -> None:
    defaults: dict[str, Any] = {
        "page": "menu",
        "category": None,
        "response": None,
        "feedback_sent": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _choose_category(category: str) -> None:
    st.session_state.category = category
    st.session_state.page = "chat"
    st.session_state.response = None
    st.session_state.feedback_sent = False


def _back_to_menu() -> None:
    st.session_state.page = "menu"
    st.session_state.category = None
    st.session_state.response = None
    st.session_state.feedback_sent = False


def _render_menu() -> None:
    st.title("Da Nang Tour Guide 🏖️")
    st.write("A grounded local guide for food, sights, and stays in Da Nang.")
    columns = st.columns(3)
    for column, category, label in zip(
        columns,
        ("eat", "see", "stay"),
        ("🍜 Eat", "🏞️ See", "🏨 Stay"),
        strict=True,
    ):
        column.button(
            label,
            use_container_width=True,
            on_click=_choose_category,
            args=(category,),
        )


def _render_sources(sources: list[dict[str, Any]]) -> None:
    with st.expander("Sources used"):
        for position, source in enumerate(sources, start=1):
            name = source.get("name", "Unknown")
            source_url = source.get("source_url")
            heading = f"[{name}]({source_url})" if source_url else name
            details = [
                source.get("address"),
                source.get("area"),
                source.get("opening_hours"),
            ]
            st.markdown(
                f"**[S{position}] {heading}**  \n"
                + " · ".join(value for value in details if value)
            )
            verification = source.get("last_verified_at") or "not manually verified"
            source_updated = source.get("source_updated_at") or "unknown"
            st.caption(
                f"Source record updated: {source_updated} · Project status: {verification}"
            )
            for enrichment in source.get("enrichment_sources") or []:
                fields = ", ".join(enrichment.get("fields") or [])
                history_url = enrichment.get("source_history_url")
                history = f" · [history/authors]({history_url})" if history_url else ""
                st.caption(
                    f"Enriched fields ({fields}): "
                    f"[{enrichment.get('source', 'source')}]({enrichment.get('source_url')}) "
                    f"· {enrichment.get('source_license', '')}{history}"
                )
        if any(source.get("source") == "OpenStreetMap" for source in sources):
            st.caption(
                "[© OpenStreetMap contributors](https://www.openstreetmap.org/copyright) · ODbL 1.0"
            )
        if any(source.get("enrichment_sources") for source in sources):
            st.caption(
                "Wikivoyage enrichment: CC BY-SA 4.0 · attribution/history links are retained in the dataset"
            )


def _record_feedback(feedback: str) -> None:
    response = st.session_state.response
    if not response:
        return
    get_feedback_store().record(
        request_id=response["request_id"],
        question=response["question"],
        answer=response["answer"],
        feedback=feedback,
        sources=response["sources"],
    )
    st.session_state.feedback_sent = True


def _render_chat() -> None:
    category = st.session_state.category
    st.button("← Categories", on_click=_back_to_menu)
    st.title(f"{category.title()} in Da Nang")
    st.caption(CATEGORY_CAPTION[category])

    prompt = st.chat_input("Ask about price, location, opening time, or preferences")
    if prompt:
        st.session_state.feedback_sent = False
        try:
            with st.spinner("Looking through the local guide…"):
                st.session_state.response = (
                    load_service().ask(prompt, type_filter=category, top_k=3).to_dict()
                )
        except Exception as error:
            st.session_state.response = None
            st.error(f"The guide could not answer right now: {error}")

    response = st.session_state.response
    if not response:
        return

    with st.chat_message("user"):
        st.write(response["question"])
    with st.chat_message("assistant"):
        # Model output is rendered as Markdown, never injected as raw HTML.
        st.markdown(response["answer"])
        _render_sources(response["sources"])
        st.caption(f"Answered in {response['latency_ms']['total']:.0f} ms")

    if st.session_state.feedback_sent:
        st.success("Thanks for your feedback!")
    else:
        like, dislike, _ = st.columns([1, 1, 4])
        like.button("👍 Helpful", on_click=_record_feedback, args=("like",))
        dislike.button("👎 Not helpful", on_click=_record_feedback, args=("dislike",))


def main() -> None:
    st.set_page_config(page_title="Da Nang Tour Guide", page_icon="🏖️")
    _apply_theme()
    _initialize_state()
    if st.session_state.page == "menu":
        _render_menu()
    else:
        _render_chat()


if __name__ == "__main__":
    main()
