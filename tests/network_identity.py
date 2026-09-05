#!/usr/bin/env python3
"""Canonical physical-holding regressions; stdlib only, isolated fictional stores."""
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/consolidate-memory/scripts'))
import sync_global as sg
import memory_status as ms
from fact_schema import stable_fact_id


def run(check):
    def canonical(domain, name, scope='stack-general'):
        fm = {'domain': domain, 'name': name, 'scope': scope}
        text = '---\nname: %s\ndomain: %s\nscope: %s\nmetadata:\n  node_type: memory\n---\nA fictional shared lesson.\n' % (name, domain, scope)
        return name, fm, text, Path('/fictional') / domain / (name+'.md')

    recs = [canonical('work', 'one-fact'), canonical('tools', 'one-fact')]
    index = sg._canonical_identity_index(recs)
    one = recs[0][2]
    native = sg._as_mirror(one, 'one-fact', fact_id=stable_fact_id('work', 'one-fact'), domain='work')
    resolve = lambda stem, body, domain: sg._physical_fact_identity(stem, body, domain, index)
    check('identity: native and namespaced mirror filenames join one canonical',
          resolve('one-fact', native, 'work') == resolve('work--one-fact', native, 'tools'))
    check('identity: a local renamed mirror retains its stamped identity', resolve('renamed', native, 'tools')[0] == stable_fact_id('work', 'one-fact'))
    legacy = '---\nmetadata:\n  global_ref: one-fact\n---\nold mirror\n'
    check('identity: legacy unqualified mirror uses its holder domain', resolve('one-fact', legacy, 'work')[0] != resolve('one-fact', legacy, 'tools')[0])
    check('identity: unknown holder domain stays unresolved', resolve('one-fact', legacy, 'unknown') is None)
    check('identity: contradictory canonical stamp stays unresolved', resolve('one-fact', native.replace(stable_fact_id('work', 'one-fact'), 'wrong-id'), 'work') is None)
    check('identity: contradictory reference stays unresolved', resolve('one-fact', native.replace('global_ref: one-fact', 'global_ref: other'), 'work') is None)
    check('identity: contradictory scope stays unresolved', resolve('one-fact', native.replace('scope: stack-general', 'scope: user-global'), 'work') is None)
    check('identity: contradictory domain stamps stay unresolved', resolve('one-fact', native.replace('canonical_domain: work', 'canonical_domain: tools'), 'work') is None)
    ambiguous = sg._canonical_identity_index([canonical('tools', 'work--one-fact'), recs[0]])
    body = legacy.replace('global_ref: one-fact', 'global_ref: work--one-fact')
    check('identity: ambiguous native -- stem versus namespace stays unresolved', sg._physical_fact_identity('work--one-fact', body, 'tools', ambiguous) is None)
    duplicate = sg._canonical_identity_index([recs[0], recs[0]])
    check('identity: duplicate canonical sources stay unresolved', sg._physical_fact_identity('one-fact', native, 'work', duplicate) is None)
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        stores=[]
        for i in range(10):
            store=root/('same-label-%d'%i)/'memory';store.mkdir(parents=True);stores.append(store)
            (store/'MEMORY.md').write_text('[recall](%s.md)\n'%('one-fact' if i==0 else 'work--one-fact'))
            (store/('one-fact.md' if i==0 else 'work--one-fact.md')).write_text(native)
        overlay={str(s.resolve()): ('work' if i==0 else 'tools',[]) for i,s in enumerate(stores)}
        with patch.object(sg,'project_store',return_value=stores[0]), patch('store_context.resolve_store',return_value=SimpleNamespace(domain_id='work')), patch.object(sg,'_network_nodes',return_value=stores), patch.object(sg,'_all_domain_records',return_value=[recs[0]]), patch.object(sg,'_fleet_overlay',return_value=(overlay,set(),[])), patch.object(sg,'_fleet_group_rows',return_value={}), patch.object(sg,'_fleet_display_names',return_value={str(s):'Duplicate name' for s in stores}), patch.object(sg,'_node_label',return_value='same label'):
            net=sg.token_network(root,fleet=True)
        check('identity: ten physical holders yield one fact and 45 exact compatibility edges', net['totals']['stack']==1 and len(net['fact_holdings'])==1 and net['fact_holdings'][0]['held_n']==10 and len(net['stack_edges'])==45 and all(e['n']==1 for e in net['stack_edges']))
        check('identity: duplicate display labels do not merge project identities', len({n['node'] for n in net['nodes']})==10 and len({n['sid'] for n in net['nodes']})==10 and all(n['display_name']=='Duplicate name' for n in net['nodes']))
        check('identity: token accounting is unchanged by canonical resolution', all(all(n[k]==sg._node_tokens(s)[k] for k in ('always_loaded_tokens','mirror_index_tokens','recall_tokens','facts','shared')) for n,s in zip(sorted(net['nodes'],key=lambda n:n['sid']),sorted(stores,key=lambda s:s.parent.name))))
        badfile=stores[0]/'unreadable.md';badfile.write_text('unreadable fixture')
        read=sg._safe_read_text
        diagnostics={'read_failures':0,'unresolved_identities':0}
        with patch.object(sg,'_safe_read_text',side_effect=lambda p:None if p==badfile else read(p)):
            sg._classify_node(stores[0],canonical_index=index,holder_domain='work',diagnostics=diagnostics)
        check('identity: failed physical reads are counted',diagnostics['read_failures']==1)
    def holding(i,count=10,prefix='sid-',scope='stack-general'):
        return {'fact_id':'id-%03d'%i,'name':'fact-%03d'%i,'domain':'work','scope':scope,'holders':{prefix+str(n) for n in range(count)}}
    holdings={str(i):holding(i) for i in range(150)}
    emitted,capture=sg._bounded_fact_holdings(holdings,'sid-0')
    check('identity: 120-fact cap preserves exact pre-limit totals',len(emitted)==120 and capture['facts_total']==150 and capture['holder_refs_total']==1500 and capture['holder_refs_emitted']==1200)
    huge={'x':holding(1,2100)}
    emitted,capture=sg._bounded_fact_holdings(huge,'sid-2099')
    check('identity: holder-reference cap retains held_n and prioritizes trigger',len(emitted[0]['holder_sids'])==2000 and emitted[0]['held_n']==2100 and emitted[0]['holder_sids'][0]=='sid-2099')
    emitted,capture=sg._bounded_fact_holdings({'x':holding(1,150,'long-'+('x'*600))},'absent')
    check('identity: UTF-8 JSON byte cap retains exact totals',len(json.dumps(emitted).encode())<=65536 and capture['holder_refs_total']==150 and capture['holder_refs_emitted']<150)
    emitted, capture=sg._bounded_fact_holdings({'x':holding(1,150,'<&'+('雪'*120))},'absent')
    from render_html import _safe_embed
    check('identity: byte cap includes HTML delimiter and non-ASCII escaping', len(_safe_embed(emitted).encode())<=65536 and capture['incidence_bytes']<=65536)
    addressed=[]
    for i in range(12):
        rec=canonical('work','addressed-%02d'%i);rec[1]['recipients']='[bridge]';addressed.append(rec)
    with patch.object(sg,'_all_domain_records',return_value=addressed):
        layer=sg._fleet_layers(Path('/fictional'),None,{'nodes':[{'node':'one','domain':'work','groups':['bridge']}]},{'one':set()},{'bridge'},[],{'bridge':{'home_domain':'work'}},fleet_full=False)
    check('identity: group fact truncation retains exact addressed count',len(layer['group_links'][0]['facts'])==8 and layer['group_links'][0]['facts_total']==12)
    ranked={'a':holding(1,20), 'b':holding(2,1,'trigger-',scope='user-global')}
    emitted,capture=sg._bounded_fact_holdings(ranked,'trigger-0')
    check('identity: trigger facts outrank stack facts and holder count',emitted[0]['fact_id']=='id-002')
    check('identity: incidence is stable across input order',sg._bounded_fact_holdings(dict(reversed(list(holdings.items()))),'sid-0')==sg._bounded_fact_holdings(holdings,'sid-0'))
    check('identity: registry-only holders are never constrained to physical nodes',not ms.validate_cycle_record({'network':{'basis_scope':'fleet','nodes':[{'node':'one'}],'totals':{'nodes':1},'universal_facts':[{'held':20}]}}))
    invalid={'network':{'basis_scope':'fleet','nodes':[{'node':'one','sid':'sid'}], 'fact_holdings':[{'fact_id':'id','held_n':1,'holder_sids':['sid','ghost']}], 'capture':{'facts_total':0,'facts_emitted':1}}}
    warnings=ms.validate_cycle_record(invalid)
    check('identity: validator rejects unknown holders and impossible capture counts',any('unknown holders' in w for w in warnings) and any('held_n' in w for w in warnings) and any('counts' in w for w in warnings))
    for bad in [None, 'bad', {'sid':[]}]:
        malformed={'network':{'basis_scope':'fleet','nodes':bad,'fact_holdings':[{'fact_id':[], 'holder_sids':[['bad']], 'held_n':0}]}}
        check('identity: malformed incidence warns without crashing '+repr(bad),bool(ms.validate_cycle_record(malformed)))


if __name__=='__main__':
    def check(name,ok):
        print(('PASS ' if ok else 'FAIL ')+name)
        assert ok,name
    run(check)
