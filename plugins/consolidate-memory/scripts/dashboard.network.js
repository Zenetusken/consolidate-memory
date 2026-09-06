/* Captured-network normalization and ranked layout. No store reads or remote assets. */
var NocturneNetwork = (function(){
  function rows(v){return Array.isArray(v)?v.filter(function(x){return x&&typeof x==='object';}):[];}
  function normalize(record){
    var net=record.network||{}, seen=new Set(), nodes=rows(net.nodes).map(function(n,i){
      // Invalid duplicate sids cannot join incidence; retain both captured nodes.
      var sid=String(n.sid||'legacy:'+i), duplicate=seen.has(sid);seen.add(sid);
      return {raw:n,id:'project:'+i,sid:sid,duplicate:duplicate,label:String(n.display_name||n.node||'Unnamed project'),domain:String(n.domain||'unknown'),groups:Array.isArray(n.groups)?n.groups:[]};
    });
    var domains=Array.from(new Set(rows(net.domains).map(function(d){return String(d.domain||'unknown');}).concat(nodes.map(function(n){return n.domain;})))).sort();
    return {raw:net,nodes:nodes,domains:domains,facts:rows(net.fact_holdings),groups:rows(net.group_links),edges:rows(net.stack_edges),canonical:Array.isArray(net.fact_holdings)};
  }
  function paint(record){
    var model=normalize(record), net=model.raw, svg=el('net'), detail=el('net-detail'), controls=el('net-controls');
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
    el('net-view').onchange=function(){var parts=this.value.split(':');if(parts[0]==='fact')focus('fact',model.facts[Number(parts[1])],true);else if(parts[0]==='group')focus('group',model.groups[Number(parts[1])],true);else if(parts[0]==='fleet')reset();};
    function focus(kind,value,keepControl){state.kind=kind;state.value=value;state.pages=Object.create(null);state.expanded=new Set(model.domains);state.query='';el('net-search').value='';draw();if(!keepControl)svg.querySelector('.network-root').focus({preventScroll:true});}
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
    function branch(d,kind,aggregate){var p=S('path',{d:d,class:'hierarchy-branch '+kind+(aggregate?' aggregate-branch':''),'data-aggregate':aggregate?'true':'false'});svg.appendChild(p);return p;}
    function rootLabel(){return state.kind==='fleet'?'Captured fleet':state.kind==='group'?String(state.value.group):state.kind==='fact'?String(state.value.name):state.value.label;}
    function draw(){
      var focusKey=document.activeElement&&document.activeElement.getAttribute('data-key');
      svg.textContent='';
      svg.dataset.kind=state.kind;detail.dataset.kind=state.kind;
      el('net-breadcrumbs').textContent='';
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
        var page=state.pages[domain]||0,shown=expanded?all.slice(page*12,page*12+12):[];
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
            var node=S('g',{class:'net-node'+(state.kind==='group'?' selected':''),'data-node':n.raw.node||n.id,'data-sid':n.sid,'data-key':n.id,'data-current':truthy(n.raw.trigger)?'true':'false'});svg.appendChild(node);
            node.appendChild(S('rect',{x:px,y:py-21,width:pw,height:44,rx:5}));
            var nt=text(px+12,py-3,n.label,'project-label',node);clipped(nt,n.label,pw-24);
            var relation=state.kind==='fact'?'Holds this fact':state.kind==='group'?'Permitted member':truthy(n.raw.trigger)?'This project':'Select to explore';
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
      if(focusKey){var target=Array.from(svg.querySelectorAll('[data-key]')).find(function(n){return n.getAttribute('data-key')===focusKey;});if(target&&target.getAttribute('aria-disabled')==='true')target=target.parentElement.querySelector('.page-control[aria-disabled="false"]');if(target)target.focus({preventScroll:true});}
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
        explanation=facts.length?'Choose a shared fact to see which projects hold it.':model.canonical?'No named shared facts were captured for this project.':'These projects share facts recorded in this dream.';
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
      detail.innerHTML=(state.kind==='fleet'?'':'<strong class="network-selection-name">'+esc(rootLabel())+'</strong>')+(explanation?'<p class="network-explanation" aria-live="polite">'+esc(explanation)+'</p>':'')+'<span class="network-attribution">Saved with this dream</span>';
      if(facts.length){
        var choices=document.createElement('div');choices.className='network-facts';detail.appendChild(choices);
        facts.forEach(function(f){var duplicate= facts.filter(function(x){return x.name===f.name;}).length>1;var b=button((duplicate?f.domain+' / ':'')+f.name,function(){focus('fact',f);},choices,'inspector-choice');b.dataset.factId=f.fact_id||'';});
      }
      el('net-cap').textContent=note;el('net-cap').hidden=!note;
      var interpretation=state.kind==='group'?'Dashed branches show permission to receive, not delivery.':state.kind==='fact'?'Solid branches show projects holding this fact.':state.kind==='project'?'Solid branches show recorded shared-fact connections.':'Projects are organized by domain. Select a domain to expand it.';
      el('net-legend').innerHTML='<span class="'+(state.kind==='group'?'permissions-key':state.kind==='fleet'?'organization-key':'holdings-key')+'">'+esc(interpretation)+'</span>';
    }
    el('net-note').textContent=Array.isArray(net.nodes)?model.nodes.length+' projects · '+model.domains.length+' domains':'Not captured';
    draw();
    // One resize listener per mounted report; old closures are removed on navigation.
    if(paint.resize)window.removeEventListener('resize',paint.resize);
    paint.resize=function(){draw();};window.addEventListener('resize',paint.resize);
  }
  return {paint:paint,normalize:normalize};
})();
