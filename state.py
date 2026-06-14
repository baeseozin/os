# state.py
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class DiagnosisState:
    # 입력 정보
    log_text: str = ""                                          # 오류 로그 원문
    error_code: str = ""                                        # 오류 코드 (있으면)
    system_state: Dict[str, Any] = field(default_factory=dict)  # CPU/메모리/권한 등 시스템 상태

    # 1단계: 규칙 기반 분류 결과
    rule_category: str = ""                                     # 1차 분류된 오류 유형
    rule_keywords: List[str] = field(default_factory=list)      # 분류 근거가 된 키워드

    # 2단계: 유사 사례 검색 결과
    similar_cases: List[Dict[str, Any]] = field(default_factory=list)

    # 3단계: 언어모델 진단 결과 (JSON)
    diagnosis: Dict[str, Any] = field(default_factory=dict)

    # 4단계: 조치 실행 결과
    resolution: Dict[str, Any] = field(default_factory=dict)

    # 최종 리포트
    report: str = ""

    # 에러
    error: str = ""
