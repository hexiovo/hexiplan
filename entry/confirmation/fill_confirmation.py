"""Fill HexiPlan's fixed confirmation sections; reuse bundled HTML/CSS/JS and feedback."""
from __future__ import annotations
import argparse, copy, json, sys, tempfile
from pathlib import Path
sys.dont_write_bytecode = True
HOME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HOME / "tools"))
from render_report import prepare, render as render_compatible
from render_layout import render as render_layout
from workflow import WorkflowError, validate_items, identifier
SCHEMA = "hexiplan.confirmation-content/1"
GATE_TYPES = {"requirements":"requirements", "solution":"solution", "roadmap":"roadmap", "step_plan":"step_plan", "step_acceptance":"acceptance"}

def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError(label + " must be nonempty text")
    return value

def obj(value, label):
    if not isinstance(value, dict): raise WorkflowError(label + " must be an object")
    return value

def items(value, label):
    if not isinstance(value, list): raise WorkflowError(label + " must be a list")
    return value

def table_rows(source, fields, label):
    return [[text(obj(x,label).get(k), label+"."+k) for k in fields] for x in items(source,label)]

def build(content):
    c = obj(content,"content")
    if c.get("schema") != SCHEMA: raise WorkflowError("Unsupported confirmation content schema")
    cfg = obj(c.get("report"),"report")
    meta = copy.deepcopy(obj(cfg.get("meta"),"report.meta"))
    if not isinstance(meta.get("is_template"),bool): raise WorkflowError("Explicit is_template true/false required")
    kind = cfg.get("type"); gate = meta.get("gate")
    if kind != GATE_TYPES.get(gate): raise WorkflowError("Report type does not match the confirmation gate")
    if not isinstance(meta.get("revision"),int) or isinstance(meta["revision"],bool) or meta["revision"] < 1:
        raise WorkflowError("Positive report revision required")
    if not meta["is_template"]:
        identifier(text(meta.get("run_id"),"run_id"))
        if meta["run_id"] == "TEMPLATE": raise WorkflowError("Real report requires a real run ID")
        if meta.get("status") != "DRAFT": raise WorkflowError("New confirmation report must be DRAFT")
        if meta.get("source_type") == "TEMPLATE": raise WorkflowError("Real report cannot use TEMPLATE source")
        if gate in {"step_plan","step_acceptance"}: identifier(text(meta.get("step"),"step"))
        elif meta.get("step","") != "": raise WorkflowError("This gate must not name an implementation step")
    changes = table_rows(c.get("changes"),["part","before","after","reason","impact"],"changes")
    if not changes: raise WorkflowError("At least one explained change is required")
    flow = table_rows(c.get("workflow"),["step","action","output","change"],"workflow")
    if not flow: raise WorkflowError("A concrete processing/implementation flow is required")
    sections = [
        {"title":"1. 准备改哪些部分", "blocks":[
            {"type":"text", "text":text(c.get("goal"),"goal")},
            {"type":"callout", "title":"与上版相比", "text":text(c.get("version_changes"),"version_changes"),"level":"info"},
            {"type":"table","columns":["改哪里","现在怎样","准备改成什么","为什么改","有什么影响"],"rows":changes}]},
        {"title":"2. 具体流程，以及哪里有改动", "blocks":[
            {"type":"table","columns":["处理环节","具体做什么","得到什么","沿用 / 改动 / 新增"],"rows":flow}]}]
    dp = obj(c.get("data_processing"),"data_processing")
    if not isinstance(dp.get("applicable"),bool): raise WorkflowError("data_processing.applicable must be boolean")
    if dp["applicable"]:
        methods = table_rows(dp.get("methods"),["method","purpose","parameters","change","impact"],"data_processing.methods")
        if not methods: raise WorkflowError("Applicable data processing requires methods and settings")
        sections.append({"title":"3. 数据怎么处理：方法、参数与影响","blocks":[
            {"type":"kv","items":[{"label":"使用哪些数据","value":text(dp.get("data_range"),"data_range")},
                                   {"label":"缺失与异常怎么处理","value":text(dp.get("missing_and_outliers"),"missing_and_outliers")} ]},
            {"type":"table","columns":["方法","它做什么、为什么需要","参数或规则","这次改哪里","对结果的影响"],"rows":methods}]})
    else:
        sections.append({"title":"3. 数据处理","blocks":[{"type":"text","text":text(dp.get("reason"),"data_processing.reason")} ]})
    decisions = table_rows(c.get("decisions"),["question","recommendation","alternatives","impact"],"decisions")
    sections.append({"title":"4. 需要你决定什么","blocks":[
        {"type":"table","columns":["要决定的事项","推荐做法与理由","有意义的其他选择","区别和影响"],"rows":decisions}
        if decisions else {"type":"text","text":"没有另外需要选择的事项，请确认下面列明的本次范围。"}]})
    conf = obj(c.get("confirmation"),"confirmation")
    sections.append({"title":"5. 你确认之后，下一步做什么","blocks":[
        {"type":"kv","items":[{"label":"这次请你确认的范围","value":text(conf.get("scope"),"confirmation.scope")},
                                 {"label":"同意后具体做什么","value":text(conf.get("next_action"),"confirmation.next_action")},
                                 {"label":"下次什么时候请你确认","value":text(conf.get("next_confirmation"),"confirmation.next_confirmation")} ]},
        {"type":"callout","title":"请确认本次范围","text":"请告诉我是否同意上面的内容，或指出要调整的部分。你的确认只覆盖本版本列明的范围。填写或导出意见不会自动批准。","level":"info"}]})
    results = obj(c.get("results",{"applicable":False}),"results")
    if not isinstance(results.get("applicable"),bool): raise WorkflowError("results.applicable must be boolean")
    if gate == "step_acceptance" and not results["applicable"]:
        raise WorkflowError("Acceptance must state actual completed work and limitations")
    if results["applicable"]:
        rows = table_rows(results.get("items"),["part","completed","evidence","remaining"],"results.items")
        if not rows: raise WorkflowError("Actual result items required")
        sections.append({"title":"6. 实际完成情况与限制","blocks":[
            {"type":"table","columns":["部分","实际完成了什么","结果或证据","未完成 / 限制"],"rows":rows},
            {"type":"text","text":text(results.get("limitations"),"results.limitations")} ]})
    extras = items(c.get("supporting_blocks",[]),"supporting_blocks")
    if extras: sections.append({"title":"补充材料（需要时再看）","blocks":copy.deepcopy(extras)})
    machine = copy.deepcopy(obj(c.get("workflow_fields",{}),"workflow_fields"))
    reserved = {"schema_version","type","title","subtitle","meta","sections","content_sha256","presentation"}
    if reserved.intersection(machine): raise WorkflowError("workflow_fields cannot replace page structure or identity")
    d = {**machine,"schema_version":1,"type":kind,"title":text(cfg.get("title"),"report.title"),
         "subtitle":text(cfg.get("subtitle"),"report.subtitle"),"meta":meta,"sections":sections}
    d.setdefault("blocking_questions",[])
    if not meta["is_template"]:
        def placeholders(v):
            if isinstance(v,str): return "待填写" in v
            if isinstance(v,list): return any(placeholders(x) for x in v)
            if isinstance(v,dict): return any(placeholders(x) for x in v.values())
            return False
        if placeholders(d): raise WorkflowError("Replace all template placeholders before a real confirmation")
        if gate == "roadmap": validate_items(d.get("roadmap_steps"),"roadmap_steps")
        if gate == "step_plan": validate_items(d.get("work_packages"),"work_packages")
    return d

def destination(out, meta):
    resolved = out.resolve()
    if out.exists(): raise WorkflowError("Output exists: use a new report version, never overwrite")
    if not resolved.is_relative_to(HOME): raise WorkflowError("Reports must stay inside HexiPlan")
    for p in [out,*out.parents]:
        try:
            attributes = p.lstat()
        except FileNotFoundError:
            continue
        if p.is_symlink() or (getattr(attributes, "st_file_attributes", 0) & 0x400):
            raise WorkflowError("Link/junction/reparse output path rejected")
    if not meta["is_template"]:
        root = HOME / "runs" / meta["run_id"]
        if not (root / "state.json").is_file(): raise WorkflowError("Real confirmation requires an existing initialized run")
        if not resolved.is_relative_to(root / "reports"): raise WorkflowError("Real report must be under its RUN/reports")
        return root / "tmp"
    return HOME / "entry" / "confirmation" / "_temp"

def render(content_file, out, layout=None, asset_root=None):
    c = json.loads(content_file.read_text(encoding="utf-8-sig"))
    d = build(c)
    temp_root = destination(out,d["meta"])
    d = prepare(d,content_file.parent,asset_root or content_file.parent)
    temp_root.mkdir(parents=True,exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="confirmation-",dir=temp_root) as tmp:
            source = Path(tmp)/"report-source.json"
            source.write_text(json.dumps(d,ensure_ascii=False,allow_nan=False),encoding="utf-8")
            result = (render_layout(source,out,layout) if layout else render_compatible(source,out))
        (out/"confirmation-content.json").write_text(json.dumps(c,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    finally:
        if temp_root.name == "_temp" and temp_root.exists() and not any(temp_root.iterdir()): temp_root.rmdir()
    result.update({"frame":"hexiplan-readable-confirmation/1","page_code_rewritten":False,"workflow_advanced":False})
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    p.add_argument("--layout",choices=["workbench","document","wizard","evidence"])
    p.add_argument("--asset-root",type=Path)
    a = p.parse_args()
    try:
        print(json.dumps(render(a.data,a.out,a.layout,a.asset_root),ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError) as e:
        print("HexiPlan confirmation: "+str(e),file=sys.stderr);return 2
if __name__ == "__main__": sys.exit(main())
