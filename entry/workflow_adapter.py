"""Reuse the packaged workflow with progress-based retry, loop detection and a 30-round cap.

The original workflow.py and checksum manifest are never modified.
All CLI commands retain the original validation and journal handling.
This public adapter contains no task-specific compatibility code.
"""
from __future__ import annotations
import ast
import hashlib
import sys
from pathlib import Path

sys.dont_write_bytecode = True
TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import workflow as original

MAX_REPAIR_ROUNDS = 30

def _repair_can_continue(run, s, evidence):
    """Require an explicit progress assessment; stop repeated/no-progress attempts.

    The agent evaluates semantic progress. This guard validates the record and
    catches repeated normalized attempts across the task; it does not claim to
    detect every semantic loop or a process hang automatically.
    """
    verdict = original.load(original.safe_path(run, evidence))
    assessment = verdict.get("repair_assessment")
    history = s.setdefault("repair_history", [])
    if not isinstance(history, list) or any(not isinstance(item, dict) for item in history):
        raise original.WorkflowError("Invalid repair history; do not reset prior attempts")
    if not isinstance(assessment, dict):
        s["repair_stop_reason"] = "Missing repair_assessment; progress is unverified"
        return False
    fields = ("issue_id", "attempt", "outcome", "reason")
    if any(not isinstance(assessment.get(key), str) or not assessment[key].strip() for key in fields):
        s["repair_stop_reason"] = "Incomplete repair_assessment; progress is unverified"
        return False
    status = assessment.get("status")
    if status not in {"progress", "stuck", "loop"}:
        s["repair_stop_reason"] = "Invalid progress status; stop until clarified"
        return False
    def normalized(value):
        return " ".join(value.casefold().split())
    information = assessment.get("new_information", "")
    if not isinstance(information, str):
        information = ""
    signature = hashlib.sha256(original.canonical([
        normalized(assessment["issue_id"]), normalized(assessment["attempt"]),
        normalized(assessment["outcome"]), normalized(information)
    ])).hexdigest()
    repeated = any(item.get("fingerprint") == signature for item in history)
    action = assessment.get("next_action", "")
    rounds = s.get("repair_rounds", 0)
    if not isinstance(rounds, int) or isinstance(rounds, bool) or rounds < 0:
        raise original.WorkflowError("Invalid repair counter; do not reset prior attempts")
    issue = normalized(assessment["issue_id"])
    issue_rounds = sum(
        1 for item in history if item.get("decision") == "continue"
        and isinstance(item.get("assessment"), dict)
        and isinstance(item["assessment"].get("issue_id"), str)
        and normalized(item["assessment"]["issue_id"]) == issue
    )
    limit_reached = max(rounds, issue_rounds) >= MAX_REPAIR_ROUNDS
    can_continue = (status == "progress" and not repeated and not limit_reached and bool(information.strip())
                    and isinstance(action, str) and bool(action.strip()))
    if can_continue:
        reason = "New evidence and a concrete next action recorded"
        s.pop("repair_stop_reason", None)
    else:
        reason = (f"Repair limit reached ({MAX_REPAIR_ROUNDS}); stop before another repair" if limit_reached
                  else "Repeated issue/attempt/outcome without new evidence" if repeated
                  else assessment["reason"] if status in {"stuck", "loop"}
                  else "No concrete new evidence or next action; stop retrying")
        s["repair_stop_reason"] = reason
    history.append({
        "at": original.now(), "repair_round": s.get("repair_rounds", 0),
        "evidence": evidence, "assessment": assessment,
        "fingerprint": signature, "decision": "continue" if can_continue else "stop",
        "decision_reason": reason,
    })
    return can_continue

def install_repair_limit():
    source = TOOLS / "workflow.py"
    tree = ast.parse(source.read_text(encoding="utf-8-sig"), filename=str(source))
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "verdict"]
    if len(functions) != 1:
        raise original.WorkflowError("Unsupported packaged verdict: expected one function")
    function = functions[0]
    expected = ast.dump(ast.parse('s["repair_rounds"] < 2', mode="eval").body)
    matches = [n for n in ast.walk(function) if isinstance(n, ast.Compare) and ast.dump(n) == expected]
    if len(matches) != 1:
        raise original.WorkflowError("Unsupported packaged repair limit; original workflow left intact")
    comparison = matches[0]
    replacement = ast.copy_location(ast.Call(
        func=ast.Name(id="_hexiplan_repair_can_continue", ctx=ast.Load()),
        args=[ast.Name(id="run", ctx=ast.Load()), ast.Name(id="s", ctx=ast.Load()),
              ast.Name(id="evidence", ctx=ast.Load())], keywords=[]), comparison)
    guards = [n for n in ast.walk(function) if isinstance(n, ast.If) and n.test is comparison]
    if len(guards) != 1:
        raise original.WorkflowError("Unsupported repair branch; original workflow left intact")
    guards[0].test = replacement
    original._hexiplan_repair_can_continue = _repair_can_continue
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    # Retain the original function's guards, evidence rules, globals and journal caller.
    exec(compile(module, str(source) + " [progress-based retry adapter]", "exec"), original.__dict__)
    return original


def main(argv=None):
    try:
        install_repair_limit()
    except (original.WorkflowError, OSError, SyntaxError) as exc:
        print("HexiPlan adapter: " + str(exc), file=sys.stderr)
        return 2
    return original.main(argv)

if __name__ == "__main__":
    raise SystemExit(main())
