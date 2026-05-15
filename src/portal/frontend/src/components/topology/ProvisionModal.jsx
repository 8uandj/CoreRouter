import React from 'react';
import { motion as Motion } from 'framer-motion';
import { X } from 'lucide-react';

// --- Theme Colors (Easily adjustable) ---
const THEME = {
  primary: "from-blue-600 to-cyan-500",
  ring: "focus:ring-cyan-500",
  accent: "text-cyan-400",
  input: "bg-cyan-500/5 border-cyan-500/10 text-cyan-100"
};

const ProvisionModal = ({
  isOpen, onClose,
  formData, setFormData,
  onSubmit, dcs
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/90 backdrop-blur-md p-6">
      <Motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="bg-[#0f172a] border border-white/10 p-10 rounded-[3rem] w-full max-w-lg shadow-[0_50px_100px_rgba(0,0,0,0.9)] relative"
      >
        <button
          onClick={onClose}
          className="absolute top-10 right-10 text-slate-500 hover:text-white transition-colors"
        >
          <X size={28} />
        </button>

        <h3 className="text-2xl font-black mb-1 italic">
          Provision <span className={THEME.accent}>VNF</span>
        </h3>
        <p className="text-slate-500 font-bold text-sm mb-10 tracking-tight">
          Deploy to the Vietnam backbone cluster labels used by Tekton.
        </p>

        <form onSubmit={onSubmit} className="space-y-6">
          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="text-[10px] font-black text-slate-500 mb-2 block uppercase tracking-widest">Type</label>
              <select
                className={`w-full ${THEME.input} border p-4 rounded-2xl text-xs font-black outline-none focus:ring-2 ${THEME.ring} transition-all`}
                value={formData.type}
                onChange={e => setFormData({ ...formData, type: e.target.value })}
              >
                <option value="firewall" className="bg-[#0f172a]">vFirewall (PRO)</option>
                <option value="idps" className="bg-[#0f172a]">vIDPS (CORE)</option>
                <option value="router" className="bg-[#0f172a]">vRouter (BASE)</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] font-black text-slate-500 mb-2 block uppercase tracking-widest">Cluster Label</label>
              <select
                className={`w-full ${THEME.input} border p-4 rounded-2xl text-xs font-black outline-none focus:ring-2 ${THEME.ring} transition-all`}
                value={formData.location}
                onChange={e => setFormData({ ...formData, location: e.target.value })}
              >
                {Object.values(dcs).map(dc => (
                  <option key={dc.id} value={dc.id} className="bg-[#0f172a]">{dc.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="text-[10px] font-black text-slate-500 mb-2 block uppercase tracking-widest">Identity</label>
            <input
              className={`w-full ${THEME.input} border p-4 rounded-2xl text-xs font-black outline-none focus:ring-2 ${THEME.ring} transition-all placeholder:text-slate-600`}
              placeholder="e.g. node-01-edge"
              value={formData.name}
              onChange={e => setFormData({ ...formData, name: e.target.value })}
            />
          </div>

          <button className={`w-full py-5 rounded-[2rem] font-black text-sm bg-gradient-to-r ${THEME.primary} hover:scale-[1.02] shadow-2xl transition-all uppercase tracking-widest`}>
            Start Orchestration
          </button>
        </form>
      </Motion.div>
    </div>
  );
};

export default ProvisionModal;
