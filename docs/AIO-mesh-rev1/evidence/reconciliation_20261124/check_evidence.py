"""Read-only numerical/provenance checks for the 24 November manuscript reconciliation."""
from pathlib import Path
import collections,csv,hashlib,json,re,statistics,subprocess
ROOT=Path(__file__).resolve().parents[4]
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
before=subprocess.check_output(['git','show','HEAD:docs/AIO-mesh-rev1/rev1.tex'],cwd=ROOT,text=True)
before=tables(expand(before,P));after=tables((P/'rev1.tex').read_text())
for label,block in before.items():
 if label in ('tab:harp_component_timing','tab:hil_e2e'):continue
 check('retained table numeric cells '+label,numbers(block)==numbers(after[label]))
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
for line in body.splitlines():
 if not re.match(r'(Vietnam|NSFNET|GEANT2) & [EBC] &',line):continue
 cells=[x.strip() for x in line.split('&')];topo=cells[0].lower();profile=profiles[cells[1]]
 for pol,cell in zip(policies,cells[2:]):
  vals=[float(r['safe_acceptance_rate']) for r in raw if r['topology']==topo and r['scenario']==profile and r['algorithm']==pol+'_protected']
  actual=re.findall(r'\d+\.\d+',cell)
  check('acceptance mean/SD '+topo+'/'+profile+'/'+pol,len(vals)==20 and actual==[f'{statistics.mean(vals):.2f}',f'{statistics.stdev(vals):.2f}'])
# Supplementary S1--S24 keep their original numeric cells, with explicit new terminal HIL outcomes in S23.
supp=(P/'supplement.tex').read_text();original=(B/'docs/AIO-mesh-rev1/supplement.tex').read_text()
for label,block in tables(expand(original,B/'docs/AIO-mesh-rev1')).items():
 if label=='tab:hil_e2e_detailed':continue
 check('retained supplementary numeric cells '+label,numbers(block)==numbers(tables(supp)[label]))
check('25 self-contained supplementary tables',len(tables(supp))==25 and not re.search(r'\\(?:input|TableRows)\{',supp))
main=(P/'rev1.tex').read_text()
check('main source has no external numeric or table inputs',not re.search(r'\\(?:input|TableRows)\{',main))
for name,text in [('main',main),('supplement',supp)]:
 check(name+' numeric SD has no baseline plus/minus',not re.search(r'\$\\pm\$\s*\d|\d\\pm\d',re.sub(r'\\textsuperscript\{\$\\pm\$[\d.]+\}','',text)))
 check(name+' labels unique',len(re.findall(r'\\label\{([^}]+)\}',text))==len(set(re.findall(r'\\label\{([^}]+)\}',text))))
old_response=subprocess.check_output(['git','show','HEAD:docs/response_rev1.tex'],cwd=ROOT,text=True)
response=(ROOT/'docs/response_rev1.tex').read_text()
check('all original reviewer comments preserved',re.findall(r'\\begin\{point\}(.*?)\\end\{point\}',old_response,re.S)==re.findall(r'\\begin\{point\}(.*?)\\end\{point\}',response,re.S))
# Supplementary lineage and hashes of the final source/figures are recorded, not treated as scientific validation by themselves.
files=[P/'rev1.tex',P/'supplement.tex',ROOT/'docs/response_rev1.tex',*sorted((P/'figs').glob('*.pdf'))]
result={'checks':checks,'passed':len(checks),'failed':0,'files_sha256':{str(p.relative_to(ROOT)):sha(p) for p in files},'scope':'Source hashes, exact HIL accounting, preservation of retained table cells, recomputed primary acceptance, references checked separately by TeX. Not a fresh execution of all scientific experiments.'}
(OUT/'checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(f'{len(checks)} evidence checks passed')
