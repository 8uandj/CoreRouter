"""Read-only numerical/provenance checks for the 24 November manuscript reconciliation."""
from pathlib import Path
import collections,csv,hashlib,json,re,statistics,subprocess
ROOT=Path(__file__).resolve().parents[4]
BASELINE_COMMIT='2271d032d5706adaca1a6b7b9deef52a7fc249fc'
B=ROOT/'AIO-mesh-submit-2';P=ROOT/'docs/AIO-mesh-rev1';OUT=Path(__file__).parent
checks=[]
def check(name,condition):
 checks.append({'check':name,'passed':bool(condition)})
 if not condition:raise AssertionError(name)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return list(csv.DictReader(p.open()))
# Verify retained source provenance without regenerating or modifying the bundle.
m=json.loads((B/'docs/AIO-mesh-rev1/evidence/model_refresh_20261120/generator_manifest.json').read_text())
for name,digest in m['inputs_sha256'].items():check('benchmark/sweep input '+name,sha(B/name)==digest)
for name,digest in m['outputs_sha256'].items():check('benchmark/sweep output '+name,sha(B/'docs/AIO-mesh-rev1/evidence/model_refresh_20261120'/name)==digest)
h=json.loads((B/'docs/AIO-mesh-rev1/generated/hil_e2e.json').read_text())
for name,digest in h['sources_sha256'].items():check('HIL input '+name,sha(B/name)==digest)
# Exact request accounting and the actual name-set stopping condition.
c=B/'results/rev1/hil_e2e_20261121/run/campaign_corrected_model'
rows=read(c/'requests.csv');baseline=set(json.loads((c/'baseline_active.json').read_text()))
rejected=collections.Counter(r['message'] for r in rows if r['http']=='409')
check('all 398 campaign terminal outcomes classified',len(rows)==398 and sum(r['http']=='200' for r in rows)==69 and rejected=={
 'forwarding requires distinct ingress and placement nodes':43,
 'requested MSD depth does not match materialized P4 path depth':231,
 'materialized path exceeds physical switch MSD profile':6,
 'resilience_no_safe_pair_available':49})
admitted=[r for r in rows if r['http']=='200']
check('57 migrations and 12 non-replacement deployments',sum(bool(r['old_vnf']) for r in admitted)==57 and sum(not r['old_vnf'] for r in admitted)==12)
last=json.loads((c/'requests/0397.json').read_text())
check('39 initial, 51 final, 30 active names absent from baseline',len(baseline)==39 and last['active_total_after']==51 and last['new_vnfs_after']==30)
# The restored arrival figure remains tied to its pinned source records.
fm=json.loads((B/'docs/AIO-mesh-rev1/figs/final_figures_manifest.json').read_text())['figures']['arrival_rate_only.pdf']
check('restored arrival figure checksum',sha(P/'figs/arrival_rate_only.pdf')==fm['sha256'])
for name,digest in fm['inputs_sha256'].items():check('arrival figure input '+name,sha(B/name)==digest)
# The submitted manuscript is the authorial baseline, including administrative declarations.
submitted=(ROOT/'docs/AIO-mesh-submitted 1/submitted-1.tex').read_text()
current=(P/'rev1.tex').read_text()
check('seven original main sections in original order',re.findall(r'^\\section\{([^}]+)\}',submitted,re.M)==re.findall(r'^\\section\{([^}]+)\}',current,re.M))
for title in ('Funding','CRediT Authorship Contribution Statement','Declaration of Generative AI and AI-Assisted Technologies in the Writing Process','Declaration of Competing Interest'):
 pattern=r'\\section\*\{'+re.escape(title)+r'\}.*?(?=\\section\*\{|\\bibliographystyle)'
 check('submitted declaration unchanged: '+title,re.search(pattern,submitted,re.S)[0].strip()==re.search(pattern,current,re.S)[0].strip())
# Existing table values must survive inline expansion and typography edits unchanged.
def expand(text,base):
 return re.sub(r'\\(?:input|TableRows)\{([^}]+)\}',lambda m:expand((base/m[1]).read_text(),base),text)
def tables(text):
 return {re.search(r'\\label\{([^}]+)\}',b)[1]:b for b in re.findall(r'\\begin\{table\*?\}.*?\\end\{table\*?\}',text,re.S) if re.search(r'\\label\{([^}]+)\}',b)}
def numbers(block):
 return re.findall(r'(?<![A-Za-z])[-+]?\d+(?:\.\d+)?', '\n'.join(l for l in block.splitlines() if '&' in l and not l.lstrip().startswith('%')))
before=subprocess.check_output(['git','show',BASELINE_COMMIT+':docs/AIO-mesh-rev1/rev1.tex'],cwd=ROOT,text=True)
before=tables(expand(before,P));main_tables=tables((P/'rev1.tex').read_text());supp_tables=tables((P/'supplement.tex').read_text());after={**supp_tables,**main_tables}
for label,block in before.items():
 if label in ('tab:harp_component_timing','tab:simulation_acceptance_summary'):continue
 target=supp_tables['tab:hil_e2e_detailed'] if label=='tab:hil_e2e' else supp_tables['tab:hil_msd_detailed'] if label=='tab:hil_msd' else after[label]
 if label=='tab:evaluation_protocols':
  # S2 additionally contains the already-completed arrival-only protocol; preserve all original rows.
  keys={line.split('&')[0].strip() for line in block.splitlines() if '&' in line and not line.lstrip().startswith('%')}
  target='\n'.join('&'.join(line.split('&')[:3]) for line in target.splitlines() if '&' in line and line.split('&')[0].strip() in keys)
  block='\n'.join('&'.join(line.split('&')[:3]) for line in block.splitlines() if '&' in line)
 check('retained table numeric cells in main or supplement '+label,numbers(block)==numbers(target))
# Compact primary HIL tables must still reproduce the source-backed full records.
def cells(block):
 return [list(map(str.strip,line.split('&'))) for line in block.splitlines() if '&' in line and not line.lstrip().startswith('%')]
def numeric(cell):return re.findall(r'[-+]?\d+(?:\.\d+)?',cell.replace(',',''))
compact={row[0]:row[1] for row in cells(main_tables['tab:hil_e2e'])}
outcomes=json.loads((c/'analysis/outcomes.json').read_text());mbb=json.loads((B/'results/rev1/hil_e2e_20261121/run/analysis_mbb_corrected_model/mbb_summary.json').read_text())
expected={
 'Offered requests':[len(rows)],'Admitted / steering confirmed':[len(admitted),outcomes['steered']],
 'Rejected: depth mismatch':[rejected['requested MSD depth does not match materialized P4 path depth']],
 'Rejected: switch MSD overflow':[rejected['materialized path exceeds physical switch MSD profile']],
 'Rejected: ingress equals placement':[rejected['forwarding requires distinct ingress and placement nodes']],
 'Rejected: no feasible resilience pair':[rejected['resilience_no_safe_pair_available']],
 'All rejected':[sum(rejected.values())],'Initial / final active VNFs':[len(baseline),last['active_total_after']],
 'Deployments without replacement':[sum(not r['old_vnf'] for r in admitted)],
 'Migrations / MBB order verified':[mbb['migrations'],mbb['order_ok']],
 'Stopping target: active names absent from baseline':[last['new_vnfs_after']],
 'Rule readback complete':[outcomes['readback_all_present'],outcomes['steered']],
 'Requests delivering 20/20 packets':[outcomes['probes_with_full_delivery'],outcomes['steered']],
 'Probe packets received / sent':[outcomes['probe_packets_received'],outcomes['probe_packets_sent']]}
for label,expected_values in expected.items():check('compact E2E '+label,list(map(float,numeric(compact[label])))==expected_values)
full={row[0]:row[1] for row in cells(supp_tables['tab:hil_e2e_detailed'])}
for short,long in [('API response (s)','Admission API response (s)'),('Deployment to Pod Ready (s)','Deployment start to Pod Ready (s)'),('Rule installation/readback (s)','Rule installation and readback confirmation (s)'),('Submission to steering (s)','Submission to steering confirmation (s)')]:
 check('compact E2E timing '+short,numeric(compact[short])==numeric(full[long]))
msd_short=cells(main_tables['tab:hil_msd'])[1:];msd_full=cells(supp_tables['tab:hil_msd_detailed'])[1:]
check('all eight MSD trials retained',len(msd_short)==len(msd_full)==8)
for i,(short,long) in enumerate(zip(msd_short,msd_full)):
 check('compact MSD trial '+str(i+1),numeric(short[2])==numeric(long[2]) and numeric(short[3])==numeric(long[5]) and re.sub(r'\s+','',short[4])==re.sub(r'\s+','',long[6]))
stability={row[0]:row[1:] for row in cells(main_tables['tab:hil_stability_summary'])[1:]}
j12=json.loads((B/'docs/AIO-mesh-rev1/generated/table11.json').read_text())
check('compact 12-hour summary',[float(x) for cell in stability['12 h, API'] for x in numeric(cell)]==[j12['requests'],j12['http_status_counts']['200'],j12['readiness']['samples'],j12['readiness']['samples']])
for label,folder in [('3 h, saturated','long_3h_corrected_model'),('3 h, released','long_3h_corrected_model_released')]:
 record=json.loads((B/'results/rev1/hil_e2e_20261121/run'/folder/'analysis/longrun_summary.json').read_text())
 check('compact stability '+label,[float(x) for cell in stability[label] for x in numeric(cell)]==[record['admission']['requests'],record['admission']['accepted'],record['kubernetes']['samples_all_ready'],record['kubernetes']['samples'],record['dataplane']['received'],record['dataplane']['sent']])
# Recompute every timing cell rather than trusting the typeset replacement.
summary=json.loads((OUT/'timing_summary.json').read_text())
field_names=[('Normalization','normalize'),('Candidate construction','candidate'),('Inference / selection','selection'),('Admission validation','validation'),('Total decision','decision')]
timing_lines=[l for l in after['tab:harp_component_timing'].splitlines() if any(l.startswith(name+' &') for name,_ in field_names)]
check('timing table has all 15 component rows',len(timing_lines)==15)
for i,line in enumerate(timing_lines):
 n=(25,50,100)[i//5];key=field_names[i%5][1];digits=4 if key=='validation' else 3
 expected=[]
 for policy in ('harp','saf_h'):
  d=next(d for d in summary if d['nodes']==n and d['policy']==policy)
  if key+'_mean' in d:expected.extend([f'{d[key+"_mean"]:.{digits}f}',f'{d[key+"_sd"]:.{digits}f}'])
 check('timing printed mean/SD '+str(n)+'/'+key,re.findall(r'\d+\.\d+',line)==expected)
# Recompute the headline acceptance table directly from retained seed-level rows.
raw=read(B/'docs/AIO-mesh-rev1/evidence/model_refresh_20261120/stress_per_seed_all_topologies.csv')
body=after['tab:simulation_acceptance_summary']
profiles={'E':'elephant_stress','B':'burst_surge','C':'chaos'}
policies=['traditional_greedy','decoupled_ai','saf_h','cspf','harp']
topo=None;checked_acceptance=0
policy_names={'Greedy':'traditional_greedy','DAI':'decoupled_ai','SAF-H':'saf_h','CSPF':'cspf','HARP':'harp'}
for line in body.splitlines():
 match=re.search(r'\\textit\{(Vietnam|NSFNET|GEANT2)\}',line)
 if match:topo=match[1].lower()
 if not re.match(r'(Greedy|DAI|SAF-H|CSPF|HARP) &',line):continue
 cells=[x.strip() for x in line.split('&')];pol=policy_names[cells[0]]
 for profile,cell in zip(('E','B','C'),cells[1:]):
  vals=[float(r['safe_acceptance_rate']) for r in raw if r['topology']==topo and r['scenario']==profiles[profile] and r['algorithm']==pol+'_protected']
  actual=re.findall(r'\d+\.\d+',cell)
  check('acceptance mean/SD '+topo+'/'+profiles[profile]+'/'+pol,len(vals)==20 and actual==[f'{statistics.mean(vals):.2f}',f'{statistics.stdev(vals):.2f}']);checked_acceptance+=1
check('all 45 acceptance mean/SD cells retained',checked_acceptance==45)
# Supplementary S1--S24 keep their original numeric cells, with explicit new terminal HIL outcomes in S23.
supp=(P/'supplement.tex').read_text();original=(B/'docs/AIO-mesh-rev1/supplement.tex').read_text()
for label,block in tables(expand(original,B/'docs/AIO-mesh-rev1')).items():
 if label=='tab:hil_e2e_detailed':continue
 check('retained supplementary numeric cells '+label,numbers(block)==numbers(tables(supp)[label]))
check('27 self-contained supplementary tables',len(tables(supp))==27 and not re.search(r'\\(?:input|TableRows)\{',supp))
main=(P/'rev1.tex').read_text()
check('main source has no external numeric or table inputs',not re.search(r'\\(?:input|TableRows)\{',main))
check('ten one-column main tables',len(main_tables)==10 and not re.search(r'\\begin\{table\*\}',main))
intro=main[main.index(r'\section{Introduction}'):main.index(r'\section{Background')];check('submitted five contribution items retained',intro.count(r'\item')==5)
for name,text in [('main',main),('supplement',supp)]:
 check(name+' numeric SD has no baseline plus/minus',not re.search(r'\$\\pm\$\s*\d|\d\\pm\d',re.sub(r'\\textsuperscript\{\$\\pm\$[\d.]+\}','',text)))
 check(name+' labels unique',len(re.findall(r'\\label\{([^}]+)\}',text))==len(set(re.findall(r'\\label\{([^}]+)\}',text))))
old_response=subprocess.check_output(['git','show',BASELINE_COMMIT+':docs/response_rev1.tex'],cwd=ROOT,text=True)
response=(ROOT/'docs/response_rev1.tex').read_text()
check('all original reviewer comments preserved',re.findall(r'\\begin\{point\}(.*?)\\end\{point\}',old_response,re.S)==re.findall(r'\\begin\{point\}(.*?)\\end\{point\}',response,re.S))
# Supplementary lineage and hashes of the final source/figures are recorded, not treated as scientific validation by themselves.
files=[P/'rev1.tex',P/'supplement.tex',ROOT/'docs/response_rev1.tex',*sorted((P/'figs').glob('*.pdf'))]
result={'comparison_commit':BASELINE_COMMIT,'checks':checks,'passed':len(checks),'failed':0,'files_sha256':{str(p.relative_to(ROOT)):sha(p) for p in files},'scope':'Source hashes, exact HIL accounting, preservation of retained table cells, recomputed primary acceptance, references checked separately by TeX. Not a fresh execution of all scientific experiments.'}
(OUT/'checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(f'{len(checks)} evidence checks passed')
