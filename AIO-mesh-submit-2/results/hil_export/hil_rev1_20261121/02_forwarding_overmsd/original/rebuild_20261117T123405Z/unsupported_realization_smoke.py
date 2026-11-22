import json,urllib.request,urllib.error,subprocess
from pathlib import Path
R=Path('results/hil/rebuild_20261117T123405Z'); src=json.load(open('configs/hil/recovered_hil_profiles.json'))['profiles'][0]
request={'flow_id':'hil-unsupported-realization-20261117T1347Z','cpu_req':src['cpu_req'],'ram_req':src['ram_req'],'msd_req':src['msd_req'],'service_type':'Data','alert_flag':True,'is_ddos_spike':False}
(R/'unsupported_smoke_request.json').write_text(json.dumps({'request':request,'resource_tuple_source':src['source'],'source_profile_name':src['vnf_name']},indent=2)+'\n')
def call(method,url,body=None):
 data=None if body is None else json.dumps(body).encode(); req=urllib.request.Request(url,data=data,headers={'Content-Type':'application/json'} if data is not None else {},method=method)
 try:
  with urllib.request.urlopen(req,timeout=30) as r: return r.status,json.loads(r.read())
 except urllib.error.HTTPError as e:
  try: body=json.loads(e.read().decode())
  except Exception: body={'raw':e.read().decode(errors='replace')}
  return e.code,body
def kubectl_json(*args): return json.loads(subprocess.check_output(['kubectl','--request-timeout=10s',*args],text=True))
pre_runs=kubectl_json('-n','core-router','get','pipelineruns.tekton.dev','-o','json'); pre_names={x['metadata']['name'] for x in pre_runs.get('items',[])}
pre_dep=kubectl_json('-n','core-router','get','deployments','-o','json'); pre_deps={x['metadata']['name'] for x in pre_dep.get('items',[])}
pre_state=call('GET','http://127.0.0.1:8000/api/orchestrate/state')[1]['data']; pre_active={x['name'] for x in pre_state['active_vnfs']}
code,resp=call('POST','http://127.0.0.1:8000/api/orchestrate',request); (R/'unsupported_smoke_response.json').write_text(json.dumps({'http_status':code,'body':resp},indent=2)+'\n')
# Restore the alert control plane even when the expected stop gate fires.
cc,clear=call('POST','http://127.0.0.1:8000/api/orchestrate/alert?alert=false'); (R/'unsupported_smoke_clear_alert.json').write_text(json.dumps({'http_status':cc,'body':clear},indent=2)+'\n')
after_state=call('GET','http://127.0.0.1:8000/api/orchestrate/state')[1]['data']; after_active={x['name'] for x in after_state['active_vnfs']}; after_runs=kubectl_json('-n','core-router','get','pipelineruns.tekton.dev','-o','json'); after_names={x['metadata']['name'] for x in after_runs.get('items',[])}; after_dep=kubectl_json('-n','core-router','get','deployments','-o','json'); after_deps={x['metadata']['name'] for x in after_dep.get('items',[])}
unsupported=code==409 and (resp.get('detail',{}).get('code')=='UNSUPPORTED_ADMITTED_REALIZATION' or (isinstance(resp.get('detail'),dict) and resp['detail'].get('code')=='UNSUPPORTED_ADMITTED_REALIZATION'))
summary={'status':'PASS' if unsupported and resp.get('detail',{}).get('reservation_released') is True and cc==200 and pre_names==after_names and pre_deps==after_deps and pre_active==after_active and len(after_active)==7 and not after_state.get('unaccounted_vnfs') and not after_state.get('alert_flag') else 'STOP_POSTCONDITION_FAILED','http_status':code,'response':resp,'alert_clear_http_status':cc,'pipeline_runs_unchanged':pre_names==after_names,'deployments_unchanged':pre_deps==after_deps,'ledger_names_unchanged':pre_active==after_active,'active_count':len(after_active),'unknown_count':len(after_state.get('unaccounted_vnfs',[])),'alert_flag_after':after_state.get('alert_flag')}
(R/'unsupported_smoke_summary.json').write_text(json.dumps(summary,indent=2)+'\n'); (R/'unsupported_smoke_state_after.json').write_text(json.dumps(after_state,indent=2)+'\n'); print(json.dumps(summary,indent=2))
