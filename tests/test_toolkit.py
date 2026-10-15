"""Offline regression tests; all temporary files stay in HOME/runs and are removed."""
from __future__ import annotations
import base64,copy,csv,hashlib,json,math,os,statistics,sys,tempfile,unittest
from pathlib import Path
sys.dont_write_bytecode=True
HOME=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(HOME/'tools'))
import workflow as w
import render_report as r
import generate_fixture as f
import launch

class ToolkitTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='_selftest-',dir=HOME/'runs')
        self.base=Path(self.temp.name);self.project=self.base/'project';self.project.mkdir()
        self.run=self.base/'run-test';self.s=w.init_run(self.run,self.project,'Local software test, not a real project')
        self.counter=0
    def tearDown(self):self.temp.cleanup()
    def doc(self,gate,**changes):
        step=w.current_step(self.s) if gate in {'step_plan','step_acceptance'} else ''
        version=self.s['gate_versions'].get(gate+':'+step,0)+1
        d={'type':'acceptance' if gate=='step_acceptance' else gate,'title':'TEST ONLY',
           'meta':{'run_id':self.run.name,'gate':gate,'step':step,'revision':version,'is_template':False},
           'sections':[{'title':'Test section','blocks':[{'type':'text','text':'Evidence fixture, not user approval.'}]}]}
        if gate=='roadmap':d['roadmap_steps']=[{'id':'S1','title':'Test step','dependencies':[]},{'id':'S2','title':'Second test step','dependencies':['S1']}]
        if gate=='step_plan':d['work_packages']=[{'id':'P1','title':'Test package','dependencies':[]}]
        d.update(changes);return d
    def render(self,d):
        self.counter+=1;p=self.run/'plans'/f'test-{self.counter}.json';p.write_text(json.dumps(d),encoding='utf-8')
        out=self.run/'reports'/f'test-{self.counter}';r.render(p,out,self.run);return out
    def submit(self,gate,**changes):
        out=self.render(self.doc(gate,**changes));w.submit(self.run,self.s,gate,out.relative_to(self.run).as_posix());return out
    def approve(self):
        p=self.run/'approvals'/'actual-test-message.txt';p.write_text(w.confirmation(self.s['pending']),encoding='utf-8')
        return w.approve(self.run,self.s,p)
    def gate(self,gate):self.submit(gate);self.approve()
    def execute_ready(self):
        for gate in ['requirements','solution','roadmap','step_plan']:self.gate(gate)
    def evidence(self,name='local.txt',text='Actual local test fixture'):
        p=self.run/'evidence'/name;p.write_text(text,encoding='utf-8');return p.relative_to(self.run).as_posix()
    def pass_package(self):w.record_package(self.run,self.s,'P1','PASS',self.evidence())
    def verdict(self,overall='PASS',status='PASS',required=True):
        data={'overall':overall,'independent_reviewer':'test-only-sol','criteria':[{'id':'T','status':status,'required':required,'evidence':'actual fixture check'}]}
        rel=self.evidence('verification.json',json.dumps(data));return w.verdict(self.run,self.s,rel)
    def report_ready(self):
        self.execute_ready();self.pass_package();w.begin_verification(self.s);self.verdict()

    def test_full_two_step_lifecycle(self):
        self.report_ready();w.clean_temps(self.run,self.s,True);self.gate('step_acceptance')
        self.assertEqual(self.s['phase'],'step_plan');self.assertEqual(w.current_step(self.s),'S2')
        self.gate('step_plan');self.pass_package();w.begin_verification(self.s);self.verdict();w.clean_temps(self.run,self.s,True);self.gate('step_acceptance')
        self.assertEqual(self.s['phase'],'complete');self.assertEqual(len(self.s['approvals']),7)
    def test_no_gate_skipping(self):
        out=self.render(self.doc('solution'))
        with self.assertRaises(w.WorkflowError):w.submit(self.run,self.s,'solution',out.relative_to(self.run).as_posix())
    def test_no_execution_before_approval(self):
        with self.assertRaises(w.WorkflowError):w.record_package(self.run,self.s,'P1','PASS',self.evidence())
    def test_templates_cannot_be_approved(self):
        d=self.doc('requirements');d['meta']['is_template']=True;out=self.render(d)
        with self.assertRaises(w.WorkflowError):w.submit(self.run,self.s,'requirements',out.relative_to(self.run).as_posix())
    def test_approval_version_must_match(self):
        d=self.doc('requirements');d['meta']['revision']=2;out=self.render(d)
        with self.assertRaises(w.WorkflowError):w.submit(self.run,self.s,'requirements',out.relative_to(self.run).as_posix())
    def test_report_run_must_match(self):
        d=self.doc('requirements');d['meta']['run_id']='other';out=self.render(d)
        with self.assertRaises(w.WorkflowError):w.submit(self.run,self.s,'requirements',out.relative_to(self.run).as_posix())
    def test_blocking_questions_prevent_submit(self):
        with self.assertRaises(w.WorkflowError):self.submit('requirements',blocking_questions=['Unanswered test question'])
    def test_approval_needs_user_text(self):
        self.submit('requirements');p=self.run/'approvals'/'bad.txt';p.write_text('not a user approval',encoding='utf-8')
        with self.assertRaises(w.WorkflowError):w.approve(self.run,self.s,p)
    def test_explicit_natural_mapping_bound_to_hash(self):
        self.submit('requirements');p=self.run/'approvals'/'message.txt';p.write_text('TEST FIXTURE: approve this requirement version',encoding='utf-8')
        with self.assertRaises(w.WorkflowError):w.approve(self.run,self.s,p,'stale_hash')
        w.approve(self.run,self.s,p,self.s['pending']['content_sha256'])
        self.assertEqual(self.s['approvals'][0]['approval_mode'],'explicit_conversation_mapping')
    def test_submitted_html_mutation_rejected(self):
        out=self.submit('requirements');(out/'report.html').write_text('changed',encoding='utf-8')
        with self.assertRaises(w.WorkflowError):self.approve()
    def test_json_hash_tamper_rejected(self):
        out=self.render(self.doc('requirements'));d=w.load(out/'report.json');d['title']='tampered';w.atomic(out/'report.json',d)
        with self.assertRaises(w.WorkflowError):w.submit(self.run,self.s,'requirements',out.relative_to(self.run).as_posix())
    def test_reject_requires_new_version(self):
        self.submit('requirements');w.reject(self.s,'test requested revision');self.submit('requirements');self.assertEqual(self.s['pending']['revision'],2)
    def test_roadmap_dependencies_validated(self):
        self.gate('requirements');self.gate('solution')
        with self.assertRaises(w.WorkflowError):self.submit('roadmap',roadmap_steps=[{'id':'S1','title':'T','dependencies':['missing']}])
    def test_verification_waits_for_all_packages(self):
        self.execute_ready()
        with self.assertRaises(w.WorkflowError):w.begin_verification(self.s)
    def test_unrun_required_check_cannot_pass(self):
        self.execute_ready();self.pass_package();w.begin_verification(self.s)
        with self.assertRaises(w.WorkflowError):self.verdict('PASS','NOT_RUN')
    def test_two_repairs_then_block(self):
        self.execute_ready();self.pass_package();w.begin_verification(self.s);self.verdict('FAIL','FAIL')
        self.assertEqual(self.s['repair_rounds'],1)
        w.begin_verification(self.s);self.verdict('FAIL','FAIL');self.assertEqual(self.s['repair_rounds'],2)
        w.begin_verification(self.s);self.verdict('FAIL','FAIL');self.assertEqual(self.s['phase'],'blocked')
        with self.assertRaises(w.WorkflowError):w.begin_verification(self.s)
    def test_replan_does_not_approve_or_reset_retries(self):
        self.execute_ready();self.s['phase']='blocked';self.s['repair_rounds']=2
        p=self.run/'approvals'/'replan.txt';p.write_text('TEST USER INSTRUCTION: replan this step',encoding='utf-8')
        w.replan(self.s,'step_plan',p,'Changed approach requested')
        self.assertEqual(self.s['phase'],'step_plan');self.assertEqual(self.s['repair_rounds'],2)
        with self.assertRaises(w.WorkflowError):w.record_package(self.run,self.s,'P1','PASS',self.evidence())
    def test_acceptance_requires_cleanup_record(self):
        self.report_ready()
        with self.assertRaises(w.WorkflowError):self.submit('step_acceptance')
    def test_sol_budget_is_shared(self):
        for i in range(3):w.lease(self.s,f'sol-{i}','sol')
        with self.assertRaises(w.WorkflowError):w.lease(self.s,'reporter','sol')
        w.lease(self.s,'sol-0','',True);w.lease(self.s,'reporter','sol')
    def test_luna_ceiling_six(self):
        for i in range(6):w.lease(self.s,f'luna-{i}','luna')
        with self.assertRaises(w.WorkflowError):w.lease(self.s,'luna-7','luna')
    def test_browser_and_memory_caps(self):
        w.lease(self.s,'b1','browser');w.lease(self.s,'b2','browser')
        with self.assertRaises(w.WorkflowError):w.lease(self.s,'b3','browser')
        w.lease(self.s,'m1','high_memory')
        with self.assertRaises(w.WorkflowError):w.lease(self.s,'m2','high_memory')
    def test_agent_cannot_use_both_model_pools(self):
        with self.assertRaises(w.WorkflowError):w.lease(self.s,'both','sol,luna')
    def test_incremental_pool_switch_is_rejected(self):
        w.lease(self.s,"one-agent","sol")
        with self.assertRaises(w.WorkflowError):w.lease(self.s,"one-agent","luna")
    def test_snapshot_recovery(self):
        self.s['notes'].append({'test':'recoverable'});self.s=w.commit(self.run,self.s,'test')
        (self.run/'state.json').write_text('damaged',encoding='utf-8')
        recovered=w.state(self.run);self.assertEqual(recovered['notes'][-1]['test'],'recoverable')
    def test_corrupt_committed_journal_fails(self):
        event=self.run/'journal'/'00000001.json';d=w.load(event);d['state']['phase']='execution';w.atomic(event,d)
        with self.assertRaises(w.WorkflowError):w.state(self.run)
    def test_existing_run_never_overwritten(self):
        with self.assertRaises(w.WorkflowError):w.init_run(self.run,self.project)
    def test_path_traversal_rejected(self):
        with self.assertRaises(w.WorkflowError):w.safe_path(self.run,'../project')
        with self.assertRaises(w.WorkflowError):w.safe_path(self.run,str(self.project.resolve()))
    def test_symlink_rejected(self):
        link=self.run/'tmp'/'link'
        try:link.symlink_to(self.project,target_is_directory=True)
        except (OSError,NotImplementedError):self.skipTest('Symlink creation not permitted by local platform')
        with self.assertRaises(w.WorkflowError):w.safe_path(self.run,'tmp/link')
    def test_safe_cleanup_preserves_unregistered_changed_referenced(self):
        self.report_ready()
        for name in ['delete','unregistered','changed','referenced']:(self.run/'tmp'/name).write_text('abc',encoding='utf-8')
        for name in ['delete','changed','referenced']:w.register_temp(self.run,self.s,'tmp/'+name)
        (self.run/'tmp'/'changed').write_text('xyz',encoding='utf-8');self.evidence('references.txt','Retain tmp/referenced')
        dry=w.clean_temps(self.run,self.s);self.assertEqual(len(dry['candidates']),1);self.assertTrue((self.run/'tmp/delete').exists())
        done=w.clean_temps(self.run,self.s,True);self.assertEqual(done['freed_bytes'],3)
        self.assertFalse((self.run/'tmp/delete').exists())
        for name in ['unregistered','changed','referenced']:self.assertTrue((self.run/'tmp'/name).exists())
    def test_cleanup_outside_report_refused(self):
        with self.assertRaises(w.WorkflowError):w.clean_temps(self.run,self.s,True)
    def test_register_temp_outside_tmp_refused(self):
        with self.assertRaises(w.WorkflowError):w.register_temp(self.run,self.s,self.evidence())
    def test_renderer_never_overwrites(self):
        out=self.render(self.doc('requirements'))
        with self.assertRaises(w.WorkflowError):r.render(self.run/'plans/test-1.json',out,self.run)
    def test_script_payload_is_escaped(self):
        d=self.doc('requirements');d['title']='</script><script>window.BAD=1</script>'
        html=r.html_for(r.prepare(d,self.run,self.run));self.assertNotIn('</script><script>window.BAD',html)
    def test_bad_table_width_rejected(self):
        d=self.doc('requirements');d['sections'][0]['blocks']=[{'type':'table','columns':['A','B'],'rows':[['one']]}]
        with self.assertRaises(w.WorkflowError):r.prepare(d,self.run,self.run)
    def test_unsafe_image_rejected(self):
        d=self.doc('requirements');d['sections'][0]['blocks']=[{'type':'figure','data_uri':'data:text/html;base64,PHNjcmlwdD4='}]
        with self.assertRaises(w.WorkflowError):r.prepare(d,self.run,self.run)
    def test_image_escape_rejected(self):
        d=self.doc('requirements');d['sections'][0]['blocks']=[{'type':'figure','src':'../project/x.png'}]
        with self.assertRaises(w.WorkflowError):r.prepare(d,self.run,self.run)
    def test_actual_synthetic_table_known_answers(self):
        out=self.run/'fixtures/t';m=f.generate(out,'tabular')
        with (out/m['file']).open() as fp:values=[float(x['known_value']) for x in csv.DictReader(fp)]
        self.assertEqual(statistics.mean(values),m['expected']['known_value_mean'])
        self.assertAlmostEqual(statistics.variance(values),m['expected']['known_value_sample_variance'])
        self.assertEqual(m['source_type'],'SYNTHETIC_ONLY')
    def test_actual_synthetic_signal_known_answers(self):
        out=self.run/'fixtures/s';m=f.generate(out,'timeseries')
        with (out/m['file']).open() as fp:values=[float(x['clean_sine']) for x in csv.DictReader(fp)]
        self.assertAlmostEqual(sum(values)/len(values),0,places=12)
        self.assertAlmostEqual(math.sqrt(sum(x*x for x in values)/len(values)),m['expected']['clean_rms'],places=12)
    def test_launcher_scope_and_models(self):
        roles=launch.role_settings();args=launch.arguments(self.project,self.run,roles)
        self.assertIn('gpt-6-astra',args);self.assertIn('agents.max_concurrent_threads_per_session=9',args)
        self.assertNotIn('--yolo',args);self.assertNotIn('features',args)
        actual={x['name']:(x['model'],x['effort']) for x in roles}
        self.assertEqual(actual['hexiplan_luna'],('gpt-6-luna','max'))
        self.assertEqual(actual['hexiplan_architect'],('gpt-6-astra','high'))
        self.assertEqual(actual['hexiplan_sol_manager'],('gpt-5.6-sol','high'))
    def test_all_twelve_templates_parse(self):
        files=list((HOME/'templates/json').glob('*.json'));self.assertEqual(len(files),12)
        for p in files:
            d=json.loads(p.read_text(encoding='utf-8'));result=r.prepare(d,p.parent,p.parent)
            self.assertTrue(result['meta']['is_template']);self.assertIn('content_sha256',result)

if __name__=='__main__':unittest.main(verbosity=2)
