import json,urllib.request,urllib.error,subprocess,hashlib
from pathlib import Path
R=Path('results/hil/rebuild_20261117T123405Z'); src=json.load(open('configs/hil/recovered_hil_profiles.json'))['profiles'][0]
request={'flow_id':'hil-admission-only-20261117T1345Z','cpu_req':src['cpu_req'],'ram_req':src['ram_req'],'msd_req':src['msd_req'],'service_type':'Data','alert_flag':False,'is_ddos_spike':False}
(R/'admission_smoke_request.json').write_text(json.dumps({'request':request,'resource_tuple_source':src['source'],'source_profile_name':src['vnf_name']},indent=2)+'\n')
def call(method,url,body=None):
 data=None if body is None else json.dumps(body).encode(); req=urllib.request.Request(url,data=data,headers={'Content-Type':'application/json'} if data is not None else {},method=method)
 try:
  with urllib.request.urlopen(req,timeout=30) as r: return r.status,json.loads(r.read())
 except urllib.error.HTTPError as e: return e.code,json.loads(e.read().decode())
code,resp=call('POST','http://127.0.0.1:8000/api/orchestrate',request); (R/'admission_smoke_response.json').write_text(json.dumps({'http_status':code,'body':resp},indent=2)+'\n'); print('ADMISSION',code,json.dumps(resp)[:1000])
summary={'http_status':code,'status':'STOP_ADMISSION_REJECTED','cleanup':None}
if code==200 and resp.get('status')=='success':
 data=resp.get('data',resp); name=data['vnf_name']; placement=data['placement_node']; route=data['routing_node']; migration=data.get('migration_result');
 state_code,state=call('GET','http://127.0.0.1:8000/api/orchestrate/state'); active=state.get('data',{}).get('active_vnfs',[]); entry=next((x for x in active if x['name']==name),None)
 dep=subprocess.run(['kubectl','-n','core-router','get','deployment',name,'-o','json'],capture_output=True,text=True); no_dep=dep.returncode!=0
 free={'vnf_name':name,'v_place':placement['id'],'v_route':route['id'],'cpu_req':request['cpu_req'],'ram_req':request['ram_req'],'msd_req':request['msd_req']}
 fc,fr=call('POST','http://127.0.0.1:8000/api/orchestrate/free',free)
 sc,after=call('GET','http://127.0.0.1:8000/api/orchestrate/state'); active_after=after.get('data',{}).get('active_vnfs',[]);
 summary={'http_status':code,'status':'PASS' if entry and not entry.get('accounting_unknown') and migration is None and no_dep and fc==200 and sc==200 and len(active_after)==7 and not after.get('data',{}).get('unaccounted_vnfs') else 'STOP_POSTCONDITION_FAILED','vnf_name':name,'branch':data.get('hybrid_branch'),'migration_result':migration,'placement':placement,'route':route,'admitted_entry':entry,'deployment_absent':no_dep,'release_http_status':fc,'release_response':fr,'active_count_after_cleanup':len(active_after),'unknown_after_cleanup':len(after.get('data',{}).get('unaccounted_vnfs',[]))}
(R/'admission_smoke_cleanup_response.json').write_text(json.dumps({'http_status':fc,'body':fr},indent=2)+'\n'); (R/'admission_smoke_state_after_cleanup.json').write_text(json.dumps(after,indent=2)+'\n')
(R/'admission_smoke_summary.json').write_text(json.dumps(summary,indent=2)+'\n'); print(json.dumps(summary,indent=2))
