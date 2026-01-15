import React, { useState } from 'react';
import ReactFlow, { Background, Controls, useNodesState, useEdgesState } from 'reactflow';
// QUAN TRỌNG: Import CSS mặc định của ReactFlow để tránh vỡ giao diện
import 'reactflow/dist/style.css'; 
import { Plus, X, Shield, Scan, Router as RouterIcon, Activity } from 'lucide-react';import { motion, AnimatePresence } from 'framer-motion';

// --- Hàm hỗ trợ lấy Icon theo vai trò ---
const getVnfIcon = (role) => {
  switch(role) {
    case 'firewall': return <Shield size={16} className="text-rose-500" />;
    case 'idps': return <Scan size={16} className="text-amber-500" />;
    default: return <RouterIcon size={16} className="text-cyan-400" />;
  }
};

const Topology = ({ vnfs, onDeploy }) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState({ 
    name: '', 
    type: 'router', 
    profile: 'standard'  
  });
  // Xử lý dữ liệu node
  const flowNodes = vnfs?.nodes?.map((v, i) => ({
    id: v.id,
    data: { label: (
      <div className={`p-4 bg-slate-900 border rounded-xl shadow-2xl backdrop-blur-md min-w-[180px] transition-all hover:scale-105 ${
        v.data.role === 'firewall' ? 'border-rose-500/30 shadow-rose-500/10' : 
        v.data.role === 'idps' ? 'border-amber-500/30 shadow-amber-500/10' : 
        'border-cyan-500/30 shadow-cyan-500/10'
      }`}>
        <div className="flex items-center gap-3 mb-3">
          <div className="p-2 bg-white/5 rounded-lg border border-white/5">{getVnfIcon(v.data.role)}</div>
          <div className="text-left overflow-hidden">
            <p className="text-[9px] font-black uppercase text-slate-500 tracking-wider">{v.data.role}</p>
            <p className="text-xs font-bold text-white truncate w-full">{v.id}</p>
          </div>
        </div>
        <div className="flex justify-between items-center pt-2 border-t border-white/5">
             <p className="text-[10px] font-mono text-slate-400">{v.data.ip || 'Allocating...'}</p>
             <div className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                <span className="text-[8px] font-bold text-emerald-500 uppercase">Active</span>
             </div>
        </div>
      </div>
    )},
    // Tăng khoảng cách Y lên 150 để các node không bị dính vào nhau
    position: { 
      x: v.data.role === 'firewall' ? 50 : v.data.role === 'idps' ? 350 : 650, 
      y: 100 + (i * 150) 
    }
  })) || [];

  const flowEdges = vnfs?.edges || [];

  const handleSubmit = (e) => {
    e.preventDefault();
    onDeploy(formData);
    setIsModalOpen(false);
    setFormData({ name: '', namespace: 'vnf' });
  };

  return (
    // Sửa lỗi giao diện: Dùng h-full và flex-col để chiếm trọn khung hình
    <div className="flex flex-col h-full w-full relative bg-[#020617]">
      
      {/* HEADER */}
      <header className="h-20 px-8 flex flex-none items-center justify-between bg-[#020617]/80 backdrop-blur-md border-b border-white/5 z-20">
        <div>
          <h2 className="text-xs font-black text-slate-500 uppercase tracking-widest">Service Chain</h2>
          <h1 className="text-xl font-bold text-white">VNF Topology</h1>
        </div>
        <button 
          onClick={() => setIsModalOpen(true)}
          className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-2.5 rounded-xl font-bold text-sm transition-all flex items-center gap-2 shadow-lg shadow-indigo-500/20 active:scale-95"
        >
          <Plus size={18} /> PROVISION VNF
        </button>
      </header>

      {/* REACT FLOW CANVAS */}
      <div className="flex-1 w-full h-full relative">
        <ReactFlow 
          nodes={flowNodes} 
          edges={flowEdges} 
          fitView 
          minZoom={0.5}
          maxZoom={2}
          attributionPosition="bottom-left"
        >
          <Background color="#334155" gap={25} size={1} />
          
          {/* NÚT ZOOM (Controls) ĐÃ ĐƯỢC STYLE LẠI */}
          <Controls 
            position="bottom-right"
            className="!bg-slate-800 !border-white/10 !shadow-xl [&>button]:!border-white/10 [&>button]:!fill-slate-300 hover:[&>button]:!fill-white hover:[&>button]:!bg-slate-700"
          />
        </ReactFlow>
      </div>

      {/* MODAL */}
      <AnimatePresence>
        {isModalOpen && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
             <motion.div 
               initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
               className="absolute inset-0" onClick={() => setIsModalOpen(false)} 
             />
             <motion.form 
              initial={{ scale: 0.9, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }} exit={{ scale: 0.9, opacity: 0 }}
              onSubmit={handleSubmit}
              className="relative bg-[#0f172a] border border-white/10 p-8 rounded-3xl w-full max-w-md shadow-2xl z-10"
            >
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-xl font-bold text-white">New VNF Instance</h3>
                <button type="button" onClick={() => setIsModalOpen(false)} className="p-1 rounded-full hover:bg-white/10 transition-colors">
                    <X className="text-slate-400" size={20} />
                </button>
              </div>
              <div className="space-y-5">
    {/* 1. Nhập tên VNF */}
    <div>
      <label className="block text-[10px] font-bold text-slate-500 uppercase mb-2">Resource Name</label>
      <input 
        className="w-full bg-black/40 border border-white/10 p-4 rounded-xl outline-none focus:border-indigo-500 text-white transition-all font-mono placeholder:text-slate-600"
        placeholder="e.g. vnf-firewall-01"
        value={formData.name}
        onChange={(e) => setFormData({...formData, name: e.target.value.toLowerCase()})}
        autoFocus
        required
      />
    </div>

    {/* 2. Chọn Loại VNF và Cấu hình (Grid 2 cột) */}
    <div className="grid grid-cols-2 gap-4">
      <div>
        <label className="block text-[10px] font-bold text-slate-500 uppercase mb-2">Service Type</label>
        <div className="relative">
          <select 
            className="w-full bg-black/40 border border-white/10 p-4 rounded-xl outline-none text-white appearance-none cursor-pointer hover:border-indigo-500 transition-colors"
            value={formData.type}
            onChange={(e) => setFormData({...formData, type: e.target.value})}
          >
            <option value="router">vRouter (FRR)</option>
            <option value="firewall">vFirewall (Secure)</option>
            <option value="idps">vIDPS (Detection)</option>
          </select>
          {/* Mũi tên chỉ xuống trang trí */}
          <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500">▼</div>
        </div>
      </div>

      <div>
        <label className="block text-[10px] font-bold text-slate-500 uppercase mb-2">Profile</label>
        <div className="relative">
          <select 
            className="w-full bg-black/40 border border-white/10 p-4 rounded-xl outline-none text-white appearance-none cursor-pointer hover:border-indigo-500 transition-colors"
            value={formData.profile}
            onChange={(e) => setFormData({...formData, profile: e.target.value})}
          >
            <option value="standard">Standard (1 vCPU)</option>
            <option value="performance">High Perf (4 vCPU)</option>
          </select>
          <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500">▼</div>
        </div>
      </div>
    </div>

    {/* Phần hiển thị Flow mô phỏng */}
    <div className="p-3 bg-indigo-500/10 rounded-lg border border-indigo-500/20 mt-2">
      <p className="text-[9px] text-indigo-300 font-mono flex items-center gap-2">
        <Activity size={10} />
        <span className="font-bold">PATH:</span> User &rarr; {formData.type.toUpperCase()} &rarr; {formData.profile === 'standard' ? 'GKE-Pool-1' : 'GKE-Pool-HighMem'}
      </p>
    </div>

    <button className="w-full bg-indigo-600 hover:bg-indigo-500 py-4 rounded-xl font-bold shadow-lg shadow-indigo-600/20 text-white transition-all active:scale-95">
      INITIALIZE DEPLOYMENT
    </button>
  </div>
            </motion.form>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default Topology;