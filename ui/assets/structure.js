
/* Structural presentation layer. It neither starts tools nor approves tasks. */
(function(){
'use strict';
const $=id=>document.getElementById(id), data=JSON.parse($('report-data').textContent),
 layout=document.body.dataset.layout,sections=[...document.querySelectorAll('#sections>.section')],
 anchors=[...document.querySelectorAll('#toc a')];
let current=0; const query=()=>($('search').value||'').trim().toLowerCase();
const notice=t=>{const n=$('toast');n.textContent=t;n.classList.remove('hidden');setTimeout(()=>n.classList.add('hidden'),4000);};
async function copy(t){try{await navigator.clipboard.writeText(t);notice('已复制，请粘贴回 Codex。');}catch(e){const x=document.createElement('textarea');x.value=t;document.body.appendChild(x);x.select();const ok=document.execCommand('copy');x.remove();notice(ok?'已复制，请粘贴回 Codex。':'浏览器未允许复制，请手动复制。');}}
function active(i){current=Math.max(0,Math.min(sections.length-1,i));
 anchors.forEach((a,n)=>{a.classList.toggle('active',n===current);if(n===current)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
 document.querySelectorAll('[data-section]').forEach(a=>{const yes=Number(a.dataset.section)===current;a.classList.toggle('active',yes);a.setAttribute('aria-selected',String(yes));});
 if(layout==='workbench'||layout==='wizard')sections.forEach((s,n)=>{s.hidden=query()?!s.textContent.toLowerCase().includes(query()):n!==current;});
 if($('read-position'))$('read-position').textContent=(current+1)+' / '+sections.length+'　仅切换阅读内容，不批准任务';
 if($('step-prev'))$('step-prev').disabled=current===0;if($('step-next'))$('step-next').disabled=current===sections.length-1;
 if($('wizard-fill'))$('wizard-fill').style.width=((current+1)/Math.max(1,sections.length)*100)+'%';
}
anchors.forEach((a,i)=>a.addEventListener('click',e=>{e.preventDefault();$('search').value='';if(layout==='document'){sections.forEach(s=>s.hidden=false);sections[i].scrollIntoView({behavior:'smooth',block:'start'});active(i);}else if(layout==='evidence'){showFull(true);sections.forEach(s=>s.hidden=false);sections[i].scrollIntoView({behavior:'smooth',block:'start'});active(i);}else {active(i);if(window.innerWidth<650)$('sections').scrollIntoView({behavior:'smooth',block:'start'});}}));
if($('section-tabs')){sections.forEach((s,i)=>{const b=document.createElement('button');b.textContent=data.sections[i].short_title||data.sections[i].title;b.dataset.section=i;b.setAttribute('role','tab');b.onclick=()=>{$('search').value='';active(i);};$('section-tabs').appendChild(b);});}
if($('step-prev'))$('step-prev').onclick=()=>{$('search').value='';active(current-1);};
if($('step-next'))$('step-next').onclick=()=>{$('search').value='';active(current+1);};
$('search').addEventListener('input',()=>{if(layout==='evidence'&&query())showFull(true);if(!query())active(current);});
const snapshots=[];for(const s of data.sections||[])for(const b of s.blocks||[]){if(b.type==='gallery')snapshots.push(...b.images||[]);if(b.type==='figure'&&b.data_uri)snapshots.push(b);}
function showFull(on){if($('full-content'))$('full-content').hidden=!on;if($('evidence-view'))$('evidence-view').hidden=on;if($('view-mode'))$('view-mode').textContent=on?'回到截图审阅':'阅读完整报告';}
if(layout==='evidence'){
 const usable=snapshots.filter(x=>/^data:image\/(png|jpeg);base64,/.test(x.data_uri||''));
 let picture=0;
 const paint=i=>{picture=i;const im=usable[i];if(!im)return;$('stage-image').src=im.data_uri;$('stage-image').alt=im.alt||im.title||'截图';$('stage-title').textContent=im.title||'截图';$('stage-caption').textContent=[im.label,im.caption,im.captured_at].filter(Boolean).join(' · ');document.querySelectorAll('.asset-item').forEach((x,n)=>x.classList.toggle('active',n===i));};
 usable.forEach((im,i)=>{const b=document.createElement('button');b.className='asset-item';b.setAttribute('aria-label','查看 '+(im.title||'截图'));const image=document.createElement('img');image.src=im.data_uri;image.alt=im.alt||im.title||'截图';const t=document.createElement('span');t.textContent=String(i+1).padStart(2,'0')+'　'+(im.title||'截图');b.append(image,t);b.onclick=()=>{showFull(false);paint(i);};$('asset-list').appendChild(b);});
 if(usable.length){paint(0);$('asset-count').textContent=usable.length+' 份截图';}
 else{$('asset-count').textContent='暂无截图';$('evidence-view').hidden=true;$('full-content').hidden=false;$('view-mode').disabled=true;}
 $('stage-enlarge').onclick=()=>{const im=usable[picture];if(!im)return;$('dialog-title').textContent=im.title||'截图';$('dialog-images').className='dialog-images';$('dialog-images').replaceChildren();const image=document.createElement('img');image.src=im.data_uri;image.alt=im.alt||im.title||'截图';$('dialog-images').appendChild(image);$('lightbox').showModal();};
 $('view-mode').onclick=()=>showFull($('full-content').hidden);
 $('compare-open').onclick=()=>{showFull(true);const g=document.querySelector('.gallery');if(g)g.closest('.section').scrollIntoView({behavior:'smooth'});else notice('本报告尚无可对比截图。');};
 const check=document.querySelector('#sections .checklist');if(check)$('aux-checks').appendChild(check.cloneNode(true));else $('aux-checks').textContent='完整验证结果见报告正文。';
 const log=document.querySelector('#sections .code');if(log)$('aux-logs').appendChild(log.cloneNode(true));else $('aux-logs').textContent='本报告未包含运行日志。';
 document.querySelectorAll('[data-aux]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-aux]').forEach(x=>x.classList.toggle('active',x===b));['checks','logs'].forEach(id=>$('aux-'+id).hidden=id!==b.dataset.aux);});
}
// Preview reports get an explicit NOT_SUBMITTED notes panel, never a real gate token.
if(!$('approval').children.length&&data.meta?.is_template){
 const box=document.createElement('section');box.className='review-panel';box.innerHTML='<div class="subheading"><span class="status-dot"></span>布局样例 · 非业务验收</div><h2>需要你决定的事</h2><p>这套结构是否方便你读方案、查看截图和给出意见？样例中的项目与状态仅用于布局演示。</p><label for="preview-notes">你的意见</label><textarea id="preview-notes" placeholder="例如：保留右侧确认区，正文更宽一些……"></textarea><button class="primary" id="copy-layout-feedback">复制布局意见</button><details><summary>这不是批准按钮</summary><p>只复制文字，不连接 Codex、不改任务状态、不安装工具。</p></details>';
 $('approval').appendChild(box);
 const key='hexiplan-layout-preview:'+layout;try{$('preview-notes').value=localStorage.getItem(key)||'';}catch(e){}
 $('preview-notes').oninput=()=>{try{localStorage.setItem(key,$('preview-notes').value);}catch(e){}};
 $('copy-layout-feedback').onclick=()=>copy('HexiPlan UI 结构意见：'+document.body.dataset.layoutName+'（'+layout+'），统一淡绿色。\n'+$('preview-notes').value+'\n此消息只反馈页面结构，不批准业务实施或安装任何具体 MCP。');
}
if($('copy-layout'))$('copy-layout').onclick=()=>copy('我确认 HexiPlan 的报告页面采用“'+document.body.dataset.layoutName+'”（layout='+layout+'），统一淡绿色。该选择只用于报告布局，不代替业务软件 UI 确认，不批准任何业务步骤。请记录后复用现成布局，不重写 HTML/CSS/JS。');
if($('layout-label'))$('layout-label').textContent=document.body.dataset.layoutName;
// Scrolling/tabs only changes presentation. Print and DOCX still include the entire document.
window.addEventListener('beforeprint',()=>{sections.forEach(s=>s.hidden=false);if($('full-content'))$('full-content').hidden=false;});
window.addEventListener('afterprint',()=>active(current));
active(0);
})();
