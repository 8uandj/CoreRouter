import { MapPin, Activity, LayoutDashboard, Plus, BrainCircuit, RefreshCw, ChevronUp, Send } from 'lucide-react';

const THEME = {
  source: { text: 'text-rose-400', bg: 'bg-rose-500/5', hover: 'hover:bg-rose-500/10' },
  dest: { text: 'text-cyan-400', bg: 'bg-cyan-500/5', hover: 'hover:bg-cyan-500/10' },
  btn: "bg-gradient-to-r from-indigo-600 to-cyan-500 hover:shadow-[0_0_40px_rgba(99,102,241,0.4)]"
};

const ControlHeader = ({
  srcDc, setSrcDc,
  dstDc, setDstDc,
  trafficOpt, setTrafficOpt,
  packetCount, setPacketCount,
  onOptimize, isBuffering,
  onOpenModal, activeVnfCount,
  dcs, trafficPolicies,
  hybridStatus,
  onSimulateMbb,
  isHeaderOpen, setIsHeaderOpen
}) => {
  const isDrl = hybridStatus?.branch === 'drl';
  const modeLabel = isDrl ? 'AI JO-VPPM ENGAGED' : 'HYBRID HEURISTIC';
  const utilPct = Math.round((hybridStatus?.globalUtilization || 0) * 100);

  return (
    <header className="shrink-0 flex flex-col lg:flex-row lg:items-center justify-between gap-4 px-6 py-4 border-b border-white/10 bg-[#030b18] z-50 select-none">
      <div className="flex items-center justify-between lg:justify-start gap-4">
        <div>
          <p className="text-[10px] font-black text-indigo-400 uppercase tracking-[0.2em] flex items-center gap-1.5">
            <LayoutDashboard size={12} /> VIETNAM 10-NODE BACKBONE
          </p>
          <h1 className="text-xl font-black italic tracking-tight text-white uppercase">3S-COM <span className="text-indigo-500">SRv6 Portal</span></h1>
        </div>
      </div>

      <div className="flex flex-wrap items-center bg-[#0f172a] rounded-2xl border border-white/10 p-1.5 shadow-2xl gap-y-2 gap-x-1 max-w-full">
        <div className={`flex items-center px-4 border-r border-white/10 group ${THEME.source.bg} ${THEME.source.hover} transition-colors`}>
          <MapPin size={14} className={THEME.source.text + " mr-2"} />
          <select
            value={srcDc}
            onChange={e => setSrcDc(e.target.value)}
            className={`bg-transparent text-xs font-black ${THEME.source.text} uppercase outline-none min-w-[110px] py-2 cursor-pointer`}
          >
            {Object.keys(dcs).map(k => (
              <option key={k} value={k} className="bg-[#0f172a]">{dcs[k].label || dcs[k].name}</option>
            ))}
          </select>
        </div>

        <div className={`flex items-center px-4 border-r border-white/10 group ${THEME.dest.bg} ${THEME.dest.hover} transition-colors`}>
          <MapPin size={14} className={THEME.dest.text + " mr-2"} />
          <select
            value={dstDc}
            onChange={e => setDstDc(e.target.value)}
            className={`bg-transparent text-xs font-black ${THEME.dest.text} uppercase outline-none min-w-[110px] py-2 cursor-pointer`}
          >
            {Object.keys(dcs).map(k => (
              <option key={k} value={k} className="bg-[#0f172a]">{dcs[k].label || dcs[k].name}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center px-4 gap-2 border-r border-white/10">
          <Activity size={14} className="text-amber-400" />
          <select
            value={trafficOpt}
            onChange={e => setTrafficOpt(e.target.value)}
            className="bg-transparent text-xs font-black text-amber-200 uppercase outline-none min-w-[140px] cursor-pointer"
          >
            {Object.entries(trafficPolicies).map(([k, policy]) => (
              <option key={k} value={k} className="bg-[#0f172a]">{policy.label || k.replace('_', ' ')}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center px-4 gap-2 border-r border-white/10 hover:bg-white/5 transition-colors py-2 cursor-default">
          <Send size={12} className="text-indigo-400 rotate-[-45deg]" />
          <span className="text-[10px] font-black text-slate-400 uppercase tracking-[0.15em]">Packets</span>
          <input
            type="number"
            min="1"
            max="100"
            value={packetCount}
            onChange={e => setPacketCount(Math.max(1, parseInt(e.target.value) || 1))}
            onClick={e => e.stopPropagation()}
            className="w-12 bg-slate-900 border border-white/10 text-slate-100 rounded-lg py-1 text-center text-xs font-black outline-none focus:border-indigo-500/50 transition-colors [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
          />
        </div>

        <button
          onClick={onOptimize}
          disabled={isBuffering}
          className={`px-4 py-2.5 rounded-xl text-xs font-black shadow-lg ml-1 transition-all active:scale-95 ${isBuffering ? 'bg-slate-700 text-slate-500 cursor-wait' : 'bg-indigo-600 hover:bg-indigo-500 text-white'}`}
        >
          {isBuffering ? 'CALCULATING...' : 'OPTIMIZE SRv6'}
        </button>

        <button
          onClick={onSimulateMbb}
          type="button"
          className="px-3 py-2.5 rounded-xl text-xs font-black border border-indigo-500/30 bg-indigo-500/10 hover:bg-indigo-500/20 hover:border-indigo-500/50 text-indigo-300 ml-1 transition-all active:scale-95"
          title="Simulate Make-Before-Break migration flow"
        >
          SIMULATE MBB
        </button>
      </div>

      <div className="flex items-center gap-4 lg:ml-auto justify-between lg:justify-end w-full lg:w-auto">
        <div
          className={`flex items-center gap-2 px-3 py-1.5 rounded-2xl border shadow-lg ${
            isDrl
              ? 'bg-red-500/10 border-red-500/40 text-red-300 animate-pulse'
              : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
          }`}
        >
          <BrainCircuit size={15} />
          <div className="leading-none">
            <div className="text-[9px] font-black tracking-widest">{modeLabel}</div>
            <div className="text-[8px] font-bold opacity-70 mt-1">U_GLOBAL {utilPct}%</div>
          </div>
        </div>
        <div className="flex flex-col items-end">
          <span className="text-[8px] font-bold text-slate-500 uppercase tracking-tighter">VNF Pool</span>
          <span className="text-sm font-black text-indigo-400">{activeVnfCount} VNFs</span>
        </div>
        <button
          onClick={onOpenModal}
          className={`relative group px-5 py-2 rounded-2xl overflow-hidden glass-btn transition-all active:scale-95`}
        >
          <div className={`absolute inset-0 bg-gradient-to-r ${THEME.btn} opacity-80 group-hover:opacity-100 transition-opacity`}></div>
          <div className="relative flex items-center gap-2 text-white text-[11px] font-black">
            <Plus size={14} strokeWidth={3} /> PROVISION VNF
          </div>
        </button>

        <button
          onClick={() => setIsHeaderOpen(false)}
          className="p-2 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 flex items-center justify-center cursor-pointer transition-colors text-slate-400 hover:text-white"
          title="Collapse Header"
        >
          <ChevronUp size={16} />
        </button>
      </div>
    </header>
  );
};

export default ControlHeader;
