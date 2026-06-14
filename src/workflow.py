# workflow.py
from .state import DiagnosisState
from .crew import RuleClassifier, CaseRetriever, LlamaDiagnoser
from .resolver import Resolver, render_resolution


class DiagnosisWorkflow:
    def __init__(self):
        self.classifier = RuleClassifier()   # 1단계: 규칙 기반 분류
        self.retriever = CaseRetriever()     # 2단계: 유사 사례 검색
        self.diagnoser = LlamaDiagnoser()    # 3단계: 언어모델 진단 (Llama 3.2)
        self.resolver = Resolver()           # 4단계: 조치 실행

    def collect_input(
        self,
        state: DiagnosisState,
        log_text: str,
        error_code: str,
        system_state: dict,
    ) -> DiagnosisState:
        state.log_text = log_text
        state.error_code = error_code
        state.system_state = system_state or {}
        return state

    # 1단계: 규칙 기반 분류
    def classify(self, state: DiagnosisState) -> DiagnosisState:
        category, keywords = self.classifier.classify(
            state.log_text, state.error_code, state.system_state
        )
        state.rule_category = category
        state.rule_keywords = keywords
        return state

    # 2단계: 유사 사례 검색
    def retrieve_cases(self, state: DiagnosisState) -> DiagnosisState:
        state.similar_cases = self.retriever.retrieve(
            state.log_text, state.rule_category
        )
        return state

    # 3단계: 언어모델 진단
    def diagnose(self, state: DiagnosisState) -> DiagnosisState:
        try:
            result = self.diagnoser.diagnose(state)
            # 오류 유형은 1단계 규칙 분류가 확정한다.
            # (슬라이드 구현 방향: 3단계 언어모델의 역할은 '자연어 설명 생성')
            result["issue_type"] = state.rule_category
            # 신뢰도: 소형 모델 값이 불안정하므로 규칙 매칭 강도로 산출
            #         (매칭 키워드 수 + 유사 사례 수가 많을수록 높음)
            kw = len(state.rule_keywords)
            cases = len(state.similar_cases)
            result["confidence"] = round(min(0.95, 0.55 + 0.08 * kw + 0.1 * cases), 2) if kw else 0.4
            # safe_action_id는 유사 사례에서 확정 (모델이 예시값을 베끼는 것 방지)
            if state.similar_cases:
                result["safe_action_id"] = state.similar_cases[0].get("safe_action_id", "")
            # evidence가 비면 규칙 매칭 키워드로 보강
            if not result.get("evidence") and state.rule_keywords:
                result["evidence"] = state.rule_keywords[:4]
            state.diagnosis = result
        except Exception as e:
            state.error = f"진단 단계 오류: {e}"
        return state

    # 4단계: 조치 실행
    #  - 읽기전용 점검은 자동 / 시스템 변경은 execute=True 또는 auto+안전작업일 때만
    def resolve(self, state: DiagnosisState, execute: bool = False, auto: bool = False) -> DiagnosisState:
        if not state.error:
            state.resolution = self.resolver.resolve(state, execute=execute, auto=auto)
        return state

    # 최종 리포트 생성
    def generate_report(self, state: DiagnosisState) -> DiagnosisState:
        if state.error:
            state.report = f"[오류 발생]\n{state.error}"
            return state

        d = state.diagnosis

        lines = []
        lines.append("SYSTEM ERROR DIAGNOSIS REPORT")
        lines.append("-" * 80)
        lines.append(
            f"규칙 분류   : {state.rule_category} "
            f"(키워드: {', '.join(state.rule_keywords) or '없음'})"
        )
        lines.append(f"유사 사례   : {len(state.similar_cases)}건 참고")
        lines.append("-" * 80)
        lines.append(f"진단 유형   : {d.get('issue_type', '')}")
        lines.append(f"신뢰도      : {d.get('confidence', 0)}")
        lines.append(f"근본 원인   : {d.get('root_cause', '')}")
        lines.append(f"판단 근거   : {', '.join(d.get('evidence', [])) or '없음'}")
        lines.append("해결 방법   :")
        for idx, sol in enumerate(d.get("solutions", []), start=1):
            lines.append(f"  {idx}. {sol}")
        lines.append(f"쉬운 설명   : {d.get('user_explanation', '') or '없음'}")
        lines.append(f"안전 조치ID : {d.get('safe_action_id', '') or '없음'}")

        # 4단계 조치 결과
        lines += render_resolution(state.resolution)

        state.report = "\n".join(lines)
        return state

    def run(
        self,
        log_text: str,
        error_code: str = "",
        system_state: dict = None,
        auto: bool = False,
    ) -> DiagnosisState:
        state = DiagnosisState()
        state = self.collect_input(state, log_text, error_code, system_state)
        state = self.classify(state)        # 1단계
        state = self.retrieve_cases(state)  # 2단계
        state = self.diagnose(state)        # 3단계
        state = self.resolve(state, auto=auto)  # 4단계 (auto면 안전작업 자동 실행)
        state = self.generate_report(state)
        return state
