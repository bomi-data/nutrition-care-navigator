"""우리동네 영양돌봄 내비게이터 -- Streamlit MVP (기능 검증용).

이 파일은 화면(입력/표시)만 담당합니다. 추천 로직은 전혀 새로 작성하지 않고,
기존 `src/recommender` 패키지와 `src/streamlit_ui/adapter` 어댑터만 사용합니다.

실행 방법: (프로젝트 루트에서)
    streamlit run app/streamlit_app.py

이번 단계 범위: 규칙 기반 추천엔진 v1을 화면에서 실제로 사용해 볼 수 있는지
검증하는 것입니다. RAG/LangChain/Vector DB/Claude API/n8n/배포는 포함하지
않습니다 (docs/streamlit_mvp_v1_report.md 참고).
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import streamlit as st

# app/ 은 src/ 와 별도 최상위 폴더이므로, streamlit이 이 파일을 직접 실행할 때도
# `recommender`/`streamlit_ui` 패키지를 import할 수 있도록 경로를 추가합니다.
_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from recommender import MatchLevel, load_services, recommend  # noqa: E402
from recommender.loader import LoaderError  # noqa: E402
from streamlit_ui import adapter  # noqa: E402
from streamlit_ui import rag_adapter  # noqa: E402

st.set_page_config(page_title="우리동네 영양돌봄 내비게이터", page_icon="🍚")

TOP_K = 5


# ---------------------------------------------------------------------------
# 데이터/엔진 로드 -- 실패해도 앱이 죽지 않고 안내만 표시 (지침 §16)
# ---------------------------------------------------------------------------


@st.cache_resource(show_spinner=False)
def _load_services_cached():
    return load_services()


@st.cache_resource(show_spinner=False)
def _load_region_options_cached():
    return adapter.load_region_options()


@st.cache_resource(show_spinner="AI 설명 기능을 준비하고 있어요 (최초 1회만 실행돼요)...")
def _load_rag_resources_cached():
    """rag_adapter.load_rag_resources()를 프로세스당 1회만 실행하도록 캐시합니다.

    st.cache_resource이므로 이 함수의 반환값(VectorStore/Embedder)은 모든 사용자
    세션과 rerun에서 공유됩니다 -- 버튼 클릭/rerun마다 embedding model이나 FAISS
    index를 다시 만들지 않습니다(지침 §10/§23).
    """
    return rag_adapter.load_rag_resources()


def _fatal(message: str, error: Exception) -> None:
    st.error(message)
    with st.expander("(개발자용) 오류 자세히 보기", expanded=False):
        st.code("".join(traceback.format_exception_only(type(error), error)))
    print("[streamlit_app] fatal startup error:", repr(error), file=sys.stderr)


services = None
region_options = None
startup_error = False

try:
    services = _load_services_cached()
except (LoaderError, FileNotFoundError, OSError) as e:
    _fatal(
        "추천 서비스 데이터를 불러오지 못했어요. "
        "data/processed/welfare_services_recommendation_ready.csv 파일을 확인해주세요.",
        e,
    )
    startup_error = True
except Exception as e:  # pragma: no cover - defensive catch-all
    _fatal("추천엔진을 불러오는 중 예상하지 못한 문제가 발생했어요.", e)
    startup_error = True

if not startup_error:
    try:
        region_options = _load_region_options_cached()
    except adapter.RegionDataError as e:
        _fatal(
            "지역 목록 데이터를 불러오지 못했어요. "
            "data/processed/region_codes.csv 파일을 확인해주세요.",
            e,
        )
        startup_error = True

if startup_error:
    st.stop()


# ---------------------------------------------------------------------------
# RAG(Retrieval + Generation) 리소스 -- 실패해도 추천엔진 자체는 계속 동작해야
# 하므로(지침 §8), startup_error와는 별도의 rag_available 플래그로만 관리합니다.
# ---------------------------------------------------------------------------

rag_store = None
rag_embedder = None
rag_available = False
try:
    rag_store, rag_embedder = _load_rag_resources_cached()
    rag_available = True
except Exception as e:  # pragma: no cover - defensive catch-all
    print("[streamlit_app] RAG resource load failed:", repr(e), file=sys.stderr)
    traceback.print_exc(file=sys.stderr)

generation_client = rag_adapter.resolve_generation_client()


# ---------------------------------------------------------------------------
# RAG 설명 UI -- service_id 범위를 벗어난 근거가 섞이지 않도록, 이 함수는
# 항상 하나의 RecommendationResult(r)만 받아 그 service_id로만 검색/생성합니다
# (지침 §6 service boundary). Claude는 사용자가 실제로 질문 버튼을 눌렀을 때만
# 호출됩니다 -- 추천 실행 자체는 이 함수를 거치지 않으므로 Claude를 부르지
# 않습니다(지침 §1 on-demand 원칙).
# ---------------------------------------------------------------------------


def _render_grounded_answer(answer) -> None:
    for label, text in rag_adapter.answer_display_fields(answer):
        st.markdown(f"**{label}**")
        st.write(text)

    if answer.confirmation_items:
        st.markdown("**추가 확인이 필요한 부분**")
        for item in answer.confirmation_items:
            st.markdown(f"- {item}")

    st.caption(answer.safety_notice)

    grouped = rag_adapter.evidence_grouped_by_section(answer.evidence)
    if grouped:
        with st.expander("📄 답변 근거 보기 (공식 원문)"):
            st.caption(
                "아래는 AI가 쓴 문장이 아니라 공식 원문 그대로예요. 위 AI 설명과 구분해서 참고해주세요."
            )
            for _section, section_label, contents in grouped:
                st.markdown(f"**[{section_label}]**")
                for content in contents:
                    st.markdown(f"> {content}")


def _render_ai_explanation_section(r, profile) -> None:
    """보조 기능: 카드의 핵심 정보(등급/이유/확인사항)를 다 확인한 뒤,
    더 궁금할 때만 펼쳐보는 부가 설명 영역입니다."""
    if not rag_available:
        st.info(
            "AI 기반 설명 기능이 현재 설정되지 않았습니다. "
            "기존 추천 결과와 공식 원문은 계속 확인할 수 있습니다."
        )
        return

    if generation_client.client is None:
        st.info(generation_client.unavailable_reason)
        return

    if generation_client.is_fake:
        st.caption("🧪 테스트 모드 응답이에요 (실제 Claude 답변이 아니에요).")
    else:
        st.caption("Claude API 기반 설명이에요. 공식 원문 범위 안에서만 답변해요.")

    st.caption("궁금한 내용을 선택하거나 직접 질문해보세요.")

    sid = r.service_id
    question_to_run = None

    preset_cols = st.columns(2)
    for idx, preset in enumerate(rag_adapter.PRESET_QUESTIONS):
        col = preset_cols[idx % 2]
        if col.button(preset, key=f"preset_{sid}_{idx}"):
            question_to_run = preset

    free_text = st.text_input(
        "직접 질문하기 (이 서비스의 공식 정보 범위 안에서만 답변해요)",
        key=rag_adapter.free_text_session_key(sid),
        placeholder="예: 신청 서류가 필요한가요?",
    )
    if st.button("근거 기반 답변 보기", key=f"submit_free_{sid}") and free_text.strip():
        question_to_run = free_text.strip()

    if question_to_run:
        st.session_state[rag_adapter.pending_question_session_key(sid)] = question_to_run
        with st.spinner("공식 서비스 정보를 바탕으로 확인하고 있어요..."):
            outcome = rag_adapter.safe_run_generation(
                generation_client, rag_store, rag_embedder, r, profile, question_to_run,
            )
        st.session_state[rag_adapter.answer_session_key(sid)] = outcome.answer
        st.session_state[rag_adapter.error_session_key(sid)] = outcome.error_message

    pending_question = st.session_state.get(rag_adapter.pending_question_session_key(sid))
    stored_answer = st.session_state.get(rag_adapter.answer_session_key(sid))
    stored_error = st.session_state.get(rag_adapter.error_session_key(sid))

    if pending_question:
        st.caption(f"질문: {pending_question}")

    if stored_error:
        st.warning(stored_error)
    elif stored_answer is not None:
        _render_grounded_answer(stored_answer)


# ---------------------------------------------------------------------------
# 헤더
# ---------------------------------------------------------------------------

st.title("🍚 우리동네 영양돌봄 내비게이터")
st.caption(
    "거주지역과 생활상황을 입력하면, 공공 영양·식사·통합돌봄 서비스 중 "
    "신청 가능성을 확인해볼 후보를 찾아드려요."
)
st.info(
    "이 결과는 **참고용 안내**예요. 정확한 자격은 거주지 주민센터나 담당 기관에서 "
    "확인해주세요. 잘 모르는 항목은 '잘 모르겠어요'를 선택해도 괜찮아요.",
    icon="ℹ️",
)

if "results" not in st.session_state:
    st.session_state["results"] = None
    st.session_state["profile"] = None
    st.session_state["search_error"] = None


# ---------------------------------------------------------------------------
# 입력 UI
# ---------------------------------------------------------------------------

st.header("1. 정보를 입력해주세요")

st.subheader("기본 정보")
respondent_label = st.radio(
    "누가 입력하고 있나요?",
    adapter.RESPONDENT_OPTIONS,
    horizontal=True,
)

col1, col2 = st.columns(2)
with col1:
    sido_options = [adapter.NO_SIDO_SELECTED] + sorted(region_options.keys())
    sido_label = st.selectbox("거주 시/도", sido_options)
with col2:
    if sido_label == adapter.NO_SIDO_SELECTED:
        sigungu_options = [adapter.NO_SIGUNGU_SELECTED]
        st.selectbox("거주 시/군/구", sigungu_options, disabled=True)
        sigungu_label = adapter.NO_SIGUNGU_SELECTED
    else:
        sigungu_options = [adapter.NO_SIGUNGU_SELECTED] + region_options[sido_label]
        sigungu_label = st.selectbox("거주 시/군/구", sigungu_options)

age_raw = st.text_input("연령 (만 나이, 모르면 비워두세요)", value="")

st.subheader("영양·식생활 상황")
st.caption(
    "현재 식생활에서 겪고 있는 어려움을 알려주세요. "
    "잘 모르겠다면 '잘 모르겠어요'를 선택해도 됩니다."
)

ncol1, ncol2 = st.columns(2)
with ncol1:
    meal_skipping_answer = st.radio(
        "최근 식사를 자주 거르나요?", adapter.TRISTATE_ANSWER_OPTIONS,
        index=2, horizontal=True, key="meal_skipping",
    )
    meal_prep_answer = st.radio(
        "직접 음식을 준비하기 어렵나요?", adapter.TRISTATE_ANSWER_OPTIONS,
        index=2, horizontal=True, key="meal_prep",
    )
with ncol2:
    grocery_shopping_answer = st.radio(
        "장보기가 어렵나요?", adapter.TRISTATE_ANSWER_OPTIONS,
        index=2, horizontal=True, key="grocery_shopping",
    )
    diet_management_answer = st.radio(
        "질환 때문에 식사관리가 필요하다고 느끼나요?", adapter.TRISTATE_ANSWER_OPTIONS,
        index=2, horizontal=True, key="diet_management",
    )

st.subheader("생활·복지 상황")
st.caption("잘 모르시면 '잘 모르겠어요'를 선택해주세요 -- 모른다고 불이익이 없습니다.")

tcol1, tcol2 = st.columns(2)
with tcol1:
    disability_answer = st.radio(
        "장애가 있으신가요?", adapter.TRISTATE_ANSWER_OPTIONS,
        index=2, horizontal=True, key="disability",
    )
    lives_alone_answer = st.radio(
        "혼자 살고 계신가요? (독거)", adapter.TRISTATE_ANSWER_OPTIONS,
        index=2, horizontal=True, key="lives_alone",
    )
    low_income_answer = st.radio(
        "저소득층(기초생활수급자/차상위 등)에 해당하시나요?", adapter.TRISTATE_ANSWER_OPTIONS,
        index=2, horizontal=True, key="low_income",
    )
with tcol2:
    mobility_answer = st.radio(
        "거동이 불편하신가요?", adapter.TRISTATE_ANSWER_OPTIONS,
        index=2, horizontal=True, key="mobility",
    )
    recent_discharge_answer = st.radio(
        "최근 병원에서 퇴원하셨나요?", adapter.TRISTATE_ANSWER_OPTIONS,
        index=2, horizontal=True, key="recent_discharge",
    )

st.subheader("원하는 도움")
desired_support_selected = st.multiselect(
    "어떤 도움을 찾고 계신가요? (여러 개 선택 가능)",
    adapter.desired_support_labels(),
)

search_clicked = st.button("🔍 내게 맞는 서비스 찾아보기", type="primary")


# ---------------------------------------------------------------------------
# 추천 실행 -- recommend()를 그대로 호출하고 결과를 재정렬/변경하지 않음
# ---------------------------------------------------------------------------

if search_clicked:
    profile = adapter.build_user_profile(
        sido_label=sido_label,
        sigungu_label=sigungu_label,
        age_raw=age_raw,
        disability_answer=disability_answer,
        low_income_answer=low_income_answer,
        lives_alone_answer=lives_alone_answer,
        mobility_answer=mobility_answer,
        meal_prep_answer=meal_prep_answer,
        recent_discharge_answer=recent_discharge_answer,
        desired_support_selected_labels=desired_support_selected,
        respondent_label=respondent_label,
        meal_skipping_answer=meal_skipping_answer,
        grocery_shopping_answer=grocery_shopping_answer,
        diet_management_answer=diet_management_answer,
    )
    st.session_state["profile"] = profile
    st.session_state["search_error"] = None
    try:
        st.session_state["results"] = recommend(profile, services=services, top_k=TOP_K)
    except Exception as e:  # pragma: no cover - defensive catch-all
        st.session_state["results"] = None
        st.session_state["search_error"] = str(e)
        print("[streamlit_app] recommend() failed:", repr(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr)


# ---------------------------------------------------------------------------
# 결과 표시
# ---------------------------------------------------------------------------

profile = st.session_state["profile"]
results = st.session_state["results"]

if st.session_state["search_error"] is not None:
    st.error(
        "추천을 계산하는 중 문제가 발생했어요. 입력값을 바꿔서 다시 시도해주세요. "
        "문제가 반복되면 개발자에게 알려주세요."
    )

if profile is not None and st.session_state["search_error"] is None:
    st.header("2. 추천 결과")

    notice = adapter.sparse_input_notice(profile)
    if notice:
        st.warning(notice, icon="⚠️")

    scarce_notice = adapter.scarce_support_warning(profile.desired_support, services)
    if scarce_notice:
        st.warning(scarce_notice, icon="⚠️")

    nutrition_situation = adapter.nutrition_situation_summary(profile)
    if nutrition_situation:
        with st.expander("📝 입력하신 식생활 상황", expanded=False):
            for item in nutrition_situation:
                st.markdown(f"- {item}")

    if not results:
        st.warning(
            "조건에 맞는 공공서비스를 찾지 못했어요. "
            "입력하신 지역/연령 조건과 정확히 맞는 서비스가 없거나, "
            "해당 조건에 대한 데이터가 아직 충분하지 않을 수 있어요. "
            "거주 시/군/구를 비워보거나 다른 조건으로 다시 시도해보세요.",
            icon="🔍",
        )
    else:
        st.caption(f"조건에 맞을 가능성이 있는 서비스 {len(results)}건을 찾았어요 (최대 {TOP_K}건 표시).")

        few_notice = adapter.few_candidates_notice(len(results), TOP_K)
        if few_notice:
            st.info(few_notice, icon="ℹ️")

        for i, r in enumerate(results, 1):
            region_text = (
                "전국"
                if r.region.get("region_scope") == "NATIONAL"
                else " ".join(filter(None, [r.region.get("sido"), r.region.get("sigungu")])) or "지역 정보 없음"
            )
            type_labels = ", ".join(adapter.service_type_tag_label(t) for t in r.service_type)

            with st.container(border=True):
                st.subheader(f"{i}. {r.service_name}")
                st.markdown(
                    f"**{adapter.match_level_label(r.match_level)}** &nbsp;|&nbsp; "
                    f"📍 {region_text} &nbsp;|&nbsp; 🍽️ {type_labels}"
                )

                if r.recommendation_reasons:
                    st.markdown("**✅ 왜 추천되었나요?**")
                    for reason in r.recommendation_reasons[:4]:
                        st.markdown(f"- {adapter.humanize_internal_tokens(reason)}")

                if r.confirmation_needed:
                    st.markdown("**❓ 추가 조건 확인이 필요해요**")
                    st.caption(
                        "신청 가능성이 있지만, 일부 자격조건은 현재 입력 정보만으로 확인하기 "
                        "어려워요. 담당기관에서 최종 확인해주세요."
                    )
                    for c in r.confirmation_needed:
                        st.markdown(f"- {adapter.humanize_internal_tokens(c)}")

                with st.expander("자세히 보기 (지원 대상 · 선정 기준 · 신청 방법 등 공식 원문)"):
                    st.caption(
                        f"내부 참고 점수 {r.match_score:.1f}/100 (참고용 지표이며 자격 점수가 아니에요) · "
                        f"정보 검증 등급 {adapter.verification_level_label(r.verification_level)} · "
                        f"{adapter.nutritionist_involvement_label(r.nutritionist_involvement)}"
                    )

                    if r.exclusion_warnings:
                        st.markdown("**참고 사항**")
                        for w in r.exclusion_warnings:
                            st.markdown(f"- {adapter.humanize_internal_tokens(w)}")

                    if r.unknown_conditions:
                        st.markdown("**아직 확인되지 않은 조건**")
                        for u in r.unknown_conditions:
                            st.markdown(f"- {adapter.humanize_internal_tokens(u)}")

                    st.divider()
                    st.markdown("**지원 대상**")
                    st.write(r.target_original or r.eligibility_summary or "원문에 명시된 지원 대상 정보가 없어요.")

                    st.markdown("**선정 기준**")
                    st.write(r.criteria_original or r.eligibility_summary or "원문에 명시된 선정 기준 정보가 없어요.")

                    st.markdown("**지원 내용**")
                    st.write(r.support_summary or "원문에 명시된 지원 내용 정보가 없어요.")

                    st.markdown("**신청 방법**")
                    st.write(r.application_method or "원문에 신청방법 정보가 없어요. 문의처에 확인해주세요.")

                    st.markdown("**문의처**")
                    st.write(r.contact or "정보 없음")

                    st.caption("📄 위 지원 대상 · 선정 기준 · 지원 내용 · 신청 방법은 공식 데이터 원문을 그대로 옮긴 공식 근거예요.")

                with st.expander("🤖 AI로 더 알아보기 (선택 기능)"):
                    _render_ai_explanation_section(r, profile)

    # 영양상담 연결 안내 -- 판정/진단 기능이 아니라 "확인해볼 수 있는 경로"만
    # 안내하는 카드. 기존 서비스 추천 결과는 위에서 이미 전부 표시가 끝난
    # 뒤에, 그 결과와 자연스럽게 이어지는 위치에만 덧붙인다.
    if adapter.nutrition_counseling_suggested(profile):
        st.divider()
        with st.container(border=True):
            st.markdown("#### 🥗 영양상담도 함께 확인해보세요")
            st.write(
                "입력하신 식생활 상황을 보면 영양상담이 도움이 될 가능성이 있어요. "
                "거주지역의 보건소·복지기관에서 이용 가능한 영양상담이 있는지 확인해보세요."
            )
            st.markdown(
                "🍽️ **식생활 어려움 확인**\n\n"
                "⬇️\n\n"
                "💡 **영양상담 필요 가능성 안내**\n\n"
                "⬇️\n\n"
                "📍 **우리동네 보건소·복지기관 영양상담 확인**"
            )
            st.caption(
                "이 안내는 영양상태를 진단하거나 상담이 반드시 필요한지를 판정하는 것이 "
                "아니에요. 참고용 연결 안내로만 봐주세요."
            )

            nutrition_items = adapter.nutrition_situation_summary(profile)
            if nutrition_items:
                st.markdown("**입력하신 내용**")
                for item in nutrition_items:
                    st.markdown(f"- {item}")
else:
    st.caption("정보를 입력하고 '내게 맞는 서비스 찾아보기'를 눌러주세요.")
