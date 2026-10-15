"""Offline v4 module-routing and prose-protection regressions."""
from __future__ import annotations
import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.dont_write_bytecode=True
HOME=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(HOME/'tools'))
import route_modules as m
import guard_report as g
import workflow as w

class ModuleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='_module-test-',dir=HOME/'runs')
        self.base=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def ids(self,role,kind,language='zh'): return [x['id'] for x in m.select(role,kind,language)['modules']]
    def report(self):
        return {'type':'academic','title':'FIXED TITLE','subtitle':'记录真实输出。',
                'meta':{'run_id':'TEST','status':'NOT_RUN','revision':1},
                'sections':[{'title':'Results','blocks':[
                    {'type':'text','text':'结果为 p = .05，SYNTHETIC_ONLY。请运行 `x = 1`。'},
                    {'type':'table','columns':['n','M'],'rows':[[24,3.2]],'note':'Note. n = 24。'},
                    {'type':'figure','caption':'图示变化，尚未验证。','source_sha256':'fixed'}]}]}
    def test_catalog_all_eleven_paths_and_hashes(self): self.assertEqual(len(m.catalog()['modules']),11)
    def test_chinese_report_only_two_modules(self): self.assertEqual(self.ids('sol-reporter','report'),['report-style','humanizer-zh'])
    def test_english_excludes_chinese(self): self.assertEqual(self.ids('sol-reporter','report','en'),['report-style','humanizer-en'])
    def test_academic_adds_fidelity_without_extra_citation_pass(self):
        ids=self.ids('sol-reporter','academic-report');self.assertEqual(len(ids),4);self.assertIn('academic-fidelity',ids);self.assertNotIn('citation-management',ids)
    def test_literature_has_shared_citations(self): self.assertIn('citation-management',self.ids('sol-researcher','literature'))
    def test_visualization_preserves_science(self): self.assertEqual(self.ids('luna','visualization'),['academic-fidelity','scientific-visualization'])
    def test_ui_does_not_load_humanizer(self): self.assertEqual(self.ids('luna','ui-implementation'),['frontend-design'])
    def test_debug_is_bounded_single_module(self): self.assertEqual(self.ids('luna','debug'),['systematic-debugging'])
    def test_astra_does_not_load_all_modules(self): self.assertEqual(self.ids('astra','plan'),[])
    def test_astra_cannot_become_reporter(self):
        with self.assertRaises(w.WorkflowError):m.select('astra','report')
    def test_normal_implementation_has_no_extra_modules(self):self.assertEqual(self.ids('luna','implementation'),[])
    def test_unknown_module_task_rejected(self):
        with self.assertRaises(w.WorkflowError):m.select('luna','everything')
    def test_stop_slop_reference_not_active(self):self.assertNotIn('stop-slop',[x['id'] for x in m.catalog()['modules']])
    def test_catalog_rejects_changed_local_module(self):
        (self.base/'modules').mkdir();(self.base/'modules/a.md').write_text('actual')
        d={'explicit_hexiplan_only':True,'register_as_skill':False,'modules':[{'id':'a','path':'modules/a.md','sha256':'0'*64}]}
        (self.base/'modules/catalog.json').write_text(json.dumps(d))
        with self.assertRaises(w.WorkflowError):m.catalog(self.base)
    def test_selection_record_keeps_phase_and_approval(self):
        project=self.base/'project';project.mkdir();run=self.base/'run';s=w.init_run(run,project)
        selected=m.select('sol-reporter','report');r=m.record_selection(run,selected,'test-reporter')
        after=w.state(run);self.assertEqual(after['phase'],s['phase']);self.assertEqual(after['approvals'],[])
        for mod in r['modules']:self.assertEqual(hashlib.sha256((run/mod['snapshot']).read_bytes()).hexdigest(),mod['sha256'])
        self.assertIn('test-reporter',w.summary(after)['module_selections'])
    def test_selection_refuses_uninitialized_directory(self):
        with self.assertRaises(w.WorkflowError):m.record_selection(self.base,m.select('sol-reporter','report'),'test')
    def test_selection_refuses_arbitrary_file_override(self):
        project=self.base/'project';project.mkdir();run=self.base/'run';w.init_run(run,project)
        s=m.select('sol-reporter','report');s['modules'][0]['path']='README.md'
        with self.assertRaises(w.WorkflowError):m.record_selection(run,s,'test')
    def test_second_record_reuses_immutable_snapshots(self):
        project=self.base/'project';project.mkdir();run=self.base/'run';w.init_run(run,project)
        s=m.select('sol-reporter','report');m.record_selection(run,s,'test');m.record_selection(run,s,'test')
        self.assertEqual(len(list((run/'references/module-snapshots').glob('*.md'))),2)
    def test_plain_prose_edit_allowed(self):
        a=self.report();b=copy.deepcopy(a);b['subtitle']='这里记录真实输出。'
        self.assertTrue(g.check(a,b)['mechanical_pass'])
    def test_numeric_change_rejected(self):
        a=self.report();b=copy.deepcopy(a);b['sections'][0]['blocks'][0]['text']=b['sections'][0]['blocks'][0]['text'].replace('.05','.01')
        self.assertFalse(g.check(a,b)['mechanical_pass'])
    def test_apa_leading_decimal_is_protected(self):self.assertEqual(g.NUMBER.findall('p = .05; p = .001'),['.05','.001'])
    def test_scientific_notation_and_negative_protected(self):self.assertEqual(g.NUMBER.findall('x = -3.2e-4; y = 5%'),['-3.2e-4','5%'])
    def test_synthetic_status_change_rejected(self):
        a=self.report();b=copy.deepcopy(a);b['sections'][0]['blocks'][0]['text']=b['sections'][0]['blocks'][0]['text'].replace('SYNTHETIC_ONLY','REAL')
        self.assertFalse(g.check(a,b)['mechanical_pass'])
    def test_table_change_rejected(self):
        a=self.report();b=copy.deepcopy(a);b['sections'][0]['blocks'][1]['rows'][0][1]=3.3
        self.assertFalse(g.check(a,b)['mechanical_pass'])
    def test_title_change_rejected(self):
        a=self.report();b=copy.deepcopy(a);b['title']='Other'
        self.assertFalse(g.check(a,b)['mechanical_pass'])
    def test_metadata_change_rejected(self):
        a=self.report();b=copy.deepcopy(a);b['meta']['status']='PASS'
        self.assertFalse(g.check(a,b)['mechanical_pass'])
    def test_code_change_rejected(self):
        a=self.report();b=copy.deepcopy(a);b['sections'][0]['blocks'][0]['text']=b['sections'][0]['blocks'][0]['text'].replace('`x = 1`','`y = 1`')
        self.assertFalse(g.check(a,b)['mechanical_pass'])
    def test_url_change_rejected(self):
        a=self.report();a['subtitle']='来源 https://example.org/a';b=copy.deepcopy(a);b['subtitle']='来源 https://example.org/b'
        self.assertFalse(g.check(a,b)['mechanical_pass'])
    def test_paths_change_rejected(self):
        a=self.report();a['subtitle']=r'保存在 F:\data\before.txt';b=copy.deepcopy(a);b['subtitle']=r'保存在 F:\data\after.txt'
        self.assertFalse(g.check(a,b)['mechanical_pass'])
    def test_added_section_rejected(self):
        a=self.report();b=copy.deepcopy(a);b['sections'].append({'title':'Extra','blocks':[]})
        self.assertFalse(g.check(a,b)['mechanical_pass'])
    def test_unmodified_pass_does_not_claim_semantic_verification(self):
        a=self.report();v=g.check(a,a);self.assertTrue(v['mechanical_pass']);self.assertFalse(v['semantic_equivalence_verified']);self.assertIsNone(v['ai_authorship_detected'])
    def test_original_rendering_assets_byte_preserved(self):
        frozen=json.loads((HOME/'tests/preserved-v3-assets.json').read_text())
        for rel,expected in frozen.items():self.assertEqual(hashlib.sha256((HOME/rel).read_bytes()).hexdigest(),expected,rel)
    def test_all_sources_have_license_files(self):
        self.assertEqual(len(list((HOME/'third_party/licenses').glob('*.txt'))),5)
        self.assertEqual(len(json.loads((HOME/'third_party/SOURCES.json').read_text())['sources']),9)
    def test_no_global_registration_directories(self):
        self.assertFalse((HOME/'.agents').exists());self.assertFalse((HOME/'.codex').exists());self.assertFalse((HOME/'AGENTS.md').exists())
    def test_limits_stay_user_selected(self):self.assertEqual(w.LIMITS,{'sol':3,'luna':6,'browser':2,'high_memory':1})

if __name__=='__main__':unittest.main(verbosity=2)
