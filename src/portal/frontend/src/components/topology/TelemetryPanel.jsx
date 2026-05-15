import React from 'react';
import { motion as Motion, AnimatePresence } from 'framer-motion';
import { Activity, ChevronUp, ChevronDown } from 'lucide-react';

const TelemetryPanel = ({ isOpen, setIsOpen, hybridStatus }) => {
  const globalUtil = Math.round((hybridStatus?.globalUtilization || 0) * 100);
  const avgCpu = Math.round((hybridStatus?.avgCpu || 0) * 100);
  const avgMsd = Math.round((hybridStatus?.avgMsdUsage || 0) * 100);
  const isDrl = hybridStatus?.branch === 'drl';

  return (
    <Motion.div 
      initial={false} 
      animate={{ 
        height: isOpen ? 'auto' : 48, 
        width: isOpen ? 280 : 180 
      }} 
      className="absolute bottom-8 left-8 z-10 bg-[#030b18]/90 backdrop-blur-xl rounded-[2rem] border border-white/10 shadow-[0_20px_50px_rgba(0,0,0,0.5)] overflow-hidden"
    >
      <div 
        className="p-4 flex items-center justify-between cursor-pointer hover:bg-white/5 transition-colors" 
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-indigo-400"/>
          <h4 className="text-[10px] font-black text-slate-300 tracking-widest uppercase">Live Telemetry</h4>
        </div>
        {isOpen ? <ChevronDown size={14} className="text-slate-500"/> : <ChevronUp size={14} className="text-slate-500"/>}
      </div>
      
      <AnimatePresence>
        {isOpen && (
          <Motion.div 
            initial={{ opacity: 0 }} 
            animate={{ opacity: 1 }} 
            exit={{ opacity: 0 }} 
            className="px-6 pb-6 pt-2 space-y-4"
          >
            <div className="flex items-center justify-between gap-4">
              <span className="text-[10px] font-bold text-slate-500 uppercase">Control Branch</span>
              <span className={`text-xs font-mono ${isDrl ? 'text-red-400' : 'text-emerald-400'}`}>
                {isDrl ? 'JO-VPPM' : 'Heuristic'}
              </span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-[10px] font-bold text-slate-500 uppercase">Vietnam Util</span>
              <span className="text-xs font-mono text-amber-400">{globalUtil}%</span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-[10px] font-bold text-slate-500 uppercase">Avg CPU / MSD</span>
              <span className="text-xs font-mono text-cyan-400">{avgCpu}% / {avgMsd}%</span>
            </div>
            <div className="h-1 bg-white/5 rounded-full overflow-hidden">
              <Motion.div 
                animate={{ width: `${Math.max(4, globalUtil)}%` }} 
                transition={{ duration: 0.4 }} 
                className={`h-full ${isDrl ? 'bg-red-500' : 'bg-emerald-500'}`}
              />
            </div>
          </Motion.div>
        )}
      </AnimatePresence>
    </Motion.div>
  );
};

export default TelemetryPanel;
