#!/usr/bin/env python3
"""Real Chromium archive/evidence/geometry regressions; dev-only Playwright.

python3 tests/dashboard_browser.py --out /tmp/cm-browser
Never reads native memory stores or launches the user's default browser.
"""
from __future__ import annotations
import argparse
import copy
import importlib
import json
from pathlib import Path
from dashboard_fixture import sample, write_preview, rh

ROOT=Path(__file__).resolve().parents[1]
GEOMETRY=ROOT/'tests/fixtures/dashboard-header-geometry.json'


def main(out):
    sync_playwright=importlib.import_module('playwright.sync_api').sync_playwright
    out.mkdir(parents=True,exist_ok=True)
    preview=write_preview(out)
    results=[]

    def check(name,ok):
        results.append({'check':name,'passed':bool(ok)})
        (out/'browser-results.json').write_text(json.dumps(results,indent=2)+'\n')
        print(('PASS ' if ok else 'FAIL ')+name,flush=True)
        if not ok:raise AssertionError(name)

    record,history,diffs=sample()
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce',color_scheme='light')
        page=context.new_page();errors=[];requests=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda req:requests.append(req.url) if req.url.startswith(('http:','https:')) else None)

        def ready(url):
            page.goto(url);page.wait_for_function("document.querySelector('#boot').style.display==='none'")
            check('render without errors: '+url.rsplit('/',1)[-1],not errors)

        def fixture(name,rec,cycles=None):
            path=out/(name+'.html');path.write_text(rh.build_html(rec,[],'2026-09-05',cycles=cycles))
            ready(path.as_uri()+'#sel='+str(len(cycles)-1 if cycles else 0));return path

        def open_evidence():
            page.locator('#pass-blk details').evaluate_all('es=>es.forEach(e=>e.open=true)')

        def resize(width):
            page.set_viewport_size({'width':width,'height':1000})
            page.wait_for_function('(width)=>innerWidth===width && document.querySelector("#net").dataset.viewport===String(width)',arg=width)

        def contained(label):
            check(label+' has no page overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))

        def geometry(label):
            check(label+' has no colliding SVG labels',page.locator('#net text').evaluate_all('''es=>es.every((a,i)=>{const A=a.getBBox();return es.slice(i+1).every(b=>{const B=b.getBBox();return !(A.x<B.x+B.width-1&&A.x+A.width>B.x+1&&A.y<B.y+B.height-1&&A.y+A.height>B.y+1);});})'''))
            check(label+' has no unintended coincident branches',page.locator('#net .hierarchy-branch').evaluate_all('''es=>{const segs=[];for(const e of es){let nums=e.getAttribute('d').match(/[A-Z]|-?\\d+(?:\\.\\d+)?/g),x=0,y=0;for(let i=0;i<nums.length;){let cmd=nums[i++];if(cmd==='M'){x=+nums[i++];y=+nums[i++];continue;}let nx=x,ny=y;if(cmd==='H')nx=+nums[i++];else if(cmd==='V')ny=+nums[i++];else return false;if(x!==nx||y!==ny)segs.push({x1:Math.min(x,nx),x2:Math.max(x,nx),y1:Math.min(y,ny),y2:Math.max(y,ny)});x=nx;y=ny;}}return segs.every((a,i)=>segs.slice(i+1).every(b=>!(a.x1===a.x2&&b.x1===b.x2&&a.x1===b.x1&&Math.min(a.y2,b.y2)>Math.max(a.y1,b.y1)+.5)&&!(a.y1===a.y2&&b.y1===b.y2&&a.y1===b.y1&&Math.min(a.x2,b.x2)>Math.max(a.x1,b.x1)+.5)));}'''))
            check(label+' branches avoid project interiors and perimeter detours',page.locator('#net .hierarchy-branch').evaluate_all('''es=>{let boxes=[...document.querySelectorAll('#net .net-node rect')].map(e=>e.getBBox());const W=document.querySelector('#net').viewBox.baseVal.width;return es.every(e=>{let l=e.getTotalLength();for(let i=1;i<l;i+=2){let p=e.getPointAtLength(i);if(p.x<10||p.x>W-10||boxes.some(b=>p.x>b.x+.5&&p.x<b.x+b.width-.5&&p.y>b.y+.5&&p.y<b.y+b.height-.5))return false;}return true;});}'''))
            check(label+' every junction names an aggregate branch',page.locator('#net .aggregate-branch').count()>0 or page.locator('#net .domain-junction').count()==0)

        ready(preview.as_uri()+'#sel=7')
        check('Nocturne is the default under a light system preference',page.locator('body').evaluate('e=>getComputedStyle(e).backgroundColor')=='rgb(8, 15, 27)')
        check('summary follows header KPIs and precedes network',page.evaluate("document.querySelector('#dream-blk').previousElementSibling.id==='kpis' && document.querySelector('#dream-blk').nextElementSibling.id==='network-blk'"))
        check('stable section hooks are retained',all(page.locator('#'+s).count()==1 for s in ['traj','trend','rigor','dream-blk','pass-blk','network-blk','history-blk','entries-blk','audit','verify','dream-arc','net-chips','net-detail']))
        check('summary names recorded outcome and evidence',all(t in page.locator('#dream-summary').inner_text() for t in ['LIGHT PASS','5 confirmed claims','4 observed file operations','1 unverifiable claim']))
        check('canonical phase labels require a valid six-beat arc',page.locator('#dream-beats button').count()==6 and page.locator('#dream-beats button').first.inner_text()=='Phase 0 · Locate')
        page.locator('#dream-beats button').nth(3).click()
        check('intermediate dream passages are selectable', 'assumption fails verification' in page.locator('#dream-passage').inner_text())
        page.locator('#complete-dream summary').click()
        check('complete dream preserves every captured string and order',page.locator('#complete-dream .dream-voice').all_text_contents()==[record['dream']['sleep']]+record['dream']['beats']+[record['dream']['wake']])
        check('captured voice alone uses Georgia italic',page.locator('#dream-passage').evaluate("e=>getComputedStyle(e).fontFamily.includes('Georgia') && getComputedStyle(e).fontStyle==='italic'") and not page.locator('#dream-summary').evaluate("e=>getComputedStyle(e).fontFamily.includes('Georgia')"))
        page.locator('#complete-dream summary').click()
        check('initial fleet shows every captured domain and expands the trigger domain',page.locator('.domain-junction').count()==3 and page.locator('.net-node').count()==3 and page.locator('.domain-junction[aria-expanded="true"]').get_attribute('data-domain')=='work')
        geometry('initial fleet')
        page.get_by_role('button',name='Group / release-kit',exact=True).click()
        check('group view has an independent permission root and exact membership',page.locator('.network-root').text_content().startswith('release-kit') and set(page.locator('.net-node').evaluate_all('es=>es.map(e=>e.dataset.node)'))=={'atlas-api','eval-lab','release-tools'})
        check('group inspector distinguishes permission from delivery', 'Permission only' in page.locator('#net-detail').inner_text() and '3 captured group members' in page.locator('#net-detail').inner_text())
        geometry('cross-domain group')
        page.get_by_role('button',name='Group / api-contract',exact=True).click()
        check('overlapping groups do not retain previous members',set(page.locator('.net-node').evaluate_all('es=>es.map(e=>e.dataset.node)'))=={'atlas-api','atlas-web'})
        page.get_by_role('button',name='Reset view',exact=True).click()
        page.locator('.net-node[data-current="true"]').focus();page.keyboard.press('Enter')
        check('keyboard selection exposes project costs and canonical facts','984' in page.locator('#net-detail').inner_text() and 'release-checks' in page.locator('#net-detail').inner_text())
        page.get_by_role('button',name='work / release-checks · 3 holders',exact=True).click()
        check('fact view branches to exact physical holders',set(page.locator('.net-node').evaluate_all('es=>es.map(e=>e.dataset.node)'))=={'atlas-api','eval-lab','release-tools'} and 'Physical holders before limits' in page.locator('#net-detail').inner_text())
        geometry('canonical fact')
        page.get_by_role('button',name='Reset view',exact=True).click()
        page.locator('#net-search').fill('dotfiles')
        check('search reaches a project outside the initial domain',page.locator('.net-node').count()==1 and page.locator('.net-node').get_attribute('data-node')=='dotfiles')
        page.get_by_role('button',name='Reset view',exact=True).click()
        check('adverse verification is open and routine store evidence is collapsed',page.locator('#verification-evidence').get_attribute('open') is not None and page.locator('#store-checks').get_attribute('open') is None)
        check('no composite health score is introduced',set(page.locator('.health-status').all_text_contents())=={'ClaimsNeeds attention','Store integrityRecorded clear','Observed changesRecorded clear'})
        page.locator('#dream-summary [data-evidence="file-changes"]').click()
        check('summary evidence link opens the file disclosure without navigation',page.url.endswith('#sel=7') and page.locator('#audit').is_visible())
        open_evidence()
        check('workflow verdicts, chains, skill use and registrar decisions are accessible',all(page.locator('#'+s).is_visible() for s in ['dstl-verdict','dstl-chains-list','dstl-used-list','demo-verdict','reg-board']))
        check('raw captured record retains every source subtree',all(json.loads(page.locator('#record-json').text_content())[k]==v for k,v in record.items()))
        page.locator('.file-evidence-link').first.click()
        check('observed file opens its captured diff with dialog semantics',page.get_by_role('dialog').is_visible() and page.locator('#dmodal-x').evaluate('e=>e===document.activeElement') and page.locator('#app').evaluate('e=>e.inert'))
        page.keyboard.press('Tab')
        check('diff traps keyboard focus',page.locator('#dmodal-x').evaluate('e=>e===document.activeElement'))
        page.keyboard.press('Escape')
        check('diff restores focus and active background',not page.get_by_role('dialog').is_visible() and page.locator('.file-evidence-link').first.evaluate('e=>e===document.activeElement') and not page.locator('#app').evaluate('e=>e.inert'))
        page.locator('.nm-diff').first.click();page.keyboard.press('Escape')
        check('existing decision-ledger diff access is preserved',page.locator('.nm-diff').first.evaluate('e=>e===document.activeElement'))
        page.locator('#pass-blk > .shead').focus();page.keyboard.press('Enter')
        check('section headings retain keyboard collapse',not page.locator('#audit').is_visible())
        page.locator('.report-nav [data-section="pass-blk"]').click()
        check('section navigation expands a collapsed section',page.locator('#audit').is_visible())
        page.locator('.skip').focus();page.keyboard.press('Enter')
        check('skip link preserves selected dream and focuses the report',page.url.endswith('#sel=7') and page.locator('#app').evaluate('e=>e===document.activeElement'))
        page.locator('.activity-cycle').first.focus();page.keyboard.press('Enter')
        check('activity selection inspects locally without archive navigation',page.url.endswith('#sel=7') and 'Dream 1' in page.locator('#activity-inspector').text_content() and page.locator('.open-dream').get_attribute('href')=='#sel=0')
        check('activity uses exact decision categories and separate usage windows',all(t in page.locator('#activity-inspector').inner_text() for t in ['added','corrected','Observed mutations','Usage window']) and 'writes' not in page.locator('#activity-legend').inner_text())
        page.locator('#activity-table summary').click()
        check('historical table preserves fact counts and cadence for every cycle',page.locator('#activity-table tbody tr').count()==8 and 'never summed' in page.locator('#activity-table').inner_text())
        page.locator('#activity-table summary').click()
        page.locator('#dens-tog').click();page.locator('#dens-tog').focus();page.keyboard.press('ArrowLeft')
        page.wait_for_function("location.hash==='#sel=6' && document.querySelector('#dreamnav .pos').textContent.includes('dream 7 /')")
        check('archive arrow navigation retains density and resets focused networks',page.locator('body').evaluate("e=>e.classList.contains('compact')") and page.locator('.grant-edge').count()==0)
        page.keyboard.press('ArrowRight');page.wait_for_function("location.hash==='#sel=7' && document.querySelector('#dreamnav .pos').textContent.includes('dream 8 /')");page.locator('#dens-tog').click();page.keyboard.press('Escape')
        page.wait_for_function("document.querySelector('#archive').style.display!=='none'")
        check('archive contains every captured cycle',page.locator('.arch-row').count()==8)
        page.locator('#f-sort').select_option('tsRaw:1')
        check('archive sorting remains functional',page.locator('.arch-row').first.get_attribute('href')=='#sel=0')
        page.locator('#f-rig').select_option('SUBSTANTIAL')
        check('archive rigor filtering remains functional','shown' in page.locator('#f-count').inner_text())
        for width in (320,390,768,1440):
            resize(width);contained('archive '+str(width))
            check('archive columns remain accessible '+str(width),page.locator('.arch-row .hh').first.is_visible() and page.locator('.arch-row .en').first.is_visible())
        page.locator('a.arch-row[href="#sel=7"]').click();page.wait_for_function("document.querySelector('#app').style.display!=='none'")
        for theme in ['dark','original','light','auto']:
            page.evaluate('(theme)=>{document.documentElement.dataset.theme=theme;localStorage.setItem("cm-theme",theme);}',theme)
            for width in (320,390,768,1440):
                resize(width);contained(theme+' '+str(width));geometry(theme+' '+str(width))
                check('inspector stays below the graph on narrow screens '+theme+' '+str(width),width>=1100 or page.locator('#net-detail').bounding_box()['y']>=page.locator('.map-scroll').bounding_box()['y']+page.locator('.map-scroll').bounding_box()['height']-1)
            page.screenshot(path=str(out/('report-'+theme+'.png')),full_page=True)
            page.emulate_media(media='print')
            check(theme+' prints with white surfaces and readable ink',page.locator('body').evaluate('e=>getComputedStyle(e).color')=='rgb(23, 43, 67)' and page.locator('html').evaluate('e=>getComputedStyle(e).colorScheme')=='light')
            page.emulate_media(media='screen')
        page.evaluate("localStorage.setItem('cm-theme','original')");page.reload();page.wait_for_function("document.querySelector('#boot').style.display==='none'")
        check('Original persists and names its next theme',page.locator('#theme-tog').inner_text()=='◒ Original' and page.locator('#theme-tog').get_attribute('aria-label')=='Color theme: Original. Switch to Light')
        page.locator('#theme-tog').click();check('Light theme control works',page.locator('html').get_attribute('data-theme')=='light')
        page.locator('#theme-tog').click();page.emulate_media(color_scheme='dark');check('System responds to changed device preference',page.locator('body').evaluate('e=>getComputedStyle(e).backgroundColor')=='rgb(8, 15, 27)')
        page.locator('#theme-tog').click();check('theme loop returns to Nocturne',page.locator('#theme-tog').inner_text()=='● Nocturne')
        check('reduced motion disables animated permission branches',page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches") and page.locator('html').evaluate("e=>getComputedStyle(e).scrollBehavior!=='smooth'"))

        # Focused evidence discriminators, including absent vs measured zero.
        sparse={'project':'sparse','marker':{'commit':'old','timestamp':'2026-08-01T00:00:00Z'}}
        fixture('sparse',sparse);open_evidence()
        check('missing observations stay missing','not measured' in page.locator('#lead-head').inner_text() and all(t in page.locator('#health-summary').inner_text() for t in ['Claims','Not captured']) and 'Not captured' in page.locator('#verify').inner_text())
        check('absent topology never claims a measured empty network','Project list not captured' in page.locator('#net-detail').inner_text())
        check('missing dream bookends remain explicit','Not captured' in page.locator('#dream-arc').inner_text())
        partial=copy.deepcopy(record);partial.update(verification={'confirmed':4},audit={'memory':{'created':1}},usage={'mentions':2},health={'broken':['missing-source']},preflight={'at':'2026-09-05T12:01:00Z','fails':['sqlite-module'],'warns':['no-git']},remediation={'over_ceiling':True,'required':True})
        fixture('partial',partial);open_evidence()
        check('partial claims never infer healthy zeroes','4' in page.locator('#verify').inner_text() and page.locator('#verify').inner_text().count('Not captured')>=3 and 'Partially captured' in page.locator('#health-summary').inner_text())
        check('preflight timestamp, IDs and unresolved attention remain conspicuous',all(t in page.locator('#store-evidence').inner_text() for t in ['2026-09-05T12:01:00Z','sqlite-module','no-git']) and all(t in page.locator('#attention-items').inner_text() for t in ['Hard ceiling','Unresolved index remediation','missing-source']))
        check('partial physical changes and reads remain partial','not fully captured' in page.locator('#audit').inner_text() and 'Not captured' in page.locator('#usage-evidence').inner_text())
        zero=copy.deepcopy(record);zero.update(verification={'confirmed':0,'corrected':0,'unverifiable':0},audit={'operations':[]},usage={'reads':0,'mentions':0},scope={'git_commits':0,'session_candidates':0},entries=[])
        zero['budget']['claude_md']={'after_tokens':0};fixture('zero',zero);open_evidence()
        check('recorded zero survives in budget, mutation and recall evidence','0/4.0k' in page.locator('#m-cmd').inner_text() and '0 observed file operations' in page.locator('#audit').inner_text() and '0' in page.locator('#usage-evidence').inner_text())
        check('recorded clear is limited to complete captured evidence',page.locator('.health-status[data-state="Recorded clear"]').count()==3)
        malformed=copy.deepcopy(record);malformed['dream']['beats']=['first',None,{'captured':'object'},'last'];fixture('malformed-dream',malformed)
        check('malformed dream uses numbered beats without invented phase completion',page.locator('#dream-beats button').all_text_contents()==['Beat 1','Beat 2','Beat 3','Beat 4'])
        page.locator('#complete-dream summary').click();check('malformed captured passages remain accessible in order',page.locator('#complete-dream .dream-voice').all_text_contents()[1:-1]==['first','{"captured":"object"}','last'])
        rich=copy.deepcopy(record)
        rich['audit']['operations']=[{'path':'file-%02d.md'%i,'store':'memory','op':'modified'} for i in range(30)]
        rich['usage']['per_fact']=[{'name':'recall-%02d'%i,'reads':i} for i in range(20)]
        rich['distill'].update(top=[{'t':'command-%02d'%i,'n':i,'d':3} for i in range(30)],top_chains=[{'t':['chain-%02d'%i,'next'],'n':i,'d':2} for i in range(12)],used=[{'a':'skill-%02d'%i,'n':i} for i in range(15)])
        rich['demotion']['surfaced']=[{'name':'demote-%02d'%i,'reads':0} for i in range(10)]
        rich['workflow_proposals']['decline_anchors']=[{'node':'decline-%02d'%i,'verdict':'nothing: test','top':[{'t':'anchor-top-%d'%j} for j in range(8)]} for i in range(10)]
        rich['audit']['conservation']={'possible_loss':True,'claude_md_drop':500,'repo_doc_growth':0}
        fixture('rich-evidence',rich);open_evidence()
        check('every formerly clipped evidence row is accessible',all(t in page.locator('#pass-blk').inner_text() for t in ['file-29.md','recall-19','command-29','chain-11','skill-14','demote-09','decline-09','anchor-top-7']))
        check('conservation concerns open the physical-change evidence',page.locator('#file-changes').get_attribute('open') is not None and 'Conservation concern' in page.locator('#attention-items').inner_text())
        check('no inert +N more labels remain in verification evidence',' more files' not in page.locator('#pass-blk').inner_text() and not page.locator('#pass-blk .dstl-more').count())
        chain=fixture('rich-sparse-rich',rich,cycles=[rich,sparse,rich]);open_evidence();count=page.locator('#pass-blk .captured-details').count()
        page.keyboard.press('ArrowLeft');page.wait_for_function("location.hash==='#sel=1' && document.querySelector('#dreamnav .pos').textContent.includes('dream 2 /')")
        check('rich to sparse navigation clears workflow and network evidence',page.locator('#dstl-chains-list').text_content()=='' and not page.locator('#registrar-blk').is_visible() and page.locator('.net-node').count()==0)
        page.keyboard.press('ArrowRight');page.wait_for_function("location.hash==='#sel=2' && document.querySelector('#dreamnav .pos').textContent.includes('dream 3 /')");open_evidence()
        check('sparse to rich navigation restores evidence without duplicate disclosures',page.locator('#pass-blk .captured-details').count()==count and 'chain-11' in page.locator('#dstl-chains-list').inner_text())

        # Dense and uneven fleets: all captured domains visible, all projects reachable.
        for name,count,domain_of in [('empty',0,lambda i:'work'),('singleton',1,lambda i:'work'),('baseline-only',10,lambda i:'work'),('disconnected',18,lambda i:'d-%d'%(i%4)),('dense',36,lambda i:'d-%d'%(i%4)),('uneven',45,lambda i:'work' if i<39 else 'tools'),('unknown-domain',7,lambda i:'unknown'),('large',125,lambda i:'d-%d'%(i%9))]:
            rec=copy.deepcopy(record);nodes=[dict(node='project-%03d'%i,sid='sid-%03d'%i,display_name='Readable project %03d'%i,domain=domain_of(i),groups=['all','even'] if i%2==0 else ['all'],trigger=i==0,shared=1) for i in range(count)]
            domains=sorted({domain_of(i) for i in range(count)})+['captured-without-rows']
            net={'basis_scope':'fleet','nodes':nodes,'domains':[{'domain':d} for d in domains], 'stack_edges':[] if name in ['baseline-only','disconnected'] else [{'a':a['node'],'b':b['node'],'n':1} for i,a in enumerate(nodes) for b in nodes[i+1:]],'group_links':[{'group':'all','members_n':count,'facts':[]},{'group':'even','members_n':(count+1)//2,'facts':[]}],'fact_holdings':[{'fact_id':'one','name':'shared-lesson','domain':'work','scope':'user-global' if name=='baseline-only' else 'stack-general','holder_sids':[n['sid'] for n in nodes],'held_n':count}] if count else [],'totals':{'nodes':count}}
            rec['network']=net;fixture('topology-'+name,rec)
            check(name+' exposes every captured domain',set(page.locator('.domain-junction').evaluate_all('es=>es.map(e=>e.dataset.domain)'))==set(domains))
            check(name+' preserves the full captured project inventory',page.locator('#network-data-body table').first.locator('tbody tr').count()==count)
            if count:
                page.locator('#net-search').fill('Readable project %03d'%(count-1));check(name+' search reaches the final captured project',page.locator('.net-node').count()==1 and page.locator('.net-node').get_attribute('data-sid')=='sid-%03d'%(count-1))
                page.get_by_role('button',name='Group / even',exact=True).click()
                check(name+' highlights only permitted members',all(int(s.split('-')[1])%2==0 for s in page.locator('.net-node').evaluate_all('es=>es.map(e=>e.dataset.sid)')))
            geometry(name+' fleet')
            if name in ['large','uneven']:
                page.get_by_role('button',name='Reset view',exact=True).click()
                before=set(page.locator('.net-node').evaluate_all('es=>es.map(e=>e.dataset.sid)'))
                page.get_by_role('button',name='Next projects in '+domain_of(0),exact=True).click()
                check(name+' pagination reaches further nodes',not set(page.locator('.net-node').evaluate_all('es=>es.map(e=>e.dataset.sid)')).issubset(before))
            resize(320);contained(name+' mobile');geometry(name+' mobile');resize(1440)
        legacy=copy.deepcopy(record);legacy['network'].pop('fact_holdings');legacy['network'].pop('capture');fixture('legacy-network',legacy)
        page.locator('.net-node[data-current="true"]').click()
        check('historical pairwise evidence names its missing canonical boundary','Canonical identities were not captured' in page.locator('#net-detail').inner_text() and 'fact names were not captured' in page.locator('#net-detail').inner_text())
        truncated=copy.deepcopy(record);truncated['network']['fact_holdings'][0]['held_n']=2001;truncated['network']['capture'].update(facts_total=130,holder_refs_total=2300,unresolved_identities=3,read_failures=2);fixture('truncated',truncated)
        check('capture limitations remain explicit','130' in page.locator('#net-detail').inner_text() and '2300' in page.locator('#net-detail').inner_text() and 'Unresolved mirror identities' in page.locator('#net-detail').inner_text())
        hostile=copy.deepcopy(record);attack='</script><img src=x onerror="window.PWNED=1">';hostile['network']['nodes'][0]['display_name']=attack;hostile['dream']['sleep']=attack;hostile['preflight']['fails']=[attack];hostile['entries'][0]['reason']=attack;fixture('hostile',hostile);open_evidence()
        check('hostile strings stay inert across all redesigned sections',page.evaluate("!window.PWNED && !document.querySelector('img')") and json.loads(page.locator('#record-json').text_content())['dream']['sleep']==attack)

        long=[]
        for i in range(30):
            c=copy.deepcopy(record);c['session']='cycle-%d'%i;c['marker']={'commit':'c%d'%i,'timestamp':'2026-08-%02dT12:00:00Z'%(i+1)}
            if i%4==0:c.pop('usage');c.pop('rigor')
            if i==27:c['entries']=[{'action':'counter-justified'},{'action':'demoted'},{'action':'custom-recorded-category'}]
            long.append(c)
        fixture('long-activity',long[-1],cycles=long)
        check('activity defaults to latest 12 ending at selection',page.locator('.activity-cycle').count()==12 and page.locator('.activity-cycle').first.get_attribute('data-cycle')=='18')
        page.get_by_role('button',name='24',exact=True).click();check('24-dream window works',page.locator('.activity-cycle').count()==24)
        page.get_by_role('button',name='All captured',exact=True).click();check('All captured window works',page.locator('.activity-cycle').count()==30)
        check('missing reads and rigor remain gaps','—' in page.locator('#trend').text_content() and '—' in page.locator('#rigor').text_content())
        check('decision categories remain exact, including unknown recorded categories','custom-recorded-category' in page.locator('#activity-legend').inner_text() and 'counter-justified' in page.locator('#activity-legend').inner_text())
        page.locator('.activity-cycle[data-cycle="4"]').focus();page.keyboard.press('Enter')
        check('missing usage inspector preserves missing observation and window',page.locator('#activity-inspector').inner_text().count('Not captured')>=2 and page.url.endswith('#sel=29'))
        page.locator('.open-dream').click();page.wait_for_function("location.hash==='#sel=4' && document.querySelector('#dreamnav .pos').textContent.includes('dream 5 /')");check('Open this dream performs archive navigation explicitly',page.locator('.activity-cycle').count()==5)

        # Golden geometry captured from the v0.4.16 header before this redesign.
        check('frozen header geometry reference is present',GEOMETRY.is_file())
        if GEOMETRY.exists():
            expected=json.loads(GEOMETRY.read_text())
            for name,case in expected.items():
                fixture('header-'+name,case['record'],cycles=case['cycles'])
                actual=page.locator('#traj').inner_html()
                check('immutable header SVG geometry: '+name,actual==case['svg'])
        check('every transition completed without browser exceptions',not errors)
        check('archives run offline without external requests',not requests)
        browser.close()
    print('%d browser checks passed'%len(results))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',required=True,type=Path)
    main(parser.parse_args().out.resolve())
