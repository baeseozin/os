# main.py
from __future__ import annotations  # Python 3.9 에서 'str | None' 표기 호환

import json
import platform
import sys

from dotenv import load_dotenv

# 다른 모듈을 import 하기 전에 .env 파일을 먼저 읽어 환경변수로 주입한다.
# (crew.LlamaDiagnoser 가 LLAMA_BASE_URL 등을 os.environ 에서 읽기 때문)
load_dotenv()

from workflow import DiagnosisWorkflow
from resolver import render_resolution

SHOW_RAW_RESULTS = False

QUIT_WORDS = {"q", "quit", "exit", "종료"}


def collect_system_state() -> dict:
    """앞단: psutil 로 현재 시스템 상태를 수집한다. (1단계 분류의 보조 신호)"""
    state = {"os": platform.system()}
    try:
        import psutil
        state["cpu_usage_percent"] = psutil.cpu_percent(interval=0.3)
        state["memory_usage_percent"] = psutil.virtual_memory().percent
    except Exception:
        pass  # psutil 미설치 시 로그만으로 분석
    return state


def read_log() -> str | None:
    """여러 줄 오류 로그를 키보드로 입력받는다.
    - 빈 줄에서 Enter 를 치면 입력 종료(분석 시작)
    - 첫 줄에 q/quit/exit/종료 를 입력하면 None 반환(프로그램 종료)
    """
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
    # --auto: 미리 허용한 안전한 조치(예: pip install)는 확인 없이 자동 실행
    auto = "--auto" in sys.argv

    # 시작 시 1회 — LLAMA_BASE_URL 등 환경변수 검증 및 단계 초기화
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

        # 자동 실행 대상이 아닌 변경 조치는 확인(y/N) 후 실행
        res = result_state.resolution
        if res.get("kind") == "confirm" and not res.get("executed"):
            answer = input(f"\n위 명령을 실제로 실행할까요? (y/N): ").strip().lower()
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
