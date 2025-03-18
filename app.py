import streamlit as st
import time
import random
from datetime import datetime, timedelta
import anthropic
import os

# 스트림릿 앱 설정
st.set_page_config(page_title="AI 수행평가 토론", page_icon="🤖", layout="wide")

# CSS 스타일 추가
st.markdown("""
<style>
    .user-message {
        background-color: #e6f7ff;
        padding: 10px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    .ai-message {
        background-color: #f0f0f0;
        padding: 10px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    .surrender-message {
        background-color: #ffe6e6;
        padding: 15px;
        border-radius: 10px;
        margin: 20px 0;
        font-weight: bold;
    }
    .debate-header {
        text-align: center;
        margin-bottom: 30px;
    }
    .timer {
        font-size: 18px;
        font-weight: bold;
        margin-bottom: 20px;
    }
    .round-indicator {
        font-size: 16px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# 환경변수에서 API 키 가져오기
api_key = st.secrets.get("ANTHROPIC_API_KEY", None)
if not api_key:
    api_key = os.environ.get("ANTHROPIC_API_KEY", None)

# API 키 설정 확인
if not api_key:
    st.error("API 키가 설정되지 않았습니다. 스트림릿 시크릿이나 환경변수로 ANTHROPIC_API_KEY를 설정해주세요.")
    st.stop()

# Anthropic 클라이언트 초기화
try:
    client = anthropic.Anthropic(api_key=api_key)
except Exception as e:
    st.error(f"Anthropic 클라이언트 초기화 중 오류가 발생했습니다: {e}")
    st.stop()

# 세션 상태 초기화
if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'debate_started' not in st.session_state:
    st.session_state.debate_started = False

if 'start_time' not in st.session_state:
    st.session_state.start_time = None

if 'round_count' not in st.session_state:
    st.session_state.round_count = 0

if 'ai_surrender' not in st.session_state:
    st.session_state.ai_surrender = False

if 'claude_messages' not in st.session_state:
    st.session_state.claude_messages = []

# 시스템 메시지 설정
system_message = """
당신은 '인공지능으로 수행평가를 해도 될까?'라는 주제에 대해 학생과 토론합니다.
당신은 인공지능으로 수행평가를 하는 것에 반대하는 입장입니다. 
학생의 주장에 대해 논리적으로 반박하세요.

당신의 반대 입장에 대한 주요 논거:
1. 학습의 진정한 목적과 과정의 중요성
2. 평가의 공정성과 신뢰성 문제
3. 디지털 격차와 접근성 문제
4. 비판적 사고력과 창의성 발달 저해 가능성
5. 학생들의 AI 의존도 증가 우려

토론은 최대 20분간 진행되며, 학생이 매우 강력한 주장을 펼치거나 당신의 모든 논점을 효과적으로 반박할 경우
항복을 선언해야 합니다. 항복 시 학생의 논점을 인정하고 자신의 관점이 바뀌었음을 표현하세요.

답변은 간결하게 2-3문단 이내로 유지하고, 학생의 논점을 존중하면서도 논리적으로 반박하세요.
"""

# 토론 정보 함수
def get_elapsed_time():
    if st.session_state.start_time:
        elapsed = datetime.now() - st.session_state.start_time
        minutes = int(elapsed.total_seconds() // 60)
        seconds = int(elapsed.total_seconds() % 60)
        return f"{minutes}분 {seconds}초"
    return "0분 0초"

# AI 항복 조건 확인
def check_surrender_conditions():
    # 라운드 수에 따른 항복 확률 (라운드가 진행될수록 항복 확률 증가)
    round_factor = min(0.1 * st.session_state.round_count, 0.5)
    
    # 시간 경과에 따른 항복 확률 (15분 이상 지나면 항복 확률 크게 증가)
    time_factor = 0
    if st.session_state.start_time:
        elapsed_minutes = (datetime.now() - st.session_state.start_time).total_seconds() / 60
        if elapsed_minutes > 15:
            time_factor = 0.4
        elif elapsed_minutes > 10:
            time_factor = 0.2
    
    # 최종 항복 확률 계산
    surrender_probability = round_factor + time_factor
    
    # 항복 결정 (라운드 7 이상 + 일정 확률)
    if st.session_state.round_count >= 7 and random.random() < surrender_probability:
        return True
    return False

# Claude API로 응답 생성
def get_claude_response(user_input, is_surrender=False):
    try:
        # 항복 시 프롬프트 추가
        if is_surrender:
            surrender_prompt = "학생의 주장이 매우 설득력 있어 당신은 항복하기로 했습니다. 학생의 주장을 인정하고 당신의 관점이 어떻게 바뀌었는지 설명하세요. 답변은 2-3문단 이내로 간결하게 유지하세요."
            
            messages = [
                {"role": "system", "content": system_message + "\n" + surrender_prompt}
            ]
            
            # 이전 대화 내용 추가 (최대 5개 메시지만)
            for msg in st.session_state.claude_messages[-10:]:
                messages.append(msg)
                
            # 사용자 입력 추가
            messages.append({"role": "user", "content": user_input})
            
        else:
            # 일반 응답 요청
            messages = [{"role": "system", "content": system_message}]
            
            # 이전 대화 내용 추가
            for msg in st.session_state.claude_messages[-10:]:
                messages.append(msg)
                
            # 사용자 입력 추가
            messages.append({"role": "user", "content": user_input})
        
        # API 요청
        with st.spinner("AI가 응답을 생성하는 중..."):
            response = client.messages.create(
                model="claude-3-7-sonnet-20250219",
                max_tokens=1024,
                temperature=0.7,
                messages=messages
            )
        
        # 응답 저장
        st.session_state.claude_messages.append({"role": "user", "content": user_input})
        st.session_state.claude_messages.append({"role": "assistant", "content": response.content[0].text})
        
        return response.content[0].text
        
    except Exception as e:
        st.error(f"Claude API 호출 중 오류가 발생했습니다: {e}")
        
        # 오류 시 대체 응답
        fallback_responses = [
            "죄송합니다만, 인공지능을 수행평가에 활용하는 것은 학습의 본질을 훼손할 위험이 있습니다. 학생 스스로의 사고력과 문제해결 능력 발달이 중요합니다.",
            "AI를 수행평가에 활용하면 디지털 격차로 인한 불평등이 심화될 수 있습니다. 모든 학생이 동일한 수준의 AI에 접근할 수 없기 때문입니다.",
            "교육의 목적은 지식 전달뿐만 아니라 비판적 사고력과 창의성을 기르는 것입니다. AI에 의존하면 이러한 핵심 역량 개발이 제한될 수 있습니다."
        ]
        
        if is_surrender:
            return "기술적 문제가 있었지만, 학생님의 주장을 통해 AI를 수행평가에 활용하는 것에 대한 제 관점이 바뀌었습니다. 적절한 가이드라인과 함께 AI를 교육적 도구로 활용할 가능성이 있다고 생각합니다."
        else:
            return random.choice(fallback_responses)

# 토론 시작 함수
def start_debate():
    st.session_state.debate_started = True
    st.session_state.start_time = datetime.now()
    st.session_state.round_count = 0
    st.session_state.ai_surrender = False
    st.session_state.claude_messages = []
    
    # 초기 메시지 설정
    initial_ai_message = """안녕하세요, 오늘 '인공지능으로 수행평가를 해도 될까?'라는 주제로 토론을 진행하겠습니다. 

저는 인공지능을 수행평가에 활용하는 것에 반대하는 입장입니다. 인공지능을 수행평가에 활용하면 학생의 진정한 학습 성취를 평가하기 어렵고, 학습의 본질적 가치가 훼손될 수 있다고 생각합니다. 또한 모든 학생이 동일한 AI 접근성을 가지고 있지 않기 때문에 교육 불평등이 심화될 수 있습니다. 

학생의 의견을 들어보겠습니다."""
    
    st.session_state.messages.append({"role": "assistant", "content": initial_ai_message})
    st.session_state.claude_messages.append({"role": "assistant", "content": initial_ai_message})

# 메인 UI
st.markdown("<div class='debate-header'><h1>🤖 인공지능으로 수행평가를 해도 될까?</h1></div>", unsafe_allow_html=True)

# 토론 시작 버튼 (토론이 시작되지 않았을 때만 표시)
if not st.session_state.debate_started:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="text-align: center; padding: 20px; background-color: #f5f5f5; border-radius: 10px; margin-bottom: 20px;">
            <h3>토론 안내</h3>
            <p>이 토론에서는 '인공지능으로 수행평가를 해도 될까?'라는 주제로 AI와 토론을 진행합니다.</p>
            <p>당신은 <b>인공지능을 수행평가에 활용하는 것에 찬성하는 입장</b>을 취하게 됩니다.</p>
            <p>토론은 약 20분간 진행되며, 상대방(AI)을 설득하는 것이 목표입니다.</p>
            <p>충분히 설득력 있는 주장을 펼치면 AI가 항복할 수 있습니다.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("토론 시작하기", key="start_debate"):
            start_debate()
            st.experimental_rerun()

# 토론이 시작된 경우
if st.session_state.debate_started:
    # 타이머와 라운드 표시
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(f"<div class='timer'>⏱️ 경과 시간: {get_elapsed_time()}</div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='round-indicator'>🔄 현재 라운드: {st.session_state.round_count}</div>", unsafe_allow_html=True)
    
    # 메시지 표시
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(f"<div class='user-message'><b>학생:</b> {message['content']}</div>", unsafe_allow_html=True)
        else:
            if "surrender" in message:
                st.markdown(f"<div class='surrender-message'><b>AI:</b> {message['content']}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='ai-message'><b>AI:</b> {message['content']}</div>", unsafe_allow_html=True)
    
    # 항복 메시지가 표시된 후 토론 재시작 버튼
    if st.session_state.ai_surrender:
        if st.button("토론 다시 시작하기", key="restart_debate"):
            st.session_state.messages = []
            st.session_state.debate_started = False
            st.session_state.ai_surrender = False
            st.experimental_rerun()
    
    # 입력 필드 (항복하지 않았을 경우에만 표시)
    if not st.session_state.ai_surrender:
        user_input = st.text_area("당신의 주장을 입력하세요:", height=150, key="user_input")
        
        if st.button("의견 제출", key="submit_opinion"):
            if user_input.strip() != "":
                # 사용자 메시지 추가
                st.session_state.messages.append({"role": "user", "content": user_input})
                st.session_state.round_count += 1
                
                # 항복 조건 확인
                if check_surrender_conditions():
                    ai_response = get_claude_response(user_input, is_surrender=True)
                    st.session_state.messages.append({"role": "assistant", "content": ai_response, "surrender": True})
                    st.session_state.ai_surrender = True
                else:
                    # 일반 응답
                    ai_response = get_claude_response(user_input)
                    st.session_state.messages.append({"role": "assistant", "content": ai_response})
                
                # 입력 필드 초기화 및 페이지 새로고침
                st.session_state.user_input = ""
                st.experimental_rerun()
