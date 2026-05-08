import React from 'react';
import { MapPin, Activity, LayoutDashboard, Plus, BrainCircuit } from 'lucide-react';

// --- Theme Colors (Easily adjustable) ---
const THEME = {
  source: { text: 'text-rose-400', bg: 'bg-rose-500/5', hover: 'hover:bg-rose-500/10' },
  dest: { text: 'text-cyan-400', bg: 'bg-cyan-500/5', hover: 'hover:bg-cyan-500/10' },
  btn: "bg-gradient-to-r from-blue-600 to-cyan-500 hover:shadow-[0_0_40px_rgba(192,38,211,0.4)]"
};

const ControlHeader = ({
  srcDc, setSrcDc,
  dstDc, setDstDc,
  trafficOpt, setTrafficOpt,
  onOptimize, isBuffering,
  onOpenModal, activeVnfCount,
  dcs, trafficPolicies,
  hybridStatus
}) => {
  const isDrl = hybridStatus?.branch === 'drl';
  const modeLabel = isDrl ? 'AI JO-VPPM ENGAGED' : 'DECOUPLED HEURISTIC';
  const utilPct = Math.round((hybridStatus?.globalUtilization || 0) * 100);

  return (
    <header className="shrink-0 flex items-center gap-6 px-8 py-4 border-b border-white/10 bg-[#030b18] z-50">
      <div>
        <p className="text-[10px] font-black text-indigo-400 uppercase tracking-[0.2em] flex items-center gap-1.5">
          <LayoutDashboard size={12} /> ORCHESTRATION LAYER
        </p>
        <h1 className="text-xl font-black italic tracking-tight">SDN/SRv6 <span className="text-indigo-500">OPTIMIZER</span></h1>
      </div>

      <div className="flex items-center bg-[#0f172a] rounded-2xl border border-white/10 p-1.5 shadow-2xl ml-6">
        <div className={`flex items-center px-4 border-r border-white/10 group ${THEME.source.bg} ${THEME.source.hover} transition-colors`}>
          <MapPin size={14} className={THEME.source.text + " mr-2"} />
          <select
            value={srcDc}
            onChange={e => setSrcDc(e.target.value)}
            className={`bg-transparent text-xs font-black ${THEME.source.text} uppercase outline-none min-w-[140px] py-2 cursor-pointer`}
          >
            {Object.keys(dcs).map(k => (
              <option key={k} value={k} className="bg-[#0f172a]">{dcs[k].name}</option>
            ))}
          </select>
        </div>

        <div className={`flex items-center px-4 border-r border-white/10 group ${THEME.dest.bg} ${THEME.dest.hover} transition-colors`}>
          <MapPin size={14} className={THEME.dest.text + " mr-2"} />
          <select
            value={dstDc}
            onChange={e => setDstDc(e.target.value)}
            className={`bg-transparent text-xs font-black ${THEME.dest.text} uppercase outline-none min-w-[140px] py-2 cursor-pointer`}
          >
            {Object.keys(dcs).map(k => (
              <option key={k} value={k} className="bg-[#0f172a]">{dcs[k].name}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center px-4 gap-2">
          <Activity size={14} className="text-amber-400" />
          <select
            value={trafficOpt}
            onChange={e => setTrafficOpt(e.target.value)}
            className="bg-transparent text-xs font-black text-amber-200 uppercase outline-none min-w-[160px]"
          >
            {Object.entries(trafficPolicies).map(([k]) => (
              <option key={k} value={k} className="bg-[#0f172a]">{k.replace('_', ' ')}</option>
            ))}
          </select>
        </div>

        <button
          onClick={onOptimize}
          disabled={isBuffering}
          className={`px-6 py-2.5 rounded-xl text-xs font-black shadow-lg ml-2 transition-all active:scale-95 ${isBuffering ? 'bg-slate-700 text-slate-500 cursor-wait' : 'bg-indigo-600 hover:bg-indigo-500 text-white'}`}
        >
          {isBuffering ? 'CALCULATING...' : 'OPTIMIZE FLOW'}
        </button>
      </div>

      <div className="ml-auto flex items-center gap-6">
        <div
          className={`flex items-center gap-2 px-4 py-2 rounded-2xl border shadow-lg ${
            isDrl
              ? 'bg-red-500/10 border-red-500/40 text-red-300 animate-pulse'
              : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
          }`}
        >
          <BrainCircuit size={15} />
          <div className="leading-none">
            <div className="text-[10px] font-black tracking-widest">{modeLabel}</div>
            <div className="text-[9px] font-bold opacity-70 mt-1">U_GLOBAL {utilPct}%</div>
          </div>
        </div>
        <div className="flex flex-col items-end">
          <span className="text-[9px] font-bold text-slate-500 uppercase tracking-tighter">Cluster Size</span>
          <span className="text-lg font-black text-indigo-400">{activeVnfCount} VNFs</span>
        </div>
        <button
          onClick={onOpenModal}
          className={`relative group px-6 py-2.5 rounded-2xl overflow-hidden glass-btn transition-all active:scale-95`}
        >
          <div className={`absolute inset-0 ${THEME.btn} opacity-80 group-hover:opacity-100 transition-opacity`}></div>
          <div className="relative flex items-center gap-2 text-white text-xs font-black">
            <Plus size={16} strokeWidth={3} /> PROVISION VNF
          </div>
        </button>
      </div>
    </header>
  );
};

export default ControlHeader;
