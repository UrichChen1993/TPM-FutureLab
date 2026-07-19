from datetime import datetime, time, timedelta

import streamlit as st

from agent.agent import build_agent_executor
from config import load_settings
from domain.states import NotificationSeverity
from rules.escalation_engine import apply_escalation, ensure_today_doses
from rules.proactive_engine import (
    maybe_trigger_proactive_message,
    maybe_trigger_time_based_checkin,
)
from simulator.clock import SimClock
from simulator.iot_simulator import simulate_meal_area_event, simulate_pillbox_event
from simulator.prescription_ocr import (
    OCRValidationError,
    PrescriptionOCRResult,
    TIMING_LABELS,
    add_manual_candidate,
    confirm_ocr_result,
    delete_ocr_candidate,
    format_ocr_result,
    persist_ocr_audit_events,
    review_ocr_candidate,
    revise_ocr_candidate,
    simulate_prescription_ocr,
    validate_ocr_candidate,
)
from storage.factory import get_repository

USER_ID = "user-001"


def extract_display_text(message) -> str:
    """Return user-visible text without exposing provider metadata/signatures."""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
                continue
            if isinstance(block, dict):
                text = block.get("text")
            else:
                text = getattr(block, "text", None)
            if isinstance(text, str) and text:
                text_parts.append(text)
        if text_parts:
            return "\n".join(text_parts)
    return "模型已完成處理，但未回傳可顯示的文字內容。"


def init_state() -> None:
    if "repo" not in st.session_state:
        st.session_state.repo = get_repository()
    if "clock" not in st.session_state:
        st.session_state.clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "proactive_event_ids" not in st.session_state:
        st.session_state.proactive_event_ids = set()
    if "proactive_time_checkin_dates" not in st.session_state:
        st.session_state.proactive_time_checkin_dates = set()
    if "ocr_result" not in st.session_state:
        st.session_state.ocr_result = None
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
    message = maybe_trigger_proactive_message(
        event, asked_event_ids, repo.get_medication_plans(user_id)
    )
    if message is not None:
        messages.append(("ai", message))


def trigger_time_advance(repo, clock, user_id: str, messages: list, asked_dates: set) -> None:
    clock.advance(30)
    run_escalation_tick(repo, clock, user_id)
    message = maybe_trigger_time_based_checkin(clock.now, asked_dates)
    if message is not None:
        messages.append(("ai", message))


def trigger_prescription_scan(
    clock,
    messages: list,
    capture_source: str = "DEMO_SAMPLE",
    repo=None,
    user_id: str = USER_ID,
) -> PrescriptionOCRResult:
    result = simulate_prescription_ocr(clock, capture_source=capture_source)
    if repo is not None:
        persist_ocr_audit_events(repo, result, user_id)
    source_labels = {
        "DEMO_SAMPLE": "示範藥單",
        "CAMERA": "相機拍攝",
        "UPLOAD": "上傳圖片",
    }
    source_label = source_labels.get(capture_source, "藥單圖片")
    messages.append(("human", f"📷（{source_label}，執行模擬 OCR）"))
    messages.append((
        "ai",
        "🔎 **OCR 辨識完成（模擬）**\n\n"
        f"{format_ocr_result(result)}\n\n"
        "目前狀態：**待家屬確認**。OCR 可能辨識錯誤，確認前不會用於服藥提醒。",
    ))
    return result


def confirm_scanned_prescription(
    repo,
    result,
    user_id: str,
    messages: list,
    confirmed_at: datetime | None = None,
) -> None:
    plans = confirm_ocr_result(repo, result, user_id, confirmed_at=confirmed_at)
    medication_text = "、".join(
        f"{plan.name} 每次 {plan.dose}"
        + (f"、{plan.frequency}" if plan.frequency else "")
        for plan in plans
    )
    messages.append((
        "ai",
        f"✅ 家屬已確認藥單：**{medication_text}**。"
        "已建立用藥計畫，後續提醒只會引用已確認且仍在有效期間內的內容。",
    ))


def render_sidebar() -> None:
    settings = load_settings()
    st.sidebar.subheader("系統狀態")
    st.sidebar.write(f"Backend：{settings.data_backend}")
    if settings.data_backend == "dynamodb":
        st.sidebar.write(f"Region：{settings.aws_region}")
    sim_time_placeholder = st.sidebar.empty()

    st.sidebar.subheader("1. 藥單建檔")
    input_mode = st.sidebar.radio(
        "藥單來源",
        ("示範藥單", "相機拍攝", "上傳圖片"),
        horizontal=True,
    )
    captured_media = None
    capture_source = "DEMO_SAMPLE"
    if input_mode == "相機拍攝":
        capture_source = "CAMERA"
        captured_media = st.sidebar.camera_input("拍攝完整、清楚的藥袋或處方箋")
    elif input_mode == "上傳圖片":
        capture_source = "UPLOAD"
        captured_media = st.sidebar.file_uploader(
            "上傳藥袋或處方箋",
            type=("jpg", "jpeg", "png"),
        )

    can_scan = input_mode == "示範藥單" or captured_media is not None
    if st.sidebar.button(
        "🔎 執行模擬 OCR",
        use_container_width=True,
        disabled=not can_scan,
    ):
        st.session_state.ocr_result = trigger_prescription_scan(
            st.session_state.clock,
            st.session_state.messages,
            capture_source=capture_source,
            repo=st.session_state.repo,
            user_id=USER_ID,
        )
    st.sidebar.caption("目前會接收照片，但仍回傳固定示範辨識結果，不會把影像送到真實 OCR 服務。")

    result = st.session_state.ocr_result
    if result is not None:
        status_label = {
            "NEEDS_REVIEW": "待逐筆確認",
            "READY_TO_CONFIRM": "已逐筆確認，待啟用",
            "CONFIRMED": "已確認並啟用",
        }.get(result.review_status, result.review_status)
        st.sidebar.caption(f"OCR 狀態：{status_label}")
        for candidate in result.medications:
            widget_prefix = f"{result.prescription_id}-{candidate.med_id}"
            timing_text = TIMING_LABELS.get(candidate.timing, candidate.timing)
            if candidate.timing == "FIXED_TIME" and candidate.fixed_times:
                timing_text += f"（{', '.join(candidate.fixed_times)}）"
            valid_period = (
                f"{candidate.valid_from:%Y-%m-%d}～{candidate.valid_to:%Y-%m-%d}"
                if candidate.valid_from and candidate.valid_to
                else "未完整設定"
            )
            review_mark = "✅ 已逐筆核對" if candidate.reviewed else "⏳ 待核對"
            st.sidebar.write(
                f"{candidate.name}｜每次 {candidate.dose}｜{candidate.frequency}｜"
                f"{timing_text}｜{valid_period}｜辨識信心 {candidate.confidence:.0%}｜"
                f"{review_mark}"
            )
            image_ref = candidate.image_reference
            if image_ref is not None:
                st.sidebar.image(
                    image_ref.image_url,
                    caption=f"藥品外觀參考｜{image_ref.source_name}",
                )
                st.sidebar.markdown(
                    f"[{image_ref.reference_id}・查看圖片來源]({image_ref.source_url})"
                )
                st.sidebar.warning("外觀圖片僅供核對，不能單靠照片判定藥品或服法。")
            else:
                st.sidebar.info("找不到可信的精確藥名圖片；請以藥袋正本或藥師確認。")

            if result.review_status != "CONFIRMED":
                with st.sidebar.expander(f"✏️ 校對 {candidate.name or candidate.med_id}"):
                    revised_name = st.text_input(
                        "藥名與規格", candidate.name, key=f"name-{widget_prefix}"
                    )
                    revised_dose = st.text_input(
                        "每次劑量", candidate.dose, key=f"dose-{widget_prefix}"
                    )
                    revised_frequency = st.text_input(
                        "頻率", candidate.frequency, key=f"frequency-{widget_prefix}"
                    )
                    timing_options = tuple(TIMING_LABELS)
                    revised_timing = st.selectbox(
                        "服用時機",
                        timing_options,
                        index=timing_options.index(candidate.timing),
                        format_func=lambda value: TIMING_LABELS[value],
                        key=f"timing-{widget_prefix}",
                    )
                    revised_valid_from = st.date_input(
                        "有效起日",
                        value=(candidate.valid_from or result.captured_at).date(),
                        key=f"valid-from-{widget_prefix}",
                    )
                    revised_valid_to = st.date_input(
                        "有效迄日",
                        value=(candidate.valid_to or result.captured_at).date(),
                        key=f"valid-to-{widget_prefix}",
                    )
                    revised_fixed_times: tuple[str, ...] = ()
                    if revised_timing == "FIXED_TIME":
                        default_time = (
                            datetime.strptime(candidate.fixed_times[0], "%H:%M").time()
                            if candidate.fixed_times else time(8, 0)
                        )
                        selected_time = st.time_input(
                            "固定服藥時間",
                            value=default_time,
                            key=f"fixed-time-{widget_prefix}",
                        )
                        revised_fixed_times = (selected_time.strftime("%H:%M"),)
                    if st.button("套用校對", key=f"revise-{widget_prefix}"):
                        revise_ocr_candidate(
                            result,
                            candidate.med_id,
                            name=revised_name,
                            dose=revised_dose,
                            frequency=revised_frequency,
                            timing=revised_timing,
                            valid_from=datetime.combine(revised_valid_from, time.min),
                            valid_to=datetime.combine(revised_valid_to, time.max),
                            fixed_times=revised_fixed_times,
                            occurred_at=st.session_state.clock.now,
                        )
                        persist_ocr_audit_events(
                            st.session_state.repo, result, USER_ID
                        )
                        st.rerun()
                    candidate_errors = validate_ocr_candidate(candidate)
                    if candidate_errors:
                        st.error("無法確認：" + "；".join(
                            f"{field} {reason}" for field, reason in candidate_errors.items()
                        ))
                    if st.button(
                        "✅ 確認此筆必要資料",
                        key=f"review-{widget_prefix}",
                        disabled=bool(candidate_errors) or candidate.reviewed,
                    ):
                        try:
                            review_ocr_candidate(
                                result, candidate.med_id,
                                occurred_at=st.session_state.clock.now,
                            )
                            persist_ocr_audit_events(
                                st.session_state.repo, result, USER_ID
                            )
                            st.rerun()
                        except OCRValidationError as exc:
                            st.error(str(exc))
                    if st.button(
                        "🗑️ 刪除此筆候選",
                        key=f"delete-{widget_prefix}",
                    ):
                        delete_ocr_candidate(
                            result, candidate.med_id,
                            occurred_at=st.session_state.clock.now,
                        )
                        persist_ocr_audit_events(
                            st.session_state.repo, result, USER_ID
                        )
                        st.rerun()

        if result.review_status != "CONFIRMED":
            manual_prefix = result.prescription_id
            with st.sidebar.expander("➕ 手動新增藥物"):
                new_name = st.text_input("藥名與規格", key=f"manual-name-{manual_prefix}")
                new_dose = st.text_input("每次劑量", key=f"manual-dose-{manual_prefix}")
                new_frequency = st.text_input("頻率", key=f"manual-frequency-{manual_prefix}")
                new_timing = st.selectbox(
                    "服用時機",
                    tuple(TIMING_LABELS),
                    format_func=lambda value: TIMING_LABELS[value],
                    key=f"manual-timing-{manual_prefix}",
                )
                new_valid_from = st.date_input(
                    "有效起日", value=result.captured_at.date(),
                    key=f"manual-valid-from-{manual_prefix}"
                )
                new_valid_to = st.date_input(
                    "有效迄日",
                    value=(result.captured_at + timedelta(days=30)).date(),
                    key=f"manual-valid-to-{manual_prefix}",
                )
                new_fixed_times: tuple[str, ...] = ()
                if new_timing == "FIXED_TIME":
                    new_fixed_time = st.time_input(
                        "固定服藥時間", value=time(8, 0),
                        key=f"manual-fixed-time-{manual_prefix}"
                    )
                    new_fixed_times = (new_fixed_time.strftime("%H:%M"),)
                if st.button(
                    "新增待確認候選", key=f"add-manual-candidate-{manual_prefix}"
                ):
                    add_manual_candidate(
                        result,
                        name=new_name,
                        dose=new_dose,
                        frequency=new_frequency,
                        timing=new_timing,
                        valid_from=datetime.combine(new_valid_from, time.min),
                        valid_to=datetime.combine(new_valid_to, time.max),
                        fixed_times=new_fixed_times,
                        occurred_at=st.session_state.clock.now,
                    )
                    persist_ocr_audit_events(
                        st.session_state.repo, result, USER_ID
                    )
                    st.rerun()

            if result.review_status != "READY_TO_CONFIRM":
                st.sidebar.info("請先逐筆補齊並確認必要資料，系統才會允許啟用提醒。")
            if st.sidebar.button(
                "✅ 啟用已確認用藥計畫",
                use_container_width=True,
                disabled=result.review_status != "READY_TO_CONFIRM",
            ):
                try:
                    confirm_scanned_prescription(
                        st.session_state.repo,
                        result,
                        USER_ID,
                        st.session_state.messages,
                        confirmed_at=st.session_state.clock.now,
                    )
                    st.rerun()
                except OCRValidationError as exc:
                    st.sidebar.error(f"無法啟用：{exc}")

    st.sidebar.subheader("2. IoT 情境模擬")
    if st.sidebar.button("🍽️ 模擬晚餐時段感測事件", use_container_width=True):
        trigger_meal_event(
            st.session_state.repo, st.session_state.clock, USER_ID,
            st.session_state.messages, st.session_state.proactive_event_ids,
        )
    if st.sidebar.button("⏩ 前進 30 分鐘", use_container_width=True):
        trigger_time_advance(
            st.session_state.repo, st.session_state.clock, USER_ID,
            st.session_state.messages, st.session_state.proactive_time_checkin_dates,
        )
    if st.sidebar.button("💊 模擬藥盒開啟＋重量下降", use_container_width=True):
        _, dose_record = simulate_pillbox_event(
            st.session_state.repo, st.session_state.clock, USER_ID, "med-001", "DINNER"
        )
        run_escalation_tick(st.session_state.repo, st.session_state.clock, USER_ID)
        if dose_record is not None:
            st.sidebar.success(f"感測器已確認服藥（{dose_record.slot}｜{dose_record.med_id}）")
        else:
            st.sidebar.warning("尚無今日對應的用藥排程，感測事件未套用到任何劑量紀錄")

    sim_time_placeholder.write(f"模擬時間：{st.session_state.clock.now.isoformat()}")

    st.sidebar.subheader("已確認用藥")
    confirmed_plans = [
        plan for plan in st.session_state.repo.get_medication_plans(USER_ID)
        if plan.is_active_at(st.session_state.clock.now)
    ]
    if confirmed_plans:
        for plan in confirmed_plans:
            frequency = f"｜{plan.frequency}" if plan.frequency else ""
            timing_text = TIMING_LABELS.get(plan.timing, plan.timing)
            if plan.fixed_times:
                timing_text += f"（{', '.join(plan.fixed_times)}）"
            valid_to = plan.valid_to.strftime("%Y-%m-%d") if plan.valid_to else "未設定"
            st.sidebar.success(
                f"{plan.name}｜每次 {plan.dose}{frequency}｜{timing_text}｜有效至 {valid_to}"
            )
    else:
        st.sidebar.caption("尚無已確認且在有效期間內的用藥計畫")

    audit_events = st.session_state.repo.list_medication_audit_events(USER_ID)
    if audit_events:
        with st.sidebar.expander("用藥計畫稽核紀錄"):
            for event in audit_events[-10:]:
                st.caption(
                    f"{event.occurred_at.isoformat()}｜{event.med_id}｜"
                    f"{event.action}｜{event.actor_id}｜{event.event_id}"
                )

    st.sidebar.subheader("家屬通知")
    for note in st.session_state.repo.list_notifications(USER_ID):
        render = st.sidebar.error if note.severity == NotificationSeverity.HIGH.value else st.sidebar.warning
        render(f"[{note.severity}] {note.message}（{note.occurred_at.isoformat()}）")


def render_chat() -> None:
    st.title("HomeWellness Companion")
    st.caption(
        "文字模擬語音互動｜藥單 OCR 為固定資料情境模擬｜"
        "僅提供提醒與資訊協助，不具醫療診斷或治療功能"
    )

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
        ai_content = extract_display_text(result["messages"][-1])
        st.session_state.messages.append(("ai", ai_content))
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="HomeWellness Companion")
    init_state()
    render_sidebar()
    render_chat()


if __name__ == "__main__":
    main()
