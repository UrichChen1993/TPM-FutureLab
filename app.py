from datetime import datetime

import streamlit as st

from agent.agent import build_agent_executor
from config import load_settings
from rules.escalation_engine import apply_escalation, ensure_today_doses
from rules.proactive_engine import maybe_trigger_proactive_message
from seed_data import seed_demo_user
from simulator.clock import SimClock
from simulator.iot_simulator import simulate_meal_area_event, simulate_pillbox_event
from storage.factory import get_repository

USER_ID = "user-001"


def init_state() -> None:
    if "repo" not in st.session_state:
        st.session_state.repo = get_repository()
        seed_demo_user(st.session_state.repo, USER_ID)
    if "clock" not in st.session_state:
        st.session_state.clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "proactive_event_ids" not in st.session_state:
        st.session_state.proactive_event_ids = set()
    if "agent_executor" not in st.session_state:
        try:
            st.session_state.agent_executor = build_agent_executor(
                st.session_state.repo, st.session_state.clock, USER_ID
            )
            st.session_state.agent_error = None
        except ValueError as exc:
            st.session_state.agent_executor = None
            st.session_state.agent_error = str(exc)


def run_escalation_tick(repo, clock, user_id: str) -> None:
    ensure_today_doses(repo, clock, user_id)
    for record in repo.list_dose_records(user_id, clock.now.strftime("%Y-%m-%d")):
        apply_escalation(repo, record, clock.now)


def trigger_meal_event(repo, clock, user_id: str, messages: list, asked_event_ids: set) -> None:
    clock.jump_to_dinner()
    event = simulate_meal_area_event(repo, clock, user_id)
    run_escalation_tick(repo, clock, user_id)
    message = maybe_trigger_proactive_message(event, asked_event_ids)
    if message is not None:
        messages.append(("ai", message))


def render_sidebar() -> None:
    settings = load_settings()
    st.sidebar.subheader("系統狀態")
    st.sidebar.write(f"Backend：{settings.data_backend}")
    if settings.data_backend == "dynamodb":
        st.sidebar.write(f"Region：{settings.aws_region}")
    st.sidebar.write(f"模擬時間：{st.session_state.clock.now.isoformat()}")

    st.sidebar.subheader("情境模擬")
    if st.sidebar.button("模擬：晚餐時段感測事件"):
        trigger_meal_event(
            st.session_state.repo, st.session_state.clock, USER_ID,
            st.session_state.messages, st.session_state.proactive_event_ids,
        )
    if st.sidebar.button("前進 30 分鐘"):
        st.session_state.clock.advance(30)
        run_escalation_tick(st.session_state.repo, st.session_state.clock, USER_ID)
    if st.sidebar.button("模擬：藥盒開啟＋重量下降"):
        simulate_pillbox_event(st.session_state.repo, st.session_state.clock, USER_ID, "med-001", "DINNER")
        run_escalation_tick(st.session_state.repo, st.session_state.clock, USER_ID)

    st.sidebar.subheader("家屬通知")
    for note in st.session_state.repo.list_notifications(USER_ID):
        st.sidebar.warning(f"[{note.severity}] {note.message}（{note.occurred_at.isoformat()}）")


def render_chat() -> None:
    st.title("HomeWellness Companion")
    st.caption("Text-based simulation of voice interaction")

    for role, content in st.session_state.messages:
        st.chat_message(role).write(content)

    if st.session_state.agent_error:
        st.info(f"LLM 尚未設定（{st.session_state.agent_error}），僅能使用左側模擬按鈕測試流程。")
        return

    user_input = st.chat_input("輸入長者的回應...")
    if user_input:
        st.session_state.messages.append(("human", user_input))
        history_messages = [
            {"role": "user" if role == "human" else "assistant", "content": content}
            for role, content in st.session_state.messages
        ]
        result = st.session_state.agent_executor.invoke({"messages": history_messages})
        ai_content = result["messages"][-1].content
        st.session_state.messages.append(("ai", ai_content))
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="HomeWellness Companion")
    init_state()
    render_sidebar()
    render_chat()


if __name__ == "__main__":
    main()
