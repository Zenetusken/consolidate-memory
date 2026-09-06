/* Bundled report sections. Inlined inside the archive closure; no external imports. */
var NocturneSections = (function(){
  function legacyEvidence(){
    function countLabel(v,singular,plural){return measured(v)?fmt(v)+' '+((fmt(v)===1)?singular:plural):'Not captured';}
    var D=CUR.distill;
    if(D&&typeof D==="object"&&!Array.isArray(D)){
      var counts=[measured(D.n_recurring)?D.n_recurring+' recurring':'Recurring count not captured',measured(D.n_chains)?D.n_chains+' chains':'Chain count not captured'];
      if(measured(D.commands))counts.push(countLabel(D.commands,'command','commands')+' / '+countLabel(D.sessions,'session','sessions'));
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
            +'<span class="ev">'+countLabel(t.n,'observation','observations')+' · '+countLabel(t.d,'day','days')+'</span></div>';
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
            +'<span class="ev">'+countLabel(t.n,'observation','observations')+' · '+countLabel(t.d,'day','days')+'</span></div>';
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
            +'<span class="ev">'+countLabel(t.n,'use','uses')+'</span></div>';
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
      var dmc=[measured(DM.windows_observed)?countLabel(DM.windows_observed,'window','windows'):'Usage windows not captured',
               measured(DM.eligible)?countLabel(DM.eligible,' eligible'):'Eligibility not captured'];
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
      if(dvd){
        var dvd2=dvd.replace(/^\s*eligible\s+\d+\s*(?:→|—|-)?\s*/i,"");
        var dm2=dvd2.match(/^\s*(dormant|demoted|justified|none|counter-justified)\b[:\s—-]*/i);
        var dtag=dm2?dm2[1].toLowerCase():"", drest=dm2?dvd2.slice(dm2[0].length):dvd2;
        var dcls=(dtag==="demoted"||dtag==="justified"||dtag==="counter-justified")?" ok":"";
        bits+=(bits?'<span class="vtx"> · </span>':"")
          +(dtag?'<span class="tag'+dcls+'">'+esc(dtag)+'</span>':"")+'<span class="vtx">'+esc(drest)+'</span>';
      }
      if(!bits)bits='<span class="vtx" style="color:var(--faint)">Demotion verdict not captured.</span>';
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
        el("reg-counts").textContent=nConf?(nConf+" placed"):(nAwait?(nAwait+" proposed"):(measured(WP.n_fleet)?WP.n_fleet+' fleet candidates':Array.isArray(WP.candidates)?wc.length+' captured candidates':'Candidate counts not captured'))+(num(WP.n_blocked,0)>0?" · "+num(WP.n_blocked,0)+" blocked":"");
        var vd=String(WP.verdict||"");
        if(vd) el("reg-verdict").innerHTML=verdictHtml(vd,"declined|confirmed|awaiting|nothing|blocked");
        else el("reg-verdict").innerHTML='<span class="vtx" style="color:var(--faint)">Placement verdict not captured.</span>';
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
  function decisions(c){if(!Array.isArray(c.entries))return null;var result=Object.create(null);c.entries.forEach(function(e){var k=e&&e.action?String(e.action):'Unspecified';result[k]=(result[k]||0)+1;});return result;}
  function decisionText(c){var d=decisions(c);return d===null?'Not captured':Object.keys(d).length?Object.keys(d).map(function(k){return d[k]+' '+k;}).join(' · '):'0 decisions';}
  function mutationText(c){var a=object(c.audit);if(Array.isArray(a.operations))return a.operations.length+' observed file operation'+(a.operations.length===1?'':'s');var stores=['memory','claude_md','repo_doc'], keys=['created','modified','deleted'];if(stores.every(function(s){return keys.every(function(k){return measured(g(a,s+'.'+k,null));});}))return stores.reduce(function(n,s){return n+keys.reduce(function(x,k){return x+a[s][k];},0);},0)+' observed file mutations';return 'File mutations not fully captured';}
  function reveal(id){
    var box=el(id);if(!box)return;
    var section=box.closest('.blk');if(section&&section.classList.contains('collapsed'))section.querySelector('.shead').click();
    for(var ancestor=box;ancestor&&ancestor!==section;ancestor=ancestor.parentElement)if(ancestor.tagName==='DETAILS')ancestor.open=true;
    var target=box===section?box.querySelector('.shead'):box.tagName==='DETAILS'?box.querySelector('summary'):box;
    box.scrollIntoView({block:'start',behavior:'auto'});
    if(!target.matches('button,a[href],input,select,textarea,summary,[tabindex]')){target.setAttribute('tabindex','-1');target.addEventListener('blur',function(){target.removeAttribute('tabindex');},{once:true});}
    target.focus({preventScroll:true});
  }
  function bindEvidence(box){box.querySelectorAll('[data-evidence]').forEach(function(b){b.onclick=function(){reveal(b.getAttribute('data-evidence'));};});}
  function evidenceButton(text,id){return '<button type="button" class="evidence-link" data-evidence="'+esc(id)+'">'+esc(text)+'</button>';}
  function sourceNote(label,c){
    var stamp=g(c||{},'marker.timestamp',null),when='';
    if(stamp){var date=new Date(stamp);when=' · '+(isNaN(date.getTime())?esc(stamp):'<time datetime="'+esc(stamp)+'">'+esc(date.toLocaleString('en-US',{month:'short',day:'numeric',year:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'UTC'}))+' UTC</time>');}
    return '<span class="source-label">Source</span> '+esc(label)+when;
  }
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
    var h='<p class="evidence-label">Recorded outcome</p><p class="summary-outcome">'+esc(outcome)+'</p><div class="summary-evidence">';
    h+='<div><span class="evidence-label">Claims checked</span>'+evidenceButton((measured(v.confirmed)?v.confirmed+' confirmed claim'+(v.confirmed===1?'':'s'):'Confirmed claims not captured')+' · '+assessment.claims,'verification-evidence')+'</div>';
    h+='<div><span class="evidence-label">Observed file changes</span>'+evidenceButton(mutationText(c),'file-changes')+'</div><div><span class="evidence-label">Decisions recorded</span>'+evidenceButton(decisionText(c),'entries-blk')+'</div></div>';
    if(assessment.errors.length)h+='<p class="summary-attention">Needs attention · '+evidenceButton(assessment.errors[0].label,assessment.errors[0].target)+(assessment.errors.length>1?' · '+evidenceButton((assessment.errors.length-1)+' further items','attention-items'):'')+'</p>';
    h+='<p id="summary-source" class="source-note">'+sourceNote('Saved dream outcome, verification, and decision ledger',c)+'</p>';
    el('dream-summary').innerHTML=h;bindEvidence(el('dream-summary'));
    var arc=el('dream-arc');arc.replaceChildren();
    arc.setAttribute('role','region');arc.setAttribute('aria-label','Dream narration');
    function paragraph(text,captured){var p=document.createElement('p');p.className=captured?'dream-voice':'dream-capture-note';p.textContent=text;arc.appendChild(p);}
    function unwrapped(text){return text.trim().replace(/^(\*{1,3}|_{1,3})(\S(?:[\s\S]*\S)?)\1$/,'$2');}
    function passage(v,label){
      if(typeof v!=='string'||!v.trim()){
        paragraph(label+': '+(v==null||typeof v==='string'?'Not captured':JSON.stringify(v)),false);return;
      }
      // Captured prose sometimes carries Markdown quote/emphasis wrappers. CSS
      // supplies the voice; keep literal symbols inside the prose and never parse HTML.
      var paragraphs=v.replace(/\r\n?/g,'\n').split('\n').map(function(line){return line.replace(/^\s*>\s?/,'');}).join('\n').trim().split(/\n\s*\n/).map(unwrapped);
      // Strip paragraph wrappers first so separately wrapped paragraphs cannot
      // be mistaken for one wrapper spanning the complete passage.
      unwrapped(paragraphs.join('\n\n')).split(/\n\s*\n/).forEach(function(text){paragraph(text,true);});
    }
    if(!Object.keys(d).length){paragraph('Dream narration: Not captured',false);return;}
    passage(d.sleep,'Sleep');
    if(Array.isArray(d.beats)&&d.beats.length)d.beats.forEach(function(beat,i){passage(beat,'Passage '+(i+1));});
    else passage(Array.isArray(d.beats)?null:d.beats,'Intermediate passages');
    passage(d.wake,'Wake');
  }
  function evidence(c,assessment){
    legacyEvidence();
    var v=object(c.verification),h=object(c.health),pf=object(c.preflight),audit=object(c.audit),ops=array(audit.operations);
    var pendingWorkflow=Object.keys(object(c.distill)).length>0&&(!String(g(c,'distill.verdict','')).trim()||/^proposed\b/i.test(String(c.distill.verdict))&&!/\bdeclined\b/i.test(String(c.distill.verdict)));
    var pendingDemotion=!!c.demotion&&!String(g(c,'demotion.verdict','')).trim()&&num(c.demotion.eligible)>0;
    var pendingRegistrar=array(g(c,'workflow_proposals.candidates',[])).some(function(x){return !x.disposition||['proposed','awaiting-confirmation'].indexOf(x.disposition)>=0;});
    var recallMisses=array(g(c,'usage.misses',[])).length>0;
    var workflowPending=pendingWorkflow||pendingDemotion||pendingRegistrar;
    el('pass-note').textContent=assessment.errors.length?'Recorded exceptions':workflowPending?'Decision pending':'Saved evidence';
    el('health-summary').replaceChildren();el('health-summary').hidden=true;
    function heading(id,label,state){el(id).querySelector('summary').innerHTML='<span class="evidence-title">'+esc(label)+'</span><span class="health-status" data-state="'+esc(state)+'">'+esc(state)+'</span>';}
    heading('verification-evidence','Verification evidence',assessment.claims);
    heading('store-checks','Store checks',assessment.stores);
    heading('file-changes','Observed file changes',assessment.changes);
    heading('workflow-evidence','Recall & workflow decisions',workflowPending?'Decision pending':recallMisses?'Needs attention':c.usage||c.distill||c.demotion||c.workflow_proposals?'Recorded':'Not captured');
    var attention=assessment.errors.slice();
    if(workflowPending)attention.push({label:'A workflow or memory decision is pending',target:'workflow-evidence'});
    if(recallMisses)attention.push({label:'An archived fact was needed again',target:'workflow-evidence'});
    el('attention-items').innerHTML=attention.length?'<p class="attention-heading">Needs attention</p><ul>'+attention.map(function(e){return '<li>'+evidenceButton(e.label,e.target)+'</li>';}).join('')+'</ul>':'';bindEvidence(el('attention-items'));
    var claimSummary=['confirmed','corrected','unverifiable'].map(function(k){return measured(v[k])?v[k]+' '+k:k+' not captured';}).join(' · ');
    el('verify').innerHTML='<p class="evidence-conclusion">'+esc(claimSummary)+'</p>'+line('Verification method',v.method)+(c._integrity?'<p class="adverse">Procedure integrity: '+esc(c._integrity.reason)+'</p>':'')+extra('Complete verification record',c.verification);
    function observedList(label,items){return line(label,Array.isArray(items)?items.length?items.map(value).join(', '):'None recorded':null);}
    function capturedDate(stamp){if(typeof stamp!=='string'||!stamp)return null;var d=new Date(stamp);return isNaN(d.getTime())?stamp:d.toLocaleString('en-US',{month:'short',day:'numeric',year:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'UTC'})+' UTC';}
    var healthDetails='<details class="captured-details"><summary>Complete store-check record</summary>'+capturedTree(c.health)+'</details>';
    el('store-evidence').innerHTML=line('Index pointers',typeof h.index_pointers_ok==='boolean'?h.index_pointers_ok?'Recorded clear':'Needs attention':null)
      +observedList('Broken pointers',h.broken)+observedList('Dangling links',h.dangling_links)+observedList('Orphan stores',h.slug_orphans)
      +'<div class="preflight-evidence"><h4>Environment preflight</h4>'+line('Captured at',capturedDate(pf.at))+observedList('Failure IDs',pf.fails)+observedList('Warning IDs',pf.warns)+'</div>'
      +healthDetails+extra('Remediation evidence',c.remediation)+extra('Identity & registry state',c.identity)+extra('Maintenance decisions',c.maintenance);
    var storeLabels={memory:'Memory files',claude_md:'Agent instructions',repo_doc:'Repository documents'};
    var accounting=['memory','claude_md','repo_doc'].map(function(s){return '<h4>'+storeLabels[s]+'</h4>'+['created','modified','deleted','token_delta'].map(function(k){return line(k.replace(/_/g,' '),audit[s]&&audit[s][k]);}).join('');}).join('');
    el('audit').innerHTML='<p class="evidence-conclusion">'+esc(mutationText(c))+'</p><div id="observed-file-rows"></div>'
      +(Array.isArray(audit.operations)?ops.length?'':'<p class="capture-note">No file operations were recorded.</p>':'<p class="capture-note">Individual file operations were not captured. Available diffs are linked in Changes & decisions.</p>')
      +'<details class="captured-details"><summary>File counts & observation window</summary>'+line('Observation window',audit.window)+accounting+'</details>'
      +extra('Conservation evidence',audit.conservation)+extra('Complete file-change record',c.audit);
    var fileRows=el('observed-file-rows');ops.forEach(function(op){var row=document.createElement('div');row.className='observed-file';
      var store=String(op.store||'memory'),path=String(op.path||''),keys=[store+'/'+path];
      // Older records include the store prefix in path; newer records may keep
      // it in store alone. Connect only when the captured diff resolves uniquely.
      if(path.indexOf(store+'/')===0)keys.push(path);
      keys=keys.filter(function(key){return capturedDiff(key);});
      var hasDiff=keys.length===1,key=hasDiff?keys[0]:'',b=document.createElement(hasDiff?'button':'span');
      if(hasDiff){b.type='button';b.className='file-evidence-link';b.dataset.p=key;b.setAttribute('aria-label','View captured diff for '+(op.path||'Unnamed file'));b.onclick=function(){openDiff(key);};}else b.className='file-evidence-name';
      b.textContent=op.path||'Unnamed file';if(hasDiff){var hint=document.createElement('span');hint.className='diff-action';hint.setAttribute('aria-hidden','true');hint.textContent='View diff';b.appendChild(hint);}row.appendChild(b);var desc=document.createElement('span');desc.className='file-operation';desc.textContent=value(op.op)+(hasDiff?'':' · Diff not captured');row.appendChild(desc);fileRows.appendChild(row);});
    el('usage-evidence').innerHTML='<h4>Observed recall</h4><p class="evidence-conclusion">'+esc(measured(g(c,'usage.reads',null))?c.usage.reads+' observed reads':'Reads not captured')+'</p><p class="capture-note">Observations belong to the recorded usage window.</p>'+extra('Usage window & complete recall evidence',c.usage);
    [['distill-blk','Complete workflow evidence',c.distill,pendingWorkflow],['demotion-blk','Complete demotion evidence',c.demotion,pendingDemotion||recallMisses],['registrar-blk','Complete registrar evidence & decline lineage',c.workflow_proposals,pendingRegistrar]].forEach(function(r){var box=el(r[0]);box.open=!!r[3];if(r[2]!=null)box.insertAdjacentHTML('beforeend',extra(r[1],r[2]));});
    ['verification-evidence','store-checks','file-changes'].forEach(function(id){el(id).open=assessment.errors.some(function(e){return e.target===id;});});
    el('workflow-evidence').open=workflowPending||recallMisses;
  }
  var activityResize;
  function activity(c,cycles){
    if(activityResize)window.removeEventListener('resize',activityResize);
    var selected=cycles.length-1,detailsOpen=false,controls=el('activity-controls'),scroller=el('trend').parentElement;
    controls.innerHTML='<button type="button" class="activity-previous" aria-label="Previous dream">←</button><label for="activity-cycle-select">Dream</label><select id="activity-cycle-select">'+cycles.map(function(r,i){var raw=g(r,'marker.timestamp',null),date=raw?new Date(raw):null,label=date&&!isNaN(date.getTime())?date.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'}):'Date not captured';return '<option value="'+i+'">'+(i+1)+' · '+esc(label)+'</option>';}).join('')+'</select><button type="button" class="activity-next" aria-label="Next dream">→</button>';
    controls.querySelector('select').onchange=function(){selectCycle(Number(this.value));};
    controls.querySelector('.activity-previous').onclick=function(){selectCycle(selected-1);};
    controls.querySelector('.activity-next').onclick=function(){selectCycle(selected+1);};
    activityResize=draw;window.addEventListener('resize',activityResize);
    function count(r){return Array.isArray(r.entries)?r.entries.length:null;}
    function observedReads(r){var n=g(r,'usage.reads',null);return measured(n)&&n>=0?n:null;}
    function stamp(r){var raw=g(r,'marker.timestamp',null),d=raw?new Date(raw):null;return !d?'Date not captured':isNaN(d.getTime())?esc(raw):'<time datetime="'+esc(raw)+'">'+esc(d.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'}))+'</time>';}
    function inspect(){
      var currentDetails=el('activity-inspector').querySelector('.activity-details');if(currentDetails)detailsOpen=currentDetails.open;
      var r=cycles[selected]||{},f=object(facts(r)),v=object(r.verification),n=count(r),reads=observedReads(r);
      el('activity-inspector').innerHTML='<div class="activity-summary"><div class="activity-summary-head"><div><div class="inspector-kicker">Dream '+(selected+1)+' <span class="activity-date">'+stamp(r)+'</span></div><h4>'+esc(r._outcome||'Outcome not captured')+'</h4></div><a class="open-dream" href="#sel='+selected+'">Open this dream →</a></div>'
        +'<div class="activity-summary-facts"><p class="activity-stat"><span class="evidence-label">Decisions</span><strong>'+esc(value(n))+'</strong></p><p class="activity-stat"><span class="evidence-label">Observed reads</span><strong>'+esc(value(reads))+'</strong><span class="activity-stat-note">'+(reads==null?'No recall observation saved':g(r,'usage.window',null)==null?'Usage window not captured':'In its recorded usage window')+'</span></p></div></div>'
        +'<details class="activity-details"'+(detailsOpen?' open':'')+'><summary>Cycle details</summary>'+line('Decisions',decisionText(r))+line('Observed mutations',mutationText(r))+line('Fact count change',measured(f.before)&&measured(f.after)?f.before+' → '+f.after+' ('+(f.after-f.before>=0?'+':'')+(f.after-f.before)+')':null)+line('Verification',Object.keys(v).length?['confirmed','corrected','unverifiable'].map(function(k){return k+': '+value(v[k]);}).join(' · '):null)+line('Recorded reads',g(r,'usage.reads',null))+line('Usage window',g(r,'usage.window',null))+line('Rigor',g(r,'rigor.applied',null))+line('Captured at',g(r,'marker.timestamp',null))+'</details>';
      el('activity-inspector').querySelector('.open-dream').onclick=function(e){if(!e.defaultPrevented&&e.button===0&&!e.metaKey&&!e.ctrlKey&&!e.shiftKey&&!e.altKey&&this.hash===location.hash){e.preventDefault();reveal('dream-blk');}};
    }
    function selectCycle(index){
      if(index<0||index>=cycles.length)return;selected=index;
      el('trend').querySelectorAll('.activity-cycle').forEach(function(group){var active=Number(group.dataset.cycle)===selected;group.setAttribute('aria-pressed',String(active));group.setAttribute('tabindex',active?'0':'-1');});
      controls.querySelector('select').value=String(selected);controls.querySelector('.activity-previous').disabled=selected<=0;controls.querySelector('.activity-next').disabled=selected>=cycles.length-1;inspect();
    }
    function draw(){
      var N=cycles.length,W=scroller.clientWidth||el('history-blk').clientWidth,svg=el('trend'),rig=el('rigor'),left=12,right=W-12,step=N>1?(right-left)/(N-1):0;
      var hadGraphFocus=svg.contains(document.activeElement)&&document.activeElement.classList.contains('activity-cycle');
      el('hist-note').textContent=N+' captured dream'+(N===1?'':'s');
      function text(target,x,y,s,cls){var t=S('text',{x:x,y:y,class:cls||'activity-label'});t.textContent=s;target.appendChild(t);return t;}
      function at(i){return N===1?W/2:left+i*step;}
      var totals=cycles.map(count),reads=cycles.map(observedReads);
      var observedMaxD=Math.max(0,...totals.map(function(x){return x||0;})),observedMaxR=Math.max(0,...reads.map(function(x){return x||0;})),maxD=Math.max(1,observedMaxD),maxR=Math.max(1,observedMaxR);
      var fullReads=reads.some(function(n){return n>0;}),readBase=fullReads?193:160,cycleY=fullReads?222:189,H=cycleY+10,pointR=N>80?1.5:2.5;
      svg.textContent='';rig.textContent='';rig.hidden=true;rig.setAttribute('hidden','');svg.setAttribute('viewBox','0 0 '+W+' '+H);svg.style.width=W+'px';svg.style.height=H+'px';
      scroller.onscroll=null;scroller.scrollLeft=0;
      function range(values,max,unit){return values.every(function(n){return n===null;})?'Not captured':(max===0?'0':'0–'+max)+' per '+unit;}
      text(svg,0,18,'Decisions','activity-axis-label');text(svg,W,18,range(totals,observedMaxD,'dream'),'activity-axis-note').setAttribute('text-anchor','end');
      text(svg,0,125,'Observed reads','activity-axis-label');text(svg,W,125,range(reads,observedMaxR,'window'),'activity-axis-note').setAttribute('text-anchor','end');
      [90,readBase].forEach(function(y){svg.appendChild(S('line',{x1:left,y1:y,x2:right,y2:y,stroke:'var(--rule)'}));});
      function series(values,base,height,max,name,color){
        var segment=[];function flush(){if(segment.length>1)svg.appendChild(S('polyline',{points:segment.join(' '),fill:'none',stroke:color,'stroke-width':1.6,'data-series':name,'aria-hidden':'true'}));segment=[];}
        values.forEach(function(n,i){if(n===null){flush();return;}segment.push(at(i)+','+(base-(n/max)*height));});flush();
      }
      series(totals,90,52,maxD,'decisions','var(--accent)');series(reads,readBase,fullReads?52:0,maxR,'reads','var(--data)');
      cycles.forEach(function(r,index){var x=at(index),description='Dream '+(index+1)+' · '+decisionText(r)+' · observed reads: '+value(reads[index]),group=S('g',{class:'activity-cycle','data-cycle':index,tabindex:index===selected?0:-1,role:'button','aria-label':description,'aria-pressed':String(index===selected)});svg.appendChild(group);
        group.appendChild(S('line',{x1:x,y1:30,x2:x,y2:readBase+9,stroke:'transparent','stroke-width':Math.max(2,Math.min(44,step||44)),class:'activity-hit'}));
        group.appendChild(S('line',{x1:x,y1:30,x2:x,y2:readBase+9,class:'activity-selection'}));
        [[totals[index],90,52,maxD,'decisions','var(--accent)'],[reads[index],readBase,fullReads?52:0,maxR,'reads','var(--data)']].forEach(function(s){
          if(s[0]===null){group.appendChild(S('line',{x1:x-2,y1:s[1]+5,x2:x+2,y2:s[1]+5,class:'activity-gap','data-series':s[4],stroke:'var(--faint)'}));return;}
          group.appendChild(S('circle',{cx:x,cy:s[1]-(s[0]/s[3])*s[2],r:pointR,fill:s[5],class:'activity-point','data-series':s[4],'data-value':s[0]}));
        });
        var desc=S('title');desc.textContent=description+' · window: '+value(g(r,'usage.window',null));group.appendChild(desc);
        group.onclick=function(e){var pointerIndex=e.detail&&N>1?Math.max(0,Math.min(N-1,Math.round((e.clientX-svg.getBoundingClientRect().left-left)/step))):index;selectCycle(pointerIndex);if(e.detail)svg.querySelector('[data-cycle="'+pointerIndex+'"]').focus({preventScroll:true});};group.onkeydown=function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();e.stopPropagation();selectCycle(index);}if(['ArrowLeft','ArrowRight','Home','End'].indexOf(e.key)>=0){e.preventDefault();e.stopPropagation();var nextIndex=e.key==='Home'?0:e.key==='End'?cycles.length-1:index+(e.key==='ArrowRight'?1:-1),next=svg.querySelector('[data-cycle="'+nextIndex+'"]');if(next){selectCycle(nextIndex);next.focus({preventScroll:true});}}};
      });
      var ticks=Math.min(N,Math.max(2,Math.floor(W/100)));for(var t=0;t<ticks;t++){var index=ticks===1?0:Math.round(t*(N-1)/(ticks-1)),label=text(svg,at(index),cycleY,'Dream '+(index+1),'activity-value activity-cycle-number');label.setAttribute('text-anchor',ticks===1?'middle':t===0?'start':t===ticks-1?'end':'middle');}
      var legend=el('activity-legend');if(!legend){legend=document.createElement('div');legend.id='activity-legend';legend.className='activity-legend';scroller.after(legend);}legend.innerHTML='<span>Choose a point or dream to see its outcome.</span><span>Gaps mean not captured.</span>';
      selectCycle(selected);
      if(hadGraphFocus){var target=svg.querySelector('[data-cycle="'+selected+'"]');if(target)target.focus({preventScroll:true});}
    }
    el('activity-table-body').innerHTML='<p>Counts and cadence are recorded history. Usage windows can overlap; reads are never summed across windows.</p><table><thead><tr><th>Dream</th><th>Timestamp</th><th>Facts before → after</th><th>Cadence</th><th>Decisions</th><th>Observed reads</th><th>Usage window</th><th>Rigor</th></tr></thead><tbody>'+cycles.map(function(r,i){var f=object(facts(r)),now=Date.parse(g(r,'marker.timestamp','')),before=i?Date.parse(g(cycles[i-1],'marker.timestamp','')):NaN;var cadence=isFinite(now)&&isFinite(before)?((now-before)/3600000).toFixed(1)+'h':null;return '<tr>'+[i+1,g(r,'marker.timestamp',null),value(f.before)+' → '+value(f.after),cadence,decisionText(r),g(r,'usage.reads',null),g(r,'usage.window',null),g(r,'rigor.applied',null)].map(function(v){return '<td>'+esc(value(v))+'</td>';}).join('')+'</tr>';}).join('')+'</tbody></table>';draw();
  }
  function paint(c,cycles){
    // Appended uncapped evidence must reset on every rich/sparse navigation.
    document.querySelectorAll('#pass-blk > details .captured-details').forEach(function(e){e.remove();});
    var assessment=assess(c);summary(c,assessment);evidence(c,assessment);activity(c,cycles);
    el('activity-source').innerHTML=sourceNote('Saved decision ledgers and recall observations');
    el('health-source').innerHTML=sourceNote('Recorded verification, store checks, and file observations',c);
    el('ledger-source').innerHTML=sourceNote('Consolidation decisions; linked diffs show observed file changes',c);
  }
  return {paint:paint,assess:assess};

})();
