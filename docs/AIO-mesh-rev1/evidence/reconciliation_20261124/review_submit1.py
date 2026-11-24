"""Index every submitted prose paragraph against the revision and emit the direct source diff."""
from pathlib import Path
import difflib,hashlib,json,re
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
OLD=ROOT/'docs/AIO-mesh-submitted 1/submitted-1.tex';NEW=ROOT/'docs/AIO-mesh-rev1/rev1.tex'

def balanced(s,start):
 depth=1;i=start
 while depth:
  if s[i]=='\\':i+=2;continue
  if s[i]=='{':depth+=1
  elif s[i]=='}':depth-=1
  i+=1
 return i-1

def unwrap(s):
 pattern=re.compile(r'\\(?:newrev|rev)\{')
 while True:
  m=pattern.search(s)
  if not m:return s
  end=balanced(s,m.end());s=s[:m.start()]+s[m.end():end]+s[end+1:]

def key(s):return re.sub(r'\s+','',unwrap(s))
def comments(s):return re.sub(r'(?<!\\)%[^\n]*',lambda m:' '*len(m[0]),s)

def chunks(s):
 t=comments(s);heads=[]
 for m in re.finditer(r'\\(?:subsection|section)\*?\{',t):
  e=balanced(t,m.end());heads.append((m.start(),e+1,unwrap(t[m.end():e])))
 result={}
 # Abstract is part of the original paper, independent of frontmatter metadata.
 m=re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}',t,re.S)
 result['Abstract']=(m.start(1),m[1])
 for i,(start,end,title) in enumerate(heads):result[title]=(end,t[end:heads[i+1][0] if i+1<len(heads) else len(t)])
 return result

def prose(text,offset,whole):
 # Keep offsets/line numbers while omitting environments audited as mathematical or data artifacts.
 text=re.sub(r'\\begin\{(table\*?|figure\*?|algorithm|equation\*?|align\*?)\}.*?\\end\{\1\}',lambda m:'\n'*m[0].count('\n')+' '*(len(m[0])-m[0].count('\n')),text,flags=re.S)
 out=[]
 for m in re.finditer(r'\S(?:[^\n]|\n(?!\s*\n))*',text):
  p=m[0].strip()
  if len(p.split())<12 or p.startswith((r'\bibliography',r'\bibliographystyle',r'\clearpage',r'\begin{itemize}',r'\end{itemize}')):continue
  out.append({'line':whole.count('\n',0,offset+m.start())+1,'text':p,'norm':key(p),'words':unwrap(p).split()})
 return out

reasons={
'Abstract':'R2.1–R2.3/P0.2/P1.2: runtime attribution and audited measurements replace unsupported result claims; original introduction retained.',
'Introduction':'R2.1/R3/R4.1/R5.1/R5.3: runtime contribution, abbreviation definitions, practical MSD failure semantics; no unsupported universal policy advantage.',
'Background and Related Work':'R2.1/R3: original framing retained.',
'AIOps and MLOps for Cloud-Native Infrastructure':'Original background and citations retained.',
'Learning-Based Resource and Service-Chain Orchestration':'R4.1: abbreviation definitions; absent original bibliography keys are not invented.',
'Programmable Data Planes and Hardware-Constrained Actuation':'R4.1/R5.1: SRH definition and MSD failure context.',
'Safe and Graph-Aware Reinforcement Learning for Infrastructure Control':'R2.1/R3/R5.3: credit established techniques and distinguish runtime from policy safety.',
'Research Gap Summary':'R2.1/R3/R5.3: qualify overbroad novelty claims; preserve submitted design principles.',
'System Model and Design Requirements':'Original section introduction retained.',
'Cloud-Native Programmable Substrate':'R4.1: expand NFVI/RAM; retain substrate/state model.',
'Service-Chain Request and Orchestration Decision':'P0.5/P1.1: requested depth and actual pair interface; retain full-chain model as system target and migration qualification.',
'Hardware-Safety and Admission Constraints':'P0.5/P1.1/R5.2: distinguish depth per profile, instance accounting, and checked versus desired full-chain feasibility.',
'Operational Objective':'Restore submitted generic objective; clarify it is not the implemented PPO reward. P0.3/R2.5: local pair selection and action-switching proxy.',
'Design Requirements':'R2.2/R5.4: guard scope of safety and searched feasible set; original topology-awareness requirement retained.',
'AIO-Mesh Architecture':'R2.2/R2.5: policy proposes a pair; runtime handles lifecycle and admission.',
'Closed-Loop Runtime Organization':'R2.5/R5.4: exact Hybrid hysteresis and route-profile check; original operational loop retained.',
'Policy Runtime and State Management':'R2.2: fallback is a proposal subject to independent admission; other submitted paragraphs retained.',
'Safety Boundary and Admission Semantics':'R2.2/R5.4: independent local validation/reservation and snapshot-version interval. Original unverified automatic recovery/counter-response guarantees are not reinstated.',
'Cloud-Native Lifecycle Actuation':'P1.1/P1.2: original deployment/MBB/steering explanation retained, campaign measurement scopes added.',
'Programmable Data-Plane Interface':'P0.5/P1.1: source-backed compiler, anchor, wire order, exact-depth/MSD checks and no path cache replace unsupported realization guarantees.',
'End-to-End Request Lifecycle':'P0.4/P1.1: original full lifecycle/Algorithm 1 restored; local reservation, admission-only branch and context-driven migration clarified.',
'HARP: Hardware-Aware Reinforcement Policy':'P0.3/P0.4/R2.2: distinguish proposal masking from admission and action switching from migration.',
'MDP Formulation':'P1.1/R2.5: correct N² pair head replaces nonexistent policy migration mode/cached K-path interface. Original displayed MDP and state restored.',
'Graph-Attention State Encoder':'R2.3/R5.4: original attention equations retained; correct actual fusion/normalization and qualify MLP-insufficiency claim.',
'Hard-Feasibility Action Mask':'P0.4/P0.5/P1.1: local BW/MSD predicates, no cache, empty mask, variant distributions and independent admission.',
'Reward for Soft Operational Objectives':'P0.3/R2.5: replace generic reward presented as implementation with actual reward and callback; preserve separate generic system objective.',
'Admission and Migration Semantics':'P0.4/P1.1: actual training/evaluation/live empty-mask behavior and lifecycle-driven migration replace unsupported policy modes.',
'Decision Procedure':'P0.4/P1.1: guarded inference/fallback replaces nonexistent cached-path selection; restore original procedural explanation and add N² cost.',
'Experiments and Evaluation':'R2.2–R2.5/R4.2/R5.5: retain original five evaluation questions with scope corrections.',
'Experimental Setup':'R2.3/P1.1/P2.1: actual workloads, 20 seeds, models, complete configured adjacency and no K-path cache replace inaccurate submitted protocol.',
'Baselines, Ablation Variants, and Metrics':'R2.2–R2.4/P2.1: actual heuristics, tested ablations, statistics and denominators replace inaccurate baseline/variant descriptions.',
'Hardware-Safe Admission under Workload Saturation':'R2.2/R2.4: retain original saturation question/figure reference; expand with common protected-admission evidence. Detailed sweeps in checklist Section 6.8.',
'Simulation Results across Distributed Topologies':'R2.3/P2.1: replace unsupported old means/claims with audited tables and paired comparisons. Old burst-results table has no independent verified full metric set and is not relabeled as new evidence.',
'Ablation Study':'R2.2–R2.4/P2.1: actual variants/admission bypass results and timing; old Pareto-optimality figure/claims are not supported by corrected records.',
'Hardware-in-the-Loop Testbed Validation':'P0.2/P0.5/P1.1/P1.2: request-correlated E2E, MSD injections and separate long-run protocols replace unsupported old scenario table.',
'Operational Interpretation, Overhead, and Limitations':'R2.3/R4.2/R5.5: qualify workload-dependent policy tradeoffs, timing regimes and measured testbed scope.',
'Conclusion':'R5.6: two paragraphs; retain original opening motivation, update results and qualify only measured scope.',
'Declaration of Competing Interest':'Restored unchanged from submitted manuscript.',
'Funding':'Restored original submitted grant; no reviewer request authorizes changing grant attribution.',
'Data and Code Availability':'P2.1/R2.3: retain repository, clarify retained artifact/reproduction scope rather than asserting unsupported full public availability.',
'Declaration of Generative AI and AI-Assisted Technologies in the Writing Process':'Retained unchanged from submitted manuscript.',
'CRediT Authorship Contribution Statement':'Restored original author roles; no reviewer request authorizes changing authorship credit.'}
old=OLD.read_text();new=NEW.read_text();oc=chunks(old);nc=chunks(new);records=[]
for title,(offset,body) in oc.items():
 assert title in nc,('Missing original heading',title)
 assert title in reasons,('Missing review reason',title)
 no,nb=nc[title];op=prose(body,offset,old);np=prose(nb,no,new)
 for p in op:
  exact=next((q for q in np if q['norm']==p['norm']),None)
  if exact:q=exact;status='retained';ratio=1.
  elif np:
   ratio,q=max((difflib.SequenceMatcher(None,p['words'],q['words']).ratio(),i) for i,q in enumerate(np));q=np[q];status='edited' if ratio>=.48 else 'replaced or omitted'
  else:q=None;ratio=0;status='replaced or omitted'
  records.append({'section':title,'submitted_line':p['line'],'revision_line':q['line'] if q else None,'status':status,'reason':reasons[title], 'submitted_text':p['text'],'nearest_revision_text':q['text'] if q else None})
summary={k:sum(r['status']==k for r in records) for k in ('retained','edited','replaced or omitted')}
(OUT/'submit1_paragraph_review.json').write_text(json.dumps({'baseline_sha256':hashlib.sha256(OLD.read_bytes()).hexdigest(),'revision_sha256':hashlib.sha256(NEW.read_bytes()).hexdigest(),'scope':'All submitted prose paragraphs (12+ words), excluding equation/table/figure/algorithm bodies; direct complete source diff supplied separately. Status is lexical, not a percentage claim about scientific equivalence.','summary':summary,'records':records},indent=2)+'\n')
lines=['# Đối chiếu toàn bộ văn bản với submit1','','Mốc: `docs/AIO-mesh-submitted 1/submitted-1.tex`. Bao phủ tất cả các phần gốc, kể cả Funding/CRediT; bảng, hình, công thức và thuật toán nằm trong diff source đầy đủ. Các số giữ lại được kiểm tra bằng `check_evidence.py`. Trạng thái so khớp là mô tả câu chữ, không phải chứng nhận nội dung khoa học.','','| Phần gốc | Dòng gốc | Trạng thái câu chữ | Lý do |','|---|---:|---|---|']
for title in oc:
 rr=[r for r in records if r['section']==title];counts={k:sum(r['status']==k for r in rr) for k in summary};line=old.count('\n',0,oc[title][0])+1
 lines.append(f"| {title} | {line} | {counts['retained']} giữ nguyên; {counts['edited']} sửa; {counts['replaced or omitted']} thay/bỏ | {reasons[title]} |")
lines+=['','Chi tiết từng đoạn và vị trí tương ứng: `submit1_paragraph_review.json`. Diff trực tiếp toàn bộ source, không dùng bản rev1 trung gian làm baseline: `SUBMIT1_TO_REV1.diff`.','',f'Tổng số đoạn văn được lập mục: {len(records)}. Số khớp nguyên câu chữ sau khi bỏ markup revision/whitespace: {summary["retained"]}. Các phần sửa/thay đều có mục lý do ở trên; cần đọc đoạn gốc và đoạn revision trong JSON khi đánh giá ý nghĩa.']
(OUT/'BASELINE_REVIEW.md').write_text('\n'.join(lines)+'\n')
(OUT/'SUBMIT1_TO_REV1.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile=str(OLD.relative_to(ROOT)),tofile=str(NEW.relative_to(ROOT)))))
print('Original sections/subsections/declarations:',len(oc),'prose paragraphs indexed:',len(records),summary)
