# mmain.py  (state + crew + resolver + workflow + main 단일 파일; 로직 동일)
# 주제: AI 기반 시스템 오류 자동 해결 마법사
#  1단계 규칙 분류 → 2단계 TF-IDF 유사 사례 검색 → 3단계 Llama 설명 생성 → 4단계 조치 실행
from __future__ import annotations  # Python 3.9 호환

import json
import os
import platform
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any

import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


# =========================================
# state.py
# =========================================
@dataclass
class DiagnosisState:
    log_text: str = ""
    error_code: str = ""
    system_state: Dict[str, Any] = field(default_factory=dict)

    rule_category: str = ""
    rule_keywords: List[str] = field(default_factory=list)

    similar_cases: List[Dict[str, Any]] = field(default_factory=list)
    diagnosis: Dict[str, Any] = field(default_factory=dict)
    resolution: Dict[str, Any] = field(default_factory=dict)

    report: str = ""
    error: str = ""


# =========================================
# crew.py
# =========================================
ISSUE_TYPES = [
    "프로그램 실행 오류",
    "네트워크 연결 오류",
    "권한 문제",
    "메모리 부족 / 앱 크래시",
]


# 1단계: 규칙 기반 분류기
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
            "memory allocation failed", "메모리", "크래시", "crash", "응답 없음",
        ],
        "프로그램 실행 오류": [
            "command not found", "no such file or directory", "modulenotfounderror",
            "importerror", "missing dll", "dll", "exited with code", "cannot execute",
            "module not found", "traceback", "exception", "실행",
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


# 2단계: TF-IDF + cosine similarity 유사 사례 검색기 (상위 3개)
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

    _ALIASES = {
        "rerun_as_admin_guide": "permission denied access is denied 권한 관리자 errno 13 forbidden 쓰기권한",
        "check_network_guide": "connection refused timeout timed out dns resolve 연결 네트워크 포트 서버 호스트",
        "free_memory_guide": "out of memory memory allocation failed oom killed heap 메모리 부족 크래시 crash",
        "reinstall_dependency_guide": "module not found modulenotfounderror importerror no module named missing dll 패키지 모듈 라이브러리 누락 pip",
        "check_path_guide": "no such file or directory file not found 경로 파일 없음 path",
    }

    def __init__(self):
        self._docs = [
            f"{c['log_signature']} {c['issue_type']} {c['root_cause']} "
            f"{' '.join(c['solutions'])} {self._ALIASES.get(c['safe_action_id'], '')}"
            for c in self.CASE_DB
        ]
        self._vectorizer = TfidfVectorizer()
        self._matrix = self._vectorizer.fit_transform(self._docs)

    def retrieve(self, log_text: str, rule_category: str, top_k: int = 3):
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


# 3단계: 언어모델 진단기 (Llama, OpenAI 호환 + 함수 호출)
REPORT_TOOL = {
    "type": "function",
    "function": {
        "name": "report_diagnosis",
        "description": "시스템 오류 진단 결과를 구조화하여 보고한다.",
        "parameters": {
            "type": "object",
            "properties": {
                "issue_type": {"type": "string", "enum": ISSUE_TYPES, "description": "오류 유형"},
                "confidence": {"type": "number", "description": "0~1 사이의 진단 신뢰도"},
                "root_cause": {"type": "string", "description": "오류의 근본 원인 (한국어 한 문장)"},
                "evidence": {"type": "array", "items": {"type": "string"}, "description": "판단 근거가 된 로그/상태 일부"},
                "solutions": {"type": "array", "items": {"type": "string"}, "description": "사용자가 따라 할 해결 단계"},
                "safe_action_id": {"type": "string", "description": "자동 안내 가능한 안전 조치 식별자 (없으면 빈 문자열)"},
                "user_explanation": {"type": "string", "description": "비전문가도 이해할 수 있는 쉬운 한국어 설명 (2~3문장)"},
            },
            "required": ["issue_type", "confidence", "root_cause", "solutions", "user_explanation"],
        },
    },
}


class LlamaDiagnoser:

    def __init__(self):
        self.base_url = os.environ.get("LLAMA_BASE_URL", "").rstrip("/")
        self.api_key = os.environ.get("LLAMA_API_KEY", "")
        self.model = os.environ.get("LLAMA_MODEL", "meta-llama/Llama-3.3-70B-Instruct")
        if not self.base_url:
            raise RuntimeError(
                "LLAMA_BASE_URL 환경변수가 설정되어 있지 않습니다. "
                "예: export LLAMA_BASE_URL=http://<서버주소>:<포트>/v1"
            )

    def _build_messages(self, log_text, error_code, system_state, rule_category, similar_cases):
        # few-shot 예시는 '검색된 유사 사례'로 동적 구성
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

                tool_calls = message.get("tool_calls") or []
                if tool_calls:
                    args = tool_calls[0]["function"]["arguments"]
                    parsed = json.loads(args) if isinstance(args, str) else args
                    return self._normalize(parsed)

                parsed = self._parse_json_payload(message.get("content") or "")
                return self._normalize(parsed)

            except Exception as e:
                last_error = e
                error_text = str(e)
                is_retryable = (
                    "503" in error_text or "429" in error_text
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
            "issue_type": "", "confidence": 0.0,
            "root_cause": f"언어모델 진단 실패: {last_error}",
            "evidence": [], "solutions": ["서버 주소/키/모델명을 확인하고 잠시 후 다시 시도하세요."],
            "safe_action_id": "",
            "user_explanation": "언어모델 서버에 연결하지 못했습니다. 서버 상태를 확인해 주세요.",
        }

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
        s = str(value).strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except Exception:
                pass
        return [s]

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


# =========================================
# resolver.py — 4단계: 조치 실행
# =========================================
class Resolver:

    # 자동 모드(auto=True)에서 확인 없이 실행해도 되는, 미리 허용한 안전한 작업
    AUTO_SAFE = {"reinstall_dependency_guide"}

    def resolve(self, state, execute: bool = False, auto: bool = False) -> Dict[str, Any]:
        action = (state.diagnosis or {}).get("safe_action_id", "")
        log = state.log_text or ""
        if auto and action in self.AUTO_SAFE:
            execute = True
        handler = {
            "reinstall_dependency_guide": self._reinstall_dependency,
            "check_network_guide": self._check_network,
            "check_path_guide": self._check_path,
            "free_memory_guide": self._free_memory,
            "rerun_as_admin_guide": self._rerun_as_admin,
        }.get(action, self._unknown)
        return handler(log, execute)

    def _reinstall_dependency(self, log, execute):
        m = re.search(r"No module named ['\"]?([A-Za-z0-9_\.]+)['\"]?", log)
        module = m.group(1).split(".")[0] if m else None
        if not module:
            return {"action": "reinstall_dependency", "kind": "guide", "executed": False,
                    "steps": ["로그에서 누락 모듈명을 찾지 못했습니다.",
                              "누락된 패키지를 직접 설치하세요: pip install <패키지명>"]}
        cmd = [sys.executable, "-m", "pip", "install", module]
        cmd_str = " ".join(cmd)
        if not execute:
            return {"action": "reinstall_dependency", "kind": "confirm", "executed": False,
                    "command": cmd_str, "message": f"누락된 모듈 '{module}' 설치가 필요합니다."}
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            ok = proc.returncode == 0
            out = (proc.stdout + proc.stderr).strip()
            out = out[-700:] if out else "(출력 없음)"
            return {"action": "reinstall_dependency", "kind": "confirm", "executed": True,
                    "command": cmd_str, "success": ok, "output": out,
                    "message": f"'{module}' 설치 {'성공' if ok else '실패'}"}
        except Exception as e:
            return {"action": "reinstall_dependency", "kind": "confirm", "executed": True,
                    "command": cmd_str, "success": False, "output": str(e)}

    def _check_network(self, log, execute):
        host = None
        m = re.search(r"https?://([^\s/:]+)", log)
        if m:
            host = m.group(1)
        if not host:
            m = re.search(r"\b([a-zA-Z0-9][a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b", log)
            if m:
                host = m.group(1)
        if not host:
            return {"action": "check_network", "kind": "auto", "executed": True,
                    "output": "로그에서 대상 호스트를 찾지 못해 연결 점검을 건너뜀."}
        lines = []
        try:
            ip = socket.gethostbyname(host)
            lines.append(f"DNS 조회 성공: {host} → {ip}")
        except Exception as e:
            return {"action": "check_network", "kind": "auto", "executed": True, "success": False,
                    "output": f"DNS 조회 실패: {host} ({e})\n→ 주소 오타 또는 DNS 설정을 확인하세요."}
        reachable = False
        for port in (443, 80):
            try:
                with socket.create_connection((host, port), timeout=3):
                    lines.append(f"포트 {port} 연결 성공")
                    reachable = True
                    break
            except Exception:
                lines.append(f"포트 {port} 연결 실패")
        if not reachable:
            lines.append("→ 서버가 응답하지 않습니다. 방화벽/포트 또는 서버 상태를 확인하세요.")
        return {"action": "check_network", "kind": "auto", "executed": True,
                "success": reachable, "output": "\n".join(lines)}

    def _check_path(self, log, execute):
        m = (re.search(r"['\"]([^'\"]+[/\\][^'\"]+)['\"]", log)
             or re.search(r"([A-Za-z]:\\[^\s]+|/[^\s]+)", log))
        path = m.group(1) if m else None
        if not path:
            return {"action": "check_path", "kind": "auto", "executed": True,
                    "output": "로그에서 경로를 찾지 못해 점검을 건너뜀."}
        exists = os.path.exists(path)
        msg = "있음" if exists else "없음 → 경로/파일명을 확인하세요."
        return {"action": "check_path", "kind": "auto", "executed": True, "success": exists,
                "output": f"경로 존재 여부: {path} → {msg}"}

    def _free_memory(self, log, execute):
        try:
            import psutil
            vm = psutil.virtual_memory()
            procs = sorted(psutil.process_iter(["name", "memory_percent"]),
                           key=lambda p: (p.info.get("memory_percent") or 0), reverse=True)[:5]
            top = "\n".join(f"  {p.info['name']}: {(p.info.get('memory_percent') or 0):.1f}%"
                            for p in procs)
            return {"action": "free_memory", "kind": "auto", "executed": True,
                    "output": f"현재 메모리 사용률: {vm.percent}%\n메모리 상위 프로세스:\n{top}"}
        except Exception:
            return {"action": "free_memory", "kind": "guide", "executed": False,
                    "steps": ["불필요한 프로그램을 종료해 메모리를 확보하세요.",
                              "작업 관리자(Windows) 또는 top/htop(리눅스)으로 점유 프로세스를 확인하세요.",
                              "(psutil 설치 시 자동 점검 가능: pip install psutil)"]}

    def _rerun_as_admin(self, log, execute):
        return {"action": "rerun_as_admin", "kind": "guide", "executed": False,
                "steps": ["프로그램을 관리자 권한으로 다시 실행하세요. "
                          "(Windows: 아이콘 우클릭 → '관리자 권한으로 실행')",
                          "또는 저장 경로를 사용자 폴더(내 문서·AppData 등)로 변경하세요."]}

    def _unknown(self, log, execute):
        return {"action": "none", "kind": "guide", "executed": False,
                "steps": ["적용 가능한 자동 조치가 없습니다. 진단 결과의 해결 방법을 수동으로 따르세요."]}


def render_resolution(resolution: Dict[str, Any]) -> List[str]:
    if not resolution:
        return []
    kind = resolution.get("kind")
    lines = ["-" * 80, "자동 조치 (Resolver)"]
    if kind == "auto":
        ok = resolution.get("success")
        tag = "" if ok is None else ("  [정상]" if ok else "  [문제 감지]")
        lines.append(f"읽기전용 점검 실행{tag}")
        lines.append(resolution.get("output", ""))
    elif kind == "confirm":
        if resolution.get("executed"):
            ok = resolution.get("success")
            lines.append(f"실행: {resolution.get('command','')}   → {'성공' if ok else '실패'}")
            lines.append(resolution.get("output", ""))
        else:
            lines.append(resolution.get("message", "조치가 필요합니다."))
            lines.append(f"실행할 명령: {resolution.get('command','')}")
            lines.append("(이 명령은 시스템을 변경합니다. 확인 후 실행됩니다.)")
    else:
        lines.append("권장 조치 (수동):")
        for i, step in enumerate(resolution.get("steps", []), start=1):
            lines.append(f"  {i}. {step}")
    return lines


# =========================================
# workflow.py
# =========================================
class DiagnosisWorkflow:
    def __init__(self):
        self.classifier = RuleClassifier()   # 1단계
        self.retriever = CaseRetriever()     # 2단계
        self.diagnoser = LlamaDiagnoser()    # 3단계 (Llama)
        self.resolver = Resolver()           # 4단계

    def collect_input(self, state, log_text, error_code, system_state):
        state.log_text = log_text
        state.error_code = error_code
        state.system_state = system_state or {}
        return state

    def classify(self, state):
        category, keywords = self.classifier.classify(
            state.log_text, state.error_code, state.system_state
        )
        state.rule_category = category
        state.rule_keywords = keywords
        return state

    def retrieve_cases(self, state):
        state.similar_cases = self.retriever.retrieve(state.log_text, state.rule_category)
        return state

    def diagnose(self, state):
        try:
            result = self.diagnoser.diagnose(state)
            result["issue_type"] = state.rule_category
            kw = len(state.rule_keywords)
            cases = len(state.similar_cases)
            result["confidence"] = round(min(0.95, 0.55 + 0.08 * kw + 0.1 * cases), 2) if kw else 0.4
            if state.similar_cases:
                result["safe_action_id"] = state.similar_cases[0].get("safe_action_id", "")
            if not result.get("evidence") and state.rule_keywords:
                result["evidence"] = state.rule_keywords[:4]
            state.diagnosis = result
        except Exception as e:
            state.error = f"진단 단계 오류: {e}"
        return state

    def resolve(self, state, execute=False, auto=False):
        if not state.error:
            state.resolution = self.resolver.resolve(state, execute=execute, auto=auto)
        return state

    def generate_report(self, state):
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

        lines += render_resolution(state.resolution)

        state.report = "\n".join(lines)
        return state

    def run(self, log_text, error_code="", system_state=None, auto=False):
        state = DiagnosisState()
        state = self.collect_input(state, log_text, error_code, system_state)
        state = self.classify(state)        # 1단계
        state = self.retrieve_cases(state)  # 2단계
        state = self.diagnose(state)        # 3단계
        state = self.resolve(state, auto=auto)  # 4단계 (auto면 안전작업 자동 실행)
        state = self.generate_report(state)
        return state


# =========================================
# main.py (대화형)
# =========================================
SHOW_RAW_RESULTS = False
QUIT_WORDS = {"q", "quit", "exit", "종료"}


def collect_system_state() -> dict:
    state = {"os": platform.system()}
    try:
        import psutil
        state["cpu_usage_percent"] = psutil.cpu_percent(interval=0.3)
        state["memory_usage_percent"] = psutil.virtual_memory().percent
    except Exception:
        pass
    return state


def read_log() -> str | None:
    print("\n" + "=" * 70)
    print("오류 로그를 입력하세요. (여러 줄 가능 · 다 적었으면 빈 줄에서 Enter)")
    print("종료하려면 첫 줄에 q 만 입력하고 Enter.")
    print("-" * 70)
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            return None
        if not lines and line.strip().lower() in QUIT_WORDS:
            return None
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def main():
    auto = "--auto" in sys.argv  # 안전한 조치는 확인 없이 자동 실행

    workflow = DiagnosisWorkflow()
    print("=" * 70)
    mode = "자동 조치 모드(--auto)" if auto else "확인 모드"
    print(f"AI 기반 시스템 오류 자동 해결 마법사  (대화형 · {mode})")
    print("=" * 70)

    while True:
        log_text = read_log()
        if log_text is None:
            print("\n종료합니다.")
            break
        if not log_text:
            print("(입력이 비어 있습니다. 다시 입력해 주세요.)")
            continue

        print("\n분석 중...\n")
        result_state = workflow.run(
            log_text=log_text, system_state=collect_system_state(), auto=auto
        )
        print(result_state.report)

        res = result_state.resolution
        if res.get("kind") == "confirm" and not res.get("executed"):
            answer = input("\n위 명령을 실제로 실행할까요? (y/N): ").strip().lower()
            if answer in ("y", "yes"):
                print("\n실행 중...\n")
                executed = workflow.resolver.resolve(result_state, execute=True)
                print("\n".join(render_resolution(executed)))
            else:
                print("→ 실행을 건너뜁니다. (위 명령을 직접 실행하셔도 됩니다.)")

        if SHOW_RAW_RESULTS and result_state.diagnosis:
            print("\n" + "-" * 80)
            print("RAW DIAGNOSIS JSON")
            print("-" * 80)
            print(json.dumps(result_state.diagnosis, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
