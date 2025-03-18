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

# AI 응답 생성 함수
def get_ai_response(user_input, is_surrender=False):
    # API 키가 설정되어 있는 경우 Claude API 사용
    if api_key:
        try:
            client = anthropic.Anthropic(api_key=api_key)
            
            # 항복 시 프롬프트 추가
            additional_system = ""
            if is_surrender:
                additional_system = "\n학생의 주장이 매우 설득력 있어 당신은 항복하기로 했습니다. 학생의 주장을 인정하고 당신의 관점이 어떻게 바뀌었는지 설명하세요."
            
            # 최근 대화 내용만 포함 (컨텍스트 길이 제한)
            messages = []
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
                    system=system_message + additional_system,
                    messages=messages
                )
            
            # 응답 저장
            st.session_state.claude_messages.append({"role": "user", "content": user_input})
            st.session_state.claude_messages.append({"role": "assistant", "content": response.content[0].text})
            
            return response.content[0].text
            
        except Exception as e:
            st.error(f"Claude API 호출 중 오류가 발생했습니다: {e}")
            # 오류 발생 시 대체 응답 사용
            return get_fallback_response(user_input, is_surrender)
    else:
        # API 키가 없는 경우 대체 응답 사용
        return get_fallback_response(user_input, is_surrender)

# 대체 응답 생성 함수 (API 오류 또는 API 키 미설정 시 사용)
def get_fallback_response(user_input, is_surrender=False):
    # 항복 메시지
    surrender_responses = [
        "지금까지의 토론을 통해 제 생각이 바뀌었습니다. 학생님의 논점들, 특히 AI를 활용한 수행평가가 미래 사회에 필요한 역량을 기르는 데 도움이 된다는 점과 적절한 가이드라인을 통해 공정성을 확보할 수 있다는 주장이 매우 설득력 있습니다. AI를 수행평가에 활용하는 것은 학생들의 디지털 리터러시를 향상시키고, 실제 사회에서 마주할 도구를 교육 환경에서 미리 익히는 기회가 될 수 있다는 점에 동의합니다. 결국 중요한 것은 AI를 어떻게 활용하느냐의 문제인 것 같습니다. 훌륭한 토론 감사합니다.",
        
        "제 생각을 바꾸게 되었습니다. 학생님이 제시한 AI 활용의 교육적 가치와 미래지향적 학습 방식에 대한 논점이 매우 타당합니다. 특히 AI를 활용하면서도 학생의 사고 과정을 평가할 수 있는 방법들과 AI 리터러시 자체를 교육 목표로 삼을 수 있다는 점은 제가 간과했던 부분입니다. 수행평가에서 AI를 완전히 배제하기보다는, 적절한 가이드라인과 함께 활용하는 것이 더 현실적이고 교육적으로 가치 있는 접근법이라는 데 동의합니다. 좋은 의견 감사합니다.",
        
        "학생님의 논리적이고 미래지향적인 관점에 설득되었습니다. AI를 수행평가에 활용하는 것은 단순히 '부정행위'의 문제가 아니라, 변화하는 교육 환경과 사회에 적응하는 방법의 문제라는 점을 이해하게 되었습니다. 특히 AI를 활용한 수행평가가 실제 직업 세계의 업무 환경을 반영한다는 점과, 중요한 것은 결과물이 아닌 AI와 함께 일하는 과정을 평가할 수 있다는, 학생님의 주장이 매우 설득력 있습니다. 제 입장을 재고하게 해주셔서 감사합니다."
    ]
    
    # 일반 반박 응답
    general_rebuttals = [
        "인공지능을 수행평가에 활용하는 것은 학생의 실제 역량을 평가하기 어렵게 만듭니다. AI가 제공하는 답변과 학생 자신의 사고 과정을 구분하기 어려워, 평가의 신뢰성이 크게 저하될 수 있습니다. 또한 모든 학생이 동일한 수준의 AI에 접근할 수 없다면, 이는 새로운 형태의 교육 불평등을 만들어낼 위험이 있습니다.",
        
        "AI를 수행평가에 활용하면 학생들의 비판적 사고력과 창의성 발달이 저해될 수 있습니다. 스스로 고민하고 해결책을 찾는 과정에서 진정한 학습이 이루어지는데, AI에 의존하면 이러한 과정이 생략될 우려가 있습니다. 교육의 목적은 단순히 결과물을 만들어내는 것이 아니라 사고하는 능력을 기르는 것입니다.",
        
        "AI가 제공하는 정보는 항상 정확하거나 적절한 것이 아닙니다. 학생들이 AI의 답변을 비판적으로 검토할 능력이 부족하다면, 잘못된 정보를 바탕으로 과제를 수행할 위험이 있습니다. 또한 AI는 윤리적 맥락이나 문화적 특수성을 완전히 이해하지 못할 수 있어, 이러한 측면이 중요한 과제에서는 부적절한 결과를 가져올 수 있습니다.",
        
        "수행평가의 목적은 학습 과정에서 학생의 성장을 평가하는 것인데, AI를 활용하면 이 과정이 왜곡될 수 있습니다. 실제로 많은 교육자들은 AI의 도움을 받은 과제와 학생 스스로 완성한 과제를 구분하기 어려워하고 있습니다. 이는 평가의 공정성에 심각한 문제를 제기합니다.",
        
        "AI에 과도하게 의존하면 학생들이 실제 문제 해결 상황에서 필요한 인내심과 끈기를 기르기 어렵습니다. 어려운 문제에 직면했을 때 스스로 해결하려는 노력 대신 즉시 AI에 해답을 구하는 습관이 형성될 수 있습니다. 이는 장기적으로 학생들의 자기주도적 학습 능력 발달에 부정적 영향을 미칠 수 있습니다."
    ]
    
    # 학생의 주장에 따른 맞춤형 반박
    specific_rebuttals = {
        "효율": "효율성과 시간 절약은 중요한 가치이지만, 교육에서는 과정을 통한 배움이 더 중요합니다. AI를 활용하여 시간을 절약할 수 있다는 점은 인정하지만, 이것이 진정한 학습으로 이어진다고 보기 어렵습니다. 실제로 연구에 따르면 어려움을 겪고 스스로 해결책을 찾는 과정에서 더 깊은 이해와 장기 기억이 형성됩니다. AI가 즉각적인 답을 제공하면 이러한 '생산적 실패'의 기회가 사라집니다.",
        
        "미래": "미래 사회를 준비한다는 관점은 중요하지만, AI를 무비판적으로 활용하는 것과 AI를 이해하고 적절히 활용하는 능력은 다릅니다. 수행평가에서 AI를 제한 없이 사용하도록 허용하면, 학생들은 AI의 작동 원리나 한계를 이해하지 못한 채 의존하게 될 위험이 있습니다. 진정한 미래 역량은 AI가 대체할 수 없는 창의성, 공감 능력, 윤리적 판단력 등이며, 이러한 능력은 스스로 사고하고 문제를 해결하는 과정에서 발달합니다.",
        
        "평등": "AI 접근성 문제를 해결할 수 있다는 주장은 이상적이지만, 현실적으로 모든 교육 환경에서 동일한 수준의 AI 접근성을 보장하기는 어렵습니다. 가정환경, 지역, 학교 간 디지털 인프라 차이가 여전히 존재하며, 이는 새로운 형태의 교육 불평등을 만들 수 있습니다. 또한 AI 사용 능력 자체가 학생마다 다르기 때문에, AI 활용을 허용하는 것이 오히려 기존의 불평등을 심화시킬 수 있습니다.",
        
        "창의": "AI가 창의성을 향상시킨다는 주장은 일부 상황에서 타당할 수 있지만, 수행평가에서는 학생 자신의 창의적 사고 과정을 평가하는 것이 중요합니다. AI가 제안하는 아이디어에 의존하면 학생들은 스스로 창의적 사고를 발전시키는 기회를 잃게 됩니다. 또한 AI는 기존 데이터를 기반으로 생성하기 때문에, 진정으로 혁신적인 아이디어보다는 이미 존재하는 패턴의 변형을 제공하는 경향이 있습니다.",
        
        "역량": "AI 활용 자체를 새로운 역량으로 볼 수 있다는 주장은 일리가 있습니다. 그러나 수행평가는 교과목의 특정 학습 목표를 달성했는지 평가하는 것이 목적입니다. AI를 무제한으로 활용하면 이러한 핵심 역량의 발달을 제대로 평가하기 어렵습니다. 예를 들어, 수학적 문제 해결 능력이나 분석적 글쓰기 능력 등 특정 교과의 본질적 역량 개발이 저해될 수 있습니다."
    }
    
    # 항복 여부에 따라 응답 선택
    if is_surrender:
        return random.choice(surrender_responses)
    
    # 맞춤형 응답 선택 (키워드 기반)
    for keyword, response in specific_rebuttals.items():
        if keyword in user_input.lower():
            return response
    
    # 일반 응답 선택
    return random.choice(general_rebuttals)

# 토론 시작 함수
def start_debate():
    st.session_state.debate_started = True
    st.session_state.start_time = datetime.now()
    st.session_state.round_count = 0
    st.session_state.ai_surrender = False
    st.session_state.claude_messages = []
    
    # 초기 메시지 설정
    initial_ai_message = """안녕하세요, 오늘 '인공지능으로 수행평가를 해도 될까?'라는 주제로 토론을 진행하겠습니다. 

저는 인공지능을 수행평가에 활용하는 것에 반대하는 입장입니다. 인공지능을 수행평가에 활용하면 학생의 진정한 학습 성취를 평가하기 어렵고, 학습의 본질적 가치가 훼손될 수 있다고 생각합니다. 또한 모든 학생이 동일한 수준의 AI 접근성을 가지고 있지 않기 때문에 교육 불평등이 심화될 수 있습니다. 

학생의 의견을 들어보겠습니다."""
    
    st.session_state.messages.append({"role": "assistant", "content": initial_ai_message})
    st.session_state.claude_messages.append({"role": "assistant", "content": initial_ai_message})

# 세션 변수 오류 방지 함수 (안전하게 값 설정)
def safe_set_session_state(key, value):
    try:
        st.session_state[key] = value
    except Exception as e:
        st.error(f"세션 상태 설정 중 오류 발생: {e}")

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
        user_input = st.text_area("당신의 주장을 입력하세요:", height=150, key="input_field")
        
        if st.button("의견 제출", key="submit_opinion"):
            if user_input.strip() != "":
                # 사용자 메시지 추가
                st.session_state.messages.append({"role": "user", "content": user_input})
                st.session_state.round_count += 1
                
                # 항복 조건 확인
                if check_surrender_conditions():
                    ai_response = get_ai_response(user_input, is_surrender=True)
                    st.session_state.messages.append({"role": "assistant", "content": ai_response, "surrender": True})
                    st.session_state.ai_surrender = True
                else:
                    # 일반 응답
                    ai_response = get_ai_response(user_input)
                    st.session_state.messages.append({"role": "assistant", "content": ai_response})
                
                # 입력 필드 초기화 및 페이지 새로고침 (오류 방지)
                st.rerun()
