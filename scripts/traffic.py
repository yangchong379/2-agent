"""Stateful mixed traffic, not one isolated acceptance case per database."""
import argparse
import copy
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from content_agent.engine import Agent
from content_agent.models import ChatModel, MockModel
from content_agent.store import Store

KIND = 'planning'

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def code_hash(folder):
    return hashlib.sha256(json.dumps({str(p.relative_to(ROOT)).replace('\\','/'): p.read_text(encoding='utf-8') for p in sorted((ROOT/folder).rglob('*.py'))}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def build(seed=20261104, count=48):
    rng = random.Random(seed)
    data = json.loads((ROOT/'data/fixtures.json').read_text(encoding='utf-8'))
    events = []
    if KIND == 'scheduling':
        data['slots'] = [f'2026-11-{day:02}T{hour:02}:00+08:00' for day in range(5,12) for hour in range(9,22)]
        data['existing_schedule'] = [{'id': f'campaign-{ch}-{day}-{hour}', 'channel': ch, 'start': f'2026-11-{day:02}T{hour:02}:00+08:00', 'end': f'2026-11-{day:02}T{hour+1:02}:00+08:00'} for day in range(5,12) for ch in ('douyin','xiaohongshu') for hour in (12,18)]
        originals = list(data['materials'].values())
        for i in range(200):
            mid = f'U{i:03}'
            m = copy.deepcopy(rng.choices(originals, weights=[40,15,10,8,7,20])[0])
            m['id'] = mid
            data['materials'][mid] = m
            if 'copyright' not in m and rng.random()<0.65:
                data['supplements'][mid] = {'copyright':'licensed'}
    for i in range(count):
        # A frozen stream of new demands and follow-ups, independent of agent outcomes.
        roll = rng.random()
        prior = rng.randrange(len(events)) if events else None
        kind = 'new'
        if i and roll < 0.22:
            req = copy.deepcopy(events[prior]['request'])
            kind = 'repeat'
        elif i and roll < 0.32:
            req = copy.deepcopy(events[prior]['request'])
            kind = 'changed_same_id'
            if KIND == 'scheduling': req['preferred_slot'] = f'2026-11-10T{rng.choice([10,16,20]):02}:00+08:00'
            else: req['budget'] = 21 if req.get('budget')==20 else 20
        elif KIND == 'scheduling':
            req = {'request_id':f'operator-{i:03}', 'material_ids':[f'U{i:03}'], 'channel':rng.choice(['douyin','xiaohongshu']), 'preferred_slot':f'2026-11-{rng.choice([5,5,6,7,8]):02}T{rng.choice([11,12,17,18,19]):02}:00+08:00', 'hard_time':rng.random()<0.8}
            if rng.random()<0.16 and i+1<200: req['material_ids'].append(f'U{i+1:03}')
        else:
            minutes = rng.choice([20,40,50,95,150])
            req = {'request_id':f'activity-{i:03}', 'topic':rng.choices(['夏日旅行','校园生活','新品发布'],[5,4,1])[0], 'budget':rng.choice([0,5,8,10,12,15,20,None]), 'start_at':'2026-11-05T09:00+08:00', 'deadline':(datetime.fromisoformat('2026-11-05T09:00+08:00')+timedelta(minutes=minutes)).isoformat(timespec='minutes')}
            if rng.random()<0.1: req['deadline']=None
        if KIND=='scheduling' and i and i%11==6:
            req=copy.deepcopy(events[prior]['request']);req['request_id']=f'operator-followup-{i:03}';kind='review_proposal'
        # Service health is sampled independently of demand type; faults can hit repeats too.
        fault = rng.choices([None, 'save_draft' if KIND=='scheduling' else 'generate_script_always', 'query_slots' if KIND=='scheduling' else 'save_plan_once'], [85,10,5])[0]
        event = {'sequence':i+1, 'arrival_minute':i*3+rng.randrange(3), 'operator':rng.choice(['运营A','运营B','运营C']), 'intent':kind, 'request':req, 'service_fault':fault}
        if kind=='review_proposal':event['review_sequence']=prior+1
        if KIND=='scheduling' and i%9==7:
            event['external_booking']={'id':f'late-booking-{i}', 'channel':req['channel'], 'start':req['preferred_slot'], 'end':(datetime.fromisoformat(req['preferred_slot'])+timedelta(hours=1)).isoformat(timespec='minutes')}
        events.append(event)
    return data, events

def inspect(store):
    if KIND=='scheduling':
        return {t:[dict(r) for r in store.db.execute(f'SELECT * FROM {t} ORDER BY id')] for t in ('drafts','schedules','requests')}
    return {t:[dict(r) for r in store.db.execute(f'SELECT * FROM {t} ORDER BY '+('id' if t!='metadata' else 'key'))] for t in ('runs','attempts','plans')}

def audit(result, req, before, after):
    checks = {'bounded':result['model_calls']<=40}
    if KIND=='scheduling':
        from content_agent.domain import review, slot_time
        checks['draft_only']=all(not x['published'] for x in result['items'])
        checks['hard_requirements_retained']=all(x['requested_slot']==req['preferred_slot'] for x in result['items'])
        checks['save_receipts_real']=all(x['draft_save_status']!='saved' or any(d['id']==x['draft_id'] for d in after['drafts']) for x in result['items'])
        checks['confirmation_authority']=all(x['draft_save_status']!='saved' or not req['hard_time'] or x['suggested_slot']==req['preferred_slot'] or req.get('approved_slots',{}).get(x['material_id'])==x['suggested_slot'] or x['save_receipt']['confirmation']=='pending_user' or any(d['id']==x['draft_id'] and d['confirmation']=='confirmed' and d['slot']==x['suggested_slot'] for d in before['drafts']) for x in result['items'])
        # Existing drafts may be made stale by external changes; verify every newly saved receipt now.
        checks['saved_slot_currently_free']=all(x['draft_save_status']!='saved' or not store_conflicts(after,req['channel'],x['suggested_slot'],x['material_id'],slot_time) for x in result['items'])
        checks['saved_review_approved']=all(x['draft_save_status']!='saved' or x['review_status']=='approved' for x in result['items'])
        checks['unique_material_channel']=len({(d['material_id'],d['channel']) for d in after['drafts']})==len(after['drafts'])
        checks['unchanged_unrelated_drafts']=all(d in after['drafts'] for d in before['drafts'] if d['material_id'] not in req['material_ids'] or d['channel']!=req['channel'])
    else:
        from content_agent.domain import DEPENDENCIES, timestamp
        ledger=[a for a in after['attempts'] if a['run_id']==req['request_id']]
        checks['ledger_sum']=result['actual_cost_total']==sum(a['cost'] for a in ledger)
        checks['budget']=req.get('budget') is None or result['actual_cost_total']<=req['budget']
        checks['deadline']=req.get('deadline') is None or timestamp(result['business_clock'])<=timestamp(req['deadline'])
        checks['saved_claim']=not result['saved_plan'] or any(p['id']==result['saved_plan']['id'] for p in after['plans'])
        checks['old_attempts_immutable']=all(a in after['attempts'] for a in before['attempts'])
        seen=set(); ordered=True
        for a in result['attempts']:
            if a['status']=='succeeded':
                ordered &= set(DEPENDENCIES[a['tool']])<=seen and a['tool'] not in seen
                seen.add(a['tool'])
        checks['dependency_and_no_rebilling']=ordered
        checks['one_plan_per_task']=len({p['run_id'] for p in after['plans']})==len(after['plans'])
    return checks

def store_conflicts(snapshot,channel,slot,mid,parse):
    start=parse(slot); end=start+timedelta(hours=1)
    candidates=[(r['start'],r['end']) for r in snapshot['schedules'] if r['channel']==channel]+[(r['slot'],r['end']) for r in snapshot['drafts'] if r['channel']==channel and r['material_id']!=mid]
    return any(start<parse(b) and parse(a)<end for a,b in candidates)

def evaluate(mode='mock', destination=None, seed=20261104, count=48):
    if not 1<=count<=200: raise ValueError('count must be 1..200')
    dest=Path(destination or ROOT/f'examples/traffic/{mode}-{seed}')
    if dest.exists(): raise ValueError('choose a NEW output directory; existing evidence is never overwritten')
    dest.mkdir(parents=True)
    data,events=build(seed,count)
    write(dest/'dataset.json',data); write(dest/'demand-stream.json',events)
    records=[]; started=time.monotonic()
    for event in events:
        store=Store(dest/'state.sqlite',data)  # Same DB, new connection on every arrival.
        try:
            if event.get('external_booking'):
                b=event['external_booking']
                store.db.execute('INSERT INTO schedules VALUES(?,?,?,?)',(b['id'],b['channel'],b['start'],b['end']))
            before=inspect(store)
            if event.get('review_sequence'):
                earlier_path=dest/f"{event['review_sequence']:03}/result.json"
                earlier=json.loads(earlier_path.read_text(encoding='utf-8'))
                approvals={x['material_id']:x['suggested_slot'] for x in earlier.get('items',[]) if x['status']=='awaiting_confirmation' and x['suggested_slot']}
                event['request']['approved_slots']=approvals
                event['operator_review']='Synthetic operator explicitly approves only previously proposed slots; no approval inferred by agent.'
            try:
                model=MockModel() if mode=='mock' else ChatModel()
                result=Agent(model,store,data,max_steps=40,fault=event['service_fault']).run(copy.deepcopy(event['request']))
                after=inspect(store)
                checks=audit(result,event['request'],before,after)
                statuses=[x['status'] for x in result['items']] if KIND=='scheduling' else [result['status']]
                completed=(all(x['status']=='draft_ready' for x in result['items']) if KIND=='scheduling' else result['status']=='completed')
                record={'sequence':event['sequence'],'statuses':statuses,'business_goal_met':completed,'checks':checks,'invariants_passed':all(checks.values())}
            except ValueError as exc:
                if 'REQUEST_ID_REUSED' not in str(exc): raise
                after=inspect(store)
                result={'status':'request_rejected','error':'REQUEST_ID_REUSED','trace':[], 'request':event['request']}
                record={'sequence':event['sequence'],'statuses':['request_rejected'],'business_goal_met':False,'checks':{'rejection_did_not_mutate_state':before==after},'invariants_passed':before==after}
            folder=dest/f"{event['sequence']:03}"
            write(folder/'input.json',event); write(folder/'result.json',result)
            write(folder/'state-before.json',before); write(folder/'state-after.json',after)
            record['result']=f"{event['sequence']:03}/result.json"
            records.append(record)
            write(dest/'progress.json',{'completed':len(records),'total':len(events),'latest':record})
            print(f"{KIND} {event['sequence']}/{count}: {','.join(record['statuses'])}; safety={'PASS' if record['invariants_passed'] else 'FAIL'}",flush=True)
        finally: store.close()
    summary={'mode':'offline_mock' if mode=='mock' else 'live_model','seed':seed,'arrivals':count,'generated_at_utc':datetime.now(timezone.utc).isoformat(),'duration_seconds':round(time.monotonic()-started,3),'runtime_src_sha256':code_hash('src'),'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'invariants_passed':sum(r['invariants_passed'] for r in records),'goals_met':sum(r['business_goal_met'] for r in records),'status_counts':dict(Counter(s for r in records for s in r['statuses'])),'records':records,'boundary':'Synthetic serial event replay with shared database, not production traffic, concurrency benchmark or model reliability estimate. Mock is workflow-only. Arrival intents and faults frozen before running; synthetic operator follow-ups may approve only actual prior proposals. No expected ideal action path.'}
    write(dest/'summary.json',summary)
    lines=['# 连续混合需求运行记录','','一个共享数据库，按顺序多运营请求；重复、同ID改条件、业务故障与外部占位混在流量中，不逐案例清库。模拟运营确认事件只批准真实返回的待确认时段，参数在每条input中保存；不冒称真实用户授权。自然语言理解不在旧产品入口范围，需求已由模拟运营端提交为结构化表单。','','模式：'+summary['mode']+f"；需求{count}条，业务目标完成{summary['goals_met']}条，边界/状态检查{summary['invariants_passed']}/{count}。",'','业务目标完成数与安全检查分开：风险阻断、缺资料、冲突待确认及输入拒绝可能是正确响应，但不计为已完成业务。不要把边界检查全过称为全部需求完成。','','[固定需求流](demand-stream.json) · [数据](dataset.json) · [逐项统计](summary.json)','','| 到达序号 | 实际状态 | 业务目标 | 边界检查 | 输出及Trace |','|---|---|---|---|---|']
    lines += [f"| {r['sequence']} | {', '.join(r['statuses'])} | {'完成' if r['business_goal_met'] else '未完成/待处理'} | {'PASS' if r['invariants_passed'] else 'FAIL'} | [result]({r['result']}) |" for r in records]
    lines+=['','每个编号目录含input、result及前后全量状态快照；未入Git的state.sqlite仅本机续跑。故障是预先抽样的服务事件，不代表实际服务故障率。任务规划每任务独立预算；没有全公司共享钱包/排队资源，模拟时间不计API等待。排期外部占位可能使旧草稿过期；测试不会把它们当成已发布。','']
    (dest/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    return 0 if summary['invariants_passed']==count else 1

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',choices=['mock','live'],default='mock');p.add_argument('--output');p.add_argument('--seed',type=int,default=20261104);p.add_argument('--count',type=int,default=48)
    a=p.parse_args()
    raise SystemExit(evaluate(a.model,a.output,a.seed,a.count))
