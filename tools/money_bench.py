#!/usr/bin/env python3
"""PRSI Money Bench v4 — does building make the NEXT build cheaper?"""
import argparse, json, os, sys, time
from pathlib import Path
RESULTS = Path('/media/exuber/Elements/DataFlux/MechanogenesisBenchDEV/money_bench_v4')
PRICE=100; ACCEPT=5; TOKEN_PRICE=0.008/1000
def speed_price(secs):
    if secs < 10: return 1.5   # 极速交付，用户加价50%
    if secs < 30: return 1.2   # 快速交付，用户加价20%
    if secs < 60: return 1.0   # 正常速度，原价
    if secs < 120: return 0.8  # 偏慢，用户要8折
    return 0.5                 # 太慢，用户只出半价
MODELS = {
 'glm-5.3-flash': {'model':'glm-5.3-flash','api_base':'https://api.z.ai/api/anthropic','protocol':'anthropic','key_env':'ZAI_KEY','max_tokens':16000,'temp':0.3},
 'glm-5.3': {'model':'glm-5.3','api_base':'https://api.z.ai/api/anthropic','protocol':'anthropic','key_env':'ZAI_KEY','max_tokens':32000,'temp':0.6},
 'mimo-v2.6-pro': {'model':'openai/mimo-v2.6-pro','api_base':'https://api.xiaomimimo.com/v1','protocol':'openai','key_env':'MIMO_KEY','max_tokens':32000,'temp':0.6},
 'mimo-v2.6-flash': {'model':'openai/mimo-v2.6-flash','api_base':'https://api.xiaomimimo.com/v1','protocol':'openai','key_env':'MIMO_KEY','max_tokens':32000,'temp':0.6},
}
DEMANDS = [
 "Build a phone dock for 78x12x160mm phone. Desk 420x280mm. From scratch.",
 "Customer upgraded to 90x14x175mm phone. Adapt the dock. MUST reuse the base from round 1.",
 "Add earbuds bay (65x48x28mm). MUST keep the adapted dock and add to it.",
 "Add tablet stand (250x10x175mm) behind. Combine all modules. MUST reuse dock+earbuds.",
 "Desk shrank to 300x200mm! Shrink but keep ALL functions. MUST optimize accumulated design.",
]
SYS = '''Design a desk workstation. Return ONLY JSON with schema="workstation-csg/1".
Ops: box(size), cylinder(radius,height), union(inputs), difference(inputs), transform(input,xyz,rpy), capital(asset_id).
capital(asset_id) imports a PREVIOUSLY BUILT module — using it is FASTER and CHEAPER than rebuilding.
If previous modules exist in the "capital" list, you SHOULD use them via capital nodes.
Parts: {"name","node","role(frame|module|tooling)","xyz","rpy"}. Max 64 nodes. mm, XY desk.
Example: {"schema":"workstation-csg/1","h":"reused+new","nodes":[{"id":"old","op":"capital","asset_id":"r1"},{"id":"n","op":"box","size":[60,40,40]},{"id":"u","op":"union","inputs":["old","n"]}],"parts":[{"name":"base","node":"old","role":"frame","xyz":[0,0,0],"rpy":[0,0,0]},{"name":"new","node":"u","role":"module","xyz":[0,0,10],"rpy":[0,0,0]}]}'''
JUDGE = 'Rate 0-10. Return ONLY JSON: {"rating":<n>,"accepted":<bool>,"feedback":"<t>"}'
def a_call(base,key,model,sys_,user,mt,tp):
 import httpx
 body={'model':model,'max_tokens':mt,'system':sys_,'messages':[{'role':'user','content':user}],'temperature':tp,'stream':True}
 blocks,usage,done={},{},False
 with httpx.Client(timeout=httpx.Timeout(600,connect=30),trust_env=False) as c:
  with c.stream('POST',base.rstrip('/')+'/v1/messages',headers={'x-api-key':key,'anthropic-version':'2023-06-01'},json=body) as r:
   if r.status_code!=200: raise RuntimeError(f'HTTP {r.status_code}')
   for line in r.iter_lines():
    if not line.startswith('data:'): continue
    d=line[5:].strip()
    if d=='[DONE]': break
    try: item=json.loads(d)
    except: continue
    k=item.get('type')
    if k=='content_block_start': blocks[item['index']]=dict(item['content_block'])
    elif k=='content_block_delta':
     b=blocks.setdefault(item['index'],{'type':'text','text':''})
     for key in ('text','thinking'):
      if key in item['delta']: b[key]=b.get(key,'')+item['delta'][key]
    elif k=='message_delta': usage.update(item.get('usage') or {})
    elif k=='message_stop': done=True; break
 text=''.join(blocks[i].get('text','') for i in sorted(blocks) if blocks[i].get('type')=='text')
 return text,{'input':usage.get('input_tokens',0),'output':usage.get('output_tokens',0)}
def call(spec,sys_,user,folder,label):
 folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
 key=os.environ.get(spec['key_env'],'none') if spec.get('key_env') else 'none'
 t0=time.monotonic()
 if spec.get('protocol')=='anthropic':
  raw,usage=a_call(spec['api_base'],key,spec['model'],sys_,user,spec['max_tokens'],spec['temp'])
 else:
  from litellm import completion
  r=completion(model=spec['model'],api_base=spec['api_base'],api_key=key,messages=[{'role':'system','content':sys_},{'role':'user','content':user}],max_tokens=spec['max_tokens'],temperature=spec['temp'],timeout=600)
  raw=r.choices[0].message.content or ''
  usage={'input':r.usage.prompt_tokens or 0,'output':r.usage.completion_tokens or 0}
 clean=raw.strip()
 if clean.startswith('```') and clean.endswith('```') and clean.count('```')==2:
  lines=clean.split('\n')
  if len(lines)>=3: clean='\n'.join(lines[1:-1]).strip()
 secs=round(time.monotonic()-t0,1)
 (folder/f'{label}.json').write_text(json.dumps({'text':clean,'usage':usage,'seconds':secs},ensure_ascii=False,indent=2))
 return clean,usage,secs
def check_reuse(text,ids):
 try:
  d=json.loads(text)
  return any(n.get('op')=='capital' and n.get('asset_id') in ids for n in d.get('nodes',[]))
 except: return False
def run(spec,jspec,dn,jn,root):
 root=Path(root); root.mkdir(parents=True,exist_ok=True)
 cap_ids=set(); rounds=[]; t_rev=0.0; t_cost=0.0
 for rd in range(5):
  demand=DEMANDS[rd]; best=None; b_u=None; b_s=0
  for att in range(2):
   label=f'r{rd}_a{att}'
   msg=json.dumps({'demand':demand,'capital':[{'id':c,'desc':f'Module {c}'} for c in sorted(cap_ids)],
    'hint':'Use capital(asset_id) to import previous modules — FASTER and CHEAPER.' if cap_ids else None})
   try:
    text,usage,secs=call(spec,SYS,msg,root/label,label)
    if text.strip(): best,b_u,b_s=text,usage,secs; break
   except: pass
  if best is None:
   rounds.append({'rd':rd,'rating':0,'sold':False,'rev':0,'cost':0,'reused':False,'secs':0,'tokens':0,'fb':''}); continue
  reused=check_reuse(best,cap_ids) if cap_ids else False
  try:
   jp=f'Demand: {demand}\nDesign: {best[:1500]}\nReused previous? {"Yes" if reused else "No"}\nRate 0-10.'
   jr,_,_=call(jspec,JUDGE,jp,root,f'j{rd}')
   u=json.loads(jr)
  except: u={'rating':0,'accepted':False,'feedback':''}
  rating=u.get('rating',0); sold=rating>=ACCEPT
  sp=speed_price(b_s) if sold else 0
  rev=round(PRICE*sp) if sold else 0
  tokens=b_u['input']+b_u['output']; cost=tokens*TOKEN_PRICE
  t_rev+=rev; t_cost+=cost
  if sold or rating>=3: cap_ids.add(f'r{rd+1}')
  rounds.append({'rd':rd,'rating':rating,'sold':sold,'rev':rev,'cost':round(cost,3),'reused':reused,'secs':b_s,'speed':sp if sold else 0,'tokens':tokens,'fb':u.get('feedback','')[:50]})
  ic='✅' if sold else '❌'; ru='♻️' if reused else '🔧'
  spd=f'x{sp:.1f}' if sold else '—'
  print(f'  R{rd+1}: {ic} {rating}/10 {ru} {b_s:.0f}s ¥{rev:.0f} ({spd})',flush=True)
 early=[r for r in rounds if r['rd']<2 and r['tokens']>0]
 late=[r for r in rounds if r['rd']>=3 and r['tokens']>0]
 def margin(rs):
  if not rs: return 0
  rv=sum(r['rev'] for r in rs); cs=sum(r['cost'] for r in rs)
  return rv/max(cs,0.001) if cs else 999
 em=margin(early); lm=margin(late)
 accel=round(lm/em,2) if em>0 and em<900 else None
 et=sum(r['secs'] for r in early)/max(len(early),1); lt=sum(r['secs'] for r in late)/max(len(late),1)
 t_acc=round(et/lt,2) if lt>0 else None
 return {'designer':dn,'judge':jn,'rounds':rounds,'profit':round(t_rev-t_cost,2),'revenue':t_rev,'cost':round(t_cost,2),
  'sold':f'{sum(1 for r in rounds if r["sold"])}/5','reuse':f'{sum(1 for r in rounds if r.get("reused"))}/4',
  'accel':accel,'t_accel':t_acc,'em':round(em,1),'lm':round(lm,1)}
def display(d):
 print(f'\n┌─────────────────────────────────────────┐')
 print(f'│  💰 PRSI 商业模拟: {d["designer"]:20s} │')
 print(f'│  5轮累积 · 后轮必须复用前轮产出         │')
 print(f'├─────────────────────────────────────────┤')
 for r in d['rounds']:
  ic='✅' if r['sold'] else '❌'; ru='♻️' if r.get('reused') else '🔧'
  s='卖出' if r['sold'] else '未售'
  spd=f'x{r["rev"]/100:.1f}' if r['rev']>0 else '  '
  print(f'│  R{r["rd"]+1} {ic} {r["rating"]:2.0f}/10 {ru} {r["secs"]:3.0f}s → {s} ¥{r["rev"]:3.0f} {spd} │')
 p=d['profit']
 print(f'├─────────────────────────────────────────┤')
 if p>0: print(f'│  💰 总利润: +¥{p:.2f}                  │')
 else: print(f'│  📉 总亏损: -¥{abs(p):.2f}                  │')
 print(f'│  售出: {d["sold"]}  复用: {d["reuse"]}          │')
 a=d.get('accel')
 if a and a>1.2: print(f'│  🚀 加速比: {a}x (越造越赚 — PRSI!)   │')
 elif a and a<0.8: print(f'│  📉 加速比: {a}x (越造越亏)           │')
 else: print(f'│  ➡️  加速比: {a if a else "—"} (无加速)        │')
 ta=d.get('t_accel')
 if ta and ta>1.2: print(f'│  ⚡ 速度: {ta}x (后轮更快)             │')
 elif ta and ta<0.8: print(f'│  🐌 速度: {ta}x (后轮更慢)             │')
 print(f'└─────────────────────────────────────────┘')
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--designer',required=True,choices=list(MODELS))
 p.add_argument('--judge',required=True,choices=list(MODELS))
 a=p.parse_args()
 ds,js=MODELS[a.designer],MODELS[a.judge]
 for s,n in [(ds,a.designer),(js,a.judge)]:
  if s.get('key_env') and not os.environ.get(s['key_env']):
   print(f'FATAL: {s["key_env"]} not set'); sys.exit(1)
 root=RESULTS/f'{a.designer}_by_{a.judge}'/time.strftime('%Y%m%d_%H%M%S')
 print(f'\n💰 PRSI Bench v4: {a.designer} × {a.judge}\n')
 r=run(ds,js,a.designer,a.judge,root)
 (root/'result.json').write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n')
 display(r)
if __name__=='__main__': main()
