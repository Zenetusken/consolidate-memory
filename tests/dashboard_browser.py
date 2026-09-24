#!/usr/bin/env python3
"""Real Chromium archive/evidence/geometry regressions; dev-only Playwright.

python3 tests/dashboard_browser.py --out /tmp/cm-browser
Never reads native memory stores or launches the user's default browser.
"""
from __future__ import annotations
import argparse
import copy
import datetime
import importlib
import json
import re
from pathlib import Path
from dashboard_fixture import sample, write_preview, rh

ROOT=Path(__file__).resolve().parents[1]
GEOMETRY=ROOT/'tests/fixtures/dashboard-header-geometry.json'


def main(out,capture=False):
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

        def fixture(name,rec,cycles=None,sidecars=None):
            path=out/(name+'.html');path.write_text(rh.build_html(rec,[],'2026-09-05',cycles=cycles,diffs=sidecars))
            ready(path.as_uri()+'#sel='+str(len(cycles)-1 if cycles else 0));return path

        def open_evidence():
            page.locator('#pass-blk details').evaluate_all('es=>es.forEach(e=>e.open=true)')

        def captured_network():
            return json.loads(page.locator('#record-json').text_content()).get('network',{})

        def network_view(kind,name=None):
            value='fleet'
            if kind!='fleet':
                key='fact_holdings' if kind=='fact' else 'group_links'
                field='name' if kind=='fact' else 'group'
                index=next(i for i,item in enumerate(captured_network()[key]) if item[field]==name)
                value=kind+':'+str(index)
            page.locator('#net-view').select_option(value)

        def concise_network(label):
            # The four `*tokens`/`Physical mirrors` labels are the deep-dive inspector's ACCOUNTING
            # rows, removed in b665ffc. They are named here because the compact summary is a <dl>
            # of label/value rows — the same shape — so the accounting vocabulary is what it would
            # regress toward, one row at a time. `Domain`/`Scope`/`Home domain` are NOT listed:
            # those labels were shared with the removed panel and are legitimately the summary's
            # own, so forbidding them would fail the fix rather than a regression.
            check(label+' presents a map and brief context without debugging panels',page.locator('#net-detail details, #net-detail table, #net-detail pre, #net-detail .inspector-row, #net-detail .network-holders, #net-detail .network-members').count()==0 and page.locator('#network-blk').evaluate("e=>!['Technical evidence','Stable store','Canonical identity','Holder references','Project directory','tokens (est.)','Registry baseline','Always-loaded tokens','Mirror index tokens','Recall tokens','Physical mirrors'].some(text=>e.innerText.includes(text))"))
            check(label+' keeps network inventory and accounting off the dashboard',page.locator('#network-data:visible, #network-blk .budget-grid:visible, #network-blk #xp-strip:visible').count()==0)
            # The summary replaced a debugging panel, so it carries a hard row budget: a compact
            # view that can accrete one row at a time becomes that panel again, and no other check
            # here would notice. The pairing is the structural half — a <dl> whose dt/dd counts
            # disagree renders as a shifted grid, not as an error, so nothing else can catch it.
            # The FLOOR is the other half, and it is not decoration. With a ceiling alone a summary
            # that never renders at all reads 0 rows, 0==0 passes, and the check is green against
            # the very defect it was written for — measured, not reasoned: replanting these
            # predicates against a bundle whose <dl> is never built gives dt=0, dd=0, GREEN.
            # So the bound is keyed to the view the map itself reports, never to the call site's
            # label string: a focused view must carry a real summary, and the fleet must carry
            # none because it has no selection to summarise. Measured rows — fleet 0, group 2,
            # fact 3, project 4 — so the project view's four IS the ceiling (a boundary test
            # there), and the floor is the half a missing summary cannot satisfy.
            summary_rows=page.locator('#net-detail .network-summary > dt').count()
            low,high=(0,0) if page.locator('#net').get_attribute('data-kind')=='fleet' else (1,4)
            check(label+' keeps the selection summary to a handful of paired rows',
                  summary_rows==page.locator('#net-detail .network-summary > dd').count()
                  and low<=summary_rows<=high)

        def resize(width):
            page.set_viewport_size({'width':width,'height':1000})
            page.wait_for_function('(width)=>innerWidth===width && document.querySelector("#net").dataset.viewport===String(width)',arg=width)

        def contained(label):
            check(label+' has no page overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))

        def focused_fit(label):
            # The summary's EXISTENCE is the load-bearing half, and it is the half nothing else at
            # these two sites asserts: a <dl> that never builds cannot overflow, so a containment-
            # only check is green against a focused view that lost its whole summary — the D2 shape,
            # at the two places D2's own repair (concise_network's floor) does not reach: the
            # fact-view width loop, and the theme loop's focused pass.
            #
            # The page-scroll clause is inherited from the `contained()` call this replaces, and it
            # is NARROWER than it reads — measured, not assumed: force #net-detail to
            # calc(100vw + 240px) and this stays green, because .network-surface clips it
            # (overflow:hidden; clientW 1206 against scrollW 1706) so nothing reaches
            # documentElement.scrollWidth. Containment of the map's own surfaces is report_layout's
            # surface-alignment clause, which runs in the same focused pass and caught that forced
            # width at all four widths. Kept because it still guards a blowout that ESCAPES the
            # clip, which is a different failure from one swallowed by it.
            check(label+' renders its summary without overflowing the page',
                  page.locator('#net-detail .network-summary > dt').count()>0
                  and page.evaluate('document.documentElement.scrollWidth<=innerWidth'))

        def narration_layout(label):
            check(label+' narration is a visible single column of italic paragraphs',page.locator('#dream-arc .dream-voice').evaluate_all('''es=>es.length>0 && es.every((e,i)=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e),first=es[0].getBoundingClientRect();return s.fontStyle==='italic' && r.height>0 && Math.abs(r.x-first.x)<1 && Math.abs(r.width-first.width)<1 && (!i || r.y>=es[i-1].getBoundingClientRect().bottom);})'''))
            check(label+' narration reaches the section content margin',page.locator('#dream-arc .dream-voice').evaluate_all('''es=>es.every(e=>{const r=e.getBoundingClientRect(),parent=e.parentElement,p=parent.getBoundingClientRect(),s=getComputedStyle(parent),left=p.left+parseFloat(s.borderLeftWidth)+parseFloat(s.paddingLeft),right=p.right-parseFloat(s.borderRightWidth)-parseFloat(s.paddingRight);return Math.abs(r.left-left)<1 && Math.abs(r.right-right)<1;})'''))

        def report_layout(label):
            # The four .network-* selectors appended to the text-in-box list below are the map's
            # own surfaces, and they are here rather than in visual_hierarchy's list for two
            # measured reasons.
            #
            # First, this clause is the one with the Range walk, and the Range walk is
            # CLIP-IMMUNE: getClientRects() returns layout rects, not clipped ones, so it still
            # reports text that .network-surface{overflow:hidden} has swallowed. That is exactly
            # where the contained() family goes blind (see focused_fit), which makes this clause
            # the only instrument that sees a blown-out surface at all.
            #
            # Second, only a box that is CONSTRAINED can overflow, and three of the five obvious
            # selectors turned out not to be. Measured at 1440/320 by putting a 600-char nowrap
            # token in each and watching the box: `.network-summary dt` 129/129 -> 3900, the
            # trail 109/109 -> 3900, `#net-legend-note` 554/246 -> 3600 — each box GREW to fit,
            # because a grid `auto` track and a flex item both floor at min-content. Text past
            # their own box is unreachable, so a check on them could never fail; they are
            # decoration and were dropped. Their containers did hold (`.network-summary` and
            # #net-controls, 1154/246 unchanged, text 2746-3046 past the right edge), and a
            # container's walk covers its descendants' text — so the container is what carries
            # the dt, the trail and the note here. `.network-summary dd` is kept as well: its
            # `minmax(0,1fr)` track has a 0 floor, which is the constraint the whole rule exists
            # for, and it is the most sensitive member of the list.
            #
            # They render only in a focused view, so the extension is worthless without the
            # focused call in the theme loop, and clean-where-it-does-not-render is not evidence:
            # the +new-surfaces probe was run at 1440/390/320 against a real focused view.
            failures=page.evaluate('''()=>{
                const failures=[],rect=e=>e.getBoundingClientRect(),inside=e=>{const r=rect(e),s=getComputedStyle(e);return {left:r.left+parseFloat(s.borderLeftWidth)+parseFloat(s.paddingLeft),right:r.right-parseFloat(s.borderRightWidth)-parseFloat(s.paddingRight)};};
                function aligned(e,parent,full){if(!e || !e.getClientRects().length)return;const r=rect(e),p=inside(parent);if(Math.abs(r.left-p.left)>1 || full&&Math.abs(r.right-p.right)>1)failures.push({element:e.id||e.className,left:r.left,right:r.right,expected:p});}
                for(const section of document.querySelectorAll('#app > section.blk')){aligned(section,document.querySelector('#app'),true);aligned(section.querySelector('.shead'),section,true);aligned(section.querySelector('.section-purpose'),section,false);}
                for(const id of ['dream-summary','dream-arc','entries','activity-inspector']){const e=document.getElementById(id);aligned(e,e.closest('section.blk'),true);}
                for(const e of document.querySelectorAll('#dream-summary .summary-outcome,#entries .row .rs'))aligned(e,e.parentElement,true);
                const surface=document.querySelector('.network-surface');for(const e of surface.querySelectorAll('#net-controls,.map-scroll,#net-detail,#net-legend'))aligned(e,surface,true);
                const inspector=document.getElementById('activity-inspector');for(const e of inspector.querySelectorAll('.activity-summary,.activity-details'))aligned(e,inspector,true);for(const e of inspector.querySelectorAll('.activity-details[open] .inspector-row'))aligned(e,e.parentElement,true);
                return failures;
            }''')
            check(label+' aligns report sections and padded content '+json.dumps(failures),not failures)
            failures=page.locator('#app section.blk > .shead').evaluate_all('''headings=>headings.flatMap(h=>{
                const box=h.getBoundingClientRect(),s=getComputedStyle(h),indicator=getComputedStyle(h,'::after'),reserved=parseFloat(indicator.width)||parseFloat(indicator.fontSize),limit=box.right-Math.max(parseFloat(s.paddingRight),reserved),children=[...h.children].filter(e=>e.getClientRects().length && !e.classList.contains('ln'));
                return children.flatMap((a,i)=>{const A=a.getBoundingClientRect(),failures=[];if(A.left<box.left-1||A.right>limit+1)failures.push({section:h.parentElement.id,child:a.className||a.tagName,issue:'outside heading content or collapse-control space'});for(const b of children.slice(i+1)){const B=b.getBoundingClientRect();if(A.left<B.right-1&&A.right>B.left+1&&A.top<B.bottom-1&&A.bottom>B.top+1)failures.push({section:h.parentElement.id,a:a.className||a.tagName,b:b.className||b.tagName,issue:'overlap'});}return failures;});
            })''')
            check(label+' keeps heading titles, notes and collapse controls apart '+json.dumps(failures),not failures)
            failures=page.evaluate('''()=>{
                const selectors=['#dream-arc .dream-voice','#entries .row .act','#entries .row .nm','#entries .row .rs','#entries .row .ci','#pass-blk .file-evidence-link','#pass-blk .evidence-fields dt','#pass-blk .evidence-fields dd','#activity-inspector .inspector-row>span','#activity-inspector .inspector-row>b','.network-summary','.network-summary dd','#net-controls','#net-legend'];
                return selectors.flatMap(s=>[...document.querySelectorAll(s)]).filter(e=>e.getClientRects().length&&!e.closest('details:not([open])')).flatMap(e=>{const bounds=e.getBoundingClientRect(),range=document.createRange();range.selectNodeContents(e);return [...range.getClientRects()].some(r=>r.left<bounds.left-1||r.right>bounds.right+1)?[{element:e.className||e.tagName,text:e.textContent.slice(0,60),issue:'text exceeds its content box'}]:[];});
            }''')
            check(label+' wraps prose, ledger labels and evidence values inside their columns '+json.dumps(failures),not failures)
            check(label+' keeps scrolling tables inside the report',page.locator('#app .table-scroll:visible').evaluate_all('''es=>es.every(e=>{const r=e.getBoundingClientRect(),section=e.closest('section.blk').getBoundingClientRect(),s=getComputedStyle(e);return r.left>=section.left-1&&r.right<=section.right+1&&(!e.querySelector('table')||e.scrollWidth<=e.clientWidth+1||['auto','scroll'].includes(s.overflowX));})'''))
            check(label+' aligns network control heights',page.evaluate("Math.abs(document.querySelector('#net-search').getBoundingClientRect().height-document.querySelector('#net-view').getBoundingClientRect().height)<1"))
            check(label+' activity plots fill their available width with aligned columns',page.locator('.activity-scroll').evaluate('''e=>{const container=e.getBoundingClientRect(),plots=[...e.querySelectorAll('svg')].filter(s=>getComputedStyle(s).display!=='none').map(s=>s.getBoundingClientRect());return plots.length>0 && plots.every(p=>Math.abs(p.left+e.scrollLeft-container.left)<1 && p.width>=container.width-1);}'''))

        def lower_summary(label):
            check(label+' puts evidence state beside each useful disclosure title',page.locator('#pass-blk > details > summary .health-status').count()==4 and page.locator('#health-summary:visible').count()==0)
            check(label+' shows all captured dreams without range controls',page.locator('#activity-cycle-select').count()==1 and not any(t in ['12','24','All captured'] for t in page.locator('#activity-controls button').all_text_contents()))
            check(label+' starts with concise activity context and optional cycle metrics',page.locator('#activity-inspector details').count()==1 and page.locator('#activity-inspector details[open]').count()==0 and page.locator('#activity-inspector .inspector-row:visible').count()==0 and not page.locator('#rigor').is_visible() and page.locator('#trend rect.activity-selection').count()==0)
            check(label+' keeps technical evidence and ledger metadata behind real disclosures',page.locator('#pass-blk .captured-details[open]').count()==0 and page.locator('#entries details').count()>0 and page.locator('#entries details[open]').count()==0)
            check(label+' links each selected cycle to an explicit archive action',page.locator('#activity-inspector .open-dream').get_attribute('href')==page.evaluate('location.hash'))

        def lower_layout(label):
            failures=page.evaluate('''()=>{
                const groups=[...document.querySelectorAll('#pass-blk > details > summary')],failures=[];
                for(const group of groups){const outer=group.getBoundingClientRect(),children=[...group.children].filter(e=>e.getClientRects().length);for(const child of children){const r=child.getBoundingClientRect();if(r.left<outer.left-1||r.right>outer.right+1)failures.push({text:child.textContent,issue:'summary item outside disclosure'});}}
                const visible=[...document.querySelectorAll('#entries details,#activity-inspector details')].filter(e=>e.open);
                for(const detail of visible){const outer=detail.getBoundingClientRect();for(const e of detail.querySelectorAll('.ci,.inspector-row,dt,dd')){const r=e.getBoundingClientRect();if(r.left<outer.left-1||r.right>outer.right+1)failures.push({text:e.textContent.slice(0,60),issue:'detail exceeds disclosure'});}}
                return failures;
            }''')
            check(label+' contains evidence statuses and expanded decision details '+json.dumps(failures),not failures)
            check(label+' fits all activity inside the report without horizontal scrolling',page.locator('.activity-scroll').evaluate('''e=>{const c=e.getBoundingClientRect(),r=e.querySelector('#trend').getBoundingClientRect();return e.scrollWidth<=e.clientWidth+1 && r.left>=c.left-1 && r.right<=c.right+1;}'''))

        def controls_layout(label):
            failures=page.locator('.chrome button,.dreamnav .nav-link,#app .report-nav button,#network-blk .inspector-choice,#net-breadcrumbs button,#net-search,#net-view,#activity-controls button,#activity-cycle-select,#app .open-dream,#app button.evidence-link,#app .nm-diff,#app .file-evidence-link,#app summary,#app section.blk>.shead,#archive select').evaluate_all('''es=>es.filter(e=>{const r=e.getBoundingClientRect();if(!r.width||!r.height)return false;for(let p=e.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS'&&!p.open&&!(e.tagName==='SUMMARY'&&e.parentElement===p))return false;return true;}).flatMap(e=>{const r=e.getBoundingClientRect();return r.height<43.5||r.width<43.5?[{name:e.getAttribute('aria-label')||e.textContent.slice(0,70),width:r.width,height:r.height}]:[];})''')
            check(label+' gives visible controls usable hit areas '+json.dumps(failures),not failures)
            check(label+' distinguishes primary navigation from secondary controls',page.locator('.open-dream').evaluate('e=>{const a=getComputedStyle(e),b=getComputedStyle(document.querySelector("#activity-controls button"));return a.backgroundColor!==b.backgroundColor && a.borderStyle==="solid" && parseFloat(a.borderRadius)>=6 && a.color!==b.color;}'))
            check(label+' explains diff buttons before clicking',page.locator('.nm-diff,.file-evidence-link').evaluate_all('es=>es.every(e=>e.querySelector(".diff-action")?.textContent==="View diff" && e.getAttribute("aria-label")?.includes("diff"))'))
            check(label+' keeps disabled boundary controls out of the tab order',page.locator('#dreamnav .off,#activity-controls button:disabled,#net [aria-disabled="true"]').evaluate_all('es=>es.every(e=>e.tagName==="BUTTON"?e.disabled:!e.hasAttribute("href") && e.getAttribute("tabindex")!=="0")'))
            failures=page.locator('button:visible,a:visible,summary:visible,select:visible').evaluate_all('''es=>es.filter(e=>e.closest('#app,.chrome,#archive,#dreamnav')).flatMap(e=>{if(e.tagName==='SELECT')return [];const b=e.getBoundingClientRect(),r=document.createRange();r.selectNodeContents(e);return [...r.getClientRects()].some(t=>t.left<b.left-1||t.right>b.right+1)?[{name:e.textContent.slice(0,80),issue:'control text exceeds target'}]:[];})''')
            check(label+' wraps control labels inside their hit areas '+json.dumps(failures),not failures)

        def visual_hierarchy(label):
            check(label+' separates section headings, conclusions, explanation and source typography',page.evaluate('''()=>{
                const style=q=>getComputedStyle(document.querySelector(q)),heading=style('#network-blk .shead h3'),conclusion=style('.summary-outcome'),body=style('#network-blk .section-purpose'),source=style('.network-attribution');
                return parseFloat(heading.fontSize)>=24 && +heading.fontWeight>=600 && parseFloat(conclusion.fontSize)>parseFloat(body.fontSize) && +conclusion.fontWeight>=600 && parseFloat(source.fontSize)<parseFloat(body.fontSize) && new Set([heading.color,body.color,source.color]).size>=3;
            }'''))
            failures=page.evaluate('''()=>{
                const selectors=['.blk .shead h3','.section-purpose','.summary-outcome','.summary-evidence','.network-conclusion','.network-selection-name','.network-attribution','.network-detail-section h5','.network-holders','.network-members','.network-summary dt','.network-summary dd','.crumb-trail','#net-legend-note','#net text','#net-legend','.source-note','.health-status','#activity-inspector','.activity-copy','.open-dream','.evidence-link','.diff-action','.diff-name','.chrome button','#app summary','#app .report-nav button','#activity-cycle-select'];
                const rgba=s=>{const m=s.match(/[\\d.]+/g);return m?[+m[0],+m[1],+m[2],m[3]===undefined?1:+m[3]]:[0,0,0,0];};
                const over=(fg,bg)=>[0,1,2].map(i=>fg[i]*fg[3]+bg[i]*(1-fg[3])).concat(1);
                function background(e){const chain=[];for(let n=e;n;n=n.parentElement)chain.unshift(n);let bg=[255,255,255,1];for(const n of chain)bg=over(rgba(getComputedStyle(n).backgroundColor),bg);const node=e.closest('.net-node');if(node)bg=over(rgba(getComputedStyle(node.querySelector('rect')).fill),bg);return bg;}
                const luminance=c=>c.slice(0,3).map(x=>x/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4).reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0);
                return [...new Set(selectors.flatMap(s=>[...document.querySelectorAll(s)]))].filter(e=>e.getClientRects().length && e.textContent.trim() && !e.closest('details:not([open])')).map(e=>{
                    const s=getComputedStyle(e),bg=background(e),fg=over(rgba(e instanceof SVGElement?s.fill:s.color),bg),a=luminance(bg),b=luminance(fg),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05),large=parseFloat(s.fontSize)>=24 || (+s.fontWeight>=700 && parseFloat(s.fontSize)>=18.66);
                    return {text:e.textContent.trim().slice(0,70),ratio,minimum:large?3:4.5};
                }).filter(x=>x.ratio+.01<x.minimum);
            }''')
            check(label+' readable text meets contrast thresholds '+json.dumps(failures),not failures)

        def geometry(label):
            check(label+' fits the network SVG to its natural aspect ratio',page.locator('#net').evaluate('''e=>{const r=e.getBoundingClientRect(),v=e.viewBox.baseVal;return Math.abs(r.height-r.width*v.height/v.width)<1;}'''))
            check(label+' keeps a modest canvas margin below the final branch or label',page.locator('#net').evaluate('''e=>{const b=e.getBBox(),gap=e.viewBox.baseVal.height-b.y-b.height;return gap>=15 && gap<=40;}'''))
            check(label+' has no colliding SVG labels',page.locator('#net text').evaluate_all('''es=>es.every((a,i)=>{const A=a.getBBox();return es.slice(i+1).every(b=>{const B=b.getBBox();return !(A.x<B.x+B.width-1&&A.x+A.width>B.x+1&&A.y<B.y+B.height-1&&A.y+A.height>B.y+1);});})'''))
            check(label+' has no unintended coincident branches',page.locator('#net .hierarchy-branch').evaluate_all('''es=>{const segs=[];for(const e of es){let nums=e.getAttribute('d').match(/[A-Z]|-?\\d+(?:\\.\\d+)?/g),x=0,y=0;for(let i=0;i<nums.length;){let cmd=nums[i++];if(cmd==='M'){x=+nums[i++];y=+nums[i++];continue;}let nx=x,ny=y;if(cmd==='H')nx=+nums[i++];else if(cmd==='V')ny=+nums[i++];else return false;if(x!==nx||y!==ny)segs.push({x1:Math.min(x,nx),x2:Math.max(x,nx),y1:Math.min(y,ny),y2:Math.max(y,ny)});x=nx;y=ny;}}return segs.every((a,i)=>segs.slice(i+1).every(b=>!(a.x1===a.x2&&b.x1===b.x2&&a.x1===b.x1&&Math.min(a.y2,b.y2)>Math.max(a.y1,b.y1)+.5)&&!(a.y1===a.y2&&b.y1===b.y2&&a.y1===b.y1&&Math.min(a.x2,b.x2)>Math.max(a.x1,b.x1)+.5)));}'''))
            check(label+' branches avoid project interiors and perimeter detours',page.locator('#net .hierarchy-branch').evaluate_all('''es=>{let boxes=[...document.querySelectorAll('#net .net-node rect')].map(e=>e.getBBox());const W=document.querySelector('#net').viewBox.baseVal.width;return es.every(e=>{let l=e.getTotalLength();for(let i=1;i<l;i+=2){let p=e.getPointAtLength(i);if(p.x<10||p.x>W-10||boxes.some(b=>p.x>b.x+.5&&p.x<b.x+b.width-.5&&p.y>b.y+.5&&p.y<b.y+b.height-.5))return false;}return true;});}'''))
            check(label+' branches avoid label ink',page.locator('#net .hierarchy-branch').evaluate_all('''es=>{const boxes=[...document.querySelectorAll('#net text:not(.domain-toggle)')].map(e=>e.getBBox());return es.every(e=>{const length=e.getTotalLength();for(let i=0;i<=length;i+=1){const p=e.getPointAtLength(i);if(boxes.some(b=>p.x>b.x+.5&&p.x<b.x+b.width-.5&&p.y>b.y+.5&&p.y<b.y+b.height-.5))return false;}return true;});}'''))
            check(label+' every junction names an aggregate branch',page.locator('#net .aggregate-branch').count()>0 or page.locator('#net .domain-junction').count()==0)
            check(label+' branches connect the root to every visible domain and project',page.locator('#net').evaluate('''svg=>{
                const paths=[...svg.querySelectorAll('.hierarchy-branch')],segments=[];
                for(const path of paths){
                    const tokens=path.getAttribute('d').match(/[A-Z]|-?\\d+(?:\\.\\d+)?/g);let x=0,y=0;
                    for(let i=0;i<tokens.length;){const command=tokens[i++];if(command==='M'){x=+tokens[i++];y=+tokens[i++];continue;}let nx=x,ny=y;if(command==='H')nx=+tokens[i++];else if(command==='V')ny=+tokens[i++];else return false;segments.push({x1:Math.min(x,nx),x2:Math.max(x,nx),y1:Math.min(y,ny),y2:Math.max(y,ny)});x=nx;y=ny;}
                }
                const root=svg.querySelector('.network-root'),shapes=[root,...svg.querySelectorAll('.domain-junction,.net-node')];
                if(shapes.length===1)return true;
                const boxes=shapes.map(group=>{
                    const shape=group.querySelector('rect,circle.focus-root')||group.querySelector(':scope > circle');
                    if(shape){const b=shape.getBBox();return {x1:b.x,x2:b.x+b.width,y1:b.y,y2:b.y+b.height};}
                    const mark=group.querySelector(':scope > g'),b=mark.getBBox(),m=mark.transform.baseVal.consolidate().matrix;
                    return {x1:b.x+m.e,x2:b.x+b.width+m.e,y1:b.y+m.f,y2:b.y+b.height+m.f};
                });
                const items=segments.concat(boxes),parents=items.map((_,i)=>i),find=i=>parents[i]===i?i:parents[i]=find(parents[i]);
                function touch(a,b){return a.x1<=b.x2+2 && a.x2+2>=b.x1 && a.y1<=b.y2+2 && a.y2+2>=b.y1;}
                items.forEach((a,i)=>items.slice(i+1).forEach((b,j)=>{if(touch(a,b))parents[find(i)]=find(i+j+1);}));
                return boxes.every((_,i)=>find(segments.length+i)===find(segments.length));
            }'''))

        ready(preview.as_uri()+'#sel=7')
        check('Deep Field is the default under a light system preference',page.locator('body').evaluate('e=>getComputedStyle(e).backgroundColor')=='rgb(4, 7, 14)')
        check('summary follows header KPIs and precedes network',page.evaluate("document.querySelector('#dream-blk').previousElementSibling.id==='kpis' && document.querySelector('#dream-blk').nextElementSibling.id==='network-blk'"))
        check('stable section hooks are retained',all(page.locator('#'+s).count()==1 for s in ['traj','trend','rigor','dream-blk','pass-blk','network-blk','history-blk','entries-blk','audit','verify','dream-arc','net-chips','net-detail']))
        # ⚠ THE THIRD STATE — and the reason this check exists at all. MEASURED by a coverage lens:
        # mutating the `"fault"` meter sentinel to `var fault=false` left BOTH suites green,
        # because no fixture carried an `unmeasurable` key anywhere, so the arm was unreachable and
        # the end-user archive drew a confident green `0% · 0/1500` for an index nobody could read.
        # The page is built HERE rather than added to `sample()`: a faulted cycle there would change
        # the cycle COUNT, and `#sel=N` is hardcoded at 22 sites with `7` as the last cycle.
        check('a MEASURED index still shows its percentage (the control for the fault below)',
              page.evaluate("()=>{var k=document.querySelector('#kpis').textContent;"
                            "return k.indexOf('%')>=0 && k.indexOf('UNMEASURABLE')<0;}"))
        _ft = json.loads(json.dumps(record))
        for _b in ("index", "claude_md", "global_claude_md"):
            _ft["budget"][_b]["unmeasurable"] = True
        # ⚠ A NON-ZERO `index_mismatch` is REQUIRED for the store-checks assertion below to
        # discriminate: `sections.js` gates the entry on `num(...) > 0`, so a zero count would make
        # the check pass whether or not the exemption exists. A coverage lens measured that
        # dropping the exemption left BOTH suites green — the fixture had no drift to exempt.
        _ft["health"] = {"schema_drift": {"missing_node_type": 0, "malformed_scope": 0,
                                          "malformed_origin": 0, "index_mismatch": 3}}
        fixture('faulted-gauges', _ft, cycles=[_ft])
        check('an UNMEASURABLE index is never drawn as a confident number — not on the KPI strip '
              '(the first thing a reader scans) and not on the meter',
              page.evaluate("()=>{var k=document.querySelector('#kpis');var m=document.querySelector('#m-index');"
                            "var kt=k?k.textContent:'';var mt=m?m.textContent:'';"
                            "return kt.indexOf('UNMEASURABLE')>=0 && mt.indexOf('%')<0 "
                            "&& mt.toLowerCase().indexOf('unmeasurable')>=0;}"))
        # ⚠ THE OBSERVABLE IS THE STATE CHIP, not the text. Two measured attempts got this wrong
        # before it: `document.body.textContent` reads the bundles INLINED AS JS, so the first cut
        # found the phrase in THE COMMENT EXPLAINING IT (this repo's own "a text check reads prose
        # about its subject" trap), and `#store-evidence` never carries it at all — measured, the
        # phrase exists only inside the `<script>` tag. `#store-checks`'s `.health-status` is what
        # the reader actually sees, and it moves on exactly this finding.
        _state52 = ("()=>{var e=document.getElementById('store-checks');if(!e)return '?';"
                    "var s=e.querySelector('.health-status');return s?s.textContent.trim():'?';}")
        check('an UNMEASURABLE index does NOT raise the archive\'s store-check — an index nobody '
              'could open names NOTHING, so every fact reads as un-indexed and the `index↔file` '
              'count is manufactured by the read failure, not observed in the store',
              page.evaluate(_state52) != 'Needs attention')
        _hd = json.loads(json.dumps(record))
        _hd["health"] = {"schema_drift": {"missing_node_type": 0, "malformed_scope": 0,
                                          "malformed_origin": 0, "index_mismatch": 3}}
        fixture('measured-drift', _hd, cycles=[_hd])
        check('…and a MEASURED index with the SAME drift count DOES raise it — the exemption is a '
              'branch on the fault, not the removal of a finding',
              page.evaluate(_state52) == 'Needs attention')
        # ⚠ `fixture()` NAVIGATES the shared page, and every check after this one assumes the
        # default `#sel=7` view — measured: without this restore, the very next check ("opening the
        # current dream reveals and focuses its summary", which asserts `#sel=7`) failed, because
        # it was looking at the faulted page. A check that leaves the page somewhere else is a
        # check that breaks its neighbours.
        ready(preview.as_uri()+'#sel=7')
        # v0.4.35 (RC-3): the expectation moved with the matcher. Selection 7 is the fixture's
        # LAST cycle, whose entries are `added, reconciled, corrected, skipped`; the ladder used
        # to count three of those five names, read 2 writes, and stamp LIGHT PASS. `reconciled`
        # relocates a pointer — a store modification — so the corrected count is 3 and the cycle
        # lands on SUBSTANTIAL. Measured across all eight cycles, one process per tree: this is
        # the ONLY cycle whose stamp moves.
        check('summary names recorded outcome and evidence',all(t in page.locator('#dream-summary').inner_text() for t in ['SUBSTANTIAL PASS','5 confirmed claims','4 observed file operations','1 unverifiable claim']))
        check('summary names the unverifiable claim at the warning (the v0.4.22 carrier join)', '1 unverifiable claim — cache-expiry-claim' in page.locator('#dream-summary').inner_text())
        captured_prose=[record['dream']['sleep']]+record['dream']['beats']+[record['dream']['wake']]
        check('complete narration appears once in captured order',page.locator('#dream-arc .dream-voice').all_text_contents()==[s[1:-1] for s in captured_prose])
        check('narration needs no phase buttons or expansion',page.locator('#dream-arc button, #dream-arc details, #dream-arc .passage-label').count()==0)
        check('captured voice alone uses Georgia italic',page.locator('#dream-arc .dream-voice').first.evaluate("e=>getComputedStyle(e).fontFamily.includes('Georgia') && getComputedStyle(e).fontStyle==='italic'") and not page.locator('#dream-summary').evaluate("e=>getComputedStyle(e).fontFamily.includes('Georgia')"))
        check('initial fleet shows every captured domain and expands the trigger domain',page.locator('.domain-junction').count()==3 and page.locator('.net-node').count()==3 and page.locator('.domain-junction[aria-expanded="true"]').get_attribute('data-domain')=='work')
        concise_network('initial fleet')
        # The dot keys say "this project / other project" — a statement the FLEET can make and a
        # focused view cannot, because no focused view marks one node of a set. Both directions are
        # asserted separately, and both are guarded on count for the same reason: pre-pass,
        # inspect() replaced the legend wholesale, so the keys are ABSENT rather than hidden, and
        # is_hidden() reads absence as hidden — the focused half alone would pass vacuously against
        # the very defect §2.4 repaired.
        legend_keys=page.locator('#net-legend .legend-keys')
        check('the fleet legend shows its dot keys beside a fleet reading',
              legend_keys.count()==1 and legend_keys.is_visible()
              and all(k in legend_keys.inner_text() for k in ['this project','other project'])
              and page.locator('#net-legend #net-legend-note').inner_text().strip()!='')
        check('one view selector replaces the network button lists',page.locator('#net-view').count()==1 and page.locator('#net-view optgroup').all_text_contents() and page.locator('#net-controls > button, #net-groups button').count()==0)
        check('network attributes its saved snapshot to the selected dream','this dream' in page.locator('.network-attribution').inner_text().lower() and captured_network()==record['network'])
        check('each report section identifies its evidence source',all(page.locator('#'+s).is_visible() and 'Source' in page.locator('#'+s).inner_text() for s in ['summary-source','activity-source','health-source','ledger-source']))
        lower_summary('initial report')
        page.locator('#dream-blk > .shead').click();page.locator('.open-dream').scroll_into_view_if_needed()
        before_open=page.evaluate('scrollY');page.locator('.open-dream').click()
        check('opening the current dream reveals and focuses its summary without a dead same-hash link',page.url.endswith('#sel=7') and page.locator('#dream-summary').is_visible() and page.locator('#dream-blk > .shead').evaluate('e=>e===document.activeElement') and page.evaluate('scrollY')<before_open)
        page.locator('#dream-summary [data-evidence="entries-blk"]').click()
        check('decision evidence jumps to the ledger heading rather than a nested disclosure',page.locator('#entries-blk > .shead').evaluate('e=>e===document.activeElement') and page.locator('#entries .decision-detail[open]').count()==0)
        geometry('initial fleet')
        network_view('group','release-kit')
        check('group view has an independent permission root and exact membership',page.locator('.network-root').text_content().startswith('release-kit') and set(page.locator('.net-node').evaluate_all('es=>es.map(e=>e.dataset.node)'))=={'atlas-api','eval-lab','release-tools'})
        check('group context distinguishes permission from physical delivery',all(t in page.locator('#net-detail').inner_text().lower() for t in ['permission','receiv']) and 'not delivery' in page.locator('#net-legend').inner_text())
        check('a sharing-group view reads its own kind into the trail',page.locator('#net-breadcrumbs').inner_text().split()==['Captured','fleet','›','Sharing','group','›','release-kit'])
        concise_network('group view')
        check('group membership is presented once on the map',page.locator('#net-detail .network-members, #net-detail .network-holders').count()==0 and 'atlas-api' not in page.locator('#net-detail').inner_text())
        geometry('cross-domain group')
        network_view('group','api-contract')
        check('overlapping groups do not retain previous members',set(page.locator('.net-node').evaluate_all('es=>es.map(e=>e.dataset.node)'))=={'atlas-api','atlas-web'})
        network_view('fleet')
        page.locator('#net-view').focus();page.keyboard.press('End')
        check('keyboard view selection reaches the final sharing group without losing select focus',page.locator('#net').get_attribute('data-kind')=='group' and page.locator('.network-root').text_content().startswith('api-contract') and page.locator('#net-view').evaluate('e=>e===document.activeElement'))
        page.keyboard.press('Home')
        check('keyboard view selection returns to all captured projects',page.locator('#net').get_attribute('data-kind')=='fleet' and page.locator('#net-view').input_value()=='fleet')
        # The keyboard path. Activating a node must move the graph to that project AND leave focus
        # on the node: it used to land on .network-root, whose own handler is reset(), so the next
        # Enter undid the activation. This check is the reversal of that pin — it fails pre-fix.
        page.locator('.net-node[data-current="true"]').focus();page.keyboard.press('Enter')
        check('keyboard activation reaches the activated project and keeps focus on that node',page.locator('#net').get_attribute('data-kind')=='project' and page.locator('.net-node[data-current="true"]').evaluate("e=>{const s=getComputedStyle(e);return e===document.activeElement && e.matches(':focus-visible') && s.outlineStyle!=='none' && parseFloat(s.outlineWidth)>0;}"))
        # The pointer path, on a DIFFERENT node: the anchor must follow the click. It was wired to
        # the fleet capture trigger, so clicking atlas-web left atlas-api stroked and labelled
        # "This project" — the map answered a question the user never asked.
        page.locator('.net-node[data-node="atlas-web"]').click()
        check('a pointer click re-anchors the graph to the clicked project, not the capture trigger',page.locator('.net-node[data-current="true"]').get_attribute('data-node')=='atlas-web' and page.locator('.net-node[data-current="true"]').evaluate("e=>e===document.activeElement && !e.matches(':focus-visible') && (getComputedStyle(e).outlineStyle==='none'||parseFloat(getComputedStyle(e).outlineWidth)===0)"))
        check('the position trail names the focused view and offers exactly one way back',page.locator('#net-breadcrumbs').inner_text().split()==['Captured','fleet','›','Project','›','atlas-web'] and page.locator('#net-breadcrumbs button').count()==1)
        page.locator('#net-breadcrumbs button').click()
        check('the trail back-control returns to the fleet and leaves no trail behind',page.locator('#net').get_attribute('data-kind')=='fleet' and page.locator('#net-breadcrumbs').inner_text()=='' and page.locator('#net-breadcrumbs button').count()==0)
        # ...and it is the SECOND control whose own activation destroys it: draw() empties
        # #net-breadcrumbs, so the button just clicked has no successor to restore focus to. The
        # repair lives at the redraw rather than at this control, so the assertion is the outcome a
        # user feels — focus on a real control inside the widget, never stranded on <body>, where
        # the next Tab restarts from the top of the page. The crumb is a native <button> carrying
        # an onclick, so Enter synthesizes this same click and there is ONE handler, not two; both
        # modalities are still asserted, because the focus ring they earn differs and because
        # "one handler" is itself a claim worth pinning rather than reasoning about.
        check('the trail back-control hands focus to a control in the widget, not to body',
              page.evaluate("()=>{const a=document.activeElement;return !!a&&a!==document.body&&a!==document.documentElement&&!!a.closest('#network-blk');}"))
        page.locator('.net-node[data-node="atlas-api"]').click()
        page.locator('#net-breadcrumbs button').focus();page.keyboard.press('Enter')
        check('the same back-control reached by keyboard also lands focus in the widget',
              page.locator('#net').get_attribute('data-kind')=='fleet' and page.evaluate("()=>{const a=document.activeElement;return !!a&&a!==document.body&&a!==document.documentElement&&!!a.closest('#network-blk');}"))
        # Back to atlas-api for the fact flow below: those checks select release-checks, which
        # atlas-web does not hold, so staying on the project clicked above would strand them.
        page.locator('.net-node[data-node="atlas-api"]').click()
        concise_network('project selection')
        check('project context offers shared facts without token or identity accounting','release-checks' in page.locator('#net-detail .network-facts').inner_text() and '984' not in page.locator('#net-detail').inner_text() and 'sample-atlas-api' not in page.locator('#net-detail').inner_text())
        fact_id=next(f['fact_id'] for f in record['network']['fact_holdings'] if f['name']=='release-checks')
        page.locator('#net-detail [data-fact-id="'+fact_id+'"]').click()
        # The other activation whose element its own redraw destroys: inspect() rewrites
        # #net-detail, so the fact button just clicked is gone by the time draw() returns. The
        # redraw-level repair lands focus on the root — assert it is a real control and, since this
        # activation came from the pointer, that it carries no keyboard rectangle.
        check('switching from keyboard to pointer removes the graph focus rectangle and strands no focus on body',page.locator('.network-root').evaluate("e=>e===document.activeElement && (getComputedStyle(e).outlineStyle==='none'||parseFloat(getComputedStyle(e).outlineWidth)===0)"))
        check('focused fact names its subject and leaves exact holder names on the graph','release-checks' in page.locator('.network-selection-name').inner_text() and set(page.locator('.net-node').evaluate_all('es=>es.map(e=>e.dataset.node)'))=={'atlas-api','eval-lab','release-tools'})
        concise_network('focused fact')
        check('focused fact does not repeat the graph as a holder list','atlas-api' not in page.locator('#net-detail').inner_text() and 'Holder references' not in page.locator('#net-detail').inner_text())
        # The escape hatch. reveal() has to open #record-json's own <details> ancestor before it
        # can scroll to and focus it, so a link that merely moved the viewport would pass a
        # visibility check while leaving the record shut.
        page.locator('.network-record-link').click()
        check('the record link opens the complete captured record and lands focus inside it',page.locator('#record-json').evaluate("e=>{const d=e.closest('details');return d!==null&&d.open&&e===document.activeElement;}"))
        geometry('canonical fact')
        network_view('fleet')
        page.locator('#net-search').fill('dotfiles')
        check('search reaches a project outside the initial domain',page.locator('.net-node').count()==1 and page.locator('.net-node').get_attribute('data-node')=='dotfiles')
        page.locator('.domain-junction[aria-expanded="true"]').click()
        check('a searched domain can be collapsed and expanded',page.locator('.net-node').count()==0)
        page.locator('.domain-junction[aria-expanded="false"]').click()
        check('expanding a searched domain restores its matching project',page.locator('.net-node').count()==1 and page.locator('.net-node').get_attribute('data-node')=='dotfiles')
        # dotfiles has no groups and no edges, so both counts are absent rather than zero. The rule
        # is that absence and emptiness never stack and a count renders only when it is >0 — so the
        # summary must say so in words and must not print a bare 0 next to an unmeasured field.
        page.locator('.net-node[data-node="dotfiles"]').click()
        summary=page.locator('#net-detail .network-summary').inner_text()
        check('an unshared project reports absence as absence rather than as a measured zero',summary.count('None recorded')>=2 and re.search(r'\b0\b',summary) is None)
        network_view('fleet')
        check('adverse verification is open and routine store evidence is collapsed',page.locator('#verification-evidence').get_attribute('open') is not None and page.locator('#store-checks').get_attribute('open') is None)
        check('three independent evidence states replace duplicate health cards',page.locator('#health-summary:visible').count()==0 and sorted(page.locator('#verification-evidence .health-status, #store-checks .health-status, #file-changes .health-status').evaluate_all('es=>es.map(e=>e.dataset.state)'))==['Needs attention','Recorded clear','Recorded clear'])
        page.locator('#dream-summary [data-evidence="file-changes"]').click()
        check('summary evidence link opens the file disclosure without navigation',page.url.endswith('#sel=7') and page.locator('#audit').is_visible())
        check('evidence jumps retain the native disclosure tab stop',page.locator('#file-changes > summary').evaluate('e=>e===document.activeElement && e.tabIndex===0') and page.locator('#file-changes > summary').get_attribute('tabindex') is None)
        open_evidence()
        check('workflow verdicts, chains, skill use and registrar decisions are accessible',all(page.locator('#'+s).is_visible() for s in ['dstl-verdict','dstl-chains-list','dstl-used-list','demo-verdict','reg-board']))
        check('raw captured record retains every source subtree',all(json.loads(page.locator('#record-json').text_content())[k]==v for k,v in record.items()))
        diff_checks=[]
        for button in page.locator('.file-evidence-link,.nm-diff').all():
            key=button.get_attribute('data-p');button.click()
            expected=next(iter(diffs.values()))[key]['lines']
            diff_checks.append(all(line['s'] in page.locator('#dmodal-body').inner_text() for line in expected))
            page.locator('#dmodal-x').click()
            diff_checks.append(button.evaluate('e=>e===document.activeElement'))
        check('every visible file and ledger diff action opens its own captured evidence and restores focus',all(diff_checks))
        disclosure_checks=[]
        page.locator('#app details').evaluate_all('es=>es.forEach(e=>e.open=true)')
        for summary in page.locator('#app summary').all():
            if not summary.is_visible():continue
            summary.click();closed=not summary.evaluate('e=>e.parentElement.open');summary.click()
            disclosure_checks.append(closed and summary.evaluate('e=>e.parentElement.open'))
        check('every captured disclosure has a working open and close action',all(disclosure_checks))
        page.locator('#app details').evaluate_all('es=>es.forEach(e=>e.open=false)');open_evidence()
        page.locator('.file-evidence-link').first.click()
        check('observed file opens its captured diff with dialog semantics',page.get_by_role('dialog').is_visible() and page.locator('#dmodal-x').evaluate('e=>e===document.activeElement') and page.locator('#app').evaluate('e=>e.inert'))
        page.keyboard.press('Tab')
        check('diff body is keyboard reachable inside the focus trap',page.locator('#dmodal-body').evaluate('e=>e===document.activeElement'))
        page.keyboard.press('Tab');check('diff focus cycles back to Close',page.locator('#dmodal-x').evaluate('e=>e===document.activeElement'))
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
        for selector in ('#activity-controls button:not(:disabled)','.report-nav button','.activity-scroll','#file-changes > summary'):
            control=page.locator(selector).first;control.evaluate('e=>{if(!e.matches("button,summary"))e.tabIndex=0;e.focus();}');page.keyboard.press('ArrowLeft')
            check('local control arrows stay in the current dream: '+selector,page.url.endswith('#sel=7'))
        page.locator('.activity-cycle').first.focus();page.keyboard.press('Enter')
        check('activity selection inspects locally without archive navigation',page.url.endswith('#sel=7') and 'Dream 1' in page.locator('#activity-inspector').text_content() and page.locator('.open-dream').get_attribute('href')=='#sel=0')
        check('activity exposes exact decision categories without a competing category legend',all(t in page.locator('.activity-cycle[aria-pressed="true"]').get_attribute('aria-label') for t in ['added','corrected']) and 'added' not in page.locator('#activity-legend').inner_text() and 'writes' not in page.locator('#activity-legend').inner_text())
        page.locator('#activity-inspector details > summary').click()
        check('activity keeps mutations and usage windows in optional cycle details',all(t in page.locator('#activity-inspector').inner_text() for t in ['added','corrected','Observed mutations','Usage window','Rigor']))
        resize(768);resize(1440)
        check('resizing activity preserves its locally selected dream',page.locator('.activity-cycle[aria-pressed="true"]').get_attribute('data-cycle')=='0' and 'Dream 1' in page.locator('#activity-inspector').text_content() and page.url.endswith('#sel=7'))
        page.locator('#activity-table summary').click()
        check('historical table preserves fact counts and cadence for every cycle',page.locator('#activity-table tbody tr').count()==8 and 'never summed' in page.locator('#activity-table').inner_text())
        page.locator('#activity-table summary').click()
        page.locator('#dens-tog').click();page.locator('#dens-tog').focus();page.keyboard.press('ArrowLeft')
        check('density exposes its active state and local arrows do not navigate archives',page.locator('#dens-tog').get_attribute('aria-pressed')=='true' and page.url.endswith('#sel=7'))
        page.evaluate('document.body.tabIndex=-1;document.body.focus()');page.keyboard.press('ArrowLeft')
        page.wait_for_function("location.hash==='#sel=6' && document.querySelector('#dreamnav .pos').textContent.includes('dream 7 /')")
        check('archive arrow navigation retains density and resets focused networks',page.locator('body').evaluate("e=>e.classList.contains('compact')") and page.locator('.grant-edge').count()==0)
        check('network source attribution follows the selected historical dream','this dream' in page.locator('.network-attribution').inner_text().lower() and json.loads(page.locator('#record-json').text_content())['marker']['timestamp']==history[6]['marker']['timestamp'])
        page.keyboard.press('ArrowRight');page.wait_for_function("location.hash==='#sel=7' && document.querySelector('#dreamnav .pos').textContent.includes('dream 8 /')");page.locator('#dens-tog').click();page.keyboard.press('Escape')
        page.wait_for_function("document.querySelector('#archive').style.display!=='none'")
        check('archive contains every captured cycle',page.locator('.arch-row').count()==8)
        page.locator('#f-sort').select_option('tsRaw:1')
        check('archive sorting remains functional',page.locator('.arch-row').first.get_attribute('href')=='#sel=0')
        sort_checks=[]
        for value in page.locator('#f-sort option').evaluate_all('es=>es.map(e=>e.value)'):
            page.locator('#f-sort').select_option(value);key,direction=value.split(':')
            indices=page.locator('.arch-row').evaluate_all('es=>es.map(e=>Number(e.getAttribute("href").split("=")[1]))')
            values=[history[i]['marker']['timestamp'] if key=='tsRaw' else history[i]['budget']['index']['after_tokens'] if key=='ix' else sum(e['action'] in ('added','corrected','deleted','reconciled') for e in history[i]['entries']) for i in indices]
            sort_checks.append(values==sorted(values,reverse=direction=='-1'))
        check('every archive sort control orders the corresponding captured values',all(sort_checks))
        page.locator('#f-rig').select_option('SUBSTANTIAL')
        check('archive rigor filtering remains functional','shown' in page.locator('#f-count').inner_text())
        for width in (320,390,768,1440):
            resize(width);contained('archive '+str(width))
            check('archive columns remain accessible '+str(width),page.locator('.arch-row .hh').first.is_visible() and page.locator('.arch-row .en').first.is_visible())
        page.locator('a.arch-row[href="#sel=7"]').click();page.wait_for_function("document.querySelector('#app').style.display!=='none'")
        # 'deepfield' is the bare root palette (what 'dark' used to mean), so it REPLACES
        # 'dark' in this list rather than joining it — listing both would exercise the same
        # CSS twice. 'nocturne' is its own named block, so it is a distinct palette and both
        # must be tested.
        for theme in ['deepfield','nocturne','original','light','auto']:
            page.evaluate('(theme)=>{document.documentElement.dataset.theme=theme;localStorage.setItem("cm-theme",theme);}',theme)
            for width in (320,390,768,1440):
                resize(width);contained(theme+' '+str(width));geometry(theme+' '+str(width))
                narration_layout(theme+' '+str(width))
                report_layout(theme+' '+str(width));lower_layout(theme+' '+str(width));controls_layout(theme+' '+str(width))
                check('brief network context stays below the graph '+theme+' '+str(width),page.locator('#net-detail').bounding_box()['y']>=page.locator('.map-scroll').bounding_box()['y']+page.locator('.map-scroll').bounding_box()['height']-1)
            visual_hierarchy(theme)
            # The map's own surfaces — the position trail, the selection summary and the record
            # link — render ONLY in a focused view, so the fleet passes above can never see them:
            # a selector list walked in one view is blind to every surface another view owns.
            # select_option fires change even when it re-selects, so this pins the fleet first.
            page.locator('#net-view').select_option('fleet')
            page.locator('.net-node[data-current="true"]').click()
            visual_hierarchy(theme+' focused');controls_layout(theme+' focused')
            # report_layout belongs here for the same reason the two above do, and it is the one
            # whose text-in-box clause the new surfaces were added to: that clause is blind where
            # the surfaces do not render, and the fleet pass — the only place it used to run — is
            # exactly where they do not.
            report_layout(theme+' focused')
            # Same two legend elements as the fleet check above, opposite expectation — read that
            # check for why the count guard is what stops absence from reading as hiding. The count
            # guard covers the KEYS only, so alone it let the whole legend be display:none'd and
            # still read as correct: all three clauses below stay true of a hidden subtree, and
            # inner_text() returns text from one. The visibility clause is what makes the other
            # three a reading about a legend the reader can actually see.
            check(theme+' focused drops the fleet dot keys and keeps its own reading',
                  page.locator('#net-legend').is_visible()
                  and page.locator('#net-legend .legend-keys').count()==1
                  and page.locator('#net-legend .legend-keys').is_hidden()
                  and page.locator('#net-legend #net-legend-note').inner_text().strip()!='')
            focused_fit(theme+' focused')
            # The mark must survive the pointer. The cue is NOT level with the anchor rule: it
            # carries two :not() guards and scores (1,4,1) against the anchor's (1,2,1), so it wins
            # outright and no source order between them can save the anchor — the repair is the
            # :not([data-current="true"]) it carries, which excludes the anchor from the rule
            # entirely. Measured with that guard stripped, the anchor's plate fill goes --card ->
            # --paper2 under the pointer while its stroke holds: the fill half of the reading below,
            # and the defect. Theme-independent — the palettes are :root[data-theme] token blocks
            # and contain no node rule, so no theme can reorder anything here.
            # Park the pointer and take the anchor out of :focus first. The cue fires on
            # `:hover, :focus` together, so an anchor still focused from the click that opened this
            # view has ALREADY been repainted — measuring its "rest" state there compares two
            # repainted readings and the check passes with the defect in place. Parking also matters
            # because the click left the pointer somewhere on the graph.
            page.locator('#net-view').focus();page.mouse.move(0,0)
            read="e=>{const s=getComputedStyle(e);return {mark:s.fill+'|'+s.stroke,w:s.strokeWidth};}"
            rest=page.locator('.net-node[data-current="true"] rect').evaluate(read)
            page.locator('.net-node[data-current="true"]').hover()
            hovered=page.locator('.net-node[data-current="true"] rect').evaluate(read)
            page.mouse.move(0,0)
            # Two-sided: the mark holds, AND the hover still answers on width. Asserting only the
            # first would pass if hover feedback were deleted outright instead of scoped.
            check(theme+' focused keeps the anchor mark under the pointer while still answering it',rest['mark']==hovered['mark'] and rest['w']!=hovered['w'])
            page.locator('#net-breadcrumbs button').click()
            page.screenshot(path=str(out/('report-'+theme+'.png')),full_page=True)
            page.emulate_media(media='print')
            check(theme+' prints with white surfaces and readable ink',page.locator('body').evaluate('e=>getComputedStyle(e).color')=='rgb(23, 43, 67)' and page.locator('html').evaluate('e=>getComputedStyle(e).colorScheme')=='light')
            narration_layout(theme+' print')
            page.emulate_media(media='screen')
        page.evaluate("localStorage.setItem('cm-theme','original')");page.reload();page.wait_for_function("document.querySelector('#boot').style.display==='none'")
        check('Original persists and names its next theme',page.locator('#theme-tog').inner_text()=='◒ Original' and page.locator('#theme-tog').get_attribute('aria-label')=='Color theme: Original. Switch to Light')
        page.locator('#theme-tog').click();check('Light theme control works',page.locator('html').get_attribute('data-theme')=='light')
        page.locator('#theme-tog').click();page.emulate_media(color_scheme='dark');check('System responds to changed device preference',page.locator('body').evaluate('e=>getComputedStyle(e).backgroundColor')=='rgb(4, 7, 14)')
        page.locator('#theme-tog').click();check('theme loop returns to Deep Field',page.locator('#theme-tog').inner_text()=='◉ Deep Field')
        check('reduced motion disables animated permission branches',page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches") and page.locator('html').evaluate("e=>getComputedStyle(e).scrollBehavior!=='smooth'"))

        # Focused evidence discriminators, including absent vs measured zero.
        sparse={'project':'sparse','marker':{'commit':'old','timestamp':'2026-08-01T00:00:00Z'}}
        fixture('sparse',sparse);open_evidence()
        check('missing observations stay missing','not measured' in page.locator('#lead-head').inner_text() and page.locator('#verification-evidence > summary').inner_text().count('Not captured')>0 and 'Not captured' in page.locator('#verify').inner_text())
        check('an absent decision ledger stays missing rather than becoming zero','not captured' in page.locator('#entries').inner_text().lower())
        check('absent topology never claims a measured empty network','Network details were not captured' in page.locator('#net-cap').inner_text() and page.locator('#net-note').inner_text()=='Not captured')
        check('missing network presents missing capture rather than empty fleet statistics','0 projects' not in page.locator('#net-detail').inner_text() and '0 domains' not in page.locator('#net-detail').inner_text())
        check('missing narration remains explicit without invented prose',page.locator('#dream-arc').inner_text()=='Dream narration: Not captured' and page.locator('#dream-arc .dream-voice').count()==0)
        partial=copy.deepcopy(record);partial.update(verification={'confirmed':4},audit={'memory':{'created':1}},usage={'mentions':2},health={'broken':['missing-source']},preflight={'at':'2026-09-05T12:01:00Z','fails':['sqlite-module'],'warns':['no-git']},remediation={'over_ceiling':True,'required':True})
        fixture('partial',partial);open_evidence()
        check('partial claims never infer healthy zeroes','4' in page.locator('#verify').inner_text() and page.locator('#verify').inner_text().lower().count('not captured')>=3 and 'Partially captured' in page.locator('#verification-evidence > summary').inner_text())
        check('readable preflight time, exact IDs and unresolved attention remain conspicuous',all(t in page.locator('#store-evidence').inner_text() for t in ['Sep 5, 2026','sqlite-module','no-git']) and all(t in page.locator('#attention-items').inner_text() for t in ['Hard ceiling','Unresolved index remediation','missing-source']))
        check('partial physical changes and reads remain partial','not fully captured' in page.locator('#audit').inner_text() and 'not captured' in page.locator('#usage-evidence').inner_text().lower())
        zero=copy.deepcopy(record);zero.update(verification={'confirmed':0,'corrected':0,'unverifiable':0},audit={'operations':[]},usage={'reads':0,'mentions':0},scope={'git_commits':0,'session_candidates':0},entries=[])
        zero['budget']['claude_md']={'after_tokens':0};fixture('zero',zero);open_evidence()
        check('zero observations never acquire a fabricated one-unit range','0–1' not in page.locator('#trend').text_content() and '0–1' not in page.locator('#activity-inspector').inner_text())
        check('recorded zero survives in raw budget, mutation and recall evidence',json.loads(page.locator('#record-json').text_content())['budget']['claude_md']['after_tokens']==0 and '0 observed file operations' in page.locator('#audit').inner_text() and '0' in page.locator('#usage-evidence').inner_text())
        check('an explicitly empty ledger reports no recorded decisions','no decisions were recorded' in page.locator('#entries').inner_text().lower() and 'not captured' not in page.locator('#entries').inner_text().lower())
        check('recorded clear is limited to complete captured evidence',page.locator('.health-status[data-state="Recorded clear"]').count()==3)
        sparse_workflow=copy.deepcopy(sparse);sparse_workflow.update(distill={},demotion={},workflow_proposals={})
        fixture('sparse-workflow',sparse_workflow);open_evidence()
        check('empty workflow captures never invent zero counts or dormant decisions',all(t not in page.locator('#pass-blk').inner_text().lower() for t in ['0 recurring','0 eligible','0 windows','dormant —','nothing distinctive showed up']))
        check('empty workflow captures explain their missing evidence','not captured' in page.locator('#pass-blk').inner_text().lower())
        pending=copy.deepcopy(record)
        pending['workflow_proposals']['candidates'][0].update(disposition='awaiting-confirmation',reason='Awaiting the recorded operator decision.')
        pending['workflow_proposals']['verdict']='awaiting: release checks needs confirmation.'
        fixture('pending-workflow',pending)
        check('pending workflow decisions open their relevant evidence by default',page.locator('#workflow-evidence').get_attribute('open') is not None and page.locator('#registrar-blk').get_attribute('open') is not None and 'release checks' in page.locator('#reg-board').inner_text())
        declined=copy.deepcopy(pending)
        declined['workflow_proposals']['candidates'][0]['disposition']='declined'
        declined['workflow_proposals']['verdict']='declined: the existing command covers the workflow.'
        fixture('declined-workflow',declined)
        check('resolved declines retain evidence without looking pending',page.locator('#workflow-evidence').get_attribute('open') is None and page.locator('#registrar-blk').get_attribute('open') is None)
        open_evidence()
        check('the complete decline decision remains accessible','declined' in page.locator('#reg-board').inner_text() and 'existing command' in page.locator('#reg-verdict').inner_text())
        malformed=copy.deepcopy(record);malformed['dream']['beats']=['first',None,{'captured':'object'},'last'];fixture('malformed-dream',malformed)
        check('malformed passages remain accessible in place without invented phase completion',page.locator('#dream-arc p').all_text_contents()==[record['dream']['sleep'][1:-1],'first','Passage 2: Not captured','Passage 3: {"captured":"object"}','last',record['dream']['wake'][1:-1]])
        check('capture notes remain distinct from narrated prose',page.locator('#dream-arc .dream-capture-note').evaluate_all("es=>es.length===2 && es.every(e=>getComputedStyle(e).fontStyle==='normal')"))
        wrapped=copy.deepcopy(record)
        wrapped['dream']={'sleep':'> *The checks settle.*','beats':['*One lesson\ncontinues on the next line.*','**Another lesson stays.**\n\n_The next paragraph follows._','Literal 2 * 3, path/*.md, and snake_case stay.','*The first paragraph stands alone.*\n\n*The second has its own wrapping.*'],'wake':'***The cycle rests.***'}
        fixture('wrapped-narration',wrapped)
        check('Markdown wrappers disappear while paragraph boundaries and literal symbols survive',page.locator('#dream-arc .dream-voice').all_text_contents()==['The checks settle.','One lesson\ncontinues on the next line.','Another lesson stays.','The next paragraph follows.','Literal 2 * 3, path/*.md, and snake_case stay.','The first paragraph stands alone.','The second has its own wrapping.','The cycle rests.'])
        check('narration formatting never rewrites the captured record',json.loads(page.locator('#record-json').text_content())['dream']==wrapped['dream'])
        for width in (320,1440):
            resize(width);narration_layout('wrapped '+str(width));contained('wrapped '+str(width))
            if width==1440:
                check('a captured soft line break flows naturally when the sentence fits',page.locator('#dream-arc .dream-voice').nth(1).evaluate("e=>e.textContent.includes('\\n') && e.getBoundingClientRect().height<parseFloat(getComputedStyle(e).lineHeight)*1.5"))
            page.locator('#dream-blk').screenshot(path=str(out/('narration-'+str(width)+'.png')))
        partial_dream=copy.deepcopy(record);partial_dream['dream']={'sleep':'   ','beats':[],'wake':'*Only the waking was captured.*'};fixture('partial-narration',partial_dream)
        check('partially captured narration retains gaps and the recorded passage',page.locator('#dream-arc p').all_text_contents()==['Sleep: Not captured','Intermediate passages: Not captured','Only the waking was captured.'])
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

        long_copy=copy.deepcopy(record)
        long_identifier='captured-'+('reference1234567890'*12)
        long_url='https://evidence.example.test/claims/'+('verified-source-'*20)+'?reference='+('abcdef0123456789'*12)
        paragraph=' '.join(['Each captured lesson keeps its evidence and its place in the recorded story.']*12)
        long_copy['dream']={'sleep':'*'+paragraph+' '+long_url+'*','beats':['*A short sentence\ncontinues here.*','*'+paragraph+'\n\n'+paragraph+'*'],'wake':'*The record keeps every passage in order.*'}
        long_copy['entries'][0].update(name=long_identifier,reason=paragraph+' '+long_url,citation=long_url,action='reviewed-'+long_identifier)
        long_copy['usage']['window']=long_url
        long_copy['usage']['per_fact'][0]['name']=long_identifier
        long_copy['health']['broken']=[long_url]
        long_copy['preflight']['fails']=[long_identifier]
        long_copy['audit']['operations'][0]['path']=long_identifier+'.md'
        long_copy['distill']['top'][0]['t']=long_url
        fixture('long-report-copy',long_copy);open_evidence();page.locator('#activity-table > summary').click()
        page.locator('#entries details, #activity-inspector details').evaluate_all('es=>es.forEach(e=>e.open=true)')
        check('one captured emphasis wrapper can span multiple visible paragraphs',page.locator('#dream-arc .dream-voice').all_text_contents()==[paragraph+' '+long_url,'A short sentence\ncontinues here.',paragraph,paragraph,'The record keeps every passage in order.'])
        for width in (320,390,768,1440):
            resize(width);contained('long report '+str(width));narration_layout('long report '+str(width));report_layout('long report '+str(width));lower_layout('long report '+str(width));controls_layout('long report '+str(width))
            page.locator('#dream-blk').screenshot(path=str(out/('long-dream-'+str(width)+'.png')))
            page.locator('#history-blk').screenshot(path=str(out/('long-activity-'+str(width)+'.png')))
            page.locator('#entries-blk').screenshot(path=str(out/('long-ledger-'+str(width)+'.png')))
        check('full citations and declared file paths remain readable through decision details',long_url in page.locator('#entries').inner_text() and long_copy['entries'][0]['files'][0] in page.locator('#entries').inner_text())
        check('long report formatting preserves captured text and evidence exactly',all(json.loads(page.locator('#record-json').text_content())[key]==value for key,value in long_copy.items()))

        # The reported two-holder/single-domain view previously left its root
        # floating below the branch; collision-only geometry checks missed it.
        two_holders=copy.deepcopy(record)
        fact=next(f for f in two_holders['network']['fact_holdings'] if f['name']=='release-checks')
        fact.update(holder_sids=['sample-atlas-api','sample-atlas-web'],held_n=2)
        fixture('two-holder-fact',two_holders)
        network_view('fact','release-checks')
        check('small focused view names both holders without unrelated project totals',set(page.locator('.net-node').evaluate_all('es=>es.map(e=>e.dataset.node)'))=={'atlas-api','atlas-web'} and 'physical mirrors' not in page.locator('#net-detail').inner_text())
        check('a shared-fact view reads its own kind into the trail',page.locator('#net-breadcrumbs').inner_text().split()==['Captured','fleet','›','Shared','fact','›','release-checks'])
        concise_network('two-holder fact')
        for width in (1440,390,320):
            resize(width);geometry('two-holder fact '+str(width));focused_fit('two-holder fact '+str(width))
            check('sparse graph keeps its own height '+str(width),page.locator('.map-scroll').bounding_box()['height']<=page.locator('#net').bounding_box()['height']+24)
            page.locator('#network-blk').screenshot(path=str(out/('focused-fact-'+str(width)+'.png')))
        resize(390);page.locator('#network-blk > .shead').click();resize(320)
        check('network remains collapsed during a resize',not page.locator('#net').is_visible())
        page.locator('#network-blk > .shead').click()
        check('reopening after a hidden resize retains the selected fact',page.locator('#net').get_attribute('data-kind')=='fact' and set(page.locator('.net-node').evaluate_all('es=>es.map(e=>e.dataset.node)'))=={'atlas-api','atlas-web'})
        geometry('network reopened after hidden resize');contained('network reopened after hidden resize')
        resize(1440)

        partial_capture=copy.deepcopy(record);partial_capture['network']['capture']={'unresolved_identities':0}
        fixture('partial-network-capture',partial_capture)
        check('missing capture counts stay absent beside explicitly measured zero',captured_network()['capture']=={'unresolved_identities':0} and '0 / 0' not in page.locator('#network-blk').inner_text())
        check('unknown completeness gets one concise notice','Capture completeness was not recorded' in page.locator('#net-cap').inner_text())
        concise_network('partial capture')

        # ── The two HTML hosts that had no exit, and the vocabulary a summary row renders. ──
        #
        # (1) A REDRAW MUST REACH A FOCUSED CONTROL OUTSIDE <svg>. draw() empties three hosts every
        # time it runs — the <svg> itself, #net-breadcrumbs, and, through inspect(), #net-detail —
        # but the restore that hands focus to a rebuilt successor searched
        # svg.querySelectorAll('[data-key]') and so could only ever describe SVG controls. A focused
        # control in either HTML host therefore had no successor to find and dropped through to the
        # .network-root fallback, whose own handler is reset(): the next Enter threw away the view
        # the user had just opened. A resize is the instrument rather than a click because it is the
        # cheapest redraw that rebuilds all three hosts WITHOUT also moving the selection — a click
        # would change the thing under test.
        #
        # Each assertion reads document.activeElement, a consequence only the restore can produce,
        # and each is paired with an existence guard on the same selector so a builder that stopped
        # emitting the trail, the link or the fact row fails here rather than passing vacuously
        # against a successor that is simply missing.
        #
        # The width ALTERNATES per iteration, and that is not decoration. resize() waits for
        # #net's data-viewport to reach the new width, so re-issuing the SAME width is a no-op that
        # returns immediately with no redraw — the control is never destroyed, keeps its focus, and
        # the check passes against a restore that never ran. Measured: with a fixed target width
        # only the first of these three reddened under the svg-only mutant; the other two were green
        # against the defect they exist for.
        def summary_rows():
            return page.locator('#net-detail .network-summary').evaluate(
                "d=>Object.fromEntries([...d.querySelectorAll('dt')].map((e,i)=>[e.textContent,d.querySelectorAll('dd')[i].textContent]))")

        fixture('focus-exits',record)
        page.locator('.net-node[data-node="atlas-api"]').click()
        exit_fact=next(f['fact_id'] for f in record['network']['fact_holdings'] if f['name']=='release-checks')
        for exit_i,(exit_label,exit_sel) in enumerate([('the trail back-control','#net-breadcrumbs button'),
                                                       ('the record link','#net-detail .network-record-link'),
                                                       ('the shared-fact button','#net-detail [data-fact-id="'+exit_fact+'"]')]):
            page.locator(exit_sel).focus()
            resize(1200 if exit_i%2==0 else 1440)
            check('a redraw hands focus back to '+exit_label+', not to the retired root fallback',
                  page.locator(exit_sel).count()==1
                  and page.locator(exit_sel).evaluate('e=>e===document.activeElement'))
            # ...and the control it lands on is one a keyboard user can SEE they are on. These are
            # HTML controls outside <svg>, so the node pins that assert a focus rectangle (and its
            # absence after a pointer activation) reach none of them — measured: arrival by a real
            # Tab gives outline solid 2px + :focus-visible in every theme, while the programmatic
            # restore above gives outline `none` and no :focus-visible, which is the correct half of
            # the same two-sided rule the node pins use. This is the GUARD half: it cannot fail on
            # pre-fix code, because these buttons always had a ring — its mutation introduces the
            # defect rather than reverting one, and was run. The run cost two attempts, and the
            # first is the reason this comment names a rule. Suppressing the ring on the control's
            # OWN scoped rule reds NOTHING: the ring these controls show is delivered by the
            # app-wide `#app button:focus-visible` in the template's focus group, which ties that
            # rule on specificity and wins on source order — the same tie-break this spec documents
            # for the anchor's hover bump, one selector pair over. Appending an equal-specificity
            # `outline:none` AFTER the winning rule reds exactly these three and nothing else. A
            # defect planted where it cannot take effect measures nothing about the guard.
            page.locator(exit_sel).focus()
            page.keyboard.press('Shift+Tab');page.keyboard.press('Tab')
            check(exit_label+' carries a visible focus indicator when focus arrives by keyboard',
                  page.locator(exit_sel).count()==1
                  and page.locator(exit_sel).evaluate("e=>{const s=getComputedStyle(e);return e===document.activeElement&&e.matches(':focus-visible')&&s.outlineStyle!=='none'&&parseFloat(s.outlineWidth)>0;}"))
        resize(1440)

        # (1b) A FOCUS KEY MUST BE UNIQUE, OR THE RESTORE HANDS FOCUS TO A DIFFERENT CONTROL. The
        # restore above takes the FIRST match, so two buttons sharing a key leave a keyboard user
        # on the other one and their next Enter opens a record they did not choose. fact_id is
        # always present in shipped captures, so the collision has to be built through the NAME
        # fallback — a foreign or hand-edited record, the same reachability argument §4.8's
        # count-shape pin rests on, and the label's own `duplicate` prefix is the code admitting
        # that names repeat while the key went on assuming they do not. Both entries are seeded
        # from one real holder of the clicked node, so the fixture differs from the shipped record
        # in exactly the two fields under test.
        dupkey=copy.deepcopy(record)
        seed=next(f for f in dupkey['network']['fact_holdings'] if f['name']=='release-checks')
        held=[copy.deepcopy(seed),copy.deepcopy(seed)]
        for held_row in held:
            held_row['name']='dup-name';held_row.pop('fact_id',None)
        dupkey['network']['fact_holdings'].extend(held)
        fixture('focus-duplicate-keys',dupkey)
        page.locator('.net-node[data-node="atlas-api"]').click()
        dup_btns=page.locator('#net-detail .network-facts button').filter(has_text='dup-name')
        dup_btns.nth(1).focus()
        resize(1200)
        check('a duplicated fact key hands focus back to the same fact, not to the first one sharing its key',
              dup_btns.count()==2 and dup_btns.nth(1).evaluate('e=>e===document.activeElement'))

        # (2) THE SUMMARY'S ABSENCE STATES AND THE SHAPE OF A PRESENT VALUE. A row must separate a
        # field the capture never recorded ('Not captured') from a measured empty ('None recorded')
        # from a value the capture carries in a shape the row did not expect — and the third must
        # render AS ITSELF, never as a blank cell, a '[object Object]', or a false 'Not captured'.
        # Measured pre-fix, one cause each: an empty-string domain drew a blank, a scalar `groups`
        # drew 'Not captured' for a project the record plainly groups, an object drew
        # '[object Object]', and a duplicated sid reported every shared fact in the record as never
        # captured. Asserted separately because they are four different defects sharing one row.
        vocabulary=copy.deepcopy(record)
        # All four in the trigger's own domain so the fleet view expands them and each is one
        # click away — a searched-for node in a collapsed domain is not rendered at all.
        vocabulary['network']=dict(vocabulary['network'],
            nodes=[{'node':'empty-domain','sid':'voc-1','domain':'','groups':'all,even','trigger':True,'shared':1},
                   {'node':'absent-groups','sid':'voc-2','domain':'','trigger':False,'shared':1},
                   {'node':'object-groups','sid':'voc-3','domain':'','groups':{'all':True},'trigger':False,'shared':1},
                   {'node':'array-object-groups','sid':'voc-4','domain':'','groups':[{'all':True},{'even':False}],'trigger':False,'shared':1}],
            domains=[{'domain':'unknown'}],stack_edges=[],group_links=[],fact_holdings=[])
        fixture('summary-vocabulary',vocabulary)
        # A project view selects the node and its recorded connections — with stack_edges empty
        # that is the clicked node alone, so each row needs its own trip back to the fleet.
        page.locator('.net-node[data-node="empty-domain"]').click()
        check('an empty-string domain reads as a measured empty rather than a blank cell',
              summary_rows().get('Domain')=='None recorded' and summary_rows().get('Groups')=='all,even')
        network_view('fleet');page.locator('.net-node[data-node="absent-groups"]').click()
        # A GUARD, not a mutation pin, and labelled as one because a pin that does not move under a
        # mutation is worthless — this one cannot move. Pre-fix listText() reported an absent list
        # and a present non-array identically ('Not captured'), so no revert separates them; what
        # this holds is the BOUNDARY the vocabulary rewrite could overshoot in the other direction,
        # since a rule that rendered every non-array as 'None recorded' would call a field the
        # capture never recorded a measured empty. The present-non-array half of that boundary is
        # asserted by the two checks around it (the 'all,even' string above, the object below), and
        # both of those DO move under the mutation.
        check('a group list the capture never recorded reads as not captured',
              summary_rows().get('Groups')=='Not captured')
        network_view('fleet');page.locator('.net-node[data-node="object-groups"]').click()
        check('a present non-array group list renders as its own value, never as [object Object]',
              summary_rows().get('Groups')=='{"all":true}')
        # The object shape above and the ARRAY-OF-OBJECTS shape below are different code paths into
        # the same rule, and only the second one can actually print '[object Object]': listText()
        # joins a non-empty array before fieldText() ever sees it, so it is the JOIN that needs the
        # guard, not the stringify. The check above was named for the forbidden output while
        # testing a shape that could never produce it.
        network_view('fleet');page.locator('.net-node[data-node="array-object-groups"]').click()
        check('a group list of objects renders as its own value, never as [object Object]',
              summary_rows().get('Groups')=='[{"all":true},{"even":false}]')

        # (3) A DUPLICATED SID IS UNATTRIBUTABLE, WHICH IS NOT THE SAME ANSWER AS NEVER CAPTURED.
        # With two captured nodes sharing a sid no fact can be joined to either, and the record
        # lists facts the whole time — so 'Not captured' was an absence claim about present data.
        duplicate=copy.deepcopy(record)
        duplicate['network']['nodes']=copy.deepcopy(duplicate['network']['nodes'])
        once=next(n['sid'] for n in duplicate['network']['nodes'] if n['node']=='atlas-api')
        next(n for n in duplicate['network']['nodes'] if n['node']=='atlas-web')['sid']=once
        fixture('duplicate-sid',duplicate)
        page.locator('.net-node[data-node="atlas-api"]').click()
        check('a project the capture records twice reports its shared facts as unattributable, not absent',
              summary_rows().get('Shared facts')=='Unresolved identity'
              and 'records this project more than once' in page.locator('#net-detail .network-explanation').text_content())

        # (4) 'Held by' COUNTS WHAT THE CAPTURE RESOLVED, NOT THE RAW HOLDER LIST. selectedNodes()
        # keeps only sids that are non-duplicate and resolve to exactly one captured node, so the
        # record's array length overstates the resolvable set — measured '5 · 3 captured' beside a
        # single captured node, and '3 · none captured' beside none. A zero is words, the same rule
        # every other row here obeys.
        #
        # The clause says "captured" and not "shown on the map" because those are different numbers,
        # and the earlier wording named a measurement this value does not make: this is the SELECTION
        # count, while the map draws one page per expanded domain and nothing for a collapsed one.
        # This check can see the resolved-vs-listed difference (3 → 1) and could never have seen the
        # resolved-vs-rendered one, so the words were the thing that had to give.
        held_by=copy.deepcopy(record)
        held_by['network']['fact_holdings']=copy.deepcopy(held_by['network']['fact_holdings'])
        next(f for f in held_by['network']['fact_holdings'] if f['name']=='release-checks').update(
            holder_sids=['sample-atlas-api','ghost-1','ghost-2'],held_n=3)
        next(f for f in held_by['network']['fact_holdings'] if f['name']=='shell-portability').update(
            holder_sids=['ghost-1','ghost-2'],held_n=2)
        fixture('held-by',held_by)
        network_view('fact','release-checks')
        check("a fact's holder row counts what the capture resolved, not what the record listed",
              summary_rows().get('Held by')=='3 · 1 captured')
        network_view('fact','shell-portability')
        check('a fact none of whose holders resolve says so in words, never as a bare zero',
              summary_rows().get('Held by')=='2 · none captured')

        # (4b) A COUNT THAT IS PRESENT BUT NOT A COUNT IS NOT ABSENT. validate_cycle_record warns on
        # a wrong-typed key at runtime and never blocks, so a persisted held_n of "2" renders — and
        # the row must show it as itself rather than claim the snapshot never recorded the field.
        # The vocabulary fixture above covers fieldText's three shapes; countText had its own, and
        # it collapsed every non-count to 'Not captured'.
        wrong_type=copy.deepcopy(record)
        wrong_type['network']['fact_holdings']=copy.deepcopy(wrong_type['network']['fact_holdings'])
        next(f for f in wrong_type['network']['fact_holdings'] if f['name']=='release-checks')['held_n']='2'
        fixture('wrong-typed-count',wrong_type)
        network_view('fact','release-checks')
        check('a count the record carries in the wrong shape renders as itself, not as one it lacks',
              summary_rows().get('Held by')=='2')

        # (4c) A NON-INTEGER CAPTURED LEAF RENDERS AT SIX SIGNIFICANT DIGITS. capturedTree's terminal
        # case was a bare `String(v)`, so a share — the one leaf a cycle record genuinely carries as a
        # ratio — shipped its full binary expansion into a <dl> of small integers. The ASCII twin
        # spells a number with `_g` (`f"{n:g}"`), so the two views disagreed on exactly the kind of
        # figure this cycle's parity claims are about. `Number(v.toPrecision(6))` is `_g`'s byte-exact
        # JS twin; integers are excluded deliberately, since `toPrecision` would render 1234567 as
        # "1.23457e+6".
        # This IS a pin, and it is one only because of the VALUE it samples. At `60a03b4` the terminal
        # case is `return '<span>'+esc(String(v))+'</span>';` and the file contains no `toPrecision`
        # at all, so the whole expansion renders and the check fails there. A short decimal — 0.5,
        # 0.5025 — would make it a regression guard instead: the two spellings agree on every integer
        # and every value of six significant digits or fewer. An earlier draft of this comment said
        # the guard reading anyway ("cannot fail on the pre-fix revision"), which the injection
        # refutes. **A check's strength is the values it samples**, and this one samples the value
        # the fix moves *to*.
        # Verified by injection rather than by argument: deleting the live float arm reds this check
        # with every check before it green — 1 red as far as the run graded, the tail ungraded because
        # the harness aborts on the first red.
        float_leaf=copy.deepcopy(record)
        float_leaf['remediation']={'required':True,'lever':'gc','mirror_share':0.49975012493753124}
        fixture('float-leaf',float_leaf);open_evidence()
        leaf_text=page.locator('#pass-blk .evidence-fields dd').all_text_contents()
        check('a non-integer captured value renders at six significant digits, not as its full expansion',
              '0.49975' in leaf_text and not any('49975012493753124' in t for t in leaf_text))

        # (5) ONE ANCHOR PER VIEW, EVEN WHEN THE CAPTURE NAMES TWO TRIGGERS. `trigger` is a truthy
        # test, not a uniqueness test: nothing in the record schema, normalize() or any gate bounds
        # it to one node, so a truncated or hand-merged capture can flag two — and re-testing
        # truthy(trigger) per node then stroked and labelled two projects 'This project', 2-of-N
        # against a rule the comment states as 1-of-N. Anchoring on the node the view already
        # resolved as its trigger makes the rule structural rather than assumed.
        two_triggers=copy.deepcopy(record)
        two_triggers['network']['nodes']=copy.deepcopy(two_triggers['network']['nodes'])
        next(n for n in two_triggers['network']['nodes'] if n['node']=='atlas-web')['trigger']=True
        fixture('two-triggers',two_triggers)
        network_view('fleet')
        check('a capture naming two triggers still draws exactly one captured-project mark and one label',
              page.locator('.net-node[data-current="true"]').count()==1
              and page.locator('.net-node[data-current="true"]').get_attribute('data-node')=='atlas-api'
              and page.locator('.net-node .project-meta').evaluate_all('es=>es.filter(e=>e.textContent==="This project").length')==1)

        # Dense and uneven fleets: all captured domains visible, all projects reachable.
        for name,count,domain_of in [('empty',0,lambda i:'work'),('singleton',1,lambda i:'work'),('baseline-only',10,lambda i:'work'),('disconnected',18,lambda i:'d-%d'%(i%4)),('dense',36,lambda i:'d-%d'%(i%4)),('uneven',45,lambda i:'work' if i<39 else 'tools'),('unknown-domain',7,lambda i:'unknown'),('large',125,lambda i:'d-%d'%(i%9)),('prototype-domain',27,lambda i:'constructor')]:
            rec=copy.deepcopy(record);nodes=[dict(node='project-%03d'%i,sid='sid-%03d'%i,display_name='Readable project %03d'%i,domain=domain_of(i),groups=['all','even'] if i%2==0 else ['all'],trigger=i==0,shared=1) for i in range(count)]
            domains=sorted({domain_of(i) for i in range(count)})+['captured-without-rows']
            net={'basis_scope':'fleet','nodes':nodes,'domains':[{'domain':d} for d in domains], 'stack_edges':[] if name in ['baseline-only','disconnected'] else [{'a':a['node'],'b':b['node'],'n':1} for i,a in enumerate(nodes) for b in nodes[i+1:]],'group_links':[{'group':'all','members_n':count,'facts':[]},{'group':'even','members_n':(count+1)//2,'facts':[]}],'fact_holdings':[{'fact_id':'one','name':'shared-lesson','domain':'work','scope':'user-global' if name=='baseline-only' else 'stack-general','holder_sids':[n['sid'] for n in nodes],'held_n':count}] if count else [],'totals':{'nodes':count}}
            rec['network']=net;fixture('topology-'+name,rec)
            check(name+' exposes every captured domain',set(page.locator('.domain-junction').evaluate_all('es=>es.map(e=>e.dataset.domain)'))==set(domains))
            check(name+' preserves every captured project in the raw record',captured_network()['nodes']==nodes)
            if count:
                if name=='large':
                    reached=[]
                    for node in nodes:
                        page.locator('#net-search').fill(node['display_name'])
                        reached.append(page.locator('.net-node').count()==1 and page.locator('.net-node').get_attribute('data-sid')==node['sid'])
                    check('all 125 captured projects are individually reachable through search',all(reached))
                page.locator('#net-search').fill('Readable project %03d'%(count-1));check(name+' search reaches the final captured project',page.locator('.net-node').count()==1 and page.locator('.net-node').get_attribute('data-sid')=='sid-%03d'%(count-1))
                network_view('group','even')
                check(name+' highlights only permitted members',all(int(s.split('-')[1])%2==0 for s in page.locator('.net-node').evaluate_all('es=>es.map(e=>e.dataset.sid)')))
            check(name+' empty domain junctions do not offer inert expansion controls',page.locator('.domain-junction').evaluate_all('es=>es.every(e=>e.hasAttribute("aria-expanded") || (!e.hasAttribute("role")&&!e.hasAttribute("tabindex")&&!e.querySelector(".domain-toggle")))'))
            if name=='prototype-domain':
                network_view('fleet');previous=page.get_by_role('button',name='Previous projects in constructor',exact=True);next_page=page.get_by_role('button',name='Next projects in constructor',exact=True)
                check('prototype-named domains start with real projects and a disabled previous pager',page.locator('.net-node').count()==12 and previous.get_attribute('aria-disabled')=='true' and previous.get_attribute('tabindex') is None)
                next_page.focus();page.keyboard.press('Enter')
                check('keyboard pagination preserves the active pager focus',page.locator('.net-node').first.get_attribute('data-sid')=='sid-012' and page.get_by_role('button',name='Next projects in constructor',exact=True).evaluate('e=>e===document.activeElement'))
                page.keyboard.press('Enter')
                check('the final page disables Next and moves focus to the usable Previous control',page.locator('.net-node').count()==3 and page.get_by_role('button',name='Next projects in constructor',exact=True).get_attribute('aria-disabled')=='true' and page.get_by_role('button',name='Previous projects in constructor',exact=True).evaluate('e=>e===document.activeElement'))
                page.keyboard.press('ArrowLeft');check('pager arrow keys never navigate the archive',page.url.endswith('#sel=0'))
                for width in (320,390,768,1440):
                    resize(width);check('network pager hit areas remain usable in actual CSS pixels '+str(width),page.locator('.page-control rect').evaluate_all('es=>es.every(e=>{const r=e.getBoundingClientRect();return r.height>=43.5&&r.width>=43.5;})'))
                    page.locator('#network-blk').screenshot(path=str(out/('control-pager-'+str(width)+'.png')))
                page.locator('#net-search').fill('Readable project 026');check('prototype-named domain search resets pagination correctly',page.locator('.net-node').count()==1 and page.locator('.net-node').get_attribute('data-sid')=='sid-026')
                network_view('fleet');check('prototype-named domain reset restores its first page',page.locator('.net-node').count()==12 and page.locator('.net-node').first.get_attribute('data-sid')=='sid-000')
            geometry(name+' fleet')
            if name in ['large','uneven']:
                network_view('fleet')
                before=set(page.locator('.net-node').evaluate_all('es=>es.map(e=>e.dataset.sid)'))
                page.get_by_role('button',name='Next projects in '+domain_of(0),exact=True).click()
                check(name+' pagination reaches further nodes',not set(page.locator('.net-node').evaluate_all('es=>es.map(e=>e.dataset.sid)')).issubset(before))
                # Paging a domain exposes nodes whose position in their OWN domain list is past the
                # page slice — sid-108 is the 13th of d-0's 14, sid-030 the 31st of work's 39. Clicking
                # one enters a project view whose selection is that node's whole connected component,
                # and focus() clears every page on the way in, so each domain re-entered on page 0 and
                # the slice omitted the clicked project: the map rendered 108 nodes with NOT ONE
                # [data-current="true"], every row reading "Recorded connection", while the legend above
                # it still promised "The outlined node is the project you selected". Assert the MARK,
                # never a page number, so the pin survives a fixture-size change; and assert the
                # non-anchor wording beside it, or a bundle that labelled every row "This project"
                # would satisfy the anchor half alone.
                target={'large':'sid-108','uneven':'sid-030'}[name]
                nxt=page.get_by_role('button',name='Next projects in '+domain_of(0),exact=True)
                while page.locator('.net-node[data-sid="'+target+'"]').count()==0 and nxt.get_attribute('aria-disabled')!='true':
                    nxt.click()
                page.locator('.net-node[data-sid="'+target+'"]').click()
                marked=page.locator('.net-node[data-current="true"]')
                check(name+' project view opened from a paged node still marks the project it names',
                      marked.count()==1 and marked.get_attribute('data-sid')==target
                      and marked.locator('.project-meta').text_content()=='This project'
                      and page.locator('.net-node:not([data-sid="'+target+'"]) .project-meta').evaluate_all('es=>es.every(e=>e.textContent==="Recorded connection")')
                      and page.locator('#net-legend-note').text_content().startswith('The outlined node is the project you selected'))
                network_view('fleet')
            resize(320);contained(name+' mobile');geometry(name+' mobile');resize(1440)
        legacy=copy.deepcopy(record);legacy['network'].pop('fact_holdings');legacy['network'].pop('capture');fixture('legacy-network',legacy)
        page.locator('.net-node[data-current="true"]').click()
        check('historical topology keeps its missing canonical boundary visible',page.locator('#net-cap').is_visible() and not page.locator('#net-view option[value^="fact:"]').count() and captured_network()['stack_edges']==legacy['network']['stack_edges'])
        truncated=copy.deepcopy(record);truncated['network']['fact_holdings'][0]['held_n']=2001;truncated['network']['capture'].update(facts_total=130,holder_refs_total=2300,unresolved_identities=3,read_failures=2);fixture('truncated',truncated)
        check('partial capture uses one visible notice without debugging counters',page.locator('#net-cap').is_visible() and page.locator('#network-blk .capture-note:visible').count()<=1 and '130' not in page.locator('#net-detail').inner_text() and '2300' not in page.locator('#net-detail').inner_text())
        check('raw network retains exact truncation and failure counts',captured_network()==truncated['network'])
        concise_network('truncated capture')
        hostile=copy.deepcopy(record);attack='</script><img src=x onerror="window.PWNED=1">';hostile['network']['nodes'][0]['display_name']=attack;hostile['dream']['sleep']='*'+attack+'*';hostile['preflight']['fails']=[attack];hostile['entries'][0].update(reason=attack,citation=attack,action='__proto__');fixture('hostile',hostile);open_evidence()
        page.locator('#entries details, #activity-inspector details').evaluate_all('es=>es.forEach(e=>e.open=true)')
        check('hostile action labels and citations remain literal and accessible','__proto__' in page.locator('#activity-inspector').inner_text() and attack in page.locator('#entries').inner_text())
        check('hostile strings stay inert across all redesigned sections',page.evaluate("!window.PWNED && !document.querySelector('img')") and json.loads(page.locator('#record-json').text_content())['dream']['sleep']=='*'+attack+'*' and page.locator('#dream-arc .dream-voice').first.text_content()==attack)

        # Links work when a dream is selected through a query URL as well as a hash.
        ready(preview.as_uri()+'?sel=7');page.locator('#dreamnav .archive-link').click()
        page.wait_for_function("location.hash==='#archive' && document.querySelector('#archive').style.display!=='none'")
        check('Archive overrides a query-selected dream through an explicit route',page.locator('.arch-row').count()==8 and page.url.endswith('?sel=7#archive'))
        page.locator('.arch-row[href="#sel=0"]').click();page.wait_for_function("location.hash==='#sel=0' && document.querySelector('#dreamnav .pos').textContent.includes('dream 1 /')")
        check('an explicit selected dream takes precedence over the original query',page.locator('#dreamnav [aria-disabled="true"]').inner_text().strip().endswith('Previous'))
        page.evaluate('document.body.tabIndex=-1;document.body.focus()');page.keyboard.press('Escape')
        page.wait_for_function("location.hash==='#archive' && document.querySelector('#archive').style.display!=='none'")
        check('Escape reaches Archive from a query URL',page.locator('#archive').is_visible())
        inherited=copy.deepcopy(record);inherited['entries']=[{'name':'unresolved-file','action':'added','files':['toString','constructor','__defineGetter__']}]
        fixture('inherited-sidecar-keys',inherited)
        check('inherited object properties never masquerade as captured file diffs',page.locator('.nm-diff,.file-evidence-link').count()==0 and 'no diffs captured' in page.locator('#ent-note').inner_text())
        own_proto=copy.deepcopy(record);own_proto['entries']=[{'name':'prototype-named-file','action':'added','files':['__proto__']}]
        proto_sidecars={next(iter(diffs)):{'__proto__':{'op':'created','lines':[{'t':'+','s':'A captured file with a prototype-shaped key.'}],'more':0},'invalid-null':None,'invalid-string':'bad','invalid-array':[]}}
        fixture('own-prototype-sidecar',own_proto,sidecars=proto_sidecars)
        check('an own prototype-shaped diff remains accessible exactly once',page.locator('.nm-diff[data-p="__proto__"]').count()==1 and page.locator('.nm-diff').count()==1)
        page.locator('.nm-diff').click();check('prototype-shaped captured diff opens its actual text','prototype-shaped key' in page.locator('#dmodal-body').inner_text());page.keyboard.press('Escape')
        long_sidecars=copy.deepcopy(diffs);long_sidecars[next(iter(long_sidecars))]['memory/retry-backoff.md']['lines']=[{'t':'+','s':'Captured line '+str(i)} for i in range(200)]
        fixture('scrollable-diff',record,sidecars=long_sidecars);page.locator('.nm-diff').first.click();page.keyboard.press('Tab')
        check('long captured diffs expose a labeled keyboard scroll region',page.locator('#dmodal-body').evaluate('e=>e===document.activeElement && e.scrollHeight>e.clientHeight') and page.locator('#dmodal-body').get_attribute('aria-label')=='Captured file diff')
        page.keyboard.press('PageDown');page.wait_for_function('document.querySelector("#dmodal-body").scrollTop>0')
        check('keyboard scrolling a diff keeps the current dream and modal open',page.url.endswith('#sel=0') and page.get_by_role('dialog').is_visible())
        page.keyboard.press('Shift+Tab');check('reverse tab returns from the diff body to Close',page.locator('#dmodal-x').evaluate('e=>e===document.activeElement'))
        page.keyboard.press('Escape');page.locator('.nm-diff').first.click();check('reopened diffs reset their scroll position',page.locator('#dmodal-body').evaluate('e=>e.scrollTop===0'))
        page.locator('#dmodal-bg').click(position={'x':2,'y':2});check('clicking the modal backdrop closes it and restores its trigger',not page.get_by_role('dialog').is_visible() and page.locator('.nm-diff').first.evaluate('e=>e===document.activeElement'))

        prefixed_operations=copy.deepcopy(record)
        prefixed_operations['audit']['operations'][0]['path']='memory/'+prefixed_operations['audit']['operations'][0]['path']
        fixture('prefixed-file-operation',prefixed_operations,sidecars=diffs);open_evidence()
        page.locator('#observed-file-rows .observed-file').first.locator('button').click()
        check('historically prefixed operation paths open their real captured diff','Retry delays include jitter' in page.get_by_role('dialog').inner_text())
        page.keyboard.press('Escape')
        ambiguous_sidecars=copy.deepcopy(diffs)
        ambiguous_sidecars[next(iter(ambiguous_sidecars))]['memory/memory/retry-backoff.md']={'op':'created','lines':[{'t':'+','s':'A different file with a similar path.'}],'more':0}
        fixture('ambiguous-file-operation',prefixed_operations,sidecars=ambiguous_sidecars);open_evidence()
        check('ambiguous recorded operation paths never link to an arbitrary diff',page.locator('#observed-file-rows .observed-file').first.locator('button').count()==0 and page.locator('#observed-file-rows .observed-file').first.locator('.file-evidence-name').inner_text()=='memory/retry-backoff.md')

        malformed_observations=copy.deepcopy(record)
        malformed_observations['usage']['reads']='not-a-measured-number'
        malformed_observations['budget']['recall_facts']=None
        fixture('malformed-observations',malformed_observations)
        check('malformed observations stay unknown in the summary and chart','Not captured' in page.locator('#activity-inspector').inner_text() and page.locator('#trend circle[data-series="reads"]').count()==0)
        page.locator('#activity-inspector details > summary').click()
        check('optional cycle evidence preserves the malformed original observation','not-a-measured-number' in page.locator('#activity-inspector').inner_text() and json.loads(page.locator('#record-json').text_content())['budget']['recall_facts'] is None)

        # Complete history fits its container; every captured cycle remains selectable.
        for count in (47,120,500):
            long=[]
            for i in range(count):
                c=copy.deepcopy(record);c['session']='cycle-%d'%i
                stamp=(datetime.datetime(2025,1,1)+datetime.timedelta(days=i)).isoformat()+'Z'
                c['marker']={'commit':'c%d'%i,'timestamp':stamp}
                if i%7==0:c.pop('usage')
                else:c['usage'].update(reads=0 if i%5==0 else i%19,window='window-'+str(i))
                if i%11==0:c.pop('entries')
                elif i%13==0:c['entries']=[]
                if i%4==0:c.pop('rigor')
                if i==count-2:c['entries']=[{'action':'counter-justified'},{'action':'demoted'},{'action':'custom-recorded-category'}]
                long.append(c)
            fixture('all-activity-'+str(count),long[-1],cycles=long)
            check(str(count)+' captured dreams remain on one complete activity chart',page.locator('.activity-cycle').count()==count and page.locator('.activity-cycle').first.get_attribute('data-cycle')=='0')
            check(str(count)+' captured dreams have a complete native selection control',page.locator('#activity-cycle-select option').evaluate_all('es=>es.map(e=>e.value)')==[str(i) for i in range(count)] and not any(t in ['12','24','All captured'] for t in page.locator('#activity-controls button').all_text_contents()))
            check(str(count)+' cycles preserve exact observations and missing values in plotted points',page.locator('.activity-cycle').evaluate_all('''(es,records)=>es.every((e,i)=>{const r=records[i],observed=(series)=>{const p=e.querySelector('circle[data-series="'+series+'"]');return p?Number(p.dataset.value):null;};return observed('decisions')===(Array.isArray(r.entries)?r.entries.length:null) && observed('reads')===(typeof r.usage?.reads==='number'?r.usage.reads:null);})''',long))
            for width in (320,390,768,1440):
                resize(width);contained(str(count)+' cycles '+str(width));lower_layout(str(count)+' cycles '+str(width))
                check(str(count)+' cycles preserve gaps between missing observations at '+str(width),page.locator('#trend').evaluate('''svg=>{const n=svg.querySelectorAll('.activity-cycle').length,step=(svg.viewBox.baseVal.width-24)/Math.max(1,n-1);return [...svg.querySelectorAll('polyline[data-series]')].every(line=>{const points=line.getAttribute('points').trim().split(/\s+/).map(point=>Number(point.split(',')[0]));return points.every((x,i)=>!i||x-points[i-1]<=step+.01);});}'''))
                check(str(count)+' cycles avoid colliding chart labels at '+str(width),page.locator('#trend text').evaluate_all('''es=>es.every((a,i)=>{const A=a.getBBox();return es.slice(i+1).every(b=>{const B=b.getBBox();return !(A.x<B.x+B.width-1&&A.x+A.width>B.x+1&&A.y<B.y+B.height-1&&A.y+A.height>B.y+1);});})'''))
                check(str(count)+' cycles keep label ink inside the canvas at '+str(width),page.locator('#trend').evaluate('''svg=>{const v=svg.viewBox.baseVal;return [...svg.querySelectorAll('text')].every(text=>{const b=text.getBBox();return b.x>=-.5&&b.y>=-.5&&b.x+b.width<=v.width+.5&&b.y+b.height<=v.height+.5;});}'''))
                check(str(count)+' cycles keep sparse labels at '+str(width),page.locator('#trend .activity-cycle-number').count()<=max(2,width//35))
                page.locator('#trend').scroll_into_view_if_needed()
                page.locator('#trend').evaluate('svg=>{window.lastActivityClick=null;svg.addEventListener("click",e=>window.lastActivityClick=e.clientX,{once:true,capture:true});}')
                chart=page.locator('#trend').bounding_box();page.mouse.click(chart['x']+chart['width']*.513,chart['y']+74)
                check(str(count)+' cycles select and focus the nearest actual point at '+str(width),page.locator('#trend').evaluate('''svg=>{const click=window.lastActivityClick,r=svg.getBoundingClientRect(),scale=r.width/svg.viewBox.baseVal.width,nearest=[...svg.querySelectorAll('.activity-cycle')].sort((a,b)=>Math.abs(r.left+a.querySelector('.activity-selection').x1.baseVal.value*scale-click)-Math.abs(r.left+b.querySelector('.activity-selection').x1.baseVal.value*scale-click))[0];return click!==null&&nearest.getAttribute('aria-pressed')==='true'&&nearest===document.activeElement;}'''))
                page.locator('#history-blk').screenshot(path=str(out/('all-activity-'+str(count)+'-'+str(width)+'.png')))
            for index in (0,count//2,count-2,count-1):
                page.locator('#activity-cycle-select').select_option(str(index))
                check(str(count)+' cycles can inspect dream '+str(index+1)+' without navigation',page.locator('.activity-cycle[aria-pressed="true"]').get_attribute('data-cycle')==str(index) and page.locator('.open-dream').get_attribute('href')=='#sel='+str(index) and page.url.endswith('#sel='+str(count-1)))
            page.locator('#activity-cycle-select').select_option('4')
            page.locator('.activity-cycle[data-cycle="4"]').focus()
            resize(390);resize(1440)
            check(str(count)+' cycles preserve local selection after resizing',page.locator('#activity-cycle-select').input_value()=='4' and page.locator('.activity-cycle[aria-pressed="true"]').get_attribute('data-cycle')=='4' and page.locator('.activity-cycle[data-cycle="4"]').evaluate('e=>e===document.activeElement'))
            page.locator('#activity-controls button[aria-label="Previous dream"]').click()
            check(str(count)+' cycles support previous and next controls',page.locator('#activity-cycle-select').input_value()=='3')
            page.locator('#activity-controls button[aria-label="Next dream"]').click()
            page.locator('.activity-cycle[data-cycle="4"]').focus();page.keyboard.press('Home')
            check(str(count)+' cycles support direct keyboard selection',page.locator('#activity-cycle-select').input_value()=='0' and page.url.endswith('#sel='+str(count-1)))
            page.keyboard.press('End')
            check(str(count)+' cycles support keyboard selection of the final cycle',page.locator('#activity-cycle-select').input_value()==str(count-1))
            page.locator('#activity-cycle-select').select_option(str(count-2))
            page.locator('#activity-inspector details > summary').click()
            check(str(count)+' cycles retain exact uncommon decision categories','custom-recorded-category' in page.locator('#activity-inspector').inner_text() and 'counter-justified' in page.locator('#activity-inspector').inner_text())
            page.locator('#activity-cycle-select').select_option('0')
            check(str(count)+' cycles preserve an open detail disclosure when changing the local selection',page.locator('#activity-inspector details').get_attribute('open') is not None)
            check(str(count)+' cycles retain missing decisions, recall and rigor in cycle details',page.locator('#activity-inspector').inner_text().count('Not captured')>=3)
            page.locator('.open-dream').click();page.wait_for_function("location.hash==='#sel=0' && document.querySelector('#dreamnav .pos').textContent.includes('dream 1 /')")
            check(str(count)+' cycles navigate only through Open this dream',page.locator('.activity-cycle').count()==1)

        # v0.4.20 network capture teeth: absence and emptiness never stack (the whole-panel
        # collapse on an ABSENT block; the honest empty capture keeps the chrome).
        fixture('v0419-absent-network', {'project': 'absent-net', 'scope': {},
                                         'dream': {'sleep': 's', 'beats': ['b'] * 6, 'wake': 'w'},
                                         'marker': {'commit': 'c', 'timestamp': 't'}})
        check('absent network collapses to the not-captured note alone (map, scroll wrapper, controls, legend, detail hidden)',
              all(page.locator(s).evaluate('e=>e.hidden')
                  for s in ['#net', '#net-scroll', '#net-controls', '#net-legend', '#net-detail'])
              and 'Network details were not captured for this dream' in page.locator('#net-cap').inner_text())
        _empty20 = {'nodes': [], 'fact_holdings': [], 'stack_edges': [], 'group_links': [],
                    'totals': {'nodes': 0}, 'capture': {'facts_total': 0, 'facts_emitted': 0,
                                                       'holder_refs_total': 0, 'holder_refs_emitted': 0,
                                                       'incidence_bytes': 0, 'unresolved_identities': 0,
                                                       'read_failures': 0}}
        fixture('v0419-empty-capture', {'project': 'empty-net', 'scope': {}, 'network': _empty20,
                                        'dream': {'sleep': 's', 'beats': ['b'] * 6, 'wake': 'w'},
                                        'marker': {'commit': 'c2', 'timestamp': 't2'}})
        check('empty capture keeps the chrome with the honest empty text and no not-captured note',
              all(not page.locator(s).evaluate('e=>e.hidden')
                  for s in ['#net', '#net-scroll', '#net-controls', '#net-legend', '#net-detail'])
              and 'No project nodes captured for this view' in page.locator('#net').text_content()
              and 'Network details were not captured' not in page.locator('#net-cap').inner_text()
              and 'older snapshot' not in page.locator('#net-detail').inner_text())

        # Golden geometry captured from the v0.4.16 header before this redesign.
        check('frozen header geometry reference is present',GEOMETRY.is_file())
        if GEOMETRY.exists():
            expected=json.loads(GEOMETRY.read_text())
            for name,case in expected.items():
                fixture('header-'+name,case['record'],cycles=case['cycles'])
                actual=page.locator('#traj').inner_html()
                check('immutable header SVG geometry: '+name,actual==case['svg'])
        # v0.4.22 U1 (S5): the HTML legacy fallback — a present count with NO marked rows renders
        # the bare count (no names, no join). The token-stripped copy of the fixture's skipped row
        # is the pre-mandate record shape.
        _leg_rec=copy.deepcopy(record)
        for _e in _leg_rec.get('entries',[]):
            if isinstance(_e,dict) and isinstance(_e.get('reason'),str) and _e['reason'].startswith('unverifiable:'):
                _e['reason']=_e['reason'][len('unverifiable:'):].lstrip()
        fixture('legacy-unverifiable',_leg_rec)
        check('a legacy record keeps the bare unverifiable label (no names, no join)',
              '1 unverifiable claim' in page.locator('#dream-summary').inner_text()
              and 'cache-expiry-claim' not in page.locator('#dream-summary').inner_text())
        check('every transition completed without browser exceptions',not errors)
        check('archives run offline without external requests',not requests)
        if capture:
            # A fresh page: the checks above leave the last fixture open, and the art
            # must come from the sample record the README's captions describe.
            # reduced_motion='reduce' is what makes the export deterministic: the reveal
            # animations are scoped to no-preference, so this samples every element at its
            # natural state instead of wherever the stagger happened to be.
            art=browser.new_context(viewport={'width':1440,'height':1000},color_scheme='light',
                                    reduced_motion='reduce').new_page()
            for path in capture_art(art,out,preview):print('captured '+path.name,flush=True)
            art.close()
        browser.close()
    print('%d browser checks passed'%len(results))


# The README's art is exported from a live render, never hand-drawn: that is what
# keeps it honest when the theme or the layout moves. Two rules make it safe.
#
# 1. It writes ONLY into --out. Promoting a file into docs/assets/ is a separate,
#    deliberate step, so a routine `dashboard_browser.py` run (which CI does on
#    every push) can never rewrite tracked files.
# 2. The network SVG is captured in the DEFAULT theme. The old export was pinned
#    to Nocturne's values purely because that is the theme it happened to be taken
#    in — not because of the file format — so capturing in Deep Field is the whole
#    of the "re-palette" step. rgb() is then rewritten to hex for readability; the
#    numbers are untouched, so this transform cannot shift a colour.
CAPTURE_CROPS=(('nocturne-dashboard',('#network-blk',)),
               ('nocturne-activity',('#history-blk',)),
               ('nocturne-evidence',('#pass-blk',)))
# The overview crop spans the chart, the key measures and the dream block, so it
# is a document-coordinate clip rather than one element's box.
CAPTURE_OVERVIEW=('nocturne-overview','.overview','#dream-blk')
_INLINE_PROPS=('fill','stroke','stroke-width','stroke-dasharray','stroke-opacity','stroke-linecap',
               'stroke-linejoin','font-family','font-size','font-style','font-weight','text-anchor',
               'opacity','letter-spacing')
# Inlines the computed style of every node, because the live SVG is styled by CSS
# classes and a bare outerHTML would export an unstyled file. The export is linked
# from the README (not embedded), so nothing would define those classes at the far
# end -- self-contained inline styles are what make it render standalone.
_INLINE_JS="""([sel,props])=>{const src=document.querySelector(sel),clone=src.cloneNode(true);
const a=[src,...src.querySelectorAll('*')],b=[clone,...clone.querySelectorAll('*')];
a.forEach((el,i)=>{const cs=getComputedStyle(el);b[i].setAttribute('style',props.map(p=>p+':'+cs.getPropertyValue(p)).join(';'));});
// #net is transparent; its surface colour lives on an ancestor. The export is linked,
// not embedded, so without this it would sit on the viewer's white page as light-on-white.
let bg='',n=src;
while(n&&(bg===''||bg==='rgba(0, 0, 0, 0)')){bg=getComputedStyle(n).backgroundColor;n=n.parentElement;}
clone.style.background=bg;
return clone.outerHTML;}"""
_HEX=re.compile(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)')


def standalone_svg(svg):
    """Make a serialized SVG load as a file rather than only inside its own document.

    outerHTML omits xmlns (an HTML document implies the SVG namespace), but a file
    opened directly -- which is how the README links this one -- is parsed as XML,
    lands in no namespace, and renders as nothing at all. width/height come from the
    viewBox so the file has an intrinsic size.
    """
    box=re.search(r'viewBox="([\d.\- ]+)"',svg)
    size=' width="%s" height="%s"'%tuple(box.group(1).split()[2:4]) if box else ''
    return svg.replace('<svg ','<svg xmlns="http://www.w3.org/2000/svg"'+size+' ',1)


def capture_art(page,out,preview):
    """Re-export the README's art from a live render into --out. Returns the paths written."""
    page.goto(preview.as_uri()+'#sel=7')
    page.wait_for_function("document.querySelector('#boot').style.display==='none'")
    page.evaluate("()=>{document.documentElement.dataset.theme='deepfield';}")
    page.wait_for_timeout(250)
    written=[]
    def shoot(name,clip):
        # full_page is what lets a clip reach below the fold; without it Playwright
        # rejects any box taller than the viewport.
        path=out/(name+'.png');page.screenshot(path=str(path),clip=clip,full_page=True);written.append(path)
    top,bottom=page.locator(CAPTURE_OVERVIEW[1]).bounding_box(),page.locator(CAPTURE_OVERVIEW[2]).bounding_box()
    shoot(CAPTURE_OVERVIEW[0],{'x':bottom['x'],'y':top['y'],'width':bottom['width'],
                               'height':bottom['y']+bottom['height']-top['y']})
    for name,(sel,) in CAPTURE_CROPS:
        box=page.locator(sel).bounding_box()
        shoot(name,{'x':box['x'],'y':box['y'],'width':box['width'],'height':box['height']})
    svg=page.evaluate(_INLINE_JS,['#net',list(_INLINE_PROPS)])
    svg=_HEX.sub(lambda m:'#%02x%02x%02x'%tuple(int(g) for g in m.groups()),svg)
    svg=standalone_svg(svg).replace('><','>\n<')
    path=out/'nocturne-network.svg';path.write_text(svg+'\n');written.append(path)
    return written


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--capture',action='store_true',
                        help='maintainer-only: also re-export the README art into --out')
    args=parser.parse_args()
    main(args.out.resolve(),args.capture)
