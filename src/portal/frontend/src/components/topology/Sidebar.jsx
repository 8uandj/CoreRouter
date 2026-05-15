import React from 'react';
import { motion as Motion, AnimatePresence } from 'framer-motion';
import { Server, ShieldAlert, Cpu, Database, ZapOff, ChevronLeft, ChevronRight, Activity } from 'lucide-react';

const Sidebar = ({ isOpen, setIsOpen, activeVnfs, vnfLocMemo, rrTrackers, logs, logEndRef }) => {
  return (
    <Motion.div 
      initial={false}
      animate={{ 
        width: isOpen ? 420 : 60,
        backgroundColor: isOpen ? 'rgba(3, 11, 24, 1)' : 'rgba(3, 11, 24, 0.8)'
      }}
      className="h-full border-l border-white/10 flex flex-col z-20 shadow-[-20px_0_30px_rgba(0,0,0,0.4)] relative overflow-hidden"
    >
      {/* Toggle Button */}
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="absolute top-1/2 -left-3 transform -translate-y-1/2 w-8 h-16 bg-indigo-600 rounded-xl flex items-center justify-center border border-white/10 shadow-xl z-30 hover:bg-indigo-500 transition-colors"
      >
        {isOpen ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
      </button>

      <AnimatePresence mode="wait">
        {isOpen ? (
          <Motion.div 
            key="open"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            className="flex flex-col h-full w-[420px]"
          >
            {/* Resource Management */}
            <div className="p-6 border-b border-white/5 space-y-4">
               <h2 className="text-xs font-black text-indigo-400 uppercase tracking-widest flex items-center gap-2">
                 <Server size={14}/> Vietnam VNF Pool
               </h2>
               <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
                  {activeVnfs.length === 0 ? (
                    <div className="p-8 text-center border-2 border-dashed border-white/5 rounded-[2rem] opacity-30">
                      <ZapOff size={24} className="mx-auto mb-2 text-slate-500"/>
                      <p className="text-[10px] font-bold">No instances deployed</p>
                    </div>
                  ) : activeVnfs.map(v => (
                    <div key={v.id} className="p-4 bg-white/5 rounded-3xl border border-white/5">
                      <div className="flex justify-between items-start mb-3">
                         <div className="flex items-center gap-3">
                            <div className={`p-2.5 rounded-2xl bg-opacity-20 ${
                              v.data?.role === 'firewall' ? 'bg-red-500' :
                              v.data?.role === 'idps' ? 'bg-cyan-500' :
                              'bg-emerald-500'
                            }`}>
                               {v.data?.role === 'firewall' ? <ShieldAlert size={14} className="text-red-400"/> :
                                v.data?.role === 'idps' ? <Cpu size={14} className="text-cyan-400"/> :
                                <Activity size={14} className="text-emerald-400"/>}
                            </div>
                            <div>
                               <p className="text-xs font-black leading-tight tracking-tight">{v.id}</p>
                               <p className="text-[10px] font-bold text-slate-500 uppercase">{vnfLocMemo.current[v.id]?.toUpperCase() || 'Auto'}</p>
                            </div>
                         </div>
                         <span className={`text-[8px] font-black px-2 py-0.5 rounded-lg uppercase ${v.data?.status==='Running'?'bg-emerald-500/20 text-emerald-400':'bg-amber-500/20 text-amber-400'}`}>
                            {v.data?.status || 'Pending'}
                         </span>
                      </div>
                      <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                         <Motion.div 
                           initial={{ width: 0 }}
                           animate={{ width: `${Math.min(100, (rrTrackers.current[v.id] || 0) * 25)}%` }}
                           className={`h-full transition-all duration-500 ${(rrTrackers.current[v.id]||0)>3?'bg-red-500':(rrTrackers.current[v.id]||0)>1?'bg-amber-400':'bg-indigo-500'}`} 
                         />
                      </div>
                    </div>
                  ))}
               </div>
            </div>

            {/* Logs */}
            <div className="flex-1 flex flex-col p-6 min-h-0">
              <h2 className="text-xs font-black text-cyan-400 uppercase tracking-widest flex items-center gap-2 mb-4">
                <Database size={14}/> Hybrid Orchestration Logs
              </h2>
              <div className="flex-1 bg-black/40 rounded-[2rem] border border-white/5 p-5 overflow-y-scroll space-y-2 font-mono text-[10px] leading-relaxed custom-scrollbar text-slate-400">
                {logs.map(l => (
                  <div key={l.id} className="border-b border-white/5 pb-1" style={{ color: l.color }}>{l.msg}</div>
                ))}
                <div ref={logEndRef}/>
              </div>
            </div>
          </Motion.div>
        ) : (
          <Motion.div 
            key="closed"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center py-8 gap-12 w-full"
          >
            <Server size={20} className="text-indigo-600" />
            <Database size={20} className="text-cyan-600" />
            <div className="h-40 w-1 bg-white/10 rounded-full" />
            <div className="transform -rotate-90 whitespace-nowrap text-[10px] font-black text-slate-600 tracking-[0.5em] uppercase">
              Vietnam Console
            </div>
          </Motion.div>
        )}
      </AnimatePresence>
    </Motion.div>
  );
};

export default Sidebar;
