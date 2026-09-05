/* Bundled report sections. Inlined inside the archive closure; no external imports. */
var NocturneSections = (function(){
  function legacyEvidence(){
    var D=CUR.distill;
    if(D&&typeof D==="object"&&!Array.isArray(D)){
      var counts=[num(D.n_recurring)+" recurring",num(D.n_chains)+" chains"];
      if(num(D.commands)>0)counts.push(fmt(num(D.commands))+" commands / "+num(D.sessions)+" session"+(num(D.sessions)!==1?"s":""));
      // v0.1.58 — the firewall-suppression count, so the transparency counter reaches the human view.
      if(num(D.secrets_omitted)>0)counts.push(num(D.secrets_omitted)+" secret-shaped");
      // L2 (v0.4.2): the top recurring commands — the BODY list below the verdict, never the
      // header's counts line (long template names wrapped the two-column header across rows).
      // Idiom (`template ×N Nd`), capped at 3 with an explicit +N more (a legacy record without
      // `top` is unchanged — the list stays hidden).
      var dtop=(Array.isArray(D.top)?D.top:[]).filter(function(t){return t&&typeof t==="object";});
      el("dstl-counts").textContent=counts.join(" · ");
      if(dtop.length){
        el("dstl-top-list").style.display="";
        el("dstl-top-list").innerHTML=dtop.map(function(t){
          return '<div class="dstl-row"><span class="cmd">'+esc(String(t.t||"?"))+'</span>'
            +'<span class="ev">×'+num(t.n)+' · '+num(t.d)+'d</span></div>';
        }).join("")
          ;
        el("dstl-top").style.display="";
      }
      // the contract's other distill evidence — chains (the workflow glue the gate reads
      // FIRST) and the skill-adoption tally; same row idiom + explicit +N more caps
      var dchains=(Array.isArray(D.top_chains)?D.top_chains:[]).filter(function(t){return t&&typeof t==="object";});
      if(dchains.length){
        el("dstl-chains-list").style.display="";
        el("dstl-chains-head").style.display="";
        el("dstl-chains-list").innerHTML=dchains.map(function(t){
          var seg=(Array.isArray(t.t)?t.t:[]).map(function(x){return esc(String(x));}).join(" → ");
          return '<div class="dstl-row"><span class="cmd">'+seg+'</span>'
            +'<span class="ev">×'+num(t.n)+' · '+num(t.d)+'d</span></div>';
        }).join("")
          ;
        el("dstl-top").style.display="";
      }
      var dused=(Array.isArray(D.used)?D.used:[]).filter(function(t){return t&&typeof t==="object"&&String(t.a||"").trim();});
      if(dused.length){
        el("dstl-used-list").style.display="";
        el("dstl-used-head").style.display="";
        el("dstl-used-list").innerHTML=dused.map(function(t){
          return '<div class="dstl-row"><span class="cmd">'+esc(String(t.a))+'</span>'
            +'<span class="ev">×'+num(t.n)+'</span></div>';
        }).join("")
          ;
        el("dstl-top").style.display="";
      }
      var vd=String(D.verdict==null?"":D.verdict), m=vd.match(/^\s*(created|proposed|nothing)\b[:\s]*/i);
      var tag=m?m[1].toLowerCase():"", rest=m?vd.slice(m[0].length):vd;
      // a DECLINED proposal is a resolved state — neutral tag, never the pending-amber (the at-a-glance
      // distinction the schema encodes as 'awaiting confirmation' vs 'declined').
      var declined=tag==="proposed"&&/\bdeclined\b/i.test(rest);
      var cls=tag==="created"?" ok":(tag==="proposed"&&!declined)?" warn":"";
      // a disposition-only verdict ('nothing:') IS a recorded verdict — show the tag alone; the
      // incomplete-step fallback fires only when the verdict string is entirely empty.
      el("dstl-verdict").innerHTML=(tag?'<span class="tag'+cls+'">'+esc(tag)+'</span>':"")
        +(rest?'<span class="vtx">'+wrapCmds(rest)+'</span>'
          :(tag?"":'<span class="vtx" style="color:var(--faint)">no verdict recorded — a distill step without one is incomplete</span>'));
      el("distill-blk").style.display="";
    }
    // v0.1.67 (Phase C) — the demotion block + the miss badge (both key-gated; legacy cycles render
    // byte-identically with the blocks hidden). Disposition counts stay entries[]-derived (the ledger);
    // this shows the SEED (windows/eligible/surfaced/struck) + the one model verdict sentence.
    var DM=CUR.demotion, U=CUR.usage;
    var missN=(U&&typeof U==="object"&&Array.isArray(U.misses))?U.misses.length:0;
    if((DM&&typeof DM==="object"&&!Array.isArray(DM))||missN>0){
      DM=(DM&&typeof DM==="object"&&!Array.isArray(DM))?DM:{};
      var dmc=[num(DM.windows_observed)+" window"+(num(DM.windows_observed)!==1?"s":""),
               num(DM.eligible)+" eligible"];
      var surf=Array.isArray(DM.surfaced)?DM.surfaced:[], stk=Array.isArray(DM.struck)?DM.struck:[];
      var surfStr=surf.filter(function(s){return typeof s==="string";});
      if(surf.length)dmc.push(surf.length+" surfaced · inspect all demotion evidence below");
      if(stk.length)dmc.push(stk.length+" struck (read this window)");
      el("demo-counts").textContent=dmc.join(" · ");
      var bits="";
      if(missN>0)bits+='<span class="tag" style="color:var(--crit);border-color:var(--crit)">'+missN+" MISS"+(missN!==1?"ES":"")+'</span>'
        +'<span class="vtx" style="color:var(--crit)">'+esc(U.misses.filter(function(m){return typeof m==="string";}).join(", "))
        +' — archived-tier fact'+(missN!==1?"s":"")+' read organically; re-promote to MEMORY.md</span>';
      // v0.1.68 — mirror the distill panel's tag+prose grammar: a leading disposition word (dormant/
      // demoted/justified/none) becomes the bordered tag, same as distill's created/proposed/nothing —
      // so a dormant triage reads as a badge + sentence, not bare italic text beside a badged sibling.
      var dvd=String(DM.verdict==null?"":DM.verdict);
      if(!dvd&&missN===0&&num(DM.eligible)===0)dvd="dormant — not enough evidence yet";
      if(dvd){
        var dvd2=dvd.replace(/^\s*eligible\s+\d+\s*(?:→|—|-)?\s*/i,"");
        var dm2=dvd2.match(/^\s*(dormant|demoted|justified|none|counter-justified)\b[:\s—-]*/i);
        var dtag=dm2?dm2[1].toLowerCase():"", drest=dm2?dvd2.slice(dm2[0].length):dvd2;
        var dcls=(dtag==="demoted"||dtag==="justified"||dtag==="counter-justified")?" ok":"";
        bits+=(bits?'<span class="vtx"> · </span>':"")
          +(dtag?'<span class="tag'+dcls+'">'+esc(dtag)+'</span>':"")+'<span class="vtx">'+esc(drest)+'</span>';
      }
      if(!bits)bits='<span class="vtx" style="color:var(--faint)">no verdict recorded — a triage with eligible candidates and no verdict is incomplete</span>';
      el("demo-verdict").innerHTML=bits;
      el("demotion-blk").style.display="";
    }
    // v0.1.87/W-C: registrar render surface. Cards are MODEL decisions only
    // (awaiting / confirmed / declined-with-a-name). Mechanical co-occurrence of
    // git add is not a workflow — never inferred as awaiting, never a card.
    var WP=CUR.workflow_proposals;
    if(D||(WP&&typeof WP==="object"&&!Array.isArray(WP))){
      var capN=el("reg-cap");
      if(capN){capN.textContent="";capN.style.display="none";}
      if(WP&&typeof WP==="object"&&!Array.isArray(WP)){
        var wc=Array.isArray(WP.candidates)?WP.candidates.filter(function(c){return c&&typeof c==="object";}):[];
        function distinctiveGuess(cand, form){
          function one(s){
            var toks=String(s||"").split(/\s+/).filter(Boolean);
            if(!toks.length) return false;
            var head=toks[0].replace(/^.*\//,"");
            if(head==="git"||head==="gh") return false;
            if(/^(python3?|pypy3?|bash|sh|zsh|node|ruby|perl)$/.test(head)){
              for(var i=1;i<toks.length;i++){
                var t=toks[i];
                if(t.charAt(0)==="-"||t==="."||t==="..") continue;
                if(t.indexOf("/")>=0||t.indexOf("\\")>=0) return true;
                if(/\.(py|sh|bash|rb|js|mjs|ts|rs|go|rhai)$/i.test(t)) return true;
              }
              return false;
            }
            return true;
          }
          if(form==="chain"||/\s*→\s*/.test(cand)){
            var sides=String(cand).split(/\s*→\s*/).filter(Boolean);
            if(sides.length>=2) return sides.some(one);
          }
          return one(cand);
        }
        function isDistinct(c){
          var d=(c.mechanical||{}).distinctive;
          if(d===false||d==="false"||d===0||d==="0") return false;
          if(d===true||d==="true"||d===1||d==="1") return true;
          return distinctiveGuess(String(c.candidate||""), String(c.form||"command"));
        }
        function isFleetRec(c){return truthy((c.mechanical||{}).fleet_recurrence);}
        function isSpread(c){return truthy((c.mechanical||{}).day_spread);}
        var named=wc.filter(function(c){
          var raw=String(c.disposition||"").trim();
          if(raw==="awaiting-confirmation"||raw==="confirmed") return true;
          return raw==="declined" && String(c.name||"").trim();
        });
        var nAwait=named.filter(function(c){return String(c.disposition)==="awaiting-confirmation";}).length;
        var nConf=named.filter(function(c){return String(c.disposition)==="confirmed";}).length;
        var nFleet=num(WP.n_fleet, wc.filter(function(c){return isFleetRec(c)&&isSpread(c)&&isDistinct(c);}).length);
        var nSpread=num(WP.n_day_spread, wc.filter(function(c){return isFleetRec(c)&&!isSpread(c)&&isDistinct(c);}).length);
        el("reg-counts").textContent=nConf?(nConf+" placed"):(nAwait?(nAwait+" proposed"):(nFleet?"none proposed":"none this pass"))+(num(WP.n_blocked,0)>0?" · "+num(WP.n_blocked,0)+" blocked":"");
        var vd=String(WP.verdict||"");
        if(vd) el("reg-verdict").innerHTML=verdictHtml(vd,"declined|confirmed|awaiting|nothing|blocked");
        else if(nFleet && !named.length) el("reg-verdict").innerHTML='<span class="vtx" style="color:var(--faint)">'+nFleet+" distinctive command"+(nFleet!==1?"s":"")+" crossed projects; none proposed as an artifact.</span>";
        else if(!named.length) el("reg-verdict").innerHTML='<span class="vtx" style="color:var(--faint)">Nothing distinctive showed up on more than one project this pass.</span>';
        else el("reg-verdict").innerHTML="";
        function regStatus(c){
          var raw=String(c.disposition||"").trim();
          if(raw==="confirmed") return {tag:"confirmed", cls:"ok"};
          if(raw==="declined") return {tag:"declined", cls:""};
          if(raw==="awaiting-confirmation") return {tag:"awaiting", cls:"warn"};
          return {tag:raw||"unjudged", cls:""};
        }
        function andList(arr){
          arr=arr.filter(Boolean);
          if(!arr.length) return "";
          if(arr.length===1) return arr[0];
          if(arr.length===2) return arr[0]+" and "+arr[1];
          if(arr.length>4) return arr.length+" projects";
          return arr.slice(0,-1).join(", ")+" and "+arr[arr.length-1];
        }
        function cardHtml(c){
          var ev=(c.evidence&&typeof c.evidence==="object")?c.evidence:{};
          var st=regStatus(c);
          var nm=String(c.name||c.candidate||"?");
          var nodes=Array.isArray(ev.nodes)?ev.nodes.map(prettyNode):[];
          var seen=nodes.length?(nodes.length>4?("on "+nodes.length+" projects"):("on "+andList(nodes))):"";
          var stats=[];
          if(seen) stats.push(seen);
          if(ev.d!=null && isFinite(num(ev.d))) stats.push(num(ev.d)+"d");
          if(ev.n!=null && isFinite(num(ev.n))) stats.push("×"+num(ev.n));
          return '<div class="reg-card"><div class="stamp"><span class="tag '+st.cls+'">'+esc(st.tag)+'</span></div>'
            +'<div><div class="cmd">'+esc(nm)+'</div>'
            +(stats.length?'<div class="ev">'+esc(stats.join(" · "))+'</div>':"")+'</div></div>';
        }
        var board=named.map(cardHtml).join("");
        if(nSpread) board+='<div class="reg-more">'+nSpread+" showed up on more than one project but only a single day each.</div>";
        // the unjudged evidence: persisted sample rows (disposition-less candidates — e.g. the
        // day-spread sample or an unjudged fleet-candidate) render as UNJUDGED cards, never
        // stamped; when only counts exist (generic-cli rows are counts-only by design), an
        // honest note naming the real split says so instead of an empty board under a
        // non-zero header count
        var evRows=wc.filter(function(c){return named.indexOf(c)<0&&String(c.disposition||"").trim()!=="declined";});
        if(evRows.length){
          board+='<div class="reg-group"><div class="gh">unjudged — evidence, not a docket</div>'
            +evRows.map(cardHtml).join("")

            +'</div>';
        }
        if(!board && num(WP.n_blocked,0)>0){
          var bParts=[];
          if(num(WP.n_generic,0)>0) bParts.push(num(WP.n_generic,0)+" generic-cli");
          if(num(WP.n_day_spread,0)>0) bParts.push(num(WP.n_day_spread,0)+" single-day");
          var bRest=Math.max(0,num(WP.n_blocked,0)-num(WP.n_generic,0)-num(WP.n_day_spread,0));
          if(bRest>0) bParts.push(bRest+" single-node");
          board='<div class="reg-group"><div class="gh">blocked rows</div><span class="reg-more">'
            +num(WP.n_blocked,0)+" blocked"+(bParts.length?" — "+bParts.join(" · "):"")
            +" — counts-only by design (samples are not persisted in the archive; the terminal consult shows them).</span></div>";
        }
        // the fleet's decline lineage — the anchors the gate consults for the
        // materially-new-evidence rule; rendered as the registrar's own card shape
        var anchors=Array.isArray(WP.decline_anchors)?WP.decline_anchors:[];
        if(anchors.length){
          board+='<div class="reg-group"><div class="gh">decline lineage — other nodes declined these</div>'
            +anchors.map(function(an){
              var aTops=(Array.isArray(an.top)?an.top:[]).map(function(t){return esc(String(t.t||"?"));}).join(" · ");
              return '<div class="reg-card"><span class="stamp">'+esc(String(an.node||"?"))+'</span>'
                +'<span class="cmd">'+esc(String(an.verdict||""))
                +(aTops?'<em>'+aTops+'</em>':'')+'</span></div>';
            }).join("")

            +'</div>';
        }
        el("reg-board").innerHTML=board;
        if(capN && nAwait){
          capN.textContent="Proposed during the dream — nothing is created until you confirm there.";
          capN.style.display="";
        }
      }else{
        el("reg-counts").textContent="skipped";
        el("reg-verdict").innerHTML='<span class="vtx" style="color:var(--faint)">Fleet placement wasn’t reviewed this pass.</span>';
        el("reg-board").innerHTML="";
      }
      el("registrar-blk").style.display="";
    }
  }
  function object(v){return v&&typeof v==='object'&&!Array.isArray(v)?v:{};}
  function array(v){return Array.isArray(v)?v:[];}
  function measured(v){return typeof v==='number'&&isFinite(v);}
  function value(v){return v==null?'Not captured':typeof v==='object'?JSON.stringify(v):String(v);}
  function line(label,v){return '<div class="inspector-row"><span>'+esc(label)+'</span><b>'+esc(value(v))+'</b></div>';}
  function facts(c){return g(c,'budget.recall_facts',{});}
  function decisions(c){if(!Array.isArray(c.entries))return null;var result={};c.entries.forEach(function(e){var k=e&&e.action?String(e.action):'Unspecified';result[k]=(result[k]||0)+1;});return result;}
  function decisionText(c){var d=decisions(c);return d===null?'Not captured':Object.keys(d).length?Object.keys(d).map(function(k){return d[k]+' '+k;}).join(' · '):'0 decisions';}
  function mutationText(c){var a=object(c.audit);if(Array.isArray(a.operations))return a.operations.length+' observed file operation'+(a.operations.length===1?'':'s');var stores=['memory','claude_md','repo_doc'], keys=['created','modified','deleted'];if(stores.every(function(s){return keys.every(function(k){return measured(g(a,s+'.'+k,null));});}))return stores.reduce(function(n,s){return n+keys.reduce(function(x,k){return x+a[s][k];},0);},0)+' observed file mutations';return 'File mutations not fully captured';}
  function reveal(id){var box=el(id),section=box.closest('.blk');if(section&&section.classList.contains('collapsed'))section.querySelector('.shead').click();if(box.tagName==='DETAILS')box.open=true;box.scrollIntoView({block:'start',behavior:'auto'});var target=box.querySelector('summary')||box;target.setAttribute('tabindex','-1');target.focus({preventScroll:true});}
  function bindEvidence(box){box.querySelectorAll('[data-evidence]').forEach(function(b){b.onclick=function(){reveal(b.getAttribute('data-evidence'));};});}
  function evidenceButton(text,id){return '<button type="button" class="evidence-link" data-evidence="'+esc(id)+'">'+esc(text)+'</button>';}
  function capturedTree(v){
    // An uncapped structured disclosure preserves scanner rows, windows and future
    // optional fields without guessing an individual check result from a total.
    if(v==null)return '<p class="capture-note">Not captured</p>';
    if(Array.isArray(v))return v.length?'<ol class="evidence-rows">'+v.map(function(x){return '<li>'+capturedTree(x)+'</li>';}).join('')+'</ol>':'<span>0 captured rows</span>';
    if(typeof v==='object')return Object.keys(v).length?'<dl class="evidence-fields">'+Object.keys(v).map(function(k){return '<div><dt>'+esc(k.replace(/_/g,' '))+'</dt><dd>'+capturedTree(v[k])+'</dd></div>';}).join('')+'</dl>':'<span>No fields captured</span>';
    return '<span>'+esc(String(v))+'</span>';
  }
  function extra(label,v){return '<details class="captured-details"><summary>'+esc(label)+'</summary>'+capturedTree(v)+'</details>';}
  function assess(c){
    var v=object(c.verification),h=object(c.health),a=object(c.audit),pf=object(c.preflight),rem=object(c.remediation),id=object(c.identity),errors=[];
    function add(test,label,target){if(test)errors.push({label:label,target:target});}
    add(c._integrity,'Procedure integrity: '+g(c,'_integrity.reason','recorded failure'),'verification-evidence');
    add(num(v.unverifiable)>0,v.unverifiable+' unverifiable claim'+(v.unverifiable===1?'':'s'),'verification-evidence');
    add(array(pf.fails).length,'Preflight failures: '+array(pf.fails).join(', '),'store-checks');
    add(array(pf.warns).length,'Preflight warnings: '+array(pf.warns).join(', '),'store-checks');
    add(h.index_pointers_ok===false||array(h.broken).length,'Broken index pointers'+(array(h.broken).length?': '+array(h.broken).join(', '):''),'store-checks');
    add(array(h.dangling_links).length,'Dangling links: '+array(h.dangling_links).map(value).join(', '),'store-checks');
    add(array(h.slug_orphans).length,'Orphan stores: '+array(h.slug_orphans).map(value).join(', '),'store-checks');
    add(['missing_node_type','malformed_scope','malformed_origin','index_mismatch'].some(function(k){return num(g(h,'schema_drift.'+k,0))>0 && (k!=='index_mismatch'||!(truthy(g(c,'budget.index.over',false))||truthy(rem.standing_justified)));}),'Schema drift recorded','store-checks');
    add(g(a,'conservation.possible_loss',false),'Conservation concern: possible lost relocation','file-changes');
    add(truthy(rem.over_ceiling),'Hard ceiling exceeded: new shares held','store-checks');
    add(truthy(rem.required)&&!(measured(rem.achieved_index)&&rem.achieved_index<=IDXB),'Unresolved index remediation','store-checks');
    add(num(id.conflicts)>0,id.conflicts+' mirror conflicts','store-checks');
    add(id.registry_state&&['healthy','absent'].indexOf(id.registry_state)<0,'Registry: '+id.registry_state,'store-checks');
    var claimKeys=['confirmed','corrected','unverifiable'], claimPresent=claimKeys.filter(function(k){return measured(v[k]);}).length;
    var healthKeys=['index_pointers_ok','broken','dangling_links','slug_orphans','schema_drift'],healthPresent=healthKeys.filter(function(k){return h[k]!=null;}).length;
    var storeComplete=typeof pf.at==='string'&&Array.isArray(pf.fails)&&Array.isArray(pf.warns)&&healthPresent===5&&typeof h.index_pointers_ok==='boolean'&&Array.isArray(h.broken)&&Array.isArray(h.dangling_links)&&Array.isArray(h.slug_orphans)&&h.schema_drift&&typeof h.schema_drift==='object';
    var auditComplete=['memory','claude_md','repo_doc'].every(function(s){return ['created','modified','deleted'].every(function(k){return measured(g(a,s+'.'+k,null));});});
    function status(target,has,complete){return errors.some(function(e){return e.target===target;})?'Needs attention':!has?'Not captured':complete?'Recorded clear':'Partially captured';}
    return {errors:errors,claims:status('verification-evidence',claimPresent,claimPresent===3),stores:status('store-checks',healthPresent||Object.keys(pf).length,storeComplete),changes:status('file-changes',Object.keys(a).length,auditComplete||Array.isArray(a.operations))};
  }
  function summary(c,assessment){
    var outcome=c._outcome||'Outcome not captured',v=object(c.verification),d=object(c.dream);
    el('dream-blk').style.display='';el('dream-note').textContent='Recorded outcome & captured voice';
    var h='<p class="summary-outcome">'+esc(outcome)+'</p><div class="summary-evidence">';
    h+=evidenceButton((measured(v.confirmed)?v.confirmed+' confirmed claim'+(v.confirmed===1?'':'s'):'Confirmed claims not captured')+' · '+assessment.claims,'verification-evidence');
    h+=evidenceButton(mutationText(c),'file-changes')+evidenceButton(decisionText(c),'entries-blk')+'</div>';
    if(assessment.errors.length)h+='<p class="summary-attention">Needs attention · '+evidenceButton(assessment.errors[0].label,assessment.errors[0].target)+(assessment.errors.length>1?' · '+evidenceButton((assessment.errors.length-1)+' further items','attention-items'):'')+'</p>';
    el('dream-summary').innerHTML=h;bindEvidence(el('dream-summary'));
    var beats=array(d.beats),valid=beats.length===6&&beats.every(function(b){return typeof b==='string'&&b.trim();});
    var labels=['Locate','Orient','Gather','Verify','Consolidate','Measure & wake'];
    function voice(v){if(typeof v!=='string')return v==null?'Not captured':JSON.stringify(v);return v.split('\n').map(function(l){return l.replace(/^\s*>\s?/,'').replace(/^\s*\*(.*)\*\s*$/,'$1');}).join('\n');}
    var arc=el('dream-arc');arc.innerHTML='<div class="dream-sequence"><div class="dream-bookend"><span class="passage-label">Sleep</span><p class="dream-voice">'+esc(voice(d.sleep))+'</p></div><div class="dream-passages"><div id="dream-beats" class="beat-controls" role="group" aria-label="Captured dream passages"></div><p id="dream-passage" class="dream-voice" aria-live="polite"></p></div><div class="dream-bookend"><span class="passage-label">Wake</span><p class="dream-voice">'+esc(voice(d.wake))+'</p></div></div>';
    var controls=el('dream-beats');beats.forEach(function(beat,i){var b=document.createElement('button');b.type='button';b.textContent=valid?'Phase '+i+' · '+labels[i]:'Beat '+(i+1);b.onclick=function(){controls.querySelectorAll('button').forEach(function(btn){btn.setAttribute('aria-pressed',String(btn===b));});el('dream-passage').textContent=voice(beat);};controls.appendChild(b);if(i===0)b.click();});
    if(!beats.length)el('dream-passage').textContent='Intermediate passages were not captured.';
    var full=document.createElement('details');full.id='complete-dream';full.innerHTML='<summary>Read the complete dream</summary>';
    ['sleep','beats','wake'].forEach(function(k){var values=k==='beats'?beats:[d[k]];values.forEach(function(v,i){if(v==null)return;var p=document.createElement('p');p.className='dream-voice';p.textContent=typeof v==='string'?v:JSON.stringify(v);var label=document.createElement('div');label.className='passage-label';label.textContent=k==='beats'?(valid?'Phase '+i+' · '+labels[i]:'Beat '+(i+1)):k;full.appendChild(label);full.appendChild(p);});});arc.appendChild(full);
  }
  function evidence(c,assessment){
    legacyEvidence();
    el("pass-note").textContent=outcomeOf(CUR)+" · "+(Array.isArray(c.entries)?c.entries.length+" decisions":"Decisions not captured");
    el('health-summary').innerHTML=[['Claims',assessment.claims,'verification-evidence'],['Store integrity',assessment.stores,'store-checks'],['Observed changes',assessment.changes,'file-changes']].map(function(s){return '<div class="health-status" data-state="'+esc(s[1])+'"><span>'+s[0]+'</span>'+evidenceButton(s[1],s[2])+'</div>';}).join('');bindEvidence(el('health-summary'));
    el('attention-items').innerHTML=assessment.errors.length?'<p class="attention-heading">Needs attention</p><ul>'+assessment.errors.map(function(e){return '<li>'+evidenceButton(e.label,e.target)+'</li>';}).join('')+'</ul>':'';bindEvidence(el('attention-items'));
    var v=object(c.verification),h=object(c.health),pf=object(c.preflight);
    el('verify').innerHTML='<p>Verification judgments · '+esc(assessment.claims)+'</p>'+['confirmed','corrected','unverifiable','method'].map(function(k){return line(k,v[k]);}).join('')+extra('All verification fields',c.verification)+(c._integrity?'<p class="adverse">Procedure integrity: '+esc(c._integrity.reason)+'</p>':'');
    el('store-evidence').innerHTML='<p>Recorded store checks · '+esc(assessment.stores)+'</p>'+line('Index pointers',h.index_pointers_ok==null?null:h.index_pointers_ok?'Recorded clear':'Needs attention')+capturedTree(c.health)
      +'<h4>Environment preflight</h4>'+line('Captured at',pf.at)+line('Failure IDs',Array.isArray(pf.fails)?pf.fails.join(', ')||'0 recorded failures':null)+line('Warning IDs',Array.isArray(pf.warns)?pf.warns.join(', ')||'0 recorded warnings':null)
      +'<p class="capture-note">The verdict records IDs and a timestamp. Individual check outcomes are not present in this snapshot.</p>'
      +extra('Remediation evidence',c.remediation)+extra('Identity & registry state',c.identity)+extra('Maintenance decisions',c.maintenance);
    var audit=object(c.audit),ops=array(audit.operations);
    el('audit').innerHTML='<p>'+esc(mutationText(c))+'. Decisions are listed separately.</p>'+line('Observation window',audit.window)
      +['memory','claude_md','repo_doc'].map(function(s){return '<h4>'+esc(s.replace(/_/g,' '))+'</h4>'+['created','modified','deleted','token_delta'].map(function(k){return line(k,audit[s]&&audit[s][k]);}).join('');}).join('')
      +'<div id="observed-file-rows"></div>'+extra('Conservation evidence',audit.conservation)+extra('Every audit field',c.audit);
    var fileRows=el('observed-file-rows');ops.forEach(function(op){var row=document.createElement('div');row.className='observed-file';var key=String(op.store||'memory')+'/'+String(op.path||''),b=document.createElement('button');b.type='button';b.textContent=op.path||'Unnamed file';b.className='file-evidence-link';b.onclick=function(){openDiff(key);};row.appendChild(b);var desc=document.createElement('span');desc.textContent=value(op.op)+' · '+(op.token_delta==null?'token delta not captured':op.token_delta+' tokens');row.appendChild(desc);fileRows.appendChild(row);});
    el('usage-evidence').innerHTML='<h4>Observed recall</h4>'+line('Usage window',g(c,'usage.window',null))+line('Observed reads',g(c,'usage.reads',null))+line('Mentions',g(c,'usage.mentions',null))+extra('All recall observations (including procedure exclusions and misses)',c.usage);
    [['distill-blk','All workflow evidence',c.distill],['demotion-blk','All demotion evidence',c.demotion],['registrar-blk','All registrar evidence & decline lineage',c.workflow_proposals]].forEach(function(r){if(r[2]!=null)el(r[0]).insertAdjacentHTML('beforeend',extra(r[1],r[2]));});
    var pending=!!c.distill&&!String(g(c,'distill.verdict','')).trim()||!!c.demotion&&!String(g(c,'demotion.verdict','')).trim()||array(g(c,'workflow_proposals.candidates',[])).some(function(x){return !x.disposition||['proposed','awaiting-confirmation'].indexOf(x.disposition)>=0;});
    ['verification-evidence','store-checks','file-changes'].forEach(function(id){el(id).open=assessment.errors.some(function(e){return e.target===id;})||({ 'verification-evidence':assessment.claims,'store-checks':assessment.stores,'file-changes':assessment.changes}[id]==='Partially captured');});
    el('workflow-evidence').open=pending;
  }
  function activity(c,cycles){
    var span=12,spanChoice='12',selected=cycles.length-1,controls=el('activity-controls');controls.innerHTML='<span>Dreams ending at this selection</span>';
    [12,24,'All captured'].forEach(function(n){var b=document.createElement('button');b.type='button';b.textContent=String(n);b.onclick=function(){span=n==='All captured'?cycles.length:n;spanChoice=String(n);draw();};controls.appendChild(b);});
    function title(c){return c._outcome||'Outcome not captured';}
    function inspect(){var r=cycles[selected],f=facts(r),v=object(r.verification);el('activity-inspector').innerHTML='<div class="inspector-kicker">Dream '+(selected+1)+' · local inspection</div><h4>'+esc(title(r))+'</h4>'+line('Decisions',decisionText(r))+line('Observed mutations',mutationText(r))+line('Fact count change',measured(f.before)&&measured(f.after)?f.before+' → '+f.after+' ('+(f.after-f.before>=0?'+':'')+(f.after-f.before)+')':null)+line('Verification',Object.keys(v).length?['confirmed','corrected','unverifiable'].map(function(k){return k+': '+value(v[k]);}).join(' · '):null)+line('Observed reads',g(r,'usage.reads',null))+line('Usage window',g(r,'usage.window',null))+'<a class="open-dream" href="#sel='+selected+'">Open this dream →</a>';}
    function draw(){
      var start=Math.max(0,cycles.length-span),shown=cycles.slice(start),N=shown.length,W=Math.max(920,N*62),H=244,svg=el('trend'),rig=el('rigor'),left=120,step=(W-left-16)/Math.max(1,N);
      controls.querySelectorAll('button').forEach(function(b){b.setAttribute('aria-pressed',String(b.textContent===spanChoice));});
      svg.textContent='';rig.textContent='';svg.setAttribute('viewBox','0 0 '+W+' '+H);svg.style.width=W+'px';svg.style.height=H+'px';rig.setAttribute('viewBox','0 0 '+W+' 48');rig.style.width=W+'px';rig.style.height='48px';
      el('hist-note').textContent=shown.length+' of '+cycles.length+' captured dreams · decisions and recall';
      function text(target,x,y,s,cls){var t=S('text',{x:x,y:y,class:cls||'activity-label'});t.textContent=s;target.appendChild(t);return t;}
      var totals=shown.map(function(r){return Array.isArray(r.entries)?r.entries.length:null;}),reads=shown.map(function(r){var v=g(r,'usage.reads',null);return measured(v)?v:null;});
      var maxD=Math.max(1,...totals.map(function(x){return x||0;})),maxR=Math.max(1,...reads.map(function(x){return x||0;}));
      var actions=Array.from(new Set(shown.flatMap(function(r){return Object.keys(decisions(r)||{});}))).sort();var palette=['var(--data)','var(--accent)','var(--warn)','var(--ok)','var(--crit)','var(--ink2)'];
      text(svg,8,34,'Decisions');text(svg,8,54,'0–'+maxD+' per dream');text(svg,8,148,'Observed reads');text(svg,8,168,'0–'+maxR+' per window');text(rig,8,27,'Captured rigor');
      shown.forEach(function(r,i){var x=left+i*step,index=start+i,group=S('g',{class:'activity-cycle','data-cycle':index,tabindex:0,role:'button','aria-label':'Inspect dream '+(index+1),'aria-pressed':String(index===selected)});svg.appendChild(group);group.appendChild(S('rect',{x:x+2,y:8,width:step-4,height:220,rx:4,class:'activity-selection'}));
        var d=decisions(r),bottom=99;
        if(d===null)text(group,x+step/2-3,75,'—');else{Object.keys(d).sort().forEach(function(a){var h=d[a]*64/maxD;group.appendChild(S('rect',{x:x+step*.25,y:bottom-h,width:step*.5,height:h,fill:palette[actions.indexOf(a)%palette.length],'data-action':a}));bottom-=h;});text(group,x+step/2-4,116,String(totals[i]));}
        if(reads[i]===null)text(group,x+step/2-3,182,'—');else {group.appendChild(S('rect',{x:x+step*.4,y:202-reads[i]*58/maxR,width:step*.2,height:reads[i]*58/maxR,fill:'var(--data)'}));text(group,x+step/2-4,220,String(reads[i]));}
        var desc=S('title');desc.textContent='Dream '+(index+1)+' · '+decisionText(r)+' · reads: '+value(reads[i])+' · window: '+value(g(r,'usage.window',null));group.appendChild(desc);
        function choose(){selected=index;svg.querySelectorAll('.activity-cycle').forEach(function(g){g.setAttribute('aria-pressed',String(+g.dataset.cycle===index));});inspect();}
        group.onclick=choose;group.onkeydown=function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();e.stopPropagation();choose();}if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();e.stopPropagation();var next=svg.querySelector('[data-cycle="'+(index+(e.key==='ArrowRight'?1:-1))+'"]');if(next)next.focus();}};
        text(svg,x+step/2-6,240,String(index+1));var rigor=g(r,'rigor.applied',null);text(rig,x+6,26,rigor==null?'—':String(rigor),'rigor-category');
      });
      var legend=el('activity-legend');if(!legend){legend=document.createElement('div');legend.id='activity-legend';legend.className='activity-legend';el('activity-controls').after(legend);}legend.innerHTML=actions.map(function(a,i){return '<span><i style="background:'+palette[i%palette.length]+'"></i>'+esc(a)+'</span>';}).join('')+'<span>— observation not captured</span>';
      inspect();
    }
    el('activity-table-body').innerHTML='<p>Counts and cadence are recorded history. Usage windows can overlap; reads are never summed across windows.</p><table><thead><tr><th>Dream</th><th>Timestamp</th><th>Facts before → after</th><th>Cadence</th><th>Decisions</th><th>Observed reads</th><th>Usage window</th><th>Rigor</th></tr></thead><tbody>'+cycles.map(function(r,i){var f=facts(r),now=Date.parse(g(r,'marker.timestamp','')),before=i?Date.parse(g(cycles[i-1],'marker.timestamp','')):NaN;var cadence=isFinite(now)&&isFinite(before)?((now-before)/3600000).toFixed(1)+'h':null;return '<tr>'+[i+1,g(r,'marker.timestamp',null),value(f.before)+' → '+value(f.after),cadence,decisionText(r),g(r,'usage.reads',null),g(r,'usage.window',null),g(r,'rigor.applied',null)].map(function(v){return '<td>'+esc(value(v))+'</td>';}).join('')+'</tr>';}).join('')+'</tbody></table>';draw();
  }
  function paint(c,cycles){
    // Appended uncapped evidence must reset on every rich/sparse navigation.
    document.querySelectorAll('#pass-blk > details .captured-details').forEach(function(e){e.remove();});
    var assessment=assess(c);summary(c,assessment);evidence(c,assessment);activity(c,cycles);
  }
  return {paint:paint,assess:assess};

})();
