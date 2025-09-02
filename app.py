import streamlit as st
import os
import re
from openai import OpenAI
from typing import Dict

# 페이지 설정
st.set_page_config(
    page_title="토론 논증 코칭 챗봇",
    page_icon="🎓",
    layout="wide"
)

# CSS 스타일
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 30px;
    }
    .argument-structure {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .claim-box {
        background-color: #e8f4f8;
        padding: 15px;
        border-left: 4px solid #1e88e5;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .evidence-box {
        background-color: #fff3e0;
        padding: 15px;
        border-left: 4px solid #fb8c00;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .reinforcement-box {
        background-color: #e8f5e9;
        padding: 15px;
        border-left: 4px solid #43a047;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .fact-check-box {
        background-color: #fce4ec;
        padding: 15px;
        border-left: 4px solid #e91e63;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .coaching-feedback {
        background-color: #f5f5f5;
        padding: 20px;
        border-radius: 10px;
        margin-top: 20px;
    }
    .progress-indicator {
        padding: 10px;
        background-color: #e3f2fd;
        border-radius: 5px;
        margin-bottom: 20px;
    }
    .chat-message {
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    .user-message {
        background-color: #e6f7ff;
        margin-left: 20%;
    }
    .assistant-message {
        background-color: #f0f0f0;
        margin-right: 20%;
    }
</style>
""", unsafe_allow_html=True)

# API 클라이언트 초기화
@st.cache_resource
def init_clients():
    upstage_key = st.secrets.get("UPSTAGE_API_KEY", None)
    if not upstage_key:
        upstage_key = os.environ.get("UPSTAGE_API_KEY", None)
    
    perplexity_key = st.secrets.get("PERPLEXITY_API_KEY", None)
    if not perplexity_key:
        perplexity_key = os.environ.get("PERPLEXITY_API_KEY", None)
    
    clients = {}
    
    if upstage_key:
        clients['upstage'] = OpenAI(
            api_key=upstage_key,
            base_url="https://api.upstage.ai/v1"
        )
    
    if perplexity_key:
        clients['perplexity'] = OpenAI(
            api_key=perplexity_key,
            base_url="https://api.perplexity.ai"
        )
    
    return clients

# 세션 상태 초기화
def init_session_state():
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'debate_topic' not in st.session_state:
        st.session_state.debate_topic = ""
    if 'user_position' not in st.session_state:
        st.session_state.user_position = None
    if 'last_section' not in st.session_state:
        st.session_state.last_section = '아직 없음'
    if 'fact_check_results' not in st.session_state:
        st.session_state.fact_check_results = []
    if 'coaching_started' not in st.session_state:
        st.session_state.coaching_started = False
    if 'current_phase' not in st.session_state:
        st.session_state.current_phase = 'topic_selection'

# 섹션 감지 및 분석
def detect_section_type(text: str) -> Dict:
    """입력 텍스트의 섹션 타입을 감지 (서론/본론/결론)"""
    
    # 서론 패턴
    intro_patterns = [
        r'저는.*찬성합니다',
        r'저는.*반대합니다',
        r'.*입장입니다',
        r'.*생각합니다',
        r'.*주장합니다'
    ]
    
    # 결론 패턴
    conclusion_patterns = [
        r'따라서',
        r'결론적으로',
        r'마지막으로',
        r'정리하면',
        r'종합해보면'
    ]
    
    # 섹션 판별
    section_type = 'body'  # 기본값은 본론
    
    for pattern in intro_patterns:
        if re.search(pattern, text):
            section_type = 'intro'
            break
    
    for pattern in conclusion_patterns:
        if re.search(pattern, text):
            section_type = 'conclusion'
            break
    
    return {
        'section_type': section_type,
        'text': text
    }

# 근거 개수 세기
def count_evidence_points(text: str) -> int:
    """본론에서 근거 개수를 센다"""
    
    # 번호 패턴
    numbered_patterns = [
        r'첫째|첫 번째|1\.',
        r'둘째|두 번째|2\.',
        r'셋째|세 번째|3\.',
        r'넷째|네 번째|4\.'
    ]
    
    # 연결어로 추가 근거 확인 (패턴 제거 - 사용 안함)
    
    evidence_count = 0
    
    # 번호 패턴 체크
    for pattern in numbered_patterns:
        if re.search(pattern, text):
            evidence_count += 1
    
    # 번호가 없으면 연결어로 추정
    if evidence_count == 0:
        # 문장 분리하여 근거 추정
        sentences = text.split('.')
        if len(sentences) > 1:
            evidence_count = min(len(sentences) - 1, 4)  # 최대 4개로 제한
        else:
            evidence_count = 1
    
    return min(evidence_count, 4)  # 최대 4개

# 논증 구조 분석 (기존 함수 유지하되 간소화)
def analyze_argument_structure(text: str) -> Dict:
    """텍스트에서 주장, 근거, 보강자료 구조 분석"""
    
    section_info = detect_section_type(text)
    
    structure = {
        'section_type': section_info['section_type'],
        'has_claim': False,
        'has_evidence': False,
        'has_reinforcement': False,
        'evidence_count': 0,
        'sources': []
    }
    
    # 섹션별 분석
    if section_info['section_type'] == 'intro':
        structure['has_claim'] = True
    elif section_info['section_type'] == 'body':
        structure['has_evidence'] = True
        structure['evidence_count'] = count_evidence_points(text)
        # 출처 확인
        if re.search(r'에 따르면|연구에서|조사 결과|통계', text):
            structure['has_reinforcement'] = True
            sources = re.findall(r'([가-힣A-Za-z0-9\s]+)(?:에 따르면|연구에서|조사 결과)', text)
            structure['sources'] = sources
    elif section_info['section_type'] == 'conclusion':
        structure['has_claim'] = True
    
    return structure

# Perplexity를 통한 팩트체크
def perplexity_fact_check(claim: str, source_text: str, clients: Dict) -> Dict:
    """Perplexity로 웹 검색 후 Groundedness Check 수행"""
    result = {
        'is_grounded': False,
        'confidence': 0.0,
        'search_results': '',
        'explanation': '',
        'sources': []
    }
    
    if 'perplexity' not in clients:
        result['explanation'] = "Perplexity API 키가 설정되지 않았습니다."
        return result
    
    try:
        # 1. Perplexity로 웹 검색 수행
        
        response = clients['perplexity'].chat.completions.create(
            model="sonar-small-online",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 팩트체커입니다. 주어진 주장에 대한 사실 여부를 웹 검색을 통해 확인하고, 신뢰할 수 있는 출처와 함께 검증 결과를 제공해주세요."
                },
                {
                    "role": "user",
                    "content": f"다음 주장의 사실 여부를 확인해주세요:\n\n출처: {source_text}\n주장: {claim}\n\n신뢰할 수 있는 출처를 바탕으로 이 주장이 사실인지 검증해주세요."
                }
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        search_results = response.choices[0].message.content
        result['search_results'] = search_results
        
        # 2. Upstage Groundedness Check로 검증 (검색 결과를 ground truth로 사용)
        if 'upstage' in clients:
            try:
                ground_response = clients['upstage'].chat.completions.create(
                    model="groundedness-check",
                    messages=[
                        {"role": "user", "content": search_results},
                        {"role": "assistant", "content": claim}
                    ]
                )
                
                ground_content = ground_response.choices[0].message.content
                
                # 응답 파싱 개선
                ground_lower = ground_content.lower()
                
                # 다양한 긍정 표현 체크
                if any(word in ground_lower for word in ['grounded', 'supported', 'verified', '사실', '확인', '입증']):
                    result['is_grounded'] = True
                    result['confidence'] = 0.85
                elif any(word in ground_lower for word in ['partially', 'partly', '부분적', '일부']):
                    result['is_grounded'] = True
                    result['confidence'] = 0.5
                elif any(word in ground_lower for word in ['not grounded', 'unsupported', 'false', '거짓', '틀림', '오류']):
                    result['is_grounded'] = False
                    result['confidence'] = 0.1
                else:
                    # 기본값: 약한 신뢰도
                    result['is_grounded'] = True
                    result['confidence'] = 0.3
                
                result['explanation'] = ground_content
            except Exception as e:
                result['explanation'] = f"Groundedness Check 오류: {str(e)}"
        else:
            # Upstage API가 없는 경우 Perplexity 결과만으로 판단
            search_lower = search_results.lower()
            if any(word in search_lower for word in ['사실', '확인', '맞습니다', '정확', 'true', 'correct', 'verified']):
                result['is_grounded'] = True
                result['confidence'] = 0.7
            elif any(word in search_lower for word in ['거짓', '틀림', '오류', 'false', 'incorrect', 'wrong']):
                result['is_grounded'] = False
                result['confidence'] = 0.1
            else:
                result['is_grounded'] = True
                result['confidence'] = 0.4
            result['explanation'] = search_results
        
        # 출처 추출 (Perplexity 응답에서)
        import re
        urls = re.findall(r'https?://[^\s]+', search_results)
        result['sources'] = urls[:3]  # 상위 3개 출처만
        
    except Exception as e:
        import traceback
        result['explanation'] = f"팩트체크 중 오류 발생: {str(e)}\n상세: {traceback.format_exc()}"
    
    return result

# 섹션별 짧은 피드백 생성
def get_section_specific_feedback(section_type: str, evidence_count: int = 0, has_sources: bool = False) -> str:
    """섹션별 맞춤형 짧은 피드백 생성"""
    
    if section_type == 'intro':
        feedbacks = [
            "좋은 시작이에요! 👍 입장이 명확해요. 이제 왜 그렇게 생각하는지 근거를 들어볼까요?",
            "입장을 잘 밝혔네요! ✨ 다음엔 구체적인 이유를 설명해주세요.",
            "명확한 주장이에요! 💡 이제 이를 뒷받침할 근거를 추가해보면 어떨까요?"
        ]
    elif section_type == 'conclusion':
        feedbacks = [
            "마무리가 깔끔해요! 🎯 핵심 주장을 한 번 더 강조했나요?",
            "좋은 결론이에요! ✨ 가장 강력한 근거를 다시 언급하면 더 좋을 거예요.",
            "잘 정리했어요! 👏 독자가 기억할 만한 한 문장을 추가해보는 건 어떨까요?"
        ]
    else:  # body
        if evidence_count == 1:
            if has_sources:
                feedbacks = [
                    "첫 번째 근거 좋네요! 출처까지 명시해서 신뢰도가 높아요. 👍 근거를 하나 더 추가해볼까요?",
                    "근거와 자료 제시가 훌륭해요! ✨ 다른 측면의 근거도 추가하면 더 설득력 있을 거예요."
                ]
            else:
                feedbacks = [
                    "첫 번째 근거 좋아요! 💡 구체적인 통계나 사례를 추가하면 더 설득력 있을 거예요.",
                    "좋은 시작이에요! 이 근거를 뒷받침할 자료를 찾아보면 어떨까요? 📚"
                ]
        elif evidence_count == 2:
            feedbacks = [
                "두 가지 근거가 잘 연결되고 있어요! 👍 각 근거마다 구체적 사례를 추가해보세요.",
                "좋은 논리 전개예요! ✨ 이제 가장 강한 근거에 집중해서 보강해볼까요?"
            ]
        elif evidence_count == 3:
            feedbacks = [
                "세 가지 근거가 체계적이에요! 🎯 이제 가장 핵심적인 것에 집중해보면 어떨까요?",
                "충실한 논증이네요! 💪 각 근거의 연결을 더 자연스럽게 만들어보세요."
            ]
        else:  # 4개 이상
            feedbacks = [
                "충분한 근거예요! 🌟 이제 가장 강력한 2-3개로 정리하면 더 임팩트 있을 거예요.",
                "많은 근거를 제시했네요! 핵심만 추려서 깊이 있게 설명하면 어떨까요? 🎯"
            ]
    
    import random
    return random.choice(feedbacks)

# 대화형 코칭 피드백 생성
def generate_coaching_feedback(text: str, structure: Dict, clients: Dict, position: str = None, topic: str = None) -> str:
    """논증 구조에 대한 코칭 피드백 생성"""
    
    # 섹션별 간단 피드백 우선 제공
    section_feedback = get_section_specific_feedback(
        structure.get('section_type', 'body'),
        structure.get('evidence_count', 0),
        bool(structure.get('sources', []))
    )
    
    # API 없으면 섹션별 피드백만 반환
    if 'upstage' not in clients:
        return section_feedback
    
    # Solar Pro 2를 사용한 추가 피드백 (필요시)
    system_prompt = """당신은 학생의 토론 친구이자 도우미입니다.

중요 규칙:
- 반드시 2-3문장으로만 답하세요
- 친근하고 격려하는 톤을 사용하세요
- 이모지를 적절히 사용하세요 (👍 💡 ✨ 🎯)
- "~해보면 어떨까요?" 같은 제안형 표현을 사용하세요
- 구체적 예시는 제공하지 마세요
- 학생의 입장(찬성/반대)을 명확히 유지하도록 도와주세요

피드백 방식:
- 잘한 점 간단히 인정 (1문장)
- 개선 방향 제안 (1-2문장)
- 격려와 함께 마무리"""

    position_str = f"\n학생의 입장: {position}" if position else ""
    topic_str = f"\n토론 주제: {topic}" if topic else ""
    
    user_prompt = f"""학생의 논증을 분석하고 코칭해주세요:{position_str}{topic_str}

논증 내용: {text}

현재 구조 분석:
- 주장 포함: {structure['has_claim']}
- 근거 포함: {structure['has_evidence']}  
- 보강자료 포함: {structure['has_reinforcement']}

2-3문장으로 짧게 피드백을 주세요. 격려와 함께 한 가지 구체적 개선점만 제안하세요."""

    if 'upstage' not in clients:
        return "Upstage API 키가 설정되지 않았습니다."
    
    try:
        response = clients['upstage'].chat.completions.create(
            model="solar-pro2",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=200  # 짧은 응답을 위해 토큰 제한
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"피드백 생성 중 오류가 발생했습니다: {str(e)}"

# 주제별 가이드 제공
def get_topic_guide(topic: str, position: str) -> str:
    """토론 주제와 입장에 따른 가이드 제공"""
    guide = f"""
### 토론 주제: {topic}
### 당신의 입장: {position}

💡 **토론 팁**
• 서론: 입장을 명확히 밝혀주세요
• 본론: 근거와 자료를 제시해주세요  
• 결론: 핵심을 다시 강조해주세요
"""
    return guide

# 메인 앱
def main():
    st.markdown('<div class="main-header"><h1>🎓 토론 논증 코칭 챗봇</h1><p>체계적인 논증 구조를 만들어 설득력을 높이세요!</p></div>', unsafe_allow_html=True)
    
    # 세션 초기화
    init_session_state()
    
    # API 클라이언트
    clients = init_clients()
    
    if not clients:
        st.error("⚠️ API 키가 설정되지 않았습니다. Streamlit Cloud 설정에서 UPSTAGE_API_KEY와 PERPLEXITY_API_KEY를 추가해주세요.")
        return
    
    if 'upstage' not in clients:
        st.warning("⚠️ Upstage API 키가 없습니다. 코칭 기능이 제한됩니다.")
    
    if 'perplexity' not in clients:
        st.warning("⚠️ Perplexity API 키가 없습니다. 팩트체크 기능이 제한됩니다.")
    
    # 사이드바
    with st.sidebar:
        st.header("📋 토론 설정")
        
        # 토론 주제 입력
        topic = st.text_input("토론 주제를 입력하세요:", 
                              placeholder="예: 학교 교복 착용 의무화",
                              value=st.session_state.debate_topic)
        
        if topic != st.session_state.debate_topic:
            st.session_state.debate_topic = topic
            st.session_state.messages = []
        
        # 입장 선택
        col1, col2 = st.columns(2)
        with col1:
            if st.button("👍 찬성", disabled=not topic):
                st.session_state.user_position = "찬성"
                st.session_state.coaching_started = True
        with col2:
            if st.button("👎 반대", disabled=not topic):
                st.session_state.user_position = "반대"
                st.session_state.coaching_started = True
        
        if st.session_state.user_position:
            st.success(f"선택된 입장: {st.session_state.user_position}")
        
        st.markdown("---")
        
        # 현재 작성 중인 부분 표시
        if 'last_section' in st.session_state:
            st.info(f"📝 현재: {st.session_state.last_section}")
        
        # 리셋 버튼
        if st.button("🔄 새로운 토론 시작"):
            for key in st.session_state.keys():
                del st.session_state[key]
            st.rerun()
    
    # 메인 컨텐츠
    if not st.session_state.coaching_started:
        st.info("👈 왼쪽 사이드바에서 토론 주제를 입력하고 입장을 선택하세요.")
        
        # 예시 토론 주제들
        st.markdown("### 💡 토론 주제 예시")
        example_topics = [
            "인공지능을 활용한 수행평가",
            "학교 내 스마트폰 사용",
            "온라인 수업의 효과성",
            "청소년 게임 시간 제한",
            "학생 자치권 확대"
        ]
        
        cols = st.columns(len(example_topics))
        for idx, topic in enumerate(example_topics):
            with cols[idx]:
                if st.button(topic, key=f"example_{idx}"):
                    st.session_state.debate_topic = topic
                    st.rerun()
    
    else:
        # 토론 가이드 표시
        st.markdown(get_topic_guide(st.session_state.debate_topic, st.session_state.user_position))
        
        # 채팅 히스토리 (단순화)
        st.markdown("### 💬 코칭 대화")
        
        # 메시지 표시
        for message in st.session_state.messages:
            if message["role"] == "user":
                st.markdown(f'<div class="chat-message user-message"><strong>학생:</strong> {message["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-message assistant-message"><strong>코치:</strong> {message["content"]}</div>', unsafe_allow_html=True)
        
        # 입력 폼
        with st.form("argument_form", clear_on_submit=True):
            user_input = st.text_area("논증을 작성하세요:", 
                                     placeholder="주장, 근거, 보강자료를 포함하여 작성해보세요...",
                                     height=150)
            
            col1, col2 = st.columns([3, 1])
            with col1:
                submitted = st.form_submit_button("📤 제출하기", use_container_width=True)
            with col2:
                fact_check = st.form_submit_button("🔍 팩트체크", use_container_width=True)
        
        if submitted and user_input:
            # 사용자 메시지 저장
            st.session_state.messages.append({"role": "user", "content": user_input})
            
            # 논증 구조 분석
            structure = analyze_argument_structure(user_input)
            
            # 섹션 타입 저장
            section_labels = {
                'intro': '서론',
                'body': f'본론 (근거 {structure.get("evidence_count", 0)}개)',
                'conclusion': '결론'
            }
            st.session_state.last_section = section_labels.get(structure.get('section_type', 'body'), '본론')
            
            # 코칭 피드백 생성 (입장과 주제 포함)
            with st.spinner("코칭 피드백을 생성하는 중..."):
                feedback = generate_coaching_feedback(
                    user_input, 
                    structure, 
                    clients,
                    position=st.session_state.user_position,
                    topic=st.session_state.debate_topic
                )
                st.session_state.messages.append({"role": "assistant", "content": feedback})
            
            # 출처가 있는 경우 자동 팩트체크
            if structure['sources']:
                st.info(f"📌 출처 발견: {', '.join(structure['sources'])} - 자동 팩트체크를 수행합니다.")
                # 여기에 팩트체크 로직 추가
            
            st.rerun()
        
        if fact_check and user_input:
            # 팩트체크 수행
            with st.spinner("Perplexity로 웹 검색 중... 잠시만 기다려주세요."):
                # 출처 패턴 찾기
                sources = re.findall(r'([가-힣A-Za-z0-9\s]+)(?:에 따르면|연구에서|조사 결과)', user_input)
                
                if sources or user_input:
                    # 전체 텍스트 또는 특정 출처에 대해 팩트체크
                    source_text = sources[0] if sources else ""
                    
                    # 주장 추출 (출처 이후 부분)
                    claim_match = re.search(r'(?:에 따르면|연구에서|조사 결과)(.+)', user_input)
                    claim = claim_match.group(1) if claim_match else user_input
                    
                    # Perplexity 팩트체크 수행
                    fact_result = perplexity_fact_check(claim.strip(), source_text, clients)
                    
                    # 결과 표시
                    st.markdown('<div class="fact-check-box"><strong>🔍 팩트체크 결과</strong></div>', unsafe_allow_html=True)
                    
                    # 신뢰도에 따른 아이콘 선택
                    if fact_result['confidence'] >= 0.7:
                        icon = "✅"
                        status = "검증됨"
                    elif fact_result['confidence'] >= 0.4:
                        icon = "⚠️"
                        status = "부분적으로 검증됨"
                    else:
                        icon = "❌"
                        status = "검증 실패"
                    
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        st.metric("검증 상태", status, f"{fact_result['confidence']*100:.0f}%")
                    with col2:
                        st.markdown(f"**{icon} 신뢰도:** {fact_result['confidence']*100:.0f}%")
                    
                    # Perplexity 검색 결과
                    with st.expander("📊 웹 검색 결과 보기"):
                        st.write(fact_result['search_results'])
                        
                        if fact_result['sources']:
                            st.markdown("**🔗 참고 출처:**")
                            for src in fact_result['sources']:
                                st.write(f"- {src}")
                    
                    # Groundedness 검증 결과
                    if fact_result['explanation'] and fact_result['explanation'] != fact_result['search_results']:
                        with st.expander("🎯 Groundedness 검증 상세"):
                            st.write(fact_result['explanation'])
                    
                    # 개선 제안
                    if fact_result['confidence'] < 0.7:
                        st.info("💡 **개선 제안:** 더 신뢰할 수 있는 출처를 인용하거나, 구체적인 통계나 연구 결과를 제시해보세요.")
                else:
                    st.warning("출처가 명시되지 않았습니다. '~에 따르면' 형식으로 출처를 포함해주세요.")

if __name__ == "__main__":
    main()