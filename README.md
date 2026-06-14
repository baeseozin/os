# AI 기반 시스템 오류 자동 해결 마법사

대화형 모드에서 오류 로그를 입력받아 AI로 진단하고 자동 조치(또는 가이드)를 제공하는 시스템입니다.

---

## 🚀 사전 준비 (최초 1회)

### 1) 프로젝트 폴더로 이동

### 2) 필요한 패키지 설치

```bash
pip3 install -r requirements.txt
```

### 3) Ollama 설치 및 모델 다운로드

1. **Ollama 설치**: https://ollama.com/download 에서 설치
2. **모델 다운로드**:
   ```bash
   ollama pull llama3.2
   ```
3. **(필수) Ollama 서버 실행** — 별도 터미널에서:
   ```bash
   ollama serve
   ```

### 4) `.env` 파일 생성

프로젝트 폴더(`os`) 안에 `.env` 파일을 만들고 다음 내용을 추가하세요:

```env
LLAMA_BASE_URL=http://<서버주소>:<포트>/v1
LLAMA_API_KEY=ollama
LLAMA_MODEL=llama3.2:latest
```

---

## 🎯 실행

### 확인 모드 (시스템 변경 작업 시 y/N으로 물어봄)

```bash
python3 run.py
# 또는
python3 -m src.main
```

### 자동 조치 모드 (안전 작업은 확인 없이 자동 실행)

```bash
python3 run.py --auto
# 또는
python3 -m src.main --auto
```

---

## 📋 프로그램 흐름

프로그램을 실행하면:

1. **오류 로그 입력**: 여러 줄 가능
2. **빈 줄에서 Enter** → 분석 시작
3. **진단 리포트 출력**:
   - 규칙 기반 분류
   - 유사 사례 검색
   - AI 진단 및 쉬운 설명
   - 자동 조치 실행 (또는 가이드)
4. **다음 로그 대기** → `q` 입력 시 종료

---

## 🧪 빠른 테스트 입력 예시

프로그램 실행 후 다음을 입력하고 Enter를 두 번 누르세요:

```
ModuleNotFoundError: No module named 'requests'
```

결과:
- `--auto` 모드면: 자동으로 `pip install requests` 실행
- 확인 모드면: 실행할지 y/N으로 물어봄

---

## 📁 파일 구조 및 내용

```
os/
├── README.md                    # 이 파일 (전체 문서)
├── requirements.txt             # Python 패키지 의존성
├── .gitignore                   # Git 무시 파일
├── .env.example                 # 환경변수 템플릿
├── run.py                       # 루트 진입점 (권장)
│
├── src/                         # 핵심 모듈 (패키지)
│   ├── __init__.py
│   ├── main.py                  # CLI 인터페이스 및 사용자 상호작용
│   ├── workflow.py              # 4단계 파이프라인 조정기
│   ├── state.py                 # DiagnosisState 상태 관리
│   ├── crew.py                  # RuleClassifier, CaseRetriever, LlamaDiagnoser
│   └── resolver.py              # 조치 실행기 (Resolver)
│
├── scripts/                     # 스크립트 및 유틸
│   └── mmain.py                 # 단일 파일 버전 (독립 실행)
│
└── tests/                       # 테스트
    └── test_types.py
```

---

## 📝 사용 팁

### 대신 환경변수로 직접 실행

`.env` 파일 없이 터미널 명령에 직접 환경변수를 지정할 수도 있습니다:

```bash
LLAMA_BASE_URL=http://127.0.0.1:11434/v1 \
LLAMA_MODEL=llama3.2:latest \
LLAMA_API_KEY=ollama \
python3 run.py
```

### 단일 파일 버전 실행

`scripts/mmain.py` 파일은 모든 로직을 한 파일에 담은 버전입니다 (import 없음):

```bash
python3 scripts/mmain.py
python3 scripts/mmain.py --auto
```

### Ollama 서버 미실행 시

Ollama 서버가 떠 있지 않으면:
```
LLAMA_BASE_URL 연결 에러 → "LLAMA_BASE_URL 환경변수가 설정되어 있지 않습니다" 또는 연결 실패
```

**해결**: 별도 터미널에서 `ollama serve` 실행 후 다시 시도

---

## ⚙️ 시스템 요구사항

- Python 3.9+ (OpenSSL 1.1.1+ 권장)
- macOS / Linux / Windows (WSL)
- Ollama 서버 실행 필수

---

## 🔍 진단 단계별 설명

### 1단계: 규칙 기반 분류
키워드 매칭으로 오류 유형을 1차 분류 (정확성: 높음)

### 2단계: 유사 사례 검색
사전 구축된 문제-해결 DB에서 유사 사례 2-3건 검색

### 3단계: 언어모델 진단
Llama 3.2 + 함수 호출로 원인 추론 및 해결책 생성

### 4단계: 조치 실행
- **읽기전용** (네트워크/경로/메모리): 자동 실행
- **변경 작업** (패키지 설치): 확인 후 실행
- **권한 작업** (관리자 권한): 가이드만 제공

---

## 📞 문제 해결

| 증상 | 원인 | 해결 |
|------|------|------|
| `LLAMA_BASE_URL 환경변수가 설정되어 있지 않습니다` | `.env` 파일 없음 또는 Ollama 연결 실패 | `.env` 파일 생성 및 `ollama serve` 실행 |
| `urllib3 NotOpenSSLWarning` | LibreSSL 사용 | pyenv로 OpenSSL 연동 Python 사용 |
| 분석이 매우 느림 | Ollama 모델 로딩 중 또는 서버 응답 지연 | 잠시 대기 또는 더 빠른 모델 로드 |

---

## 🧠 상세 로직 및 아키텍처

### 전체 플로우 다이어그램

```
┌─────────────────────────────────────────────────────────────┐
│ 1️⃣  규칙 기반 분류 (Rule Classifier)                      │
│ • 키워드 매칭으로 오류 유형 결정                             │
│ • 시스템 상태(CPU/메모리) 정보 활용                          │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 2️⃣  유사 사례 검색 (Case Retriever)                        │
│ • 사전 DB에서 로그 서명(signature) 기반 검색               │
│ • 상위 2-3건 사례 반환 (근거 제공)                          │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 3️⃣  언어모델 진단 (Llama Diagnoser)                        │
│ • Few-shot 예시 + 1차 분류 + 유사 사례 → 모델 입력          │
│ • 함수 호출(Function Calling)로 근본 원인/해결책 구조화     │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 4️⃣  조치 실행 (Resolver)                                   │
│ • 읽기전용: 자동 (네트워크/경로/메모리 점검)               │
│ • 변경작업: 확인 후 (패키지 설치)                            │
│ • 권한작업: 가이드만 (관리자 권한)                           │
└─────────────────────────────────────────────────────────────┘
```

---

### 1단계: 규칙 기반 분류 (RuleClassifier)

**목표**: 로그 텍스트와 시스템 상태로부터 오류 유형을 빠르게 결정

**알고리즘**:
```python
1. 오류 로그를 소문자로 변환
2. 각 오류 유형별 키워드 리스트와 매칭
3. 매칭된 키워드 개수(score) 누적
4. 시스템 상태 정보 추가 (메모리 >= 90% → 메모리 부족 점수 +1)
5. 최고 점수인 유형 선택 (동점이면 1순위)
```

**지원하는 오류 유형**:
- 프로그램 실행 오류 (ModuleNotFoundError, ImportError, 등)
- 네트워크 연결 오류 (Connection refused, DNS 실패, 등)
- 권한 문제 (Permission denied, Access denied, 등)
- 메모리 부족 / 앱 크래시 (OutOfMemory, Segmentation fault, 등)

**예시**:
```
로그: "ModuleNotFoundError: No module named 'requests'"
매칭 키워드: "modulenotfounderror" → 프로그램 실행 오류 (점수 +1)
결과: 프로그램 실행 오류 (확도 높음)
```

---

### 2단계: 유사 사례 검색 (CaseRetriever)

**목표**: 유사한 과거 사례를 찾아 모델에 근거 제공 (Few-shot Learning)

**알고리즘**:
```python
1. 사전 구축된 CASE_DB (15+ 사례) 순회
2. 각 사례에 대해 점수 계산:
   - 오류 유형 일치 → +2점
   - 로그 서명(signature) 포함 → +3점
   - 키워드 교집합 수 → +N점
3. 점수 내림차순 정렬
4. 상위 K개(기본값 2) 반환
```

**사례 DB 예시**:
```json
{
  "issue_type": "네트워크 연결 오류",
  "log_signature": "Connection refused",
  "root_cause": "대상 서버가 응답하지 않거나 포트가 닫혀 있음",
  "solutions": ["네트워크 연결 상태 확인", "방화벽/포트 설정 확인", "잠시 후 재시도"],
  "safe_action_id": "check_network_guide"
}
```

**이점**:
- 모델이 과거 사례를 "본다" → 더 정확한 진단
- 출력 형식 예시 역할 → 모델의 일관성 향상
- 검색 결과 → 리포트에 "유사 사례 N건 참고" 표시

---

### 3단계: 언어모델 진단 (LlamaDiagnoser)

**목표**: 1단계 + 2단계 결과를 바탕으로 AI가 자연어 설명과 해결책 생성

**호출 흐름**:
```
1. System Prompt 구성:
   • 역할: "너는 시스템 오류 진단 전문가다"
   • 규칙: "issue_type은 1단계 분류를 기본으로 삼되..."
   • few-shot 예시 (2단계 검색 결과 기반)
   
2. User Prompt 구성:
   • [규칙 분류] → 1단계 결과
   • [유사 사례] → 2단계 결과 (JSON)
   • [오류 코드] → 문자열
   • [시스템 상태] → dict
   • [오류 로그] → 원문
   
3. 함수 호출(Function Calling) 설정:
   • 모델이 report_diagnosis() 함수 호출 강제
   • 파라미터: issue_type, confidence, root_cause, evidence, solutions, safe_action_id
   
4. 응답 파싱:
   • tool_calls[0]["function"]["arguments"] 추출
   • JSON 파싱 → 구조화된 진단 결과
```

**함수 스키마** (report_diagnosis):
```json
{
  "issue_type": "string (enum)",
  "confidence": "number (0~1)",
  "root_cause": "string (한국어 한 문장)",
  "evidence": ["string array"],
  "solutions": ["string array"],
  "safe_action_id": "string (action identifier)"
}
```

**신뢰도 계산** (모델 값 대신 규칙 기반):
```python
confidence = min(0.95, 0.55 + 0.08 * len(keywords) + 0.1 * len(cases))
# 이유: 소형 모델의 신뢰도 값이 불안정 → 규칙 신호로 대체
```

---

### 4단계: 조치 실행 (Resolver)

**목표**: 진단 결과(safe_action_id)에 따라 실행 할 조치 결정 및 수행

**조치 유형**:

#### A) 읽기전용 (자동 실행)

| Action ID | 설명 | 구현 |
|-----------|------|------|
| `check_network_guide` | 네트워크 점검 | DNS 조회 + 포트 연결 테스트 (sockets) |
| `check_path_guide` | 파일 경로 존재 여부 | os.path.exists() |
| `free_memory_guide` | 메모리 상위 프로세스 | psutil.virtual_memory(), process_iter() |

#### B) 변경 조치 (확인 후 실행)

| Action ID | 설명 | 구현 |
|-----------|------|------|
| `reinstall_dependency_guide` | 누락 패키지 설치 | subprocess.run(`python3 -m pip install <module>`) |
| `rerun_as_admin_guide` | 관리자 권한 재실행 | 가이드 텍스트만 제공 (자동 실행 불가) |

**조치 실행 로직**:
```python
def resolve(state, execute=False):
    safe_action_id = state.diagnosis.get("safe_action_id")
    
    # 1. 읽기전용 조치 (auto / execute 무시, 항상 실행)
    if safe_action_id in ["check_network_guide", "check_path_guide", "free_memory_guide"]:
        return handler(state, execute=False)  # 결과만 반환
    
    # 2. 변경 조치 (execute=False면 명령만 제시, =True면 실행)
    elif safe_action_id in ["reinstall_dependency_guide"]:
        if not execute:
            return {"kind": "confirm", "executed": False, "command": "pip install ..."}
        else:
            result = subprocess.run(...)
            return {"kind": "confirm", "executed": True, "success": ..., "output": ...}
    
    # 3. 권한 조치 (가이드만)
    elif safe_action_id == "rerun_as_admin_guide":
        return {"kind": "guide", "executed": False, "steps": [...]}
```

---

### 상태 관리 (DiagnosisState)

프로그램은 `DiagnosisState` 데이터 클래스로상태를 추적합니다:

```python
@dataclass
class DiagnosisState:
    # 입력
    log_text: str                           # 사용자 입력 로그
    error_code: str                         # 오류 코드 (있으면)
    system_state: Dict                      # CPU/메모리 등 시스템 정보
    
    # 1단계 결과
    rule_category: str                      # 분류된 오류 유형
    rule_keywords: List[str]                # 매칭된 키워드
    
    # 2단계 결과
    similar_cases: List[Dict]               # 검색된 유사 사례
    
    # 3단계 결과
    diagnosis: Dict                         # 모델 진단 (JSON)
    
    # 4단계 결과
    resolution: Dict                        # 실행할 조치 정보
    
    # 최종 출력
    report: str                             # 리포트 (문자열)
    error: str                              # 발생한 오류
```

---

### 워크플로우 파이프라인 (DiagnosisWorkflow)

```python
def run(self, log_text, error_code="", system_state=None):
    state = DiagnosisState()
    state = self.classify(state)        # 1단계
    state = self.retrieve_cases(state)  # 2단계
    state = self.diagnose(state)        # 3단계
    state = self.resolve(state)         # 4단계
    state = self.generate_report(state) # 리포트 생성
    return state
```

각 단계는 입력 `state`를 받아 처리 후 새로운 `state`로 반환 → 함수형 파이프라인

---

### 출력 리포트 포맷

```
================================================================================
SYSTEM ERROR DIAGNOSIS REPORT
================================================================================
규칙 분류   : 프로그램 실행 오류 (키워드: modulenotfounderror, importerror)
유사 사례   : 2건 참고
================================================================================
진단 유형   : 프로그램 실행 오류
신뢰도      : 0.75
근본 원인   : 필요한 패키지/모듈이 설치되어 있지 않음
판단 근거   : modulenotfounderror, importerror
해결 방법   :
  1. 누락된 패키지 설치
  2. 가상환경 활성화 여부 확인
안전 조치ID : reinstall_dependency_guide
================================================================================
자동 조치 (Resolver)
실행: python3 -m pip install requests   → 성공
실행 결과: Successfully installed requests-2.32.5
================================================================================
```

---

## 🔗 모듈 간 의존성

```
main.py
├── from dotenv import load_dotenv
├── from workflow import DiagnosisWorkflow
├── from resolver import render_resolution
│
workflow.py
├── from state import DiagnosisState
├── from crew import RuleClassifier, CaseRetriever, LlamaDiagnoser
├── from resolver import Resolver, render_resolution
│
crew.py
├── import requests (Llama API 호출)
├── import re, json (텍스트 파싱)
│
resolver.py
├── import subprocess (명령 실행)
├── import socket (네트워크 점검)
├── import os (경로 점검)
├── import psutil (선택사항, 메모리 점검)
│
state.py
├── from dataclasses import dataclass
```

---

## 📊 실행 시간 예상

- **1단계** (규칙 분류): ~1ms
- **2단계** (유사 사례 검색): ~5ms
- **3단계** (Llama 진단): ~5-30초 (모델 로드 / 응답 대기)
- **4단계** (조치 실행): ~0-60초 (패키지 설치 시)

**전체**: 모델 응답에 따라 5~90초

