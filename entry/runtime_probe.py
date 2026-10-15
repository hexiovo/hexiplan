"""Read-only, allowlisted native Codex routing evidence. No config or auth reads."""
from __future__ import annotations
import argparse, json, os, re, sys
from pathlib import Path

def read_thread(home: Path, thread_id: str) -> dict:
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", thread_id):
        raise ValueError("Invalid native thread ID")
    sessions = home / "sessions"
    if not sessions.is_dir():
        raise ValueError("Native sessions directory unavailable; do not guess another CODEX_HOME")
    candidates = list(sessions.rglob("*" + thread_id + ".jsonl"))
    if len(candidates) != 1:
        raise ValueError("Expected one native rollout for the requested thread")
    path = candidates[0]
    if path.is_symlink() or path.is_junction() or not path.resolve().is_relative_to(sessions.resolve()):
        raise ValueError("Unsafe rollout path")
    metadata = None
    context = None
    incomplete = 0
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                incomplete += 1
                continue
            payload = event.get("payload", {})
            if event.get("type") == "session_meta":
                metadata = payload
            elif event.get("type") == "turn_context":
                context = payload
    if not metadata or metadata.get("id") != thread_id or not context:
        raise ValueError("Native identity or turn_context unavailable")
    source = metadata.get("source")
    spawn = source.get("subagent", {}).get("thread_spawn", {}) if isinstance(source, dict) else {}
    model = context.get("model")
    effort = context.get("effort", context.get("reasoning_effort"))
    if not isinstance(model, str) or not isinstance(effort, str):
        raise ValueError("Native model/effort unavailable")
    return {"thread_id": thread_id, "model": model, "effort": effort,
            "parent_thread_id": spawn.get("parent_thread_id"),
            "agent_path": spawn.get("agent_path"),
            "source": "native rollout session_meta + latest turn_context",
            "incomplete_lines_ignored": incomplete}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thread-id", help="Exact runtime thread ID; defaults to existing CODEX_THREAD_ID")
    args = parser.parse_args()
    try:
        home_value = os.environ.get("CODEX_HOME")
        thread_id = args.thread_id or os.environ.get("CODEX_THREAD_ID")
        if not home_value or not thread_id:
            raise ValueError("CODEX_HOME or CODEX_THREAD_ID missing; no location guessed")
        home = Path(home_value)
        if not home.is_absolute() or not home.is_dir():
            raise ValueError("Existing absolute CODEX_HOME required")
        current = read_thread(home, thread_id)
        parent_id = current["parent_thread_id"]
        parent = read_thread(home, parent_id) if parent_id else None
        print(json.dumps({"status": "OBSERVED", "current": current, "parent": parent,
                          "writes": False, "credentials_read": False,
                          "scope": "Client runtime routing; not independent backend attestation"}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "UNVERIFIED", "reason": str(exc), "writes": False}, ensure_ascii=False))
        return 2

if __name__ == "__main__":
    sys.exit(main())
