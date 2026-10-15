"""Reuse the packaged workflow, allowing at most three corrective rounds.

The original workflow.py and checksum manifest are never modified.
All CLI commands retain the original validation and journal handling.
"""
from __future__ import annotations
import ast
import sys
from pathlib import Path

sys.dont_write_bytecode = True
TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import workflow as original

MAX_REPAIR_ROUNDS = 3
P4_RUN_ID = "20261007-qiling"
P4_PACKAGE_ID = "final-cleanup-handoff"
P4_FLAG = "--final-cleanup-handoff"

def _p4_cleanup_allowed(run, s, apply):
    if not getattr(original, "_hexiplan_p4_cleanup_requested", False):
        return False
    if not apply:
        raise original.WorkflowError("The P4 compatibility flag requires cleanup --apply.")
    expected_run = (Path(__file__).resolve().parents[1] / "runs" / P4_RUN_ID).resolve()
    if run.resolve() != expected_run or s.get("run_id") != P4_RUN_ID:
        raise original.WorkflowError("P4 compatibility cleanup is limited to the exact legacy RUN.")
    if s.get("phase") != "execution":
        raise original.WorkflowError("P4 compatibility cleanup requires the preserved execution phase.")
    if s.get("pending") is not None or s.get("cleanup") is not None or s.get("verification") is not None:
        raise original.WorkflowError("P4 compatibility cleanup requires no pending gate, prior cleanup, or verification.")
    leases = s.get("leases")
    if not isinstance(leases, dict) or leases:
        raise original.WorkflowError("P4 compatibility cleanup requires zero active leases.")
    packages = s.get("packages")
    if not isinstance(packages, list) or any(not isinstance(p, dict) for p in packages):
        raise original.WorkflowError("P4 compatibility cleanup requires a valid package list.")
    targets = [p for p in packages if p.get("id") == P4_PACKAGE_ID]
    if len(targets) != 1 or targets[0].get("status") != "BLOCKED":
        raise original.WorkflowError("Exactly one BLOCKED final-cleanup-handoff package is required.")
    if not packages or packages[-1] is not targets[0]:
        raise original.WorkflowError("The final-cleanup-handoff package must be last in the approved package list.")
    if any(p is not targets[0] and p.get("status") != "PASS" for p in packages):
        raise original.WorkflowError("Every other approved package must already be PASS.")
    return True

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
    matches[0].comparators[0] = ast.copy_location(ast.Constant(MAX_REPAIR_ROUNDS), matches[0].comparators[0])
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    # Retain the original function's guards, evidence rules, globals and journal caller.
    exec(compile(module, str(source) + " [three-round adapter]", "exec"), original.__dict__)
    return original

def install_p4_cleanup_compat():
    source = TOOLS / "workflow.py"
    tree = ast.parse(source.read_text(encoding="utf-8-sig"), filename=str(source))
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "clean_temps"]
    if len(functions) != 1:
        raise original.WorkflowError("Unsupported packaged cleanup: expected one function")
    function = functions[0]
    # The P4 flag is installed only for an explicit request. Validate its complete
    # allowlist before the legacy report-phase guard can short-circuit.
    entry_guard = ast.Expr(value=ast.Call(
        func=ast.Name(id="_hexiplan_p4_cleanup_allowed", ctx=ast.Load()),
        args=[ast.Name(id="run", ctx=ast.Load()), ast.Name(id="s", ctx=ast.Load()), ast.Name(id="apply", ctx=ast.Load())],
        keywords=[],
    ))
    docstring = ast.get_docstring(function, clean=False)
    entry_guard = ast.copy_location(entry_guard, function.body[0]) if function.body else entry_guard
    function.body.insert(1 if docstring is not None else 0, entry_guard)
    expected = ast.dump(ast.parse('s["phase"] != "report"', mode="eval").body)
    guards = [n for n in ast.walk(function) if isinstance(n, ast.If) and ast.dump(n.test) == expected]
    if len(guards) != 1:
        raise original.WorkflowError("Unsupported cleanup phase guard; original workflow left intact")
    prior_guard = guards[0].test
    allowed = ast.Call(
        func=ast.Name(id="_hexiplan_p4_cleanup_allowed", ctx=ast.Load()),
        args=[ast.Name(id="run", ctx=ast.Load()), ast.Name(id="s", ctx=ast.Load()), ast.Name(id="apply", ctx=ast.Load())],
        keywords=[],
    )
    guards[0].test = ast.copy_location(
        ast.BoolOp(op=ast.And(), values=[prior_guard, ast.UnaryOp(op=ast.Not(), operand=allowed)]),
        prior_guard,
    )
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    original._hexiplan_p4_cleanup_allowed = _p4_cleanup_allowed
    exec(compile(module, str(source) + " [targeted P4 cleanup adapter]", "exec"), original.__dict__)
    return original

def _prepare_args(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    count = args.count(P4_FLAG)
    if count == 0:
        return args, False
    if count != 1 or args.count("cleanup") != 1:
        raise original.WorkflowError("The P4 flag is accepted only once with the cleanup command.")
    command_index = args.index("cleanup")
    flag_index = args.index(P4_FLAG)
    if flag_index <= command_index or "--apply" not in args[command_index + 1:]:
        raise original.WorkflowError("Use cleanup --apply --final-cleanup-handoff.")
    if args.count("--run") != 1:
        raise original.WorkflowError("P4 compatibility cleanup requires one explicit --run path.")
    run_index = args.index("--run")
    if run_index + 1 >= len(args):
        raise original.WorkflowError("Missing --run path.")
    run_path = Path(args[run_index + 1])
    expected_run = (Path(__file__).resolve().parents[1] / "runs" / P4_RUN_ID).resolve()
    if not run_path.is_absolute() or run_path.resolve() != expected_run:
        raise original.WorkflowError("The P4 flag requires the exact absolute legacy RUN path.")
    args.pop(flag_index)
    return args, True

def main(argv=None):
    try:
        args, p4_requested = _prepare_args(argv)
        original._hexiplan_p4_cleanup_requested = p4_requested
        install_repair_limit()
        if p4_requested:
            install_p4_cleanup_compat()
    except (original.WorkflowError, OSError, SyntaxError, IndexError, ValueError) as exc:
        print("HexiPlan adapter: " + str(exc), file=sys.stderr)
        return 2
    return original.main(args)

if __name__ == "__main__":
    raise SystemExit(main())
