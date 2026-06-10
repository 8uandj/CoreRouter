import React from 'react';
import { motion as Motion } from 'framer-motion';
import { X } from 'lucide-react';

const THEME = {
  primary: "from-indigo-600 to-cyan-500",
  ring: "focus:ring-cyan-500",
  accent: "text-cyan-400",
  input: "bg-slate-900 border-white/10 text-slate-100"
};

const ProvisionModal = ({
  isOpen, onClose,
  formData, setFormData,
  onSubmit
}) => {
  if (!isOpen) return null;

  const PROVINCES = [
    { id: 'auto', name: 'Auto Scheduler (Hybrid JO-VPPM)' },
    { id: 'hanoi-1', name: 'Hanoi Node (hanoi-1)' },
    { id: 'haiphong-1', name: 'Hai Phong Node (haiphong-1)' },
    { id: 'ninhbinh-1', name: 'Ninh Binh Node (ninhbinh-1)' },
    { id: 'vinh-1', name: 'Vinh Node (vinh-1)' },
    { id: 'hue-1', name: 'Hue Node (hue-1)' },
    { id: 'danang-1', name: 'Da Nang Node (danang-1)' },
    { id: 'quynhon-1', name: 'Quy Nhon Node (quynhon-1)' },
    { id: 'nhatrang-1', name: 'Nha Trang Node (nhatrang-1)' },
    { id: 'hcm-1', name: 'Ho Chi Minh Node (hcm-1)' },
    { id: 'cantho-1', name: 'Can Tho Node (cantho-1)' },
  ];

  const VNF_TYPES = [
    { id: 'firewall', name: 'vFirewall (Security Guard)' },
    { id: 'idps', name: 'vIDPS (Intrusion Detection)' },
    { id: 'router', name: 'vRouter (FRR Routing)' },
    { id: 'nat', name: 'vNAT (Network Address Translation)' },
    { id: 'lb', name: 'vLB (Traffic Balancer)' },
    { id: 'voc', name: 'vVOC (Voice & VoIP Optimizer)' },
  ];

  const handleFormSubmit = (e) => {
    e.preventDefault();
    let finalLocation = formData.location || 'auto';
    let finalName = formData.name || `vnf-${formData.type}-${Math.floor(Math.random() * 1000)}`;

    onSubmit({
      ...formData,
      name: finalName,
      location: finalLocation
    });
  };

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/90 backdrop-blur-md p-6">
      <Motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="bg-[#0f172a] border border-white/10 p-10 rounded-[3rem] w-full max-w-lg shadow-[0_50px_100px_rgba(0,0,0,0.9)] relative"
      >
        <button
          onClick={onClose}
          type="button"
          className="absolute top-10 right-10 text-slate-500 hover:text-white transition-colors"
        >
          <X size={28} />
        </button>

        <h3 className="text-2xl font-black mb-1 italic uppercase text-white">
          Provision <span className={THEME.accent}>VNF Instance</span>
        </h3>
        <p className="text-slate-500 font-bold text-xs mb-10 tracking-tight uppercase">
          Deploy to the Vietnam backbone cluster labels used by Tekton.
        </p>

        <form onSubmit={handleFormSubmit} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="text-[10px] font-black text-slate-500 mb-2 block uppercase tracking-widest">VNF Type</label>
              <select
                className={`w-full ${THEME.input} border p-4 rounded-2xl text-xs font-black outline-none focus:ring-2 ${THEME.ring} transition-all`}
                value={formData.type}
                onChange={e => setFormData({ ...formData, type: e.target.value })}
              >
                {VNF_TYPES.map(type => (
                  <option key={type.id} value={type.id} className="bg-[#0f172a]">{type.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[10px] font-black text-slate-500 mb-2 block uppercase tracking-widest">Target Location</label>
              <select
                className={`w-full ${THEME.input} border p-4 rounded-2xl text-xs font-black outline-none focus:ring-2 ${THEME.ring} transition-all`}
                value={formData.location}
                onChange={e => setFormData({ ...formData, location: e.target.value })}
              >
                {PROVINCES.map(prov => (
                  <option key={prov.id} value={prov.id} className="bg-[#0f172a]">{prov.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="text-[10px] font-black text-slate-500 mb-2 block uppercase tracking-widest">Instance Name Identity</label>
            <input
              className={`w-full ${THEME.input} border p-4 rounded-2xl text-xs font-black outline-none focus:ring-2 ${THEME.ring} transition-all placeholder:text-slate-600`}
              placeholder="e.g. vnf-firewall-01"
              value={formData.name}
              onChange={e => setFormData({ ...formData, name: e.target.value })}
              required
            />
          </div>

          <button type="submit" className={`w-full py-5 rounded-[2rem] font-black text-sm bg-gradient-to-r ${THEME.primary} hover:scale-[1.02] shadow-2xl transition-all uppercase tracking-widest text-white`}>
            Start Orchestration Pipeline
          </button>
        </form>
      </Motion.div>
    </div>
  );
};

export default ProvisionModal;
