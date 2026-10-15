#!/usr/bin/env python3
"""HexiPlan's local gate journal, cooperative resource ledger and safe temp cleaner.
Python 3.10+, standard library only. This is NOT an authentication or OS sandbox.
"""
from __future__ import annotations
import argparse
import contextlib
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid

LIMITS = {"sol": 3, "luna": 6, "browser": 2, "high_memory": 1}
GATES = {"requirements": "requirements", "solution": "solution", "roadmap": "roadmap", "step_plan": "step_plan", "step_acceptance": "report"}
NEXT = {"requirements": "solution", "solution": "roadmap", "roadmap": "step_plan", "step_plan": "execution"}
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")

class WorkflowError(ValueError):
    pass

def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda:f.read(1024*1024), b""): h.update(part)
    return h.hexdigest()

def load(path: Path):
    with path.open(encoding="utf-8-sig") as f: return json.load(f)

def atomic(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    try:
        with tmp.open("x", encoding="utf-8", newline="\n") as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write("\n"); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists(): tmp.unlink()

def identifier(value: str) -> str:
    if not SAFE_ID.fullmatch(value): raise WorkflowError("Use a short ID containing only letters, digits, dash, underscore or dot.")
    return value

def safe_path(root: Path, rel: str, must_exist=True) -> Path:
    """Reject traversal, symlinks and Windows reparse points in every existing component."""
    p=Path(rel)
    if p.is_absolute() or ".." in p.parts: raise WorkflowError("Expected a relative path without '..'.")
    root=root.resolve()
    q=root
    for part in p.parts:
        q=q/part
        if q.exists() or q.is_symlink():
            st=q.lstat()
            if q.is_symlink() or (getattr(st,"st_file_attributes",0) & 0x400):
                raise WorkflowError("Symlink/junction/reparse point is not permitted: "+str(q))
    target=(root/p).resolve()
    if not target.is_relative_to(root): raise WorkflowError("Path escapes its authorized root.")
    if must_exist and not target.exists(): raise WorkflowError("Missing file: "+str(target))
    return target

@contextlib.contextmanager
def locked(run: Path):
    if not (run/"journal").is_dir(): raise WorkflowError("Not an initialized HexiPlan run.")
    lock=run/".state.lock"
    deadline=time.monotonic()+8
    while True:
        try:
            fd=os.open(lock, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
            os.write(fd, canonical({"pid":os.getpid(),"at":now()}));os.close(fd);break
        except FileExistsError:
            if time.monotonic()>deadline:
                raise WorkflowError("State is locked. Check live writers before manually removing a stale .state.lock; never auto-steal it.")
            time.sleep(.08)
    try: yield
    finally:
        lock.unlink(missing_ok=True)

def state(run: Path) -> dict:
    events=sorted((run/"journal").glob("[0-9]*.json"))
    if not events: raise WorkflowError("No committed journal state.")
    event=load(events[-1]); check=event.pop("sha256",None)
    if hashlib.sha256(canonical(event)).hexdigest()!=check:
        raise WorkflowError("The latest committed journal is damaged. Do not silently roll back approvals.")
    s=event["state"]
    if s["run_id"]!=run.name: raise WorkflowError("Run folder was renamed. Restore its run ID; moving HOME is allowed, renaming a run is not.")
    return s

def commit(run: Path, s: dict, action: str, payload=None) -> dict:
    s=copy.deepcopy(s);s["sequence"]+=1;s["updated_at"]=now()
    event={"sequence":s["sequence"],"at":s["updated_at"],"action":action,"detail":payload or {},"state":s}
    event["sha256"]=hashlib.sha256(canonical(event)).hexdigest()
    target=run/"journal"/f'{s["sequence"]:08d}.json'
    if target.exists(): raise WorkflowError("Journal sequence conflict.")
    atomic(target,event)  # write-ahead: this is the authoritative commit
    atomic(run/"state.json",s)  # recoverable convenience snapshot
    return s

def init_run(run: Path, project: Path, task="") -> dict:
    identifier(run.name)
    if run.exists(): raise WorkflowError("Run already exists; use resume. Never overwrite a run.")
    if not project.is_dir(): raise WorkflowError("The authorized project directory must already exist.")
    run.mkdir(parents=True)
    for folder in ["journal","approvals","plans","reports","evidence","logs","fixtures","references","tmp"]:
        (run/folder).mkdir()
    s={"schema_version":1,"run_id":run.name,"project":str(project.resolve()),"task":task,
       "phase":"requirements","step_index":0,"steps":[],"packages":[],"pending":None,
       "approvals":[],"gate_versions":{},"repair_rounds":0,"verification":None,
       "leases":{},"temps":{},"cleanup":None,"limits":LIMITS.copy(),
       "sequence":0,"created_at":now(),"updated_at":now(),"notes":[]}
    return commit(run,s,"init")

def current_step(s):
    return s["steps"][s["step_index"]]["id"] if s["steps"] and s["step_index"]<len(s["steps"]) else ""

def report_content_hash(data):
    d=copy.deepcopy(data);d.pop("content_sha256",None)
    return hashlib.sha256(canonical(d)).hexdigest()

def confirmation(p):
    return f'确认 HexiPlan | task={p["run_id"]} | gate={p["gate"]} | step={p["step"] or "-"} | revision={p["revision"]} | sha256={p["content_sha256"]}'

def validate_items(items, label):
    if not isinstance(items,list) or not items: raise WorkflowError(label+" must be a nonempty list.")
    seen=set()
    for x in items:
        key=identifier(x["id"])
        if key in seen: raise WorkflowError("Duplicate "+label+" id.")
        if any(dep not in seen for dep in x.get("dependencies",[])):
            raise WorkflowError("Dependencies must precede dependants in the listed sequence.")
        if not x.get("title"): raise WorkflowError(label+" title is required.")
        seen.add(key)

def _report_manifest(run, folder):
    manifest={}
    for p in sorted(folder.rglob("*")):
        if p.is_file():
            safe_path(run,p.relative_to(run).as_posix())
            manifest[p.relative_to(run).as_posix()]=digest(p)
    return manifest

def submit(run: Path,s: dict,gate: str,report: str):
    if s["phase"]!=GATES[gate] or s["pending"]:
        raise WorkflowError("Wrong phase for gate submission: "+s["phase"])
    folder=safe_path(run,report)
    if not folder.is_dir() or not folder.is_relative_to((run/"reports").resolve()):
        raise WorkflowError("Report must be a versioned directory under this run/reports.")
    d=load(folder/"report.json")
    if not (folder/"report.html").is_file(): raise WorkflowError("Render HTML before submitting.")
    m=d.get("meta",{})
    if m.get("is_template") or m.get("run_id")!=s["run_id"] or m.get("gate")!=gate:
        raise WorkflowError("Template or mismatched report cannot be approved.")
    step=current_step(s) if gate in {"step_plan","step_acceptance"} else ""
    if m.get("step","")!=step: raise WorkflowError("Report step does not match the active step.")
    key=gate+":"+step
    expected=s["gate_versions"].get(key,0)+1
    if m.get("revision")!=expected: raise WorkflowError(f"Expected report revision {expected}.")
    if d.get("content_sha256")!=report_content_hash(d): raise WorkflowError("Report content hash is invalid.")
    if gate=="roadmap": validate_items(d.get("roadmap_steps"),"roadmap_steps")
    if gate=="step_plan": validate_items(d.get("work_packages"),"work_packages")
    if d.get("blocking_questions"): raise WorkflowError("Resolve blocking questions before requesting approval.")
    if gate=="step_acceptance":
        if not s.get("verification") or s["verification"]["overall"]!="PASS": raise WorkflowError("Independent verification must pass.")
        if s.get("cleanup") is None: raise WorkflowError("Run the bounded cleanup, even if zero files qualify.")
    p={"run_id":s["run_id"],"gate":gate,"step":step,"revision":expected,
       "content_sha256":d["content_sha256"],"folder":folder.relative_to(run).as_posix(),
       "files":_report_manifest(run,folder),"submitted_at":now()}
    s["pending"]=p;s["gate_versions"][key]=expected;s["phase"]="awaiting_"+gate
    return {"confirmation":confirmation(p),"html":str(folder/"report.html")}

def approve(run,s,message_file,map_content_sha256=None):
    p=s.get("pending")
    if not p or not s["phase"].startswith("awaiting_"): raise WorkflowError("No pending gate.")
    raw=Path(message_file).read_text(encoding="utf-8-sig").strip()
    if not raw: raise WorkflowError("The actual user message is required.")
    # Feedback exports are data, never approval receipts, even if they quote a token.
    if "HEXIPLAN_REVIEW_FEEDBACK" in raw or "hexiplan.review-feedback" in raw:
        raise WorkflowError("This is a feedback export, not a direct approval. Import/review it separately; do not advance the gate.")
    exact = confirmation(p) in raw
    if not exact:
        # The trusted conversation host must map a real, unambiguous user decision.
        # This is a declared binding, NOT automatic NLP or user authentication.
        if map_content_sha256 != p["content_sha256"]:
            raise WorkflowError("Use the exact confirmation, or explicitly bind an actual unambiguous user decision with --map-content-sha256.")
    for rel,h in p["files"].items():
        f=safe_path(run,rel)
        if digest(f)!=h: raise WorkflowError("Submitted report changed; reject and render a new version.")
    d=load(run/p["folder"]/"report.json")
    s["approvals"].append({**p,"user_message":raw,"approval_mode":"exact_token" if exact else "explicit_conversation_mapping","approved_at":now()})
    receipt=run/"approvals"/f'{len(s["approvals"]):04d}-{p["gate"]}.json'
    atomic(receipt,s["approvals"][-1])
    g=p["gate"]
    if g=="roadmap":
        s["steps"]=copy.deepcopy(d["roadmap_steps"]);s["step_index"]=0
    if g=="step_plan":
        s["packages"]=[{**copy.deepcopy(x),"status":"PLANNED","evidence":None} for x in d["work_packages"]]
        s["repair_rounds"]=0;s["verification"]=None;s["cleanup"]=None
    if g=="step_acceptance":
        s["steps"][s["step_index"]]["status"]="ACCEPTED"
        s["step_index"]+=1
        s["phase"]="complete" if s["step_index"]==len(s["steps"]) else "step_plan"
        s["packages"]=[]
    else: s["phase"]=NEXT[g]
    s["pending"]=None
    return {"phase":s["phase"],"next_step":current_step(s)}

def reject(s,reason):
    p=s.get("pending")
    if not p: raise WorkflowError("No pending gate.")
    s["notes"].append({"at":now(),"type":"rejection","gate":p["gate"],"revision":p["revision"],"reason":reason})
    s["phase"]=GATES[p["gate"]];s["pending"]=None

def replan(s,gate,message_file,reason):
    if gate not in {"solution", "step_plan"}: raise WorkflowError("Replan target must be solution or step_plan.")
    raw=Path(message_file).read_text(encoding="utf-8-sig").strip()
    if not raw or not reason.strip(): raise WorkflowError("Actual user instruction and reason are required.")
    if not any(a["gate"]=="requirements" for a in s["approvals"]):
        raise WorkflowError("Requirements have not been approved yet.")
    if gate=="step_plan" and (not current_step(s) or s["phase"]=="complete"):
        raise WorkflowError("No current step to replan.")
    s["notes"].append({"at":now(),"type":"explicit_replan","target":gate,
        "reason":reason,"user_message":raw,"prior_phase":s["phase"],
        "prior_step":current_step(s),"prior_packages":copy.deepcopy(s["packages"]),
        "prior_verification":copy.deepcopy(s["verification"]),"prior_repair_rounds":s["repair_rounds"],
        "prior_pending":copy.deepcopy(s["pending"])})
    # Never approve a new plan or reset retries here. A new plan must go through
    # its ordinary HTML gate. Past decisions remain in the append-only journal.
    s["phase"]=gate;s["pending"]=None;s.pop("paused_from",None)
    return {"phase":gate,"requires_new_user_approval":True}

def record_package(run,s,package,status,evidence):
    if s["phase"] not in {"execution","repair"}: raise WorkflowError("Implementation is not authorized in this phase.")
    found=next((x for x in s["packages"] if x["id"]==package),None)
    if found is None: raise WorkflowError("Unknown approved work package.")
    f=safe_path(run,evidence)
    if not f.is_file(): raise WorkflowError("Evidence must be a file.")
    found.update(status=status,evidence=evidence,evidence_sha256=digest(f))

def begin_verification(s):
    if s["phase"] not in {"execution","repair"}: raise WorkflowError("Wrong phase for verification.")
    if not s["packages"] or any(x["status"]!="PASS" for x in s["packages"]):
        raise WorkflowError("All approved work packages must report PASS first.")
    s["phase"]="verification"

def verdict(run,s,evidence):
    if s["phase"]!="verification": raise WorkflowError("Not in independent verification.")
    f=safe_path(run,evidence);v=load(f)
    if v.get("overall") not in {"PASS","FAIL"}: raise WorkflowError("overall must be PASS or FAIL.")
    if not v.get("independent_reviewer") or not isinstance(v.get("criteria"),list) or not v["criteria"]:
        raise WorkflowError("Independent reviewer and nonempty criterion evidence are required.")
    for c in v["criteria"]:
        if c.get("status") not in {"PASS","FAIL","BLOCKED","NOT_RUN","NOT_APPLICABLE"} or not c.get("evidence"):
            raise WorkflowError("Every criterion needs an explicit status and actual evidence/explanation.")
    failed=[c for c in v["criteria"] if c.get("required",True) and c["status"] in {"FAIL","BLOCKED","NOT_RUN"}]
    if v["overall"]=="PASS" and failed: raise WorkflowError("Required failures or unrun tests cannot pass.")
    s["verification"]={**v,"file":evidence,"sha256":digest(f),"repair_round":s["repair_rounds"]}
    if v["overall"]=="PASS": s["phase"]="report"
    elif s["repair_rounds"]<2:
        s["repair_rounds"]+=1;s["phase"]="repair"
    else: s["phase"]="blocked"
    return {"phase":s["phase"],"repair_rounds":s["repair_rounds"]}

def lease(s,owner,kinds,release=False):
    identifier(owner)
    if release:
        if owner not in s["leases"]: raise WorkflowError("Unknown resource owner.")
        del s["leases"][owner];return
    ks=[x.strip() for x in kinds.split(",") if x.strip()]
    if len(ks)!=len(set(ks)) or any(k not in LIMITS for k in ks) or not ks: raise WorkflowError("Invalid resource kinds.")
    if "sol" in ks and "luna" in ks: raise WorkflowError("A single agent cannot claim both model pools.")
    old=s["leases"].get(owner,{"resources":[]})
    resources=sorted(set(old["resources"])|set(ks))
    if "sol" in resources and "luna" in resources: raise WorkflowError("A single agent cannot change model pools while holding an active lease.")
    for k in resources:
        used=sum(k in v["resources"] for o,v in s["leases"].items() if o!=owner)
        if used>=s["limits"][k]: raise WorkflowError(f"{k} capacity exhausted; queue, do not spawn more.")
    s["leases"][owner]={"resources":resources,"since":old.get("since",now())}

def register_temp(run,s,rel):
    f=safe_path(run,rel)
    if not f.is_file() or not f.is_relative_to((run/"tmp").resolve()): raise WorkflowError("Only individual run/tmp files may be registered.")
    s["temps"][f.relative_to(run).as_posix()]={"sha256":digest(f),"bytes":f.stat().st_size,"registered_at":now()}

def clean_temps(run,s,apply=False):
    plan=[];retained=[]
    docs=[]
    for folder in ["reports","evidence","plans"]:
        for p in (run/folder).rglob("*"):
            if p.is_file() and p.suffix.lower() in {".json",".md",".txt",".html"} and p.stat().st_size<20_000_000:
                docs.append(p.read_text(encoding="utf-8",errors="replace"))
    for rel,info in s["temps"].items():
        f=safe_path(run,rel,must_exist=False)
        if not f.exists(): continue
        if not f.is_file() or not f.is_relative_to((run/"tmp").resolve()): raise WorkflowError("Unsafe registered temp path.")
        if digest(f)!=info["sha256"]:
            retained.append({"path":rel,"reason":"changed since registration"});continue
        if any(rel in t or str(f) in t for t in docs):
            retained.append({"path":rel,"reason":"referenced by retained material"});continue
        plan.append({"path":rel,"bytes":f.stat().st_size})
    out={"at":now(),"applied":apply,"deleted":plan if apply else [],"candidates":plan,
         "retained":retained,"freed_bytes":sum(x["bytes"] for x in plan) if apply else 0}
    if apply:
        if s["phase"]!="report": raise WorkflowError("Final step cleanup is permitted in the report phase only.")
        for item in plan:
            safe_path(run,item["path"]).unlink();s["temps"].pop(item["path"],None)
        s["cleanup"]=out
        atomic(run/"logs"/f'cleanup-{current_step(s)}-{s["sequence"]+1}.json',out)
    return out

def summary(s):
    return {"run_id":s["run_id"],"phase":s["phase"],"step":current_step(s),"steps":s["steps"],
            "pending":s["pending"],"packages":s["packages"],"repair_rounds":s["repair_rounds"],
            "resources":{k:{"used":sum(k in x["resources"] for x in s["leases"].values()),"limit":v} for k,v in s["limits"].items()},
            "last_approval":s["approvals"][-1] if s["approvals"] else None,"sequence":s["sequence"],
            "latest_feedback":s.get("feedback_records",[])[-1] if s.get("feedback_records") else None,
            "module_selections":{owner:{"kind":rec["kind"],"phase":rec["phase"],"step":rec["step"],"modules":[{"id":m["id"],"sha256":m["sha256"],"snapshot":m.get("snapshot")} for m in rec["modules"]]} for owner,rec in s.get("module_selections",{}).items()}}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run",required=True,type=Path)
    sub=p.add_subparsers(dest="command",required=True)
    q=sub.add_parser("init");q.add_argument("--project",type=Path,required=True);q.add_argument("--task",default="")
    sub.add_parser("status");sub.add_parser("recover")
    q=sub.add_parser("submit");q.add_argument("--gate",choices=GATES,required=True);q.add_argument("--report",required=True)
    q=sub.add_parser("approve");q.add_argument("--user-message-file",required=True);q.add_argument("--map-content-sha256")
    q=sub.add_parser("replan");q.add_argument("--gate",choices=["solution","step_plan"],required=True);q.add_argument("--user-message-file",required=True);q.add_argument("--reason",required=True)
    q=sub.add_parser("reject");q.add_argument("--reason",required=True)
    q=sub.add_parser("package-result");q.add_argument("--package",required=True);q.add_argument("--status",choices=["PASS","FAILED","BLOCKED"],required=True);q.add_argument("--evidence",required=True)
    sub.add_parser("verify-start")
    q=sub.add_parser("verdict");q.add_argument("--evidence",required=True)
    q=sub.add_parser("lease-acquire");q.add_argument("--owner",required=True);q.add_argument("--kinds",required=True)
    q=sub.add_parser("lease-release");q.add_argument("--owner",required=True)
    q=sub.add_parser("temp-add");q.add_argument("--path",required=True)
    q=sub.add_parser("cleanup");q.add_argument("--apply",action="store_true")
    q=sub.add_parser("note");q.add_argument("--text",required=True)
    q=sub.add_parser("pause");q.add_argument("--reason",required=True)
    sub.add_parser("resume-phase")
    a=p.parse_args(argv);run=a.run.resolve()
    try:
        if a.command=="init": out=init_run(run,a.project,a.task)
        elif a.command=="status": out=summary(state(run))
        else:
            with locked(run):
                s=state(run);out=None
                if a.command=="recover": atomic(run/"state.json",s);out=summary(s)
                elif a.command=="submit": out=submit(run,s,a.gate,a.report)
                elif a.command=="approve": out=approve(run,s,a.user_message_file,a.map_content_sha256)
                elif a.command=="replan": out=replan(s,a.gate,a.user_message_file,a.reason)
                elif a.command=="reject": reject(s,a.reason)
                elif a.command=="package-result": record_package(run,s,a.package,a.status,a.evidence)
                elif a.command=="verify-start": begin_verification(s)
                elif a.command=="verdict": out=verdict(run,s,a.evidence)
                elif a.command=="lease-acquire": lease(s,a.owner,a.kinds)
                elif a.command=="lease-release": lease(s,a.owner,"",True)
                elif a.command=="temp-add": register_temp(run,s,a.path)
                elif a.command=="cleanup": out=clean_temps(run,s,a.apply)
                elif a.command=="note": s["notes"].append({"at":now(),"text":a.text})
                elif a.command=="pause":
                    if s["phase"] in {"paused","complete"}: raise WorkflowError("Cannot pause this phase.")
                    s["paused_from"]=s["phase"];s["phase"]="paused";s["notes"].append({"at":now(),"pause_reason":a.reason})
                elif a.command=="resume-phase":
                    if s["phase"]!="paused": raise WorkflowError("Run is not paused.")
                    s["phase"]=s.pop("paused_from")
                if a.command!="recover" and not (a.command=="cleanup" and not a.apply):
                    s=commit(run,s,a.command,{"result":out} if out else {})
                if out is None: out=summary(s)
        print(json.dumps(out,ensure_ascii=False,indent=2))
        return 0
    except (WorkflowError,OSError,KeyError,json.JSONDecodeError,TypeError) as e:
        print("HexiPlan: "+str(e),file=sys.stderr);return 2

if __name__=="__main__": raise SystemExit(main())
