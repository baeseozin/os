# crew.py
import json
import os
import re
import time
from typing import List, Dict, Any

import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# crew 를 단독으로 import 하는 경우에도 .env 가 반영되도록 한다.
# (main.py 처럼 이미 load_dotenv 가 호출된 경우엔 중복 호출돼도 무해함)
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# -----------------------------------
# 진단 대상 오류 유형 (구현 범위)
# -----------------------------------
ISSUE_TYPES = [
    "프로그램 실행 오류",
    "네트워크 연결 오류",
    "권한 문제",
    "메모리 부족 / 앱 크래시",
]


# =========================================
# 1단계: 규칙 기반 분류기
# 오류 코드 · 로그 키워드 · 시스템 상태를 보고 1차 분류한다.
# =========================================
class RuleClassifier:

    KEYWORDS = {
        "권한 문제": [
            "access is denied", "permission denied", "eacces",
            "operation not permitted", "permissionerror", "forbidden",
            "errno 13", "권한", "관리자 권한",
        ],
        "네트워크 연결 오류": [
            "connection refused", "econnrefused", "timed out", "etimedout",
            "network is unreachable", "could not resolve host", "connection reset",
            "no route to host", "dns", "네트워크", "연결",
        ],
        "메모리 부족 / 앱 크래시": [
            "out of memory", "outofmemoryerror", "memoryerror", "oom",
            "segmentation fault", "bad_alloc", "stack overflow", "killed",
            "메모리", "크래시", "crash", "응답 없음",
        ],
        "프로그램 실행 오류": [
            "command not found", "no such file or directory", "modulenotfounderror",
            "importerror", "dll", "exited with code", "cannot execute",
            "traceback", "exception", "실행",
        ],
    }

    def classify(self, log_text: str, error_code: str, system_state: Dict[str, Any]):
        text = f"{log_text}\n{error_code}".lower()

        scores = {issue: 0 for issue in self.KEYWORDS}
        matched = {issue: [] for issue in self.KEYWORDS}

        for issue, keywords in self.KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    scores[issue] += 1
                    matched[issue].append(kw)

        mem = system_state.get("memory_usage_percent")
        if isinstance(mem, (int, float)) and mem >= 90:
            scores["메모리 부족 / 앱 크래시"] += 1
            matched["메모리 부족 / 앱 크래시"].append(f"memory_usage={mem}%")

        best = max(scores, key=lambda k: scores[k])
        if scores[best] == 0:
            return "프로그램 실행 오류", []

        return best, matched[best]


# =========================================
# 2단계: 유사 사례 검색기
# 입력 로그를 TF-IDF 벡터화 → 사례 DB와 cosine similarity 비교 → 상위 3개 추천.
# =========================================
class CaseRetriever:

    CASE_DB = [
        {
            "issue_type": "권한 문제",
            "log_signature": "Access is denied",
            "root_cause": "설정 파일 저장 경로에 쓰기 권한이 없음",
            "solutions": ["관리자 권한으로 재실행", "저장 경로를 사용자 폴더로 변경"],
            "safe_action_id": "rerun_as_admin_guide",
        },
        {
            "issue_type": "네트워크 연결 오류",
            "log_signature": "Connection refused",
            "root_cause": "대상 서버가 응답하지 않거나 포트가 닫혀 있음",
            "solutions": ["네트워크 연결 상태 확인", "방화벽/포트 설정 확인", "잠시 후 재시도"],
            "safe_action_id": "check_network_guide",
        },
        {
            "issue_type": "네트워크 연결 오류",
            "log_signature": "Could not resolve host",
            "root_cause": "DNS 조회 실패로 호스트 주소를 찾지 못함",
            "solutions": ["주소(URL) 오타 확인", "DNS 서버 설정 확인", "인터넷 연결 확인"],
            "safe_action_id": "check_network_guide",
        },
        {
            "issue_type": "메모리 부족 / 앱 크래시",
            "log_signature": "OutOfMemoryError",
            "root_cause": "사용 가능한 메모리가 부족하여 프로세스가 강제 종료됨",
            "solutions": ["불필요한 프로그램 종료", "처리 데이터 단위를 줄여 재실행", "메모리 증설 검토"],
            "safe_action_id": "free_memory_guide",
        },
        {
            "issue_type": "프로그램 실행 오류",
            "log_signature": "ModuleNotFoundError",
            "root_cause": "필요한 패키지/모듈이 설치되어 있지 않음",
            "solutions": ["누락된 패키지 설치", "가상환경 활성화 여부 확인"],
            "safe_action_id": "reinstall_dependency_guide",
        },
        {
            "issue_type": "프로그램 실행 오류",
            "log_signature": "No such file or directory",
            "root_cause": "실행에 필요한 파일/경로가 존재하지 않음",
            "solutions": ["파일 경로가 올바른지 확인", "필요한 파일이 삭제/이동되지 않았는지 확인"],
            "safe_action_id": "check_path_guide",
        },
    ]

    # 실제 로그에서 자주 등장하는 표현(별칭)을 사례별로 보강 → TF-IDF 매칭 강화
    _ALIASES = {
        "rerun_as_admin_guide": "permission denied access is denied 권한 관리자 errno 13 forbidden 쓰기권한",
        "check_network_guide": "connection refused timeout timed out dns resolve 연결 네트워크 포트 서버 호스트",
        "free_memory_guide": "out of memory memory allocation failed oom killed heap 메모리 부족 크래시 crash",
        "reinstall_dependency_guide": "module not found modulenotfounderror importerror no module named missing dll 패키지 모듈 라이브러리 누락 pip",
        "check_path_guide": "no such file or directory file not found 경로 파일 없음 path",
    }

    def __init__(self):
        # 각 사례를 하나의 문서로 만들어 TF-IDF 벡터라이저를 미리 학습해 둔다.
        self._docs = [
            f"{c['log_signature']} {c['issue_type']} {c['root_cause']} "
            f"{' '.join(c['solutions'])} {self._ALIASES.get(c['safe_action_id'], '')}"
            for c in self.CASE_DB
        ]
        self._vectorizer = TfidfVectorizer()
        self._matrix = self._vectorizer.fit_transform(self._docs)

    def retrieve(self, log_text: str, rule_category: str, top_k: int = 3):
        # 입력 로그(+1차 분류)를 같은 공간에 벡터화하여 cosine similarity 비교
        query = f"{log_text} {rule_category}"
        q_vec = self._vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self._matrix)[0]

        ranked = sorted(range(len(self.CASE_DB)), key=lambda i: sims[i], reverse=True)

        results = []
        for i in ranked[:top_k]:
            if sims[i] <= 0:
                continue
            case = dict(self.CASE_DB[i])
            case["similarity"] = round(float(sims[i]), 3)
            results.append(case)
        return results


# =========================================
# 3단계: 언어모델 진단기 (Llama 3.3, OpenAI 호환 + 함수 호출)
# 규칙 분류 + 유사 사례를 근거로 원인 추론과 해결책을 생성한다.
# 출력은 report_diagnosis 함수 호출(function calling)로 구조화하여 받는다.
# =========================================

# 언어모델이 호출할 함수(도구) 스키마 — 진단 결과를 구조화해 반환받는 용도
REPORT_TOOL = {
    "type": "function",
    "function": {
        "name": "report_diagnosis",
        "description": "시스템 오류 진단 결과를 구조화하여 보고한다.",
        "parameters": {
            "type": "object",
            "properties": {
                "issue_type": {
                    "type": "string",
                    "enum": ISSUE_TYPES,
                    "description": "오류 유형",
                },
                "confidence": {
                    "type": "number",
                    "description": "0~1 사이의 진단 신뢰도",
                },
                "root_cause": {
                    "type": "string",
                    "description": "오류의 근본 원인 (한국어 한 문장)",
                },
                "evidence": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "판단 근거가 된 로그/상태 일부",
                },
                "solutions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "사용자가 따라 할 해결 단계",
                },
                "safe_action_id": {
                    "type": "string",
                    "description": "자동 안내 가능한 안전 조치 식별자 (없으면 빈 문자열)",
                },
                "user_explanation": {
                    "type": "string",
                    "description": "비전문가도 이해할 수 있는 쉬운 한국어 설명 (2~3문장)",
                },
            },
            "required": ["issue_type", "confidence", "root_cause", "solutions", "user_explanation"],
        },
    },
}


class LlamaDiagnoser:

    def __init__(self):
        # 연구실 자체 모델 서버(OpenAI 호환) 접속 정보 — 환경변수로 주입
        self.base_url = os.environ.get("LLAMA_BASE_URL", "").rstrip("/")
        self.api_key = os.environ.get("LLAMA_API_KEY", "")
        self.model = os.environ.get("LLAMA_MODEL", "meta-llama/Llama-3.3-70B-Instruct")

        if not self.base_url:
            raise RuntimeError(
                "LLAMA_BASE_URL 환경변수가 설정되어 있지 않습니다. "
                "예: export LLAMA_BASE_URL=http://<서버주소>:<포트>/v1"
            )

    # few-shot 예시 + 실제 입력으로 messages 구성
    def _build_messages(self, log_text, error_code, system_state, rule_category, similar_cases):
        # few-shot 예시는 '검색된 유사 사례'로 동적 구성한다.
        # (고정 예시를 쓰면 소형 모델이 유형과 무관하게 그 예시를 베끼는 문제가 있음)
        if similar_cases:
            top = similar_cases[0]
            example = {
                "issue_type": top.get("issue_type", rule_category),
                "confidence": 0.9,
                "root_cause": top.get("root_cause", ""),
                "evidence": [top.get("log_signature", "")],
                "solutions": top.get("solutions", []),
                "safe_action_id": top.get("safe_action_id", ""),
                "user_explanation": "이 오류는 ~ 때문에 발생했습니다. 아래 해결 방법을 순서대로 시도해 보세요.",
            }
        else:
            example = {
                "issue_type": rule_category,
                "confidence": 0.6,
                "root_cause": "<근본 원인을 한국어 한 문장으로>",
                "evidence": ["<판단 근거1>", "<판단 근거2>"],
                "solutions": ["<해결 단계1>", "<해결 단계2>"],
                "safe_action_id": "",
                "user_explanation": "<비전문가도 이해할 수 있는 쉬운 설명 2~3문장>",
            }

        system = (
            "너는 시스템 오류를 진단하는 전문가다. 로그·오류코드·시스템 상태와 "
            "규칙 기반 1차 분류, 유사 사례를 참고하여 오류의 원인을 추론하고 "
            "비숙련 사용자도 따라 할 수 있는 해결 방법을 제시하라.\n"
            "issue_type은 '규칙 기반 1차 분류' 결과를 기본 전제로 삼되, 로그에 명백히 "
            "다른 유형의 근거가 있을 때만 바꿔라.\n"
            "safe_action_id는 유사 사례의 값을 참고해 반드시 채워라.\n"
            "user_explanation에는 비전문가도 이해할 수 있는 쉬운 한국어 설명을 2~3문장으로 작성하라.\n"
            "진단 결과는 반드시 report_diagnosis 함수를 호출하여 보고하라.\n"
            "evidence와 solutions는 반드시 문자열 배열(list)로 작성하라.\n"
            "모든 자연어 값은 한국어로 작성하라.\n"
            "아래 예시는 출력 형식 참고용일 뿐이다. 값은 절대 그대로 베끼지 말고, "
            "주어진 로그·상태에 맞게 새로 작성하라.\n\n"
            "[형식 예시]\n"
            f"{json.dumps(example, ensure_ascii=False, indent=2)}"
        )

        user = (
            f"[규칙 기반 1차 분류]\n{rule_category}\n\n"
            f"[유사 사례 (참고용)]\n{json.dumps(similar_cases, ensure_ascii=False, indent=2)}\n\n"
            f"[오류 코드]\n{error_code or '(없음)'}\n\n"
            f"[시스템 상태]\n{json.dumps(system_state, ensure_ascii=False)}\n\n"
            f"[오류 로그]\n{log_text}"
        )

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def diagnose(self, state) -> Dict[str, Any]:
        messages = self._build_messages(
            state.log_text, state.error_code, state.system_state,
            state.rule_category, state.similar_cases,
        )

        payload = {
            "model": self.model,
            "messages": messages,
            "tools": [REPORT_TOOL],
            "tool_choice": {"type": "function", "function": {"name": "report_diagnosis"}},
            "temperature": 0,
        }

        headers = {"Content-Type": "application/json", "accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = f"{self.base_url}/chat/completions"

        last_error: Exception | None = None
        for attempt in range(3):
            print(f"[Llama] model={self.model} (attempt {attempt + 1}/3)")
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=120)
                response.raise_for_status()
                data = response.json()

                message = data["choices"][0]["message"]

                # 1) 함수 호출(tool_calls) 결과 우선 파싱
                tool_calls = message.get("tool_calls") or []
                if tool_calls:
                    args = tool_calls[0]["function"]["arguments"]
                    parsed = json.loads(args) if isinstance(args, str) else args
                    return self._normalize(parsed)

                # 2) 함수 호출이 없으면 본문 텍스트에서 JSON 추출
                parsed = self._parse_json_payload(message.get("content") or "")
                return self._normalize(parsed)

            except Exception as e:
                last_error = e
                error_text = str(e)
                is_retryable = (
                    "503" in error_text
                    or "429" in error_text
                    or "timed out" in error_text.lower()
                    or "connection" in error_text.lower()
                )
                if is_retryable and attempt < 2:
                    wait_seconds = 2 ** attempt
                    print(f"[Llama] retry in {wait_seconds}s ({attempt + 1}/3)")
                    time.sleep(wait_seconds)
                    continue
                break

        return {
            "issue_type": "",
            "confidence": 0.0,
            "root_cause": f"언어모델 진단 실패: {last_error}",
            "evidence": [],
            "solutions": ["서버 주소/키/모델명을 확인하고 잠시 후 다시 시도하세요."],
            "safe_action_id": "",
            "user_explanation": "언어모델 서버에 연결하지 못했습니다. 서버 상태를 확인해 주세요.",
        }

    # -----------------------------------
    # 출력 정규화 (키 누락/타입 방어)
    # -----------------------------------
    def _normalize(self, parsed: Any) -> Dict[str, Any]:
        if not isinstance(parsed, dict):
            parsed = {}

        try:
            confidence = float(parsed.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = round(max(0.0, min(1.0, confidence)), 2)

        return {
            "issue_type": str(parsed.get("issue_type", "")),
            "confidence": confidence,
            "root_cause": str(parsed.get("root_cause", "")),
            "evidence": self._as_str_list(parsed.get("evidence")),
            "solutions": self._as_str_list(parsed.get("solutions")),
            "safe_action_id": str(parsed.get("safe_action_id", "")),
            "user_explanation": str(parsed.get("user_explanation", "")),
        }

    @staticmethod
    def _as_str_list(value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(x) for x in value]
        if value in (None, ""):
            return []
        # 모델이 배열을 문자열("[...]")로 반환한 경우 파싱 시도
        s = str(value).strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except Exception:
                pass
        return [s]

    # -----------------------------------
    # JSON 파싱 (코드펜스/혼합 텍스트 방어)
    # -----------------------------------
    def _parse_json_payload(self, raw_text: str) -> Any:
        if not raw_text:
            raise ValueError("언어모델 응답이 비어 있습니다.")

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass

        fenced_match = re.search(r"```json\s*(.*?)\s*```", raw_text, re.DOTALL | re.IGNORECASE)
        if fenced_match:
            return json.loads(fenced_match.group(1))

        object_match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
        if object_match:
            return json.loads(object_match.group(1))

        raise ValueError("JSON 파싱 가능한 응답을 찾지 못했습니다.")
