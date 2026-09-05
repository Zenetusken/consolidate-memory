/* Captured-network normalization and ranked layout. No store reads or remote assets. */
var NocturneNetwork = (function(){
  function rows(v){return Array.isArray(v)?v.filter(function(x){return x&&typeof x==='object';}):[];}
  function normalize(record){
    var net=record.network||{}, seen=new Set(), nodes=rows(net.nodes).map(function(n,i){
      // Invalid duplicate sids cannot join incidence; retain both inventory rows.
      var sid=String(n.sid||'legacy:'+i), duplicate=seen.has(sid);seen.add(sid);
      return {raw:n,id:'project:'+i,sid:sid,duplicate:duplicate,label:String(n.display_name||n.node||'Unnamed project'),domain:String(n.domain||'unknown'),groups:Array.isArray(n.groups)?n.groups:[]};
    });
    var domains=Array.from(new Set(rows(net.domains).map(function(d){return String(d.domain||'unknown');}).concat(nodes.map(function(n){return n.domain;})))).sort();
    return {raw:net,nodes:nodes,domains:domains,facts:rows(net.fact_holdings),groups:rows(net.group_links),edges:rows(net.stack_edges),canonical:Array.isArray(net.fact_holdings)};
  }
  function paint(record){
    var model=normalize(record), net=model.raw, svg=el('net'), detail=el('net-detail'), controls=el('net-controls');
    var trigger=model.nodes.find(function(n){return truthy(n.raw.trigger);});
    var state={kind:'fleet',value:null,expanded:new Set(trigger?[trigger.domain]:[]),pages:{},query:''};
    svg.classList.add('hierarchy-map');svg.setAttribute('role','group');
    controls.innerHTML='<div id="net-breadcrumbs" class="breadcrumbs"></div><label class="network-search">Find a captured project or fact<input id="net-search" type="search" autocomplete="off" placeholder="Search name, domain or identity"></label><div id="net-groups"></div>';
    el('net-search').oninput=function(){state.query=this.value.trim().toLowerCase();state.kind='fleet';state.value=null;state.pages={};draw();};
    function button(label,fn,box,cls){var b=document.createElement('button');b.type='button';b.textContent=label;if(cls)b.className=cls;b.onclick=fn;box.appendChild(b);return b;}
    function reset(){state.kind='fleet';state.value=null;state.expanded=new Set(trigger?[trigger.domain]:[]);state.pages={};state.query='';el('net-search').value='';draw();}
    button('Reset view',reset,el('net-groups'));
    model.groups.forEach(function(group){button('Group / '+group.group,function(){focus('group',group);},el('net-groups'));});
    function focus(kind,value){state.kind=kind;state.value=value;state.pages={};state.expanded=new Set(model.domains);state.query='';el('net-search').value='';draw();svg.querySelector('.network-root').focus({preventScroll:true});}
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
      var breadcrumb=el('net-breadcrumbs');breadcrumb.textContent='';button('Fleet',reset,breadcrumb);
      if(state.kind!=='fleet'){var crumb=document.createElement('span');crumb.textContent=' / '+state.kind+' / '+rootLabel();breadcrumb.appendChild(crumb);}
      var selected=selectedNodes(), matching=selected.filter(function(n){return !state.query||(n.label+' '+n.domain+' '+n.sid+' '+n.raw.node).toLowerCase().indexOf(state.query)>=0;});
      var domains=state.kind==='fleet'?model.domains:model.domains.filter(function(d){return selected.some(function(n){return n.domain===d;});});
      // Search preserves domain coverage while expanding matching domains.
      var mobile=window.innerWidth<700, W=mobile?Math.max(260,el('network-blk').clientWidth-36):960;
      var blocks=[],y=mobile?108:38;
      domains.forEach(function(domain){
        var all=matching.filter(function(n){return n.domain===domain;}), expanded=state.query?all.length>0:state.expanded.has(domain);
        var page=state.pages[domain]||0,shown=expanded?all.slice(page*12,page*12+12):[];
        var height=expanded?Math.max(mobile?94:90,shown.length*(mobile?60:56)+(mobile?94:36)):mobile?72:84;
        blocks.push({domain:domain,all:all,shown:shown,expanded:expanded,page:page,y:y,height:height,cy:mobile?y:y+height/2});y+=height;
      });
      var H=Math.max(mobile?200:260,y+24), rootX=mobile?W/2:92, rootY=mobile?36:H/2;
      svg.setAttribute('viewBox','0 0 '+W+' '+H);svg.style.height=H+'px';
      var kind=state.kind==='group'?'grant-edge':state.kind==='fact'||state.kind==='project'?'fact-edge':'structure-edge';
      if(blocks.length){
        if(mobile){branch('M '+rootX+' '+(rootY+18)+' V 78 H 14 V '+blocks[blocks.length-1].cy,kind,true);}
        else{branch('M '+(rootX+24)+' '+rootY+' H 234',kind,true);branch('M 234 '+blocks[0].cy+' V '+blocks[blocks.length-1].cy,kind,true);}
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
        text(dx,dy+4,b.expanded?'−':'+','domain-toggle',dg).setAttribute('text-anchor','middle');
        var dt=text(mobile?56:dx,mobile?dy+4:dy+31,b.domain,'domain-label',dg);if(!mobile)dt.setAttribute('text-anchor','middle');clipped(dt,b.domain,mobile?W-70:225);
        var count=b.all.length+' project'+(b.all.length===1?'':'s');var ct=text(mobile?56:dx,mobile?dy+23:dy+50,count,'domain-count',dg);if(!mobile)ct.setAttribute('text-anchor','middle');
        dg.setAttribute('aria-expanded',String(b.expanded));activate(dg,function(){if(state.expanded.has(b.domain))state.expanded.delete(b.domain);else state.expanded.add(b.domain);draw();},b.domain+' / '+count+' / '+(b.expanded?'collapse':'expand'));
        if(b.shown.length){
          var first=mobile?dy+62:b.y+26,last=first+(b.shown.length-1)*(mobile?60:56),jx=mobile?34:570;
          if(mobile)branch('M '+dx+' '+(dy+13)+' V '+last,kind,true);
          else {branch('M '+(dx+13)+' '+dy+' H '+jx,kind,true);branch('M '+jx+' '+Math.min(first,dy)+' V '+Math.max(last,dy),kind,true);}
          b.shown.forEach(function(n,i){
            var py=first+i*(mobile?60:56),px=mobile?52:608,pw=mobile?W-64:330;
            branch('M '+jx+' '+py+' H '+px,kind,false);svg.appendChild(S('circle',{cx:jx,cy:py,r:2.5,class:'aggregate-junction'}));
            var node=S('g',{class:'net-node'+(state.kind==='group'?' selected':''),'data-node':n.raw.node||n.id,'data-sid':n.sid,'data-key':n.id,'data-current':truthy(n.raw.trigger)?'true':'false'});svg.appendChild(node);
            node.appendChild(S('rect',{x:px,y:py-21,width:pw,height:44,rx:5}));
            var nt=text(px+12,py-3,n.label,'project-label',node);clipped(nt,n.label,pw-24);
            text(px+12,py+14,(truthy(n.raw.trigger)?'This project · ':'')+(n.raw.shared==null?'Holdings not captured':n.raw.shared+' physical mirrors'),'project-meta',node);
            var title=S('title');title.textContent=n.label+' · '+n.sid;node.appendChild(title);
            activate(node,function(){focus('project',n);},n.label+' / inspect captured project');
          });
        }
        if(b.expanded&&b.all.length>12){
          var pg=S('g',{class:'domain-page','data-key':'page:'+b.domain});svg.appendChild(pg);
          var px=mobile?56:608,py=b.y+b.height-22;
          var prev=text(px,py,'← Previous','page-link',pg),next=text(px+(mobile?114:190),py,'Next →','page-link',pg);
          activate(prev,function(){state.pages[b.domain]=Math.max(0,b.page-1);draw();},'Previous projects in '+b.domain);
          activate(next,function(){state.pages[b.domain]=Math.min(Math.ceil(b.all.length/12)-1,b.page+1);draw();},'Next projects in '+b.domain);
          text(px,py-18,(b.page*12+1)+'–'+Math.min(b.all.length,b.page*12+12)+' of '+b.all.length,'domain-count',pg);
        }
      });
      if(!blocks.length)text(mobile?24:285,mobile?142:120,'No project nodes captured for this view.','empty-network');
      inspect(selected);
      svg.dataset.viewport=String(window.innerWidth);
      if(focusKey){var target=Array.from(svg.querySelectorAll('[data-key]')).find(function(n){return n.getAttribute('data-key')===focusKey;});if(target)target.focus({preventScroll:true});}
    }
    function kv(label,value){return '<div class="inspector-row"><span>'+esc(label)+'</span><b>'+esc(value==null?'Not captured':value)+'</b></div>';}
    function inspect(selected){
      var h='<div class="inspector-kicker">'+esc(state.kind==='fleet'?'Snapshot evidence':state.kind+' evidence')+'</div><h4>'+esc(rootLabel())+'</h4>';
      if(state.kind==='project'){
        var n=state.value.raw;h+=kv('Stable store',state.value.sid)+kv('Domain',state.value.domain)+kv('Always-loaded tokens',n.always_loaded_tokens)+kv('Mirror index tokens',n.mirror_index_tokens)+kv('Recall tokens',n.recall_tokens)+kv('Physical mirrors',n.shared);
      }else if(state.kind==='fact')h+=kv('Canonical identity',state.value.fact_id)+kv('Home domain',state.value.domain)+kv('Scope',state.value.scope)+kv('Physical holders before limits',state.value.held_n)+kv('Captured holder references',(state.value.holder_sids||[]).length)+kv('Resolved captured projects',selected.length)+((state.value.holder_sids||[]).length!==selected.length?'<p class="capture-note">Some captured holder references do not uniquely identify project rows.</p>':'');
      else if(state.kind==='group')h+='<p>Permission only · '+selected.length+' captured group members. Membership does not establish physical presence or delivery.</p>'+kv('Home domain',state.value.home_domain)+kv('Facts addressed before limit',state.value.facts_total)+kv('Captured addressed facts',rows(state.value.facts).length);
      else h+='<p>'+(Array.isArray(net.nodes)?model.nodes.length+' captured projects':'Project list not captured')+' in '+model.domains.length+' domains. Expand a domain, then select a project.</p>';
      if(!model.canonical)h+='<p class="capture-note">Canonical identities were not captured. This archive supports exploration of its recorded pairwise links; fact holders cannot be reconstructed.</p>';
      if(net.capture)h+=kv('Unresolved mirror identities',num(net.capture.unresolved_identities))+kv('Unreadable fact files',num(net.capture.read_failures))+kv('Canonical facts captured / total',num(net.capture.facts_emitted)+' / '+num(net.capture.facts_total))+kv('Holder references captured / total',num(net.capture.holder_refs_emitted)+' / '+num(net.capture.holder_refs_total));
      detail.innerHTML=h;
      var facts=model.facts.filter(function(f){return state.kind!=='project'||(f.holder_sids||[]).indexOf(state.value.sid)>=0;}).filter(function(f){return !state.query||(f.name+' '+f.domain+' '+f.fact_id).toLowerCase().indexOf(state.query)>=0;});
      if(facts.length){var disclosure=document.createElement('details');disclosure.open=state.kind==='project'||!!state.query;disclosure.innerHTML='<summary>'+facts.length+' captured facts</summary>';detail.appendChild(disclosure);facts.forEach(function(f){button(f.domain+' / '+f.name+' · '+f.held_n+' holders',function(){focus('fact',f);},disclosure,'inspector-choice');});}
      if(state.kind==='project'){
        var links=model.edges.filter(function(e){return e.a===state.value.raw.node||e.b===state.value.raw.node;});
        var list=document.createElement('details');list.open=true;list.innerHTML='<summary>'+links.length+' recorded pairwise connections</summary>';detail.appendChild(list);
        links.forEach(function(e){var named=rows(net.stack_edge_facts).find(function(f){return f.a===e.a&&f.b===e.b||f.b===e.a&&f.a===e.b;});var p=document.createElement('p');p.textContent=(e.a===state.value.raw.node?e.b:e.a)+' · '+e.n+' shared stack facts · '+(named?(named.names||[]).join(', '):'fact names were not captured');list.appendChild(p);});
      }
      if(state.kind==='group'){rows(state.value.facts).forEach(function(f){var p=document.createElement('p');p.textContent='Addressed: '+f.domain+' / '+f.name;detail.appendChild(p);});}
    }
    el('net-note').textContent=Array.isArray(net.nodes)?model.nodes.length+' captured projects · '+model.domains.length+' domains':'Project list not captured';
    el('net-cap').textContent='Coverage: captured stores holding shared mirrors plus the triggering store. Absent projects are outside this snapshot. Branches organize captured evidence; junctions aggregate their visible members.';
    el('net-legend').innerHTML='<span>○ Domain / expand projects</span><span id="net-leg-stack" class="holdings-key">— Observed holdings in a focused view</span><span class="permissions-key">┄ Group permission only</span>';
    var inventory='<h4>Project inventory</h4><div class="table-scroll"><table><thead><tr><th>Project</th><th>Domain</th><th>Stable store</th><th>Index</th><th>Mirror index</th><th>Recall</th><th>Groups</th></tr></thead><tbody>'+model.nodes.map(function(n){return '<tr>'+[n.label,n.domain,n.sid,n.raw.always_loaded_tokens,n.raw.mirror_index_tokens,n.raw.recall_tokens,n.groups.join(', ')].map(function(v){return '<td>'+esc(v==null?'Not captured':v)+'</td>';}).join('')+'</tr>';}).join('')+'</tbody></table></div>';
    inventory+='<h4>Permissions</h4><div class="table-scroll"><table><thead><tr><th>Group</th><th>Captured group members</th><th>Facts addressed to group</th></tr></thead><tbody>'+model.groups.map(function(g){return '<tr><td>'+esc(g.group)+'</td><td>'+esc(g.members_n==null?'Not captured':g.members_n)+'</td><td>'+rows(g.facts).map(function(f){return esc(f.domain+' / '+f.name);}).join(', ')+(g.facts_total!=null?' · '+g.facts_total+' before limit':' · total before limit not captured')+'</td></tr>';}).join('')+'</tbody></table></div>';
    inventory+='<h4>Registry baseline holdings</h4><p>Registry holder counts use a different basis from observed physical presence.</p>'+rows(net.universal_facts).map(function(f){return '<p>'+esc(f.domain+' / '+f.name)+' · '+esc(f.held==null?'Not captured':f.held)+' registry holders</p>';}).join('')+'<details><summary>Every recorded network field</summary><pre>'+esc(JSON.stringify(net,null,2))+'</pre></details>';
    el('network-data-body').innerHTML=inventory;
    draw();
    // One resize listener per mounted report; old closures are removed on navigation.
    if(paint.resize)window.removeEventListener('resize',paint.resize);
    paint.resize=function(){draw();};window.addEventListener('resize',paint.resize);
  }
  return {paint:paint,normalize:normalize};
})();
