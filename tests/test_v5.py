"""V5 structural UI and non-executing tool plan regressions."""
import copy, json, sys, tempfile, unittest
from pathlib import Path
sys.dont_write_bytecode=True
HOME=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(HOME/'tools'))
import render_layout as r
import check_tool_plan as t
import workflow as w

class V5Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='_v5test-',dir=HOME/'runs');self.base=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def doc(self):
  return {'type':'solution','title':'Test','meta':{'run_id':'run','gate':'solution','revision':1,'is_template':False},'sections':[{'title':'One','blocks':[{'type':'text','text':'Evidence.'}]}]}
 def write(self,d):
  p=self.base/'input.json';p.write_text(json.dumps(d));return p
 def plan(self):
  return {'schema_version':1,'plan_id':'tools-v1','tools':[],'budget':{'download_mb':0,'cache_mb':0,'paid_cost':0}}
 def toolplan(self):
  p=self.plan();p['tools']=[{'id':'synthetic-test','kind':'stdio_mcp','source_url':'https://example.org/tool','version':'1.0.0','license':'TEST ONLY','purpose':'Synthetic fixture, never executed','install_argv':['python','--version'],'start_argv':['python','--version'],'allowed_domains':['example.org'],'read_dirs':[],'write_dirs':[],'data_sent':['public query'],'credentials':'none','cost':'none in synthetic fixture','rollback':'none started','telemetry':'off in fixture','external_writes':'none','estimated_download_mb':0,'estimated_cache_mb':0}];return p
 def test_four_distinct_dom_shells(self):
  bodies=[(HOME/'ui/layouts'/f'{x}.html').read_text() for x in r.LAYOUTS];self.assertEqual(len(set(bodies)),4)
 def test_all_structures_same_pale_green(self):
  d=r.prepare(self.doc(),self.base,self.base)
  for x in r.LAYOUTS:self.assertIn('--bg:#f4f7f4',r.html_for(d,x))
 def test_layout_required_and_unknown_rejected(self):
  with self.assertRaises(w.WorkflowError):r.render(self.write(self.doc()),self.base/'out','unknown')
 def test_new_renderer_refuses_overwrite(self):
  p=self.write(self.doc());out=self.base/'out';r.render(p,out,'document')
  with self.assertRaises(w.WorkflowError):r.render(p,out,'workbench')
 def test_layout_presentation_in_approval_hash(self):
  p=self.write(self.doc());a=r.render(p,self.base/'a','document');b=r.render(p,self.base/'b','workbench');self.assertNotEqual(a['content_sha256'],b['content_sha256'])
 def test_no_faux_preview_for_real_gate(self):
  with self.assertRaises(w.WorkflowError):r.render(self.write(self.doc()),self.base/'out','wizard',preview=True)
 def test_data_cannot_inject_html(self):
  d=self.doc();d['title']='</script><script>WRONG()</script>';p=self.write(d);res=r.render(p,self.base/'out','document');text=Path(res['html']).read_text();self.assertNotIn('</script><script>WRONG()',text)
 def test_user_placeholder_cannot_replace_scripts(self):
  d=self.doc();d['sections'][0]['blocks'][0]['text']='/*SCRIPT*/';p=self.write(d);out=r.render(p,self.base/'out','document');text=Path(out['html']).read_text();self.assertIn('"text": "/*SCRIPT*/"',text)
 def test_core_docx_exporter_reused(self):
  d=r.prepare(self.doc(),self.base,self.base)
  for x in r.LAYOUTS:self.assertIn((HOME/'tools/report_assets/report.js').read_text(),r.html_for(d,x))
 def test_original_twelve_content_templates_fit_all_layouts(self):
  for p in (HOME/'templates/json').glob('*.json'):
   d=json.loads(p.read_text());d=r.prepare(d,p.parent,p.parent)
   for x in r.LAYOUTS:self.assertIn('id="report-data"',r.html_for(d,x))
 def test_empty_tools_no_installation(self):
  q=t.validate(self.plan());self.assertEqual(q['tool_count'],0);self.assertFalse(q['commands_executed']);self.assertFalse(q['security_verified'])
 def test_tool_requires_pinned_version(self):
  p=self.toolplan();p['tools'][0]['version']='latest'
  with self.assertRaises(w.WorkflowError):t.validate(p)
 def test_no_wildcard_network_scope(self):
  p=self.toolplan();p['tools'][0]['allowed_domains']=['*']
  with self.assertRaises(w.WorkflowError):t.validate(p)
 def test_credentials_not_in_source_url(self):
  p=self.toolplan();p['tools'][0]['source_url']='https://user:secret@example.org'
  with self.assertRaises(w.WorkflowError):t.validate(p)
 def test_realistic_budget_required(self):
  p=self.toolplan();p['tools'][0]['estimated_download_mb']=2
  with self.assertRaises(w.WorkflowError):t.validate(p)
 def test_cli_never_executes_argv(self):
  p=self.toolplan();p['tools'][0]['start_argv']=['nonexistent-do-not-run','--test'];self.assertFalse(t.validate(p)['commands_executed'])
 def test_no_matching_approval_means_stop(self):
  project=self.base/'project';project.mkdir();run=self.base/'run';w.init_run(run,project)
  with self.assertRaises(w.WorkflowError):t.match_approval(run,self.plan())
 def test_approved_solution_plan_matches_but_tamper_does_not(self):
  project=self.base/'project';project.mkdir();run=self.base/'run';s=w.init_run(run,project);s['phase']='solution';w.commit(run,s,'test-phase')
  d=self.doc();d['tool_plan']=self.plan();out=run/'reports/v1';r.render(self.write(d),out,'document');s=w.state(run);w.submit(run,s,'solution','reports/v1');s=w.commit(run,s,'submit')
  msg=self.base/'message.txt';msg.write_text(w.confirmation(s['pending']));w.approve(run,s,msg);w.commit(run,s,'approve')
  self.assertTrue(t.match_approval(run,self.plan())['recorded_approval_match'])
  (out/'report.html').write_text('Changed')
  with self.assertRaises(w.WorkflowError):t.match_approval(run,self.plan())
 def test_registry_ships_empty(self):
  d=json.loads((HOME/'extensions/approved-tools.json').read_text());self.assertEqual(d['tools'],[])
 def test_palette_not_default_approval(self):
  c=json.loads((HOME/'ui/catalog.json').read_text());self.assertEqual(c['selection_status'],'USER_CHOICE_PENDING')

if __name__=='__main__':unittest.main()
