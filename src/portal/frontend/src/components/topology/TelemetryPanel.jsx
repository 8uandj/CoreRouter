import React from 'react';
import { motion as Motion, AnimatePresence } from 'framer-motion';
import { Activity, ChevronUp, ChevronDown, Cpu, Layers, HardDrive, ShieldAlert, Server } from 'lucide-react';

const TelemetryPanel = ({ isOpen, setIsOpen, hybridStatus }) => {
  const isDrl = hybridStatus?.branch === 'drl';
  
  // Dynamic aggregations
  const nodes = hybridStatus?.nodes || [];
  const numNodes = nodes.length || 10;
  
  const alertingNodesCount = nodes.filter(n => n.alert).length || 0;
  
  const avgCpu = nodes.length 
    ? Math.round(nodes.reduce((sum, n) => sum + (n.cpu_util || 0), 0) / numNodes) 
    : Math.round((hybridStatus?.avgCpu || 0) * 100);
    
  const avgRam = nodes.length 
    ? Math.round(nodes.reduce((sum, n) => sum + (n.ram_util || 0), 0) / numNodes) 
    : 8;
    
  const avgMsd = nodes.length 
    ? Math.round(nodes.reduce((sum, n) => sum + (n.msd_util || 0), 0) / numNodes) 
    : Math.round((hybridStatus?.avgMsdUsage || 0) * 100);

  const activeVnfsCount = hybridStatus?.active_vnfs?.length || 0;

  // SLA Health Score logic
  const healthScore = Math.max(10, Math.round(100 - (alertingNodesCount * 15) - (avgCpu * 0.15)));
  
  let healthLabel = 'Optimal';
  let healthColor = 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10';
  if (healthScore < 70) {
    healthLabel = 'Critical';
    healthColor = 'text-rose-400 border-rose-500/30 bg-rose-500/10';
  } else if (healthScore < 90) {
    healthLabel = 'Degraded';
    healthColor = 'text-amber-400 border-amber-500/30 bg-amber-500/10';
  }

  // Helper to determine bar color based on utilization
  const getBarColor = (val) => {
    if (val > 80) return 'bg-gradient-to-r from-rose-500 to-red-600';
    if (val > 50) return 'bg-gradient-to-r from-amber-400 to-orange-500';
    return 'bg-gradient-to-r from-emerald-400 to-indigo-500';
  };

  return (
    <Motion.div 
      initial={false} 
      animate={{ 
        height: isOpen ? 'auto' : 48, 
        width: isOpen ? 340 : 200 
      }} 
      className="absolute bottom-8 left-8 z-10 bg-[#030b18]/90 backdrop-blur-xl rounded-[2rem] border border-white/10 shadow-[0_20px_50px_rgba(0,0,0,0.7)] overflow-hidden"
    >
      {/* Header */}
      <div 
        className="p-4 flex items-center justify-between cursor-pointer hover:bg-white/5 transition-colors select-none" 
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${alertingNodesCount > 0 ? 'bg-rose-500' : 'bg-emerald-500'}`}></span>
            <span className={`relative inline-flex rounded-full h-2 w-2 ${alertingNodesCount > 0 ? 'bg-rose-500' : 'bg-emerald-500'}`}></span>
          </span>
          <Activity size={14} className="text-indigo-400"/>
          <h4 className="text-[10px] font-black text-slate-300 tracking-widest uppercase">Vietnam Backbone HUD</h4>
        </div>
        {isOpen ? <ChevronDown size={14} className="text-slate-500"/> : <ChevronUp size={14} className="text-slate-500"/>}
      </div>
      
      {/* Expanded Content */}
      <AnimatePresence>
        {isOpen && (
          <Motion.div 
            initial={{ opacity: 0 }} 
            animate={{ opacity: 1 }} 
            exit={{ opacity: 0 }} 
            className="px-6 pb-6 pt-1 space-y-4"
          >
            {/* Health SLA Badge */}
            <div className="flex items-center justify-between p-3 rounded-2xl border border-white/5 bg-slate-950/40">
              <div>
                <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Network SLA</span>
                <div className="text-lg font-mono font-black text-white">{healthScore}%</div>
              </div>
              <span className={`text-[10px] font-black px-2.5 py-1 rounded-xl border uppercase tracking-wider ${healthColor}`}>
                {healthLabel}
              </span>
            </div>

            {/* General stats */}
            <div className="grid grid-cols-2 gap-2">
              <div className="p-3 rounded-xl border border-white/5 bg-slate-900/30 flex items-center gap-2">
                <Server size={14} className="text-indigo-400" />
                <div>
                  <span className="text-[9px] font-black text-slate-500 uppercase block">Active VNFs</span>
                  <span className="text-xs font-mono font-bold text-white">{activeVnfsCount} instances</span>
                </div>
              </div>
              
              <div className="p-3 rounded-xl border border-white/5 bg-slate-900/30 flex items-center gap-2">
                <ShieldAlert size={14} className={alertingNodesCount > 0 ? 'text-rose-400' : 'text-slate-500'} />
                <div>
                  <span className="text-[9px] font-black text-slate-500 uppercase block">Alerting Nodes</span>
                  <span className={`text-xs font-mono font-bold ${alertingNodesCount > 0 ? 'text-rose-400' : 'text-slate-400'}`}>
                    {alertingNodesCount} active
                  </span>
                </div>
              </div>
            </div>

            {/* Nationwide averaged progress bars */}
            <div className="space-y-3 pt-1 border-t border-white/5">
              <div className="space-y-1">
                <div className="flex justify-between items-center text-[9px] font-black uppercase text-slate-400">
                  <span className="flex items-center gap-1"><Cpu size={10} className="text-indigo-400" /> Avg CPU Load</span>
                  <span className="font-mono">{avgCpu}%</span>
                </div>
                <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                  <Motion.div 
                    animate={{ width: `${Math.max(4, avgCpu)}%` }} 
                    transition={{ duration: 0.4 }} 
                    className={`h-full ${getBarColor(avgCpu)}`}
                  />
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex justify-between items-center text-[9px] font-black uppercase text-slate-400">
                  <span className="flex items-center gap-1"><HardDrive size={10} className="text-cyan-400" /> Avg RAM Load</span>
                  <span className="font-mono">{avgRam}%</span>
                </div>
                <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                  <Motion.div 
                    animate={{ width: `${Math.max(4, avgRam)}%` }} 
                    transition={{ duration: 0.4 }} 
                    className={`h-full ${getBarColor(avgRam)}`}
                  />
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex justify-between items-center text-[9px] font-black uppercase text-slate-400">
                  <span className="flex items-center gap-1"><Layers size={10} className="text-purple-400" /> Avg MSD Usage</span>
                  <span className="font-mono">{avgMsd}%</span>
                </div>
                <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                  <Motion.div 
                    animate={{ width: `${Math.max(4, avgMsd)}%` }} 
                    transition={{ duration: 0.4 }} 
                    className={`h-full ${getBarColor(avgMsd)}`}
                  />
                </div>
              </div>
            </div>

            {/* Decision Mode Info */}
            <div className="flex items-center justify-between pt-3 border-t border-white/5 text-[9px] font-black uppercase text-slate-400">
              <span>Dynamic Engine</span>
              <span className={`font-mono px-2 py-0.5 rounded-lg text-[9px] ${isDrl ? 'text-amber-400 bg-amber-500/10 border border-amber-500/20' : 'text-indigo-400 bg-indigo-500/10 border border-indigo-500/20'}`}>
                {isDrl ? 'JO-VPPM' : 'Heuristic'}
              </span>
            </div>
          </Motion.div>
        )}
      </AnimatePresence>
    </Motion.div>
  );
};

export default TelemetryPanel;
