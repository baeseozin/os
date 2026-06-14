# test_types.py
# 4개 오류 유형이 의도대로 분류/진단되는지 확인하는 테스트 스크립트
from workflow import DiagnosisWorkflow

# (기대 유형, 로그, 오류코드, 시스템상태)
SAMPLES = [
    (
        "프로그램 실행 오류",
        "Traceback (most recent call last):\n"
        '  File "app.py", line 3, in <module>\n'
        "    import pandas\n"
        "ModuleNotFoundError: No module named 'pandas'",
        "",
        {"os": "Ubuntu 22.04", "memory_usage_percent": 35},
    ),
    (
        "네트워크 연결 오류",
        "2026-06-11 10:12:03 ERROR Failed to fetch https://api.example.com/data\n"
        "ConnectionError: [Errno 111] Connection refused",
        "Errno 111",
        {"os": "Ubuntu 22.04", "memory_usage_percent": 40},
    ),
    (
        "권한 문제",
        "2026-06-11 14:03:21 ERROR Failed to save config to C:\\Program Files\\MyApp\\settings.ini\n"
        "PermissionError: [Errno 13] Access is denied\n"
        "현재 사용자는 관리자 권한이 아님",
        "Errno 13",
        {"os": "Windows 11", "memory_usage_percent": 47, "is_admin": False},
    ),
    (
        "메모리 부족 / 앱 크래시",
        "2026-06-11 22:41:55 FATAL Process killed\n"
        "java.lang.OutOfMemoryError: Java heap space",
        "",
        {"os": "Ubuntu 22.04", "memory_usage_percent": 96},
    ),
]


def main():
    workflow = DiagnosisWorkflow()

    print("=" * 80)
    print("4개 유형 분류/진단 테스트")
    print("=" * 80)

    correct = 0
    for expected, log_text, error_code, system_state in SAMPLES:
        state = workflow.run(log_text=log_text, error_code=error_code, system_state=system_state)
        d = state.diagnosis

        rule_ok = state.rule_category == expected
        llm_ok = d.get("issue_type") == expected
        if rule_ok and llm_ok:
            correct += 1

        print()
        print(f"[기대 유형] {expected}")
        print(f"  규칙 분류 : {state.rule_category}        {'✅' if rule_ok else '❌'}")
        print(f"  LLM 진단  : {d.get('issue_type')} (신뢰도 {d.get('confidence')})   {'✅' if llm_ok else '❌'}")
        print(f"  안전조치ID: {d.get('safe_action_id') or '없음'}")

    print()
    print("=" * 80)
    print(f"결과: {correct}/{len(SAMPLES)} 유형 정확 분류")
    print("=" * 80)


if __name__ == "__main__":
    main()
