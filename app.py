import streamlit as st
import time
import random
import uuid
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

# 세션 ID 생성 (각 사용자마다 고유한 ID 부여)
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# 세션별 상태 관리를 위한 키 생성 함수
def get_session_key(base_key):
    return f"{base_key}_{st.session_state.session_id}"

# 세션 상태 초기화
if get_session_key('messages') not in st.session_state:
    st.session_state[get_session_key('messages')] = []

if get_session_key('debate_started') not in st.session_state:
    st.session_state[get_session_key('debate_started')] = False

if get_session_key('start_time') not in st.session_state:
    st.session_state[get_session_key('start_time')] = None

if get_session_key('round_count') not in st.session_state:
    st.session_state[get_session_key('round_count')] = 0

if get_session_key('ai_surrender') not in st.session_state:
    st.session_state[get_session_key('ai_surrender')] = False

if get_session_key('claude_messages') not in st.session_state:
    st.session_state[get_session_key('claude_messages')] = []

# 시스템 메시지 설정
system_message = """
당신은 '인공지능으로 수행평가를 해도 될까?'라는 주제에 대해 고등학생과 토론합니다.
당신은 인공지능으로 수행평가를 하는 것에 반대하는 입장입니다.

지침:
1. 친근하고 자연스러운 말투를 사용하세요. 학생과 대화하는 느낌으로 말하세요.
2. 너무 형식적이거나 딱딱하게 말하지 마세요.
3. 문단을 나누지 말고 한 문단으로 답변하세요.
4. 질문을 던질 때는 "학생의 의견을 듣고 싶습니다" 같은 공식적인 표현보다 "넌 어떻게 생각해?" 같은 친근한 표현을 사용하세요.
5. 적절히 구어체 표현과 감정을 섞어 자연스러운 대화를 만드세요.

당신의 반대 입장에 대한 주요 논거:
1. 학습의 진정한 목적과 과정의 중요성
2. 평가의 공정성과 신뢰성 문제
3. 디지털 격차와 접근성 문제
4. 비판적 사고력과 창의성 발달 저해 가능성
5. 학생들의 AI 의존도 증가 우려

토론은 최대 20분간 진행되며, 학생이 매우 강력한 주장을 펼치거나 당신의 모든 논점을 효과적으로 반박할 경우
항복을 선언해야 합니다. 항복 시 학생의 논점을 인정하고 자신의 관점이 바뀌었음을 표현하세요.
"""

# 토론 정보 함수
def get_elapsed_time():
    if st.session_state[get_session_key('start_time')]:
        elapsed = datetime.now() - st.session_state[get_session_key('start_time')]
        minutes = int(elapsed.total_seconds() // 60)
        seconds = int(elapsed.total_seconds() % 60)
        return f"{minutes}분 {seconds}초"
    return "0분 0초"

# AI 항복 조건 확인
def check_surrender_conditions():
    # 라운드 수에 따른 항복 확률 (라운드가 진행될수록 항복 확률 증가)
    round_factor = min(0.1 * st.session_state[get_session_key('round_count')], 0.5)
    
    # 시간 경과에 따른 항복 확률 (15분 이상 지나면 항복 확률 크게 증가)
    time_factor = 0
    if st.session_state[get_session_key('start_time')]:
        elapsed_minutes = (datetime.now() - st.session_state[get_session_key('start_time')]).total_seconds() / 60
        if elapsed_minutes > 15:
            time_factor = 0.4
        elif elapsed_minutes > 10:
            time_factor = 0.2
    
    # 최종 항복 확률 계산
    surrender_probability = round_factor + time_factor
    
    # 항복 결정 (라운드 7 이상 + 일정 확률)
    if st.session_state[get_session_key('round_count')] >= 7 and random.random() < surrender_probability:
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
                additional_system = "\n학생의 주장이 매우 설득력 있어 당신은 항복하기로 했습니다. 학생의 주장을 인정하고 당신의 관점이 어떻게 바뀌었는지 설명하세요. 친근한 말투로 한 문단으로 표현하세요."
            
            # 최근 대화 내용만 포함 (컨텍스트 길이 제한)
            messages = []
            for msg in st.session_state[get_session_key('claude_messages')][-10:]:
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
            st.session_state[get_session_key('claude_messages')].append({"role": "user", "content": user_input})
            st.session_state[get_session_key('claude_messages')].append({"role": "assistant", "content": response.content[0].text})
            
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
    # 항복 메시지 (친근한 말투로 수정)
    surrender_responses = [
        "와, 네 의견을 들으니 내 생각이 바뀌었어. 특히 AI를 활용한 수행평가가 미래 사회에 필요한 역량을 기르는 데 도움된다는 점과 가이드라인으로 공정성을 확보할 수 있다는 주장이 정말 설득력 있더라. AI를 활용하면 디지털 리터러시도 향상되고, 실제 사회에서 사용할 도구를 미리 배울 기회가 된다는 점에 동의해. 결국 중요한 건 AI를 어떻게 활용하느냐인 것 같아. 좋은 토론 고마워!",
        
        "음, 내 생각이 바뀌었어. 네가 말한 AI 활용의 교육적 가치와 미래지향적 학습 방식에 대한 논점이 정말 타당하더라. 특히 AI를 활용하면서도 학생의 사고 과정을 평가할 수 있는 방법이 있고, AI 리터러시 자체를 교육 목표로 삼을 수 있다는 건 내가 미처 생각 못 했던 부분이야. 수행평가에서 AI를 완전히 배제하기보다는 적절한 가이드라인과 함께 활용하는 게 더 현실적이고 교육적으로도 가치 있겠다. 좋은 의견 고마워!",
        
        "네 논리적이고 미래지향적인 관점에 완전히 설득됐어. AI를 수행평가에 활용하는 건 단순한 '부정행위' 문제가 아니라 변화하는 교육 환경과 사회에 적응하는 방법의 문제라는 걸 이제 알겠어. 특히 AI를 활용한 수행평가가 실제 직업 세계를 반영한다는 점과, 중요한 건 결과물이 아니라 AI와 함께 일하는 과정을 평가할 수 있다는 네 주장이 정말 설득력 있었어. 내 입장을 다시 생각하게 해줘서 고마워."
    ]
    
    # 일반 반박 응답 (친근한 말투로 수정)
    general_rebuttals = [
        "AI를 수행평가에 활용하면 학생의 실제 능력을 평가하기 어려워질 것 같아. AI가 제공한 답변과 네가 직접 생각한 내용을 구분하기 어려워서 평가의 신뢰성이 떨어질 수 있거든. 또 모든 친구들이 같은 수준의 AI를 쓸 수 있는 것도 아니라서 새로운 불평등이 생길 수도 있어. 너는 이런 문제에 대해서는 어떻게 생각해?",
        
        "AI에 의존하면 비판적 사고력이나 창의성 발달이 방해받을 수 있지 않을까? 스스로 고민하고 해결책을 찾는 과정에서 진짜 배움이 이루어지는데, AI가 바로 답을 주면 이런 과정이 생략될 수 있잖아. 교육의 목적은 단순히 결과물을 만드는 게 아니라 생각하는 능력을 기르는 거라고 생각하는데, 너는 어떻게 생각해?",
        
        "AI가 항상 정확한 정보를 주는 건 아니라는 점도 생각해봐야 할 것 같아. 학생들이 AI 답변을 비판적으로 검토할 능력이 부족하면 잘못된 정보로 과제를 할 위험도 있어. 또 AI는 윤리적 맥락이나 문화적 특수성을 완전히 이해 못 하는 경우도 있어서 이런 측면이 중요한 과제에선 문제가 될 수도 있지. 이런 부분에 대해선 어떻게 생각해?",
        
        "수행평가의 목적은 네가 배우는 과정에서 얼마나 성장했는지 평가하는 건데, AI를 쓰면 이 과정이 왜곡될 수 있지 않을까? 실제로 많은 선생님들이 AI의 도움을 받은 과제와 학생이 직접 한 과제를 구분하기 힘들어한대. 이건 평가의 공정성에 꽤 심각한 문제가 될 수 있을 것 같은데, 이 부분은 어떻게 생각해?",
        
        "AI에 너무 의존하면 실제 문제 해결할 때 필요한 인내심이나 끈기를 기르기 어려울 것 같아. 어려운 문제가 나왔을 때 스스로 해결하려고 노력하는 대신 바로 AI에 답을 구하는 습관이 생길 수 있잖아. 이건 장기적으로 자기주도 학습 능력에 안 좋은 영향을 미칠 수도 있을 것 같은데, 너는 어떻게 생각해?"
    ]
    
    # 학생의 주장에 따른 맞춤형 반박 (친근한 말투로 수정)
    specific_rebuttals = {
        "효율": "효율성이나 시간 절약이 중요하다는 건 맞지만, 교육에선 과정을 통한 배움이 더 중요하지 않을까? AI로 시간을 아낄 수는 있겠지만, 그게 진짜 학습으로 이어진다고 보기는 좀 어려울 것 같아. 연구에 따르면 어려움을 겪고 스스로 해결책을 찾는 과정에서 더 깊이 이해하고 오래 기억한다고 해. AI가 바로 답을 주면 이런 '생산적 실패'의 기회가 없어질 수 있어. 너는 어떻게 생각해?",
        
        "미래": "미래를 준비한다는 건 중요하지. 근데 AI를 무비판적으로 쓰는 것과 제대로 이해하고 활용하는 건 다른 문제 아닐까? 수행평가에서 AI를 마음대로 쓰게 하면 학생들이 AI 작동 원리나 한계를 이해 못한 채 의존하게 될 수도 있어. 진짜 미래에 필요한 건 AI가 대체 못하는 창의성이나 공감 능력, 윤리적 판단력 같은 거고, 이런 능력은 스스로 생각하고 문제 해결하는 과정에서 키워지는 것 같은데, 너는 어떻게 생각해?",
        
        "평등": "AI 접근성 문제를 해결할 수 있다는 건 이상적인 생각이지만, 현실적으로 모든 학교나 집에서 같은 수준의 AI를 쓸 수 있게 하기는 어려울 것 같아. 집안 형편이나 지역, 학교마다 디지털 환경 차이가 있고, 이게 새로운 교육 불평등을 만들 수 있거든. 또 AI 사용 능력 자체가 학생마다 다르니까, AI 활용을 허용하면 오히려 기존 불평등이 더 심해질 수도 있지 않을까? 이 부분에 대해선 어떻게 생각해?",
        
        "창의": "AI가 창의성을 높여준다는 건 어떤 상황에선 맞을 수 있지만, 수행평가에선 네가 스스로 얼마나 창의적으로 생각하는지 평가하는 게 중요하지 않을까? AI가 제안하는 아이디어에 의존하면 스스로 창의적 사고력을 키울 기회를 놓칠 수 있어. 또 AI는 기존 데이터를 기반으로 생성하기 때문에 정말 새롭고 혁신적인 아이디어보다는 이미 있는 패턴의 변형을 주로 만들어내는 경향이 있거든. 너는 이 부분에 대해 어떻게 생각해?",
        
        "역량": "AI 활용 자체를 새로운 역량으로 볼 수 있다는 건 일리가 있어. 하지만 수행평가는 각 과목의 특정 학습 목표를 얼마나 달성했는지 평가하는 게 목적이잖아. AI를 마음대로 쓰면 이런 핵심 역량 발달을 제대로 평가하기 어려울 것 같아. 예를 들어 수학 문제 해결 능력이나 글쓰기 능력 같은 교과 본연의 역량 개발이 방해받을 수 있지 않을까? 이 부분은 어떻게 생각해?"
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
    st.session_state[get_session_key('debate_started')] = True
    st.session_state[get_session_key('start_time')] = datetime.now()
    st.session_state[get_session_key('round_count')] = 0
    st.session_state[get_session_key('ai_surrender')] = False
    st.session_state[get_session_key('claude_messages')] = []
    
    # 초기 메시지 설정 (친근한 말투로 수정)
    initial_ai_message = """안녕! 오늘은 'AI로 수행평가를 해도 될까?'라는 주제로 토론해보자. 나는 AI를 수행평가에 활용하는 건 좋지 않다고 생각해. AI를 활용하면 네가 진짜로 배운 것인지 확인하기 어렵고, 학습의 진짜 가치가 훼손될 수 있거든. 또 모든 친구들이 똑같은 AI를 쓸 수 있는 것도 아니라서 불공평한 상황이 생길 수도 있어. 너는 이 주제에 대해 어떻게 생각해? 편하게 얘기해줘."""
    
    st.session_state[get_session_key('messages')].append({"role": "assistant", "content": initial_ai_message})
    st.session_state[get_session_key('claude_messages')].append({"role": "assistant", "content": initial_ai_message})

# 메인 UI
st.markdown("<div class='debate-header'><h1>🤖 인공지능으로 수행평가를 해도 될까?</h1></div>", unsafe_allow_html=True)

# 세션 ID 표시 (디버깅용 - 필요시 주석 해제)
# st.sidebar.write(f"세션 ID: {st.session_state.session_id}")

# 토론 시작 버튼 (토론이 시작되지 않았을 때만 표시)
if not st.session_state[get_session_key('debate_started')]:
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
            st.rerun()

# 토론이 시작된 경우
if st.session_state[get_session_key('debate_started')]:
    # 타이머와 라운드 표시
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(f"<div class='timer'>⏱️ 경과 시간: {get_elapsed_time()}</div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='round-indicator'>🔄 현재 라운드: {st.session_state[get_session_key('round_count')]}</div>", unsafe_allow_html=True)
    
    # 메시지 표시
    for message in st.session_state[get_session_key('messages')]:
        if message["role"] == "user":
            st.markdown(f"<div class='user-message'><b>학생:</b> {message['content']}</div>", unsafe_allow_html=True)
        else:
            if "surrender" in message:
                st.markdown(f"<div class='surrender-message'><b>AI:</b> {message['content']}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='ai-message'><b>AI:</b> {message['content']}</div>", unsafe_allow_html=True)
    
    # 항복 메시지가 표시된 후 토론 재시작 버튼
    if st.session_state[get_session_key('ai_surrender')]:
        if st.button("토론 다시 시작하기", key="restart_debate"):
            st.session_state[get_session_key('messages')] = []
            st.session_state[get_session_key('debate_started')] = False
            st.session_state[get_session_key('ai_surrender')] = False
            st.rerun()
    
    # 입력 필드 (항복하지 않았을 경우에만 표시)
    if not st.session_state[get_session_key('ai_surrender')]:
        user_input = st.text_area("당신의 주장을 입력하세요:", height=150, key="input_field")
        
        if st.button("의견 제출", key="submit_opinion"):
            if user_input.strip() != "":
                # 사용자 메시지 추가
                st.session_state[get_session_key('messages')].append({"role": "user", "content": user_input})
                st.session_state[get_session_key('round_count')] += 1
                
                # 항복 조건 확인
                if check_surrender_conditions():
                    ai_response = get_ai_response(user_input, is_surrender=True)
                    st.session_state[get_session_key('messages')].append({"role": "assistant", "content": ai_response, "surrender": True})
                    st.session_state[get_session_key('ai_surrender')] = True
                else:
                    # 일반 응답
                    ai_response = get_ai_response(user_input)
                    st.session_state[get_session_key('messages')].append({"role": "assistant", "content": ai_response})
                
                # 페이지 새로고침
                st.rerun()
