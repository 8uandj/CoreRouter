import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, ChevronUp, ChevronDown } from 'lucide-react';

const TelemetryPanel = ({ isOpen, setIsOpen }) => {
  return (
    <motion.div 
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
          <h4 className="text-[10px] font-black text-slate-300 tracking-widest uppercase">Telemetry</h4>
        </div>
        {isOpen ? <ChevronDown size={14} className="text-slate-500"/> : <ChevronUp size={14} className="text-slate-500"/>}
      </div>
      
      <AnimatePresence>
        {isOpen && (
          <motion.div 
            initial={{ opacity: 0 }} 
            animate={{ opacity: 1 }} 
            exit={{ opacity: 0 }} 
            className="px-6 pb-6 pt-2 space-y-4"
          >
            <div className="flex items-center justify-between gap-4">
              <span className="text-[10px] font-bold text-slate-500 uppercase">Latency</span>
              <span className="text-xs font-mono text-amber-400">12.4 ms</span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-[10px] font-bold text-slate-500 uppercase">Throughput</span>
              <span className="text-xs font-mono text-cyan-400">4.2 Gbps</span>
            </div>
            <div className="h-1 bg-white/5 rounded-full overflow-hidden">
              <motion.div 
                animate={{ width: ['20%', '60%', '40%'] }} 
                transition={{ repeat: Infinity, duration: 4 }} 
                className="h-full bg-indigo-500"
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default TelemetryPanel;
