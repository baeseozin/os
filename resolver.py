# resolver.py
# 4단계: 진단 결과(safe_action_id)에 따라 실제 조치를 수행한다.
#  - 읽기전용 점검(네트워크/경로/메모리)은 자동 실행
#  - 시스템을 바꾸는 조치(패키지 설치)는 명령을 제시하고 execute=True 일 때만 실행
#  - 권한 등 위험 조치는 단계 안내만
import os
import re
import socket
import subprocess
import sys
from typing import Dict, Any, List


class Resolver:

    # 자동 모드(auto=True)에서 확인 없이 실행해도 되는, 미리 허용한 안전한 작업
    # (안전·복구 가능한 것만. 권한 변경·삭제 등 위험 작업은 포함하지 않는다.)
    AUTO_SAFE = {"reinstall_dependency_guide"}

    def resolve(self, state, execute: bool = False, auto: bool = False) -> Dict[str, Any]:
        action = (state.diagnosis or {}).get("safe_action_id", "")
        log = state.log_text or ""

        # 자동 모드 + 안전 작업이면 확인 없이 바로 실행
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

    # ---------- 변경 조치: 누락 패키지 설치 ----------
    def _reinstall_dependency(self, log: str, execute: bool) -> Dict[str, Any]:
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
                    "command": cmd_str,
                    "message": f"누락된 모듈 '{module}' 설치가 필요합니다."}

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

    # ---------- 읽기전용: 네트워크 연결 점검 ----------
    def _check_network(self, log: str, execute: bool) -> Dict[str, Any]:
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

    # ---------- 읽기전용: 경로 존재 점검 ----------
    def _check_path(self, log: str, execute: bool) -> Dict[str, Any]:
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

    # ---------- 읽기전용: 메모리 상위 프로세스 ----------
    def _free_memory(self, log: str, execute: bool) -> Dict[str, Any]:
        try:
            import psutil
            vm = psutil.virtual_memory()
            procs = sorted(
                psutil.process_iter(["name", "memory_percent"]),
                key=lambda p: (p.info.get("memory_percent") or 0),
                reverse=True,
            )[:5]
            top = "\n".join(f"  {p.info['name']}: {(p.info.get('memory_percent') or 0):.1f}%"
                            for p in procs)
            return {"action": "free_memory", "kind": "auto", "executed": True,
                    "output": f"현재 메모리 사용률: {vm.percent}%\n메모리 상위 프로세스:\n{top}"}
        except Exception:
            return {"action": "free_memory", "kind": "guide", "executed": False,
                    "steps": ["불필요한 프로그램을 종료해 메모리를 확보하세요.",
                              "작업 관리자(Windows) 또는 top/htop(리눅스)으로 점유 프로세스를 확인하세요.",
                              "(psutil 설치 시 자동 점검 가능: pip install psutil)"]}

    # ---------- 안내만: 관리자 권한 재실행 ----------
    def _rerun_as_admin(self, log: str, execute: bool) -> Dict[str, Any]:
        return {"action": "rerun_as_admin", "kind": "guide", "executed": False,
                "steps": ["프로그램을 관리자 권한으로 다시 실행하세요. "
                          "(Windows: 아이콘 우클릭 → '관리자 권한으로 실행')",
                          "또는 저장 경로를 사용자 폴더(내 문서·AppData 등)로 변경하세요."]}

    def _unknown(self, log: str, execute: bool) -> Dict[str, Any]:
        return {"action": "none", "kind": "guide", "executed": False,
                "steps": ["적용 가능한 자동 조치가 없습니다. 진단 결과의 해결 방법을 수동으로 따르세요."]}


# -----------------------------------
# 조치 결과를 리포트 문자열(라인 리스트)로 렌더링
# -----------------------------------
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

    else:  # guide
        lines.append("권장 조치 (수동):")
        for i, step in enumerate(resolution.get("steps", []), start=1):
            lines.append(f"  {i}. {step}")

    return lines
