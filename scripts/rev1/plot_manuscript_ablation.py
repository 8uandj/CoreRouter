"""Plot retained ablation aggregates and measured simulator timings."""
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/rev1-paper-mpl')
import csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/AIO-mesh-rev1/figs'

def main():
    OUT.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':9,'pdf.fonttype':42})
    rows=list(csv.DictReader(open(ROOT/'docs/AIO-mesh-rev1/evidence/e3/ablation_admission_summary.csv')))
    fig,axes=plt.subplots(1,2,figsize=(10,3.8))
    for topo,color in [('vietnam','#2672a3'),('nsfnet','#c45b25'),('geant2','#25845b')]:
        rr=[next(r for r in rows if r['topology']==topo and r['variant']==v) for v in ['harp_full','harp_wo_hard_masking']]
        x=np.arange(2)+{'vietnam':-.22,'nsfnet':0,'geant2':.22}[topo]
        for ax,metric in zip(axes,['mask_eliminated_candidate_rate','safe_acceptance_rate']):
            ax.bar(x,[float(r[metric+'_mean']) for r in rr],width=.21,color=color,label=topo.upper() if topo!='vietnam' else 'Vietnam',yerr=[float(r[metric+'_sample_sd']) for r in rr],capsize=2)
            ax.set_xticks([0,1],['Full','No mask + admission']); ax.set_ylim(0,100); ax.grid(axis='y',alpha=.2)
    axes[0].set_ylabel('Mask-pruned candidates (%)');axes[1].set_ylabel('Safe acceptance (%)')
    axes[0].legend(frameon=False,fontsize=8);fig.tight_layout();fig.savefig(OUT/'ablation_mask_admission.pdf',bbox_inches='tight');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,3.8))
    for variant,label,color,offset in [('harp_full','Full','#25845b',-.15),('harp_wo_gat','MLP','#2672a3',.15)]:
        vals=[];errs=[];acc=[];acerr=[]
        for workload in ['uniform','bursty']:
            rr=list(csv.DictReader(open(ROOT/f'results/rev1/e3_timed/vietnam/{workload}/harp_ablation_summary.csv')))
            rr=[r for r in rr if r['key']==variant];assert len(rr)==20
            a=np.array([float(r['policy_decision_ms_p95']) for r in rr]);b=np.array([float(r['safe_acceptance_rate']) for r in rr])
            vals.append(a.mean());errs.append(a.std(ddof=1));acc.append(b.mean());acerr.append(b.std(ddof=1))
        for ax,means,sd in [(axes[0],acc,acerr),(axes[1],vals,errs)]:
            ax.bar(np.arange(2)+offset,means,width=.28,yerr=sd,capsize=3,label=label,color=color)
            ax.set_xticks([0,1],['Uniform','Bursty']);ax.grid(axis='y',alpha=.2)
    axes[0].set_ylabel('Safe acceptance (%)');axes[0].set_ylim(0,65)
    axes[1].set_ylabel('Seed-level policy-decision p95 (ms)');axes[1].set_ylim(0,2.7)
    axes[0].legend(frameon=False);fig.tight_layout();fig.savefig(OUT/'ablation_compute_cost.pdf',bbox_inches='tight');plt.close(fig)
if __name__=='__main__':main()
