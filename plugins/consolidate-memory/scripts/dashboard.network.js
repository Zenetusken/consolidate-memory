/* Captured-network normalization and ranked layout. No store reads or remote assets. */
var NocturneNetwork = (function(){
  function rows(v){return Array.isArray(v)?v.filter(function(x){return x&&typeof x==='object';}):[];}
  function normalize(record){
    var net=record.network||{}, seen=new Set(), nodes=rows(net.nodes).map(function(n,i){
      // Invalid duplicate sids cannot join incidence; retain both captured nodes.
      var sid=String(n.sid||'legacy:'+i), duplicate=seen.has(sid);seen.add(sid);
      // `key` is what draw() restores focus by, so it must survive a re-normalize. A
      // positional index (the old 'project:'+i) does not: a repaint on a cycle change
      // re-enters draw() with a fresh model, and the stale index would land focus on
      // whatever project now occupies that slot. The key is therefore the SID — but only
      // where a sid exists to be had. A capture with no sids, and a duplicated sid, both
      // fall back to the index, and there the old fragility survives by construction rather
      // than by oversight: the record supplies no stable identity to key on, so the only
      // thing left is the position. Bounded, not fixed — the fallback is recorded as an open
      // hole in the spec's coverage ledger. Duplicate sids are additionally invalid capture
      // data, and they stay distinct from each other only via that index.
      return {raw:n,id:'project:'+i,key:duplicate?'project:'+sid+'#'+i:'project:'+sid,sid:sid,duplicate:duplicate,label:String(n.display_name||n.node||'Unnamed project'),domain:String(n.domain||'unknown'),groups:Array.isArray(n.groups)?n.groups:[]};
    });
    var domains=Array.from(new Set(rows(net.domains).map(function(d){return String(d.domain||'unknown');}).concat(nodes.map(function(n){return n.domain;})))).sort();
    return {raw:net,nodes:nodes,domains:domains,facts:rows(net.fact_holdings),groups:rows(net.group_links),edges:rows(net.stack_edges),canonical:Array.isArray(net.fact_holdings)};
  }
  function paint(record){
    var model=normalize(record), net=model.raw, svg=el('net'), detail=el('net-detail'), controls=el('net-controls');
    // v0.4.20 (docs/network-capture-teeth.spec.md): absence and emptiness never stack. When the
    // block is ABSENT (net.nodes is not an array) the panel collapses to the not-captured note
    // alone — the map, controls, legend, and detail attribution all hide (they painted
    // unconditionally over a blank canvas, the same stacked read one level up). A PRESENT block
    // with 0 nodes keeps the chrome and shows the honest empty-capture state. Reset each paint
    // (the archive re-paints per dream), then hide only on absence.
    svg.hidden=false;controls.hidden=false;el('net-legend').hidden=false;detail.hidden=false;
    el('net-scroll').hidden=false;
    if(!Array.isArray(net.nodes)){svg.hidden=true;controls.hidden=true;el('net-legend').hidden=true;detail.hidden=true;el('net-scroll').hidden=true;}
    var trigger=model.nodes.find(function(n){return truthy(n.raw.trigger);});
    var state={kind:'fleet',value:null,expanded:new Set(trigger?[trigger.domain]:[]),pages:Object.create(null),query:''};
    svg.classList.add('hierarchy-map');svg.setAttribute('role','group');
    // Programmatic focus retains keyboard navigation after redraws. Keep pointer
    // selection from inheriting a keyboard outline, including after typing a search.
    if(paint.focusHost)paint.focusHost.removeEventListener('pointerdown',paint.pointerHandler,true);
    if(paint.keyboardHandler)window.removeEventListener('keydown',paint.keyboardHandler,true);
    paint.focusHost=el('network-blk');
    paint.pointerHandler=function(){svg.dataset.focusMode='pointer';};
    paint.keyboardHandler=function(){svg.dataset.focusMode='keyboard';};
    paint.focusHost.addEventListener('pointerdown',paint.pointerHandler,true);
    window.addEventListener('keydown',paint.keyboardHandler,true);
    if(!svg.dataset.focusMode)svg.dataset.focusMode='pointer';
    controls.innerHTML='<div id="net-breadcrumbs" class="breadcrumbs"></div><label class="network-search">Find a project<input id="net-search" type="search" autocomplete="off" placeholder="Search project or domain"></label><div id="net-groups"><label class="network-view">View<select id="net-view"><option value="fleet">All captured projects</option></select></label></div>';
    function matches(n){return !state.query||(n.label+' '+n.domain+' '+n.sid+' '+(n.raw.node||'')).toLowerCase().indexOf(state.query)>=0;}
    el('net-search').oninput=function(){state.query=this.value.trim().toLowerCase();state.kind='fleet';state.value=null;state.pages=Object.create(null);state.expanded=new Set(state.query?model.nodes.filter(matches).map(function(n){return n.domain;}):trigger?[trigger.domain]:[]);draw();};
    function button(label,fn,box,cls){var b=document.createElement('button');b.type='button';b.textContent=label;if(cls)b.className=cls;b.onclick=fn;box.appendChild(b);return b;}
    function reset(){state.kind='fleet';state.value=null;state.expanded=new Set(trigger?[trigger.domain]:[]);state.pages=Object.create(null);state.query='';el('net-search').value='';draw();}
    function viewOptions(label,kind,values){
      if(!values.length)return;
      var group=document.createElement('optgroup');group.label=label;el('net-view').appendChild(group);
      values.forEach(function(value,i){var option=document.createElement('option');option.value=kind+':'+i;option.textContent=kind==='fact'?(value.domain||'Unknown domain')+' / '+value.name:value.group;group.appendChild(option);});
    }
    viewOptions('Shared facts','fact',model.facts);viewOptions('Sharing groups','group',model.groups);
    el('net-view').onchange=function(){var parts=this.value.split(':');if(parts[0]==='fact')focus('fact',model.facts[Number(parts[1])]);else if(parts[0]==='group')focus('group',model.groups[Number(parts[1])]);else if(parts[0]==='fleet')reset();};
    function focus(kind,value){
      state.kind=kind;state.value=value;state.pages=Object.create(null);state.expanded=new Set(model.domains);state.query='';el('net-search').value='';
      draw();
      // No focus repair here, and no keepControl flag to suppress one. Focusing the root
      // unconditionally ran AFTER draw()'s own restore and moved focus to a control the pointer
      // never touched — and the root's own handler is reset(), so the next Enter undid the
      // activation that had just happened. The stranded case it was later narrowed to cover (an
      // activation whose own element the redraw destroys) is real, but it is NOT specific to this
      // function: the trail's back-control is destroyed by the same draw(). The invariant is
      // enforced where the destruction happens, once — see the tail of draw().
    }
    function selectedNodes(){
      if(state.kind==='fact'){
        var sids=Array.isArray(state.value.holder_sids)?state.value.holder_sids:[];
        return model.nodes.filter(function(n){return !n.duplicate&&sids.indexOf(n.sid)>=0&&model.nodes.filter(function(x){return x.sid===n.sid;}).length===1;});
      }
      if(state.kind==='group')return model.nodes.filter(function(n){return n.groups.indexOf(state.value.group)>=0;});
      if(state.kind==='project'){
        var names=new Set([state.value.raw.node]);model.edges.forEach(function(e){if(e.a===state.value.raw.node)names.add(e.b);if(e.b===state.value.raw.node)names.add(e.a);});
        return model.nodes.filter(function(n){return names.has(n.raw.node);});
      }
      return model.nodes;
    }
    function activate(n,fn,label){n.setAttribute('tabindex','0');n.setAttribute('role','button');n.setAttribute('aria-label',label);n.addEventListener('click',fn);n.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();e.stopPropagation();fn();}});}
    function text(x,y,value,cls,parent){var t=S('text',{x:x,y:y,class:cls||''});t.textContent=value;(parent||svg).appendChild(t);return t;}
    function clipped(t,value,width){var s=value;while(t.getComputedTextLength()>width&&s.length){s=s.slice(0,-1);t.textContent=s+'…';}}
    // --blen feeds the Deep Field draw-on (CSS dasharray/dashoffset). It is set here, not in
    // CSS, because only the path knows its own length. Purely presentational: nothing reads
    // it back, and the geometry checks measure `d` and getTotalLength(), not this.
    function branch(d,kind,aggregate){var p=S('path',{d:d,class:'hierarchy-branch '+kind+(aggregate?' aggregate-branch':''),'data-aggregate':aggregate?'true':'false'});svg.appendChild(p);try{p.style.setProperty('--blen',p.getTotalLength());}catch(e){}return p;}
    function rootLabel(){return state.kind==='fleet'?'Captured fleet':state.kind==='group'?String(state.value.group):state.kind==='fact'?String(state.value.name):state.value.label;}
    function draw(){
      // Focus repair is a two-step contract. `focusKey` identifies a control this redraw will
      // REBUILD, so the restore at the tail can hand focus to its successor. The search spans the
      // whole widget, not just <svg>: a redraw also destroys controls that live OUTSIDE it — the
      // trail's back-control (this function empties #net-breadcrumbs), the record link and the
      // shared-fact buttons (inspect() replaces #net-detail's innerHTML) — and an <svg>-only
      // search cannot reach their successors, so it dropped a focused control onto .network-root
      // instead. Root's own handler is reset(), so the next Enter then discarded the view the
      // user had opened. `hadFocus` records that a real control held focus at all, which is what
      // tells a STRANDING apart from a redraw nobody was focused in. Captured before
      // svg.textContent='' below, which is what destroys.
      var focusKey=document.activeElement&&document.activeElement.getAttribute('data-key');
      var hadFocus=!!document.activeElement&&document.activeElement!==document.body&&document.activeElement!==document.documentElement;
      svg.textContent='';
      svg.dataset.kind=state.kind;detail.dataset.kind=state.kind;
      // The trail b665ffc left headless: #net-breadcrumbs was created and cleared but never
      // filled, so a focused view had no visible "where am I / go back". Fleet stays empty and
      // #net-breadcrumbs:empty{display:none} hides it, so the default look is unchanged. The
      // crumb is a real button because the SVG root's visible label is the VIEW's own name —
      // in a project view that leaves no visible way back.
      var crumbs=el('net-breadcrumbs');crumbs.textContent='';
      if(state.kind!=='fleet'){
        button('Captured fleet',reset,crumbs,'crumb-back').setAttribute('data-key','crumb:back');
        var trail=document.createElement('span');trail.className='crumb-trail';
        trail.textContent='› '+(state.kind==='fact'?'Shared fact':state.kind==='group'?'Sharing group':'Project')+' › '+rootLabel();
        crumbs.appendChild(trail);
      }
      var view=el('net-view'),projectOption=view.querySelector('option[value="project"]');
      if(projectOption)projectOption.remove();
      if(state.kind==='project'){projectOption=document.createElement('option');projectOption.value='project';projectOption.textContent=state.value.label;view.appendChild(projectOption);}
      view.value=state.kind==='fact'?'fact:'+model.facts.indexOf(state.value):state.kind==='group'?'group:'+model.groups.indexOf(state.value):state.kind;
      var selected=selectedNodes(), matching=selected.filter(matches);
      var domains=state.kind==='fleet'?model.domains:model.domains.filter(function(d){return selected.some(function(n){return n.domain===d;});});
      // Search preserves domain coverage while expanding matching domains.
      // Change ranks before the horizontal map would shrink its text and controls.
      // A vertical map uses its actual container width, including narrow phones.
      var available=svg.parentElement.clientWidth||Math.max(200,el('network-blk').clientWidth-36);
      var mobile=available<960, W=mobile?Math.max(200,available):960;
      var blocks=[],y=mobile?108:38;
      domains.forEach(function(domain){
        var all=matching.filter(function(n){return n.domain===domain;}), expanded=all.length>0&&state.expanded.has(domain);
        // A project view OPENS ON its anchor. focus() clears every page, so each domain would enter
        // on page 0 — but the selection this view renders is the anchor's whole connected component,
        // which can outgrow one page: measured on the suite's 125-node fixture, the component is the
        // entire fleet, 14 members in d-0 against a 12-node page, so page 0 omitted the very project
        // the user clicked. The view then marked NOTHING — no [data-current="true"] in the whole map —
        // while its own legend still read "The outlined node is the project you selected", and every
        // rendered row read "Recorded connection", the string reserved for the non-anchor members.
        // Entering on the anchor's page keeps the slice contiguous on the anchor and leaves the
        // pager's 1-of-N arithmetic untouched. `page==null` rather than `||0` so an explicitly
        // pressed page is respected: paging moves the anchor like any other member, and can carry it
        // off-screen, exactly as fleet paging can already carry the captured trigger off-screen.
        var page=state.pages[domain];
        if(page==null&&state.kind==='project'&&domain===state.value.domain){var at=all.indexOf(state.value);if(at>=0)page=Math.floor(at/12);}
        if(page==null)page=0;
        var shown=expanded?all.slice(page*12,page*12+12):[];
        var height=expanded?Math.max(mobile?94:90,shown.length*(mobile?60:56)+(mobile?94:36))+(all.length>12?(mobile?32:56):0):mobile?72:84;
        blocks.push({domain:domain,all:all,shown:shown,expanded:expanded,page:page,y:y,height:height,cy:mobile?y:y+height/2});y+=height;
      });
      var H=Math.max(mobile?200:260,y+24), rootX=mobile?W/2:92, rootY=mobile?36:H/2;
      // Let the viewBox set the displayed height when the map scales down.
      // Capping its width preserves the existing scale and centering on wide screens.
      svg.setAttribute('viewBox','0 0 '+W+' '+H);svg.style.height='auto';svg.style.maxWidth=W+'px';svg.style.marginLeft='auto';svg.style.marginRight='auto';
      if(!mobile){
        text(rootX,18,state.kind==='fleet'?'FLEET':state.kind.toUpperCase(),'rank-label').setAttribute('text-anchor','middle');
        text(358,18,'DOMAIN','rank-label').setAttribute('text-anchor','middle');
        text(608,18,state.kind==='fact'?'PROJECTS HOLDING THIS FACT':state.kind==='group'?'PERMITTED PROJECTS':'PROJECTS','rank-label');
      }
      var kind=state.kind==='group'?'grant-edge':state.kind==='fact'||state.kind==='project'?'fact-edge':'structure-edge';
      if(blocks.length){
        var rootRadius=state.kind==='fleet'?16:18;
        // Use a side port: the root's readable label occupies the space below it.
        if(mobile){branch('M '+(rootX-rootRadius)+' '+rootY+' H 14 V '+blocks[blocks.length-1].cy,kind,true);}
        else{branch('M '+(rootX+rootRadius)+' '+rootY+' H 234',kind,true);branch('M 234 '+Math.min(rootY,blocks[0].cy)+' V '+Math.max(rootY,blocks[blocks.length-1].cy),kind,true);}
      }
      var root=S('g',{class:'network-root','data-key':'root'});svg.appendChild(root);
      if(state.kind==='fleet'){
        var mark=S('g',{transform:'translate('+(rootX-20)+' '+(rootY-20)+')'});root.appendChild(mark);
        mark.appendChild(S('path',{d:'M20 4A16 16 0 1 0 36 20',class:'orbit'}));
        mark.appendChild(S('path',{d:'M20 11a9 9 0 1 0 9 9',class:'orbit',style:'stroke:var(--accent)'}));
        mark.appendChild(S('path',{d:'M20 20 32 8',class:'orbit',style:'stroke:var(--rule2)'}));
        mark.appendChild(S('circle',{cx:20,cy:20,r:3,class:'core'}));
        mark.appendChild(S('circle',{cx:32,cy:8,r:3,class:'core'}));
      }else root.appendChild(S('circle',{cx:rootX,cy:rootY,r:18,class:'focus-root'}));
      var rt=text(rootX,rootY+(mobile?34:44),rootLabel(),'root-label',root);rt.setAttribute('text-anchor','middle');clipped(rt,rootLabel(),mobile?W-36:175);
      var title=S('title');title.textContent=rootLabel();root.appendChild(title);activate(root,reset,'Return to captured fleet');
      blocks.forEach(function(b){
        var dx=mobile?34:358, dy=b.cy, linkX=mobile?14:234;
        branch('M '+linkX+' '+dy+' H '+(dx-12),kind,false);
        svg.appendChild(S('circle',{cx:linkX,cy:dy,r:2.5,class:'aggregate-junction'}));
        var dg=S('g',{class:'domain-junction','data-domain':b.domain,'data-key':'domain:'+b.domain});svg.appendChild(dg);
        dg.appendChild(S('circle',{cx:dx,cy:dy,r:12}));
        if(b.all.length)text(dx,dy+4,b.expanded?'−':'+','domain-toggle',dg).setAttribute('text-anchor','middle');
        var dt=text(mobile?56:dx,mobile?dy+4:dy+31,b.domain,'domain-label',dg);if(!mobile)dt.setAttribute('text-anchor','middle');clipped(dt,b.domain,mobile?W-70:225);
        var count=b.all.length?b.all.length+(state.query?' matching project':' project')+(b.all.length===1?'':'s'):state.query?'No matching projects':'No captured projects';var ct=text(mobile?56:dx,mobile?dy+23:dy+50,count,'domain-count',dg);if(!mobile)ct.setAttribute('text-anchor','middle');
        if(b.all.length){dg.setAttribute('aria-expanded',String(b.expanded));activate(dg,function(){if(state.expanded.has(b.domain))state.expanded.delete(b.domain);else state.expanded.add(b.domain);draw();},b.domain+' / '+count+' / '+(b.expanded?'collapse':'expand'));}
        else{var emptyTitle=S('title');emptyTitle.textContent=b.domain+' / '+count;dg.appendChild(emptyTitle);}
        if(b.shown.length){
          var first=mobile?dy+62:b.y+26,last=first+(b.shown.length-1)*(mobile?60:56),jx=mobile?34:570;
          if(mobile)branch('M '+dx+' '+(dy+12)+' V '+last,kind,true);
          else {branch('M '+(dx+12)+' '+dy+' H '+jx,kind,true);branch('M '+jx+' '+Math.min(first,dy)+' V '+Math.max(last,dy),kind,true);}
          b.shown.forEach(function(n,i){
            var py=first+i*(mobile?60:56),px=mobile?52:608,pw=mobile?W-64:330;
            branch('M '+jx+' '+py+' H '+px,kind,false);svg.appendChild(S('circle',{cx:jx,cy:py,r:2.5,class:'aggregate-junction'}));
            // One anchor per view, and only the two views that have one: fleet marks the
            // dream's captured project, a project view marks the project you selected.
            // Fleet anchors on the SINGLE node :30 resolved, not on re-testing truthy(trigger)
            // per node: nothing in normalize(), the record schema or any gate constrains `trigger`
            // to one node, and truthy() accepts 'true'/'1'/'yes', so a truncated or hand-merged
            // capture that flags two projects drew two outlined nodes both labelled "This
            // project" — 2-of-N against a rule this comment states as 1-of-N. Anchoring on the
            // same node the view already treats as its trigger makes the rule structural.
            // Fact and group views are peer sets — no node is their anchor — and marking the
            // fleet trigger there stroked and labelled a project the user never chose.
            // Every rendered node IS a member — rendered ⊆ matching ⊆ selected, and matching
            // only narrows further under a search — so the map can never show a non-member to
            // mark, which makes the anchor the only 1-of-N mark it can carry. Note it is a
            // STRICT subset in the default view: a collapsed domain and a paged one both render
            // fewer nodes than the selection holds.
            // That containment is ONE-DIRECTIONAL, and reading it as if it closed the question is
            // what this round got wrong: it rules out marking a NON-member, and says nothing about
            // the anchor's own presence. The other direction is carried by the entry page computed
            // above — a project view opens on its anchor's page — and only there. So the residual
            // is real and deliberate: a user who pages AWAY, or who collapses the anchor's own
            // domain, hides it, and this branch then matches nothing at all. That is a
            // user-initiated hide, the same semantics fleet paging already has for the captured
            // trigger, and it is recorded as an open hole in the spec's coverage ledger.
            var anchor=state.kind==='project'?n===state.value:state.kind==='fleet'&&n===trigger;
            var node=S('g',{class:'net-node'+(state.kind==='group'?' selected':''),'data-node':n.raw.node||n.id,'data-sid':n.sid,'data-key':n.key,'data-current':anchor?'true':'false'});svg.appendChild(node);
            node.appendChild(S('rect',{x:px,y:py-21,width:pw,height:44,rx:5}));
            var nt=text(px+12,py-3,n.label,'project-label',node);clipped(nt,n.label,pw-24);
            var relation=state.kind==='fact'?'Holds this fact':state.kind==='group'?'Permitted member':anchor?'This project':state.kind==='project'?'Recorded connection':'Select to explore';
            text(px+12,py+14,relation,'project-meta',node);
            var title=S('title');title.textContent=n.label+' · '+n.domain;node.appendChild(title);
            activate(node,function(){focus('project',n);},n.label+' / inspect captured project');
          });
        }
        if(b.expanded&&b.all.length>12){
          var pg=S('g',{class:'domain-page'});svg.appendChild(pg);
          var px=mobile?52:608,py=b.y+b.height-66,gap=mobile?8:12,width=((mobile?W-64:330)-gap)/2,lastPage=Math.ceil(b.all.length/12)-1;
          function pageControl(direction,x,label,disabled){var key='page:'+direction+':'+b.domain,control=S('g',{class:'page-control','data-key':key,role:'button','aria-label':(direction==='previous'?'Previous':'Next')+' projects in '+b.domain,'aria-disabled':String(disabled)});pg.appendChild(control);
            control.appendChild(S('rect',{x:x,y:py,width:width,height:44,rx:5}));text(x+width/2,py+27,label,'page-link',control).setAttribute('text-anchor','middle');
            if(!disabled)activate(control,function(){state.pages[b.domain]=b.page+(direction==='previous'?-1:1);draw();},(direction==='previous'?'Previous':'Next')+' projects in '+b.domain);
          }
          pageControl('previous',px,'← Previous',b.page===0);pageControl('next',px+width+gap,'Next →',b.page===lastPage);
          text(px,py-10,(b.page*12+1)+'–'+Math.min(b.all.length,b.page*12+12)+' of '+b.all.length,'domain-count',pg);
        }
      });
      if(!blocks.length)text(mobile?24:285,mobile?142:120,'No project nodes captured for this view.','empty-network');
      // Block spacing leaves room for the next domain. The final domain needs
      // only a small bottom inset; measure the drawn content so pagination stays visible.
      var bounds=svg.getBBox(),contentHeight=Math.ceil(bounds.y+bounds.height+24);
      if(bounds.height>0&&contentHeight<H)svg.setAttribute('viewBox','0 0 '+W+' '+contentHeight);
      inspect(selected);
      svg.dataset.viewport=String(window.innerWidth);
      if(focusKey){var target=Array.from(el('network-blk').querySelectorAll('[data-key]')).find(function(n){return n.getAttribute('data-key')===focusKey;});if(target&&target.getAttribute('aria-disabled')==='true')target=target.parentElement.querySelector('.page-control[aria-disabled="false"]');if(target)target.focus({preventScroll:true});}
      // The stranded case, repaired once for every activation — and only here, because only the
      // redraw knows what it destroyed. This is a genuine LAST RESORT: the restore above now
      // reaches every rebuildable control, including the ones outside <svg>, so it has already
      // had its chance. What is left is a focused control the redraw destroyed with no successor
      // to hand focus to. TWO controls reach it, and both reach it because their own activation
      // destroys them: the trail's back-control (that activation leaves the fleet, where no crumb
      // builds) and a shared-fact button (inspect() rewrites #net-detail, and a fact view renders
      // no fact button for its own fact). Root is the right landing for both only because the fleet
      // is where each of them leads — reset() is what root does, which is why this is a last resort
      // and not a general repair. An earlier draft of this comment listed only the crumb and called
      // any focused control reaching this fallback "a bug in the key map above"; the fact button is
      // one of the two cases the fallback exists for, and the check below it says so.
      // Guarded on hadFocus, because a redraw nobody was focused in (the initial paint, the
      // per-dream repaint in the archive) must never seize focus. Test <body>/<html> explicitly
      // rather than !document.activeElement: Chrome points activeElement at <body> when the
      // focused node is removed, and never uses null.
      if(hadFocus&&(document.activeElement===document.body||document.activeElement===document.documentElement))
        svg.querySelector('.network-root').focus({preventScroll:true});
    }
    function count(v){return typeof v==='number'&&isFinite(v)&&v>=0?v:null;}
    function inspect(selected){
      var capture=net.capture||{},facts=[],note='',explanation='';
      var partial=count(capture.unresolved_identities)>0||count(capture.read_failures)>0;
      [['facts_total','facts_emitted'],['holder_refs_total','holder_refs_emitted']].forEach(function(keys){if(count(capture[keys[0]])!=null&&count(capture[keys[1]])!=null&&capture[keys[1]]<capture[keys[0]])partial=true;});
      if(state.kind==='project'){
        var unique=model.nodes.filter(function(n){return n.sid===state.value.sid;}).length===1;
        if(unique)facts=model.facts.filter(function(f){return Array.isArray(f.holder_sids)&&f.holder_sids.indexOf(state.value.sid)>=0;});
        else partial=true;
        // The !unique arm comes FIRST. Without it a duplicated sid falls through to the empty-facts
        // wording and asserts "No named shared facts were captured for this project" while the
        // record lists them — an absence claim about data that is present, which is the collapse
        // the capture-teeth rule forbids. Unattributable and not-captured are different answers.
        explanation=!unique?'This capture records this project more than once, so its shared facts cannot be attributed.':facts.length?'Choose a shared fact to see which projects hold it.':model.canonical?'No named shared facts were captured for this project.':'These projects share facts recorded in this dream.';
      }else if(state.kind==='fact'){
        var refs=Array.isArray(state.value.holder_sids)?state.value.holder_sids:null;
        if(!refs||refs.length!==selected.length||count(state.value.held_n)!=null&&state.value.held_n>selected.length)partial=true;
        explanation='These projects held a local copy of this fact.';
      }else if(state.kind==='group'){
        if(!Array.isArray(net.nodes)||model.nodes.some(function(n){return !Array.isArray(n.raw.groups);}))partial=true;
        if(count(state.value.facts_total)!=null&&state.value.facts_total>rows(state.value.facts).length)partial=true;
        explanation='These projects have permission to receive facts addressed to this group.';
      }
      if(!Array.isArray(net.nodes))note='Network details were not captured for this dream.';
      else if(!model.canonical)note='This older snapshot records project connections, but not individual fact holders.';
      else if(partial)note='This snapshot is partial; some facts or connections cannot be shown.';
      else if(['facts_total','facts_emitted','holder_refs_total','holder_refs_emitted','unresolved_identities','read_failures'].some(function(key){return count(capture[key])==null;}))note='Capture completeness was not recorded for this dream.';
      // A focused view states its selection's captured basis in words. These rows are readable
      // labels, NOT the v0.4.14 inventory: concise_network (tests/dashboard_browser.py) already
      // forbids that inventory's accounting labels and debugging structures inside #net-detail,
      // and this is written TO that guard rather than around it — if a row needs a label the
      // guard happens to miss, the design is wrong, not the pin.
      // Absence and emptiness never collapse into one another (the capture-teeth rule above):
      // "Not captured" is a field the snapshot never recorded, "None recorded" a measured empty,
      // and a bare 0 never renders as a measurement.
      // A field that is PRESENT but not the shape its row expects is neither absent nor empty, and
      // rendering it as "Not captured" reports a value the record carries as one it does not have —
      // measured: a duplicated sid did exactly that for every shared fact in the record, and a
      // present-but-scalar `groups` did it for a project the record plainly groups. So a present
      // value renders as ITSELF — non-scalars through the same JSON.stringify treatment the page's
      // own value() uses, never '[object Object]' — and only genuine absence reads "Not captured".
      // The empty string is a measured empty, not absence: sync_global.py writes str(x or '') for
      // captured node domains, so '' is reachable from the emitter rather than only from hand edits.
      function fieldText(v){
        if(v==null)return 'Not captured';
        if(v===''||(Array.isArray(v)&&!v.length))return 'None recorded';
        return typeof v==='object'?JSON.stringify(v):String(v);
      }
      // A list of scalars joins readably, and a list of OBJECTS must not: join() stringifies each
      // element, so an array of objects renders '[object Object], [object Object]' — the exact
      // output the rule above forbids. Anything this cannot join readably goes to fieldText, which
      // is where 'as ITSELF' is implemented; the two functions have to agree on that or the row
      // that reaches the second shape is the one that lies.
      function listText(v){return Array.isArray(v)&&v.length&&!v.some(function(x){return x&&typeof x==='object';})?v.join(', '):fieldText(v);}
      // A value that is PRESENT but not a count is neither absent nor empty: falling through to
      // fieldText renders it as itself, which is the rule the block above states for a value the
      // row did not expect. Collapsing it to 'Not captured' reported a count the record carries as
      // one it does not have — and it is reachable, because validate_cycle_record warns on a
      // wrong-typed key at runtime and never blocks, so a persisted members_n of "2" renders.
      function countText(v){if(v===undefined||v===null)return 'Not captured';var n=count(v);return n===null?fieldText(v):(n===0?'None recorded':String(n));}
      var summary=[];
      if(state.kind==='project'){
        // domain/groups are read from raw, not the normalized node: normalize() collapses an
        // absent field to 'unknown'/[] and would misreport absence as a captured value.
        var pn=state.value,uniqueSid=model.nodes.filter(function(x){return x.sid===pn.sid;}).length===1;
        summary=[['Domain',fieldText(pn.raw.domain)],
                 ['Groups',listText(pn.raw.groups)],
                 ['Recorded connections',Array.isArray(net.stack_edges)?countText(model.edges.filter(function(e){return e.a===pn.raw.node||e.b===pn.raw.node;}).length):'Not captured'],
                 // Three states, not two: absent (the capture carries no fact_holdings at all),
                 // unattributable (this project's sid appears more than once, so no fact can be
                 // joined to it), and a real count. Folding the middle into "Not captured" claimed
                 // the snapshot never recorded the field while the facts sat in the record —
                 // measured: baseline 5, then "Not captured" once the sid was duplicated. The word
                 // is the record's own: the capture block already counts unresolved_identities.
                 ['Shared facts',!model.canonical?'Not captured':uniqueSid?countText(model.facts.filter(function(f){return Array.isArray(f.holder_sids)&&f.holder_sids.indexOf(pn.sid)>=0;}).length):'Unresolved identity']];
      }else if(state.kind==='fact'){
        var pf=state.value,held=count(pf.held_n);
        // The clause counts what the capture RESOLVED, not what the record listed — and it says
        // "captured", not "shown on the map", because those are different numbers. selectedNodes()
        // keeps only non-duplicate sids that resolve to exactly one captured node, so the raw array
        // length overstates the resolvable set; but selected is still the whole SELECTION, while the
        // map draws one page per expanded domain and nothing for a collapsed one. The rendered count
        // is strictly smaller in both of those reachable states, so "shown on the map" named a
        // measurement this value does not make. A zero renders as words, the rule every row here
        // obeys, so "never a bare 0" holds by construction.
        summary=[['Domain',fieldText(pf.domain)],['Scope',fieldText(pf.scope)],
                 ['Held by',countText(pf.held_n)+(held!==null&&selected.length<held?' · '+(selected.length?selected.length+' captured':'none captured'):'')]];
      }else if(state.kind==='group'){
        var pg=state.value;
        summary=[['Home domain',fieldText(pg.home_domain)],['Members',countText(pg.members_n)]];
      }
      // Fleet has no selection to summarise, so it carries the instruction the template seeds —
      // which the first draw() used to destroy, leaving initial markup and drawn state disagreeing.
      var lead=state.kind==='fleet'?'Select a project to inspect its captured evidence.':explanation;
      detail.innerHTML=(state.kind==='fleet'?'':'<strong class="network-selection-name">'+esc(rootLabel())+'</strong>')
        +(lead?'<p class="network-explanation">'+esc(lead)+'</p>':'')
        +'<span class="network-attribution">Saved with this dream</span>';
      var attribution=detail.querySelector('.network-attribution');
      if(summary.length){
        var dl=document.createElement('dl');dl.className='network-summary';
        summary.forEach(function(row){var dt=document.createElement('dt');dt.textContent=row[0];var dd=document.createElement('dd');dd.textContent=row[1];dl.appendChild(dt);dl.appendChild(dd);});
        detail.insertBefore(dl,attribution);
      }
      // The escape hatch. reveal() is the page's one "open the disclosure, scroll to it, focus it"
      // routine, and #record-json needs it: the record sits inside a closed <details>. Guarded on
      // capability so a bundle loaded without NocturneSections renders NO link, never a dead one.
      if(state.kind!=='fleet'&&typeof NocturneSections!=='undefined'&&typeof NocturneSections.reveal==='function'){
        var recordLink=document.createElement('button');recordLink.type='button';
        recordLink.className='inspector-choice network-record-link';recordLink.setAttribute('data-key','record:link');
        recordLink.textContent='Open the complete captured cycle record';
        recordLink.onclick=function(){NocturneSections.reveal('record-json');};
        detail.insertBefore(recordLink,attribution);
      }
      if(facts.length){
        var choices=document.createElement('div');choices.className='network-facts';detail.appendChild(choices);
        // The focus key must be UNIQUE, or a redraw hands focus to a different button: the restore
        // above takes the FIRST match, so two facts sharing a key mean the next Enter opens the
        // other one. `duplicate` already decides the visible label (the domain prefix below), so
        // the key disambiguates exactly where the label does — identity first, then index — which
        // is the shape normalize() uses for node keys. fact_id is always present in shipped
        // records; the name fallback exists for foreign or hand-edited ones, and that is where a
        // collision lives.
        facts.forEach(function(f,i){var duplicate= facts.filter(function(x){return x.name===f.name;}).length>1;var b=button((duplicate?f.domain+' / ':'')+f.name,function(){focus('fact',f);},choices,'inspector-choice');b.dataset.factId=f.fact_id||'';b.setAttribute('data-key','fact:'+(f.fact_id||f.name)+(duplicate?'#'+i:''));});
      }
      el('net-cap').textContent=note;el('net-cap').hidden=!note;
      // The legend is UPDATED, not replaced. Overwriting #net-legend's children orphaned the
      // template's dot markup — smoke.py pins "this project</span>" in _TEMPLATE_SRC, and a
      // pin on markup nothing renders is exactly the fossil this pass exists to clear. The dot
      // keys describe the FLEET's node roles, so they hide in focused views where no node is
      // "this project"; the interpretation then says what this view's branches and mark mean.
      var interpretation=state.kind==='group'?'Dashed branches show permission to receive, not delivery.':state.kind==='fact'?'Solid branches show projects holding this fact.':state.kind==='project'?'The outlined node is the project you selected; solid branches show its recorded shared-fact connections.':'Projects are organized by domain. Select a domain to expand it.';
      var legendNote=el('net-legend-note');
      if(legendNote){legendNote.className=state.kind==='group'?'permissions-key':state.kind==='fleet'?'organization-key':'holdings-key';legendNote.textContent=interpretation;}
      var legendKeys=el('net-legend')&&el('net-legend').querySelector('.legend-keys');
      if(legendKeys)legendKeys.hidden=state.kind!=='fleet';
    }
    el('net-note').textContent=Array.isArray(net.nodes)?model.nodes.length+' projects · '+model.domains.length+' domains':'Not captured';
    draw();
    // One resize listener per mounted report; old closures are removed on navigation.
    if(paint.resize)window.removeEventListener('resize',paint.resize);
    paint.resize=function(){draw();};window.addEventListener('resize',paint.resize);
  }
  return {paint:paint,normalize:normalize};
})();
