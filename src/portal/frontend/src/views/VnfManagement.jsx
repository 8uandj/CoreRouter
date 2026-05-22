import React, { useState } from 'react';
import { motion as Motion } from 'framer-motion';
import { Shield, ShieldAlert, Cpu, Activity, Server, Trash2, Globe, Settings, Eye, Code, X } from 'lucide-react';

const CITY_NAMES = {
  hn: 'Hanoi', hanoi: 'Hanoi', s1: 'Hanoi',
  hp: 'Hai Phong', haiphong: 'Hai Phong', s2: 'Hai Phong',
  nb: 'Ninh Binh', ninhbinh: 'Ninh Binh', s3: 'Ninh Binh',
  vinh: 'Vinh', s4: 'Vinh',
  hue: 'Hue', s5: 'Hue',
  dn: 'Da Nang', danang: 'Da Nang', s6: 'Da Nang',
  qn: 'Quy Nhon', quynhon: 'Quy Nhon', s7: 'Quy Nhon',
  nt: 'Nha Trang', nhatrang: 'Nha Trang', s8: 'Nha Trang',
  hcm: 'Ho Chi Minh', hochiminh: 'Ho Chi Minh', s9: 'Ho Chi Minh',
  ct: 'Can Tho', cantho: 'Can Tho', s10: 'Can Tho',
};

const getVnfLocationDisplay = (name, rawLocation) => {
  const normName = String(name || '').toLowerCase();
  const normLoc = String(rawLocation || '').toLowerCase();

  const keys = Object.keys(CITY_NAMES).sort((a, b) => b.length - a.length);

  for (const key of keys) {
    if (normName.endsWith(key) || normName.includes(`-${key}`) || normName.includes(`_${key}`)) {
      return CITY_NAMES[key];
    }
  }

  for (const key of keys) {
    if (normLoc.includes(key)) {
      return CITY_NAMES[key];
    }
  }

  if (normLoc.includes('master') || normLoc.includes('hn')) return 'Hanoi';
  if (normLoc.includes('worker1') || normLoc.includes('dn')) return 'Da Nang';
  if (normLoc.includes('worker2') || normLoc.includes('hcm')) return 'Ho Chi Minh';

  return rawLocation || 'Dynamic Scheduler';
};

const VnfManagement = ({ vnfs, onDelete }) => {
  const [selectedVnf, setSelectedVnf] = useState(null);
  const vnfList = vnfs?.nodes || [];

  const getVnfIcon = (role) => {
    switch (role?.toLowerCase()) {
      case 'firewall':
        return <ShieldAlert className="text-rose-400 w-5 h-5" />;
      case 'idps':
        return <Cpu className="text-cyan-400 w-5 h-5" />;
      case 'router':
        return <Activity className="text-emerald-400 w-5 h-5" />;
      default:
        return <Server className="text-amber-400 w-5 h-5" />;
    }
  };

  const getRoleBadge = (role) => {
    const roles = {
      firewall: 'bg-rose-500/10 text-rose-300 border-rose-500/30',
      idps: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30',
      router: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
    };
    const style = roles[role?.toLowerCase()] || 'bg-amber-500/10 text-amber-300 border-amber-500/30';
    return (
      <span className={`px-2.5 py-1 text-[10px] font-black border rounded-lg uppercase tracking-wider ${style}`}>
        {role || 'VNF'}
      </span>
    );
  };

  const getStatusBadge = (status) => {
    const isRunning = status === 'Running';
    return (
      <span className={`px-2 py-0.5 text-[9px] font-black rounded-md uppercase ${
        isRunning ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-amber-500/20 text-amber-400 border border-amber-500/30 animate-pulse'
      }`}>
        {status || 'Pending'}
      </span>
    );
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#020617] overflow-hidden select-none">
      {/* Header */}
      <header className="h-20 px-8 flex items-center justify-between border-b border-white/10 bg-[#030b18]/60 backdrop-blur-md">
        <div>
          <p className="text-[10px] font-black text-indigo-400 uppercase tracking-[0.2em]">
            Lifecycle & Config Management
          </p>
          <h2 className="text-xl font-black italic tracking-tight text-white uppercase">
            VNF <span className="text-indigo-500">Instance Registry</span>
          </h2>
        </div>
        <div className="text-right">
          <p className="text-[10px] font-bold text-slate-500 uppercase">Active Inventory</p>
          <p className="text-lg font-black text-indigo-400">{vnfList.length} Deployed VNFs</p>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 p-8 overflow-y-auto custom-scrollbar">
        {vnfList.length === 0 ? (
          <Motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="h-[60vh] flex flex-col items-center justify-center border-2 border-dashed border-white/5 rounded-[3rem] bg-slate-900/10 p-10 max-w-4xl mx-auto my-6"
          >
            <Server size={48} className="text-slate-600 mb-4 animate-bounce" />
            <h3 className="text-lg font-black text-slate-400 mb-2">No Active VNF Instances Found</h3>
            <p className="text-sm text-slate-500 max-w-md text-center font-semibold leading-relaxed">
              No virtual network functions are currently provisioned on the Kubernetes cluster. Go to the Topology page and trigger SRv6 optimization or provision a VNF manually.
            </p>
          </Motion.div>
        ) : (
          <Motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="max-w-7xl mx-auto space-y-6"
          >
            {/* Grid layout */}
            <div className="bg-slate-950/60 border border-white/10 rounded-[2rem] overflow-hidden backdrop-blur-xl shadow-2xl">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-white/10 bg-[#081225] text-slate-400 text-[10px] font-black uppercase tracking-wider">
                    <th className="py-5 px-6">VNF Name</th>
                    <th className="py-5 px-6">Type</th>
                    <th className="py-5 px-6">Location</th>
                    <th className="py-5 px-6">Node Status</th>
                    <th className="py-5 px-6">Specs (CPU / RAM)</th>
                    <th className="py-5 px-6">K8s Namespace</th>
                    <th className="py-5 px-6 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 text-sm">
                  {vnfList.map((vnf) => {
                    const data = vnf.data || {};
                    const name = vnf.id;
                    const location = data.location || 'auto';
                    const status = data.status || 'Pending';
                    const role = data.role || 'router';
                    const readyStr = vnf.ready !== undefined ? `${vnf.ready}/${vnf.desired}` : '1/1';
                    
                    // Virtual Specs based on role
                    const cpuAlloc = role === 'firewall' ? '4 Cores' : role === 'idps' ? '8 Cores' : '2 Cores';
                    const ramAlloc = role === 'firewall' ? '8 GB' : role === 'idps' ? '16 GB' : '4 GB';

                    return (
                      <tr key={name} className="hover:bg-white/5 transition-colors group">
                        <td className="py-4 px-6 font-bold text-white flex items-center gap-3">
                          <div className="p-2 bg-slate-900 rounded-xl border border-white/5 group-hover:border-indigo-500/30 transition-colors">
                            {getVnfIcon(role)}
                          </div>
                          <div>
                            <p className="text-xs font-black tracking-tight text-white leading-tight">{name}</p>
                            <p className="text-[9px] font-bold text-slate-500 font-mono mt-0.5">UID: {name.slice(-8)}</p>
                          </div>
                        </td>
                        <td className="py-4 px-6">{getRoleBadge(role)}</td>
                        <td className="py-4 px-6 font-semibold text-slate-300">
                          <span className="flex items-center gap-1.5 capitalize text-xs">
                            <Globe size={13} className="text-indigo-400" />
                            {getVnfLocationDisplay(name, location)}
                          </span>
                        </td>
                        <td className="py-4 px-6">
                          <div className="flex flex-col gap-1">
                            <div>{getStatusBadge(status)}</div>
                            <span className="text-[10px] font-bold text-slate-500 font-mono">Ready: {readyStr}</span>
                          </div>
                        </td>
                        <td className="py-4 px-6 text-xs text-slate-300 font-mono font-bold">
                          {cpuAlloc} / {ramAlloc}
                        </td>
                        <td className="py-4 px-6 text-xs text-slate-400 font-mono">
                          core-router
                        </td>
                        <td className="py-4 px-6 text-right space-x-2">
                          <button
                            onClick={() => setSelectedVnf({ ...vnf, cpuAlloc, ramAlloc })}
                            className="p-2 bg-[#0b1329] border border-white/10 hover:border-indigo-500/40 text-slate-400 hover:text-white rounded-xl transition-all"
                            title="Inspect Config"
                          >
                            <Eye size={15} />
                          </button>
                          <button
                            onClick={() => onDelete(name)}
                            className="p-2 bg-rose-500/10 border border-rose-500/20 hover:bg-rose-500/20 text-rose-400 rounded-xl transition-all"
                            title="Terminate VNF"
                          >
                            <Trash2 size={15} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Motion.div>
        )}
      </div>

      {/* Detail Modal */}
      {selectedVnf && (
        <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/90 backdrop-blur-md p-6">
          <Motion.div 
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="bg-[#0f172a] border border-white/10 p-10 rounded-[3rem] w-full max-w-2xl shadow-[0_50px_100px_rgba(0,0,0,0.9)] relative"
          >
            <button
              onClick={() => setSelectedVnf(null)}
              className="absolute top-10 right-10 text-slate-500 hover:text-white transition-colors"
            >
              <X size={28} />
            </button>

            <h3 className="text-xl font-black mb-1 italic text-white uppercase flex items-center gap-2">
              <Settings size={20} className="text-indigo-400" />
              Inspect <span className="text-indigo-400">VNF Config</span>
            </h3>
            <p className="text-slate-500 font-bold text-xs mb-8 tracking-tight uppercase">
              Kubernetes Resource Manifest specs & details
            </p>

            <div className="space-y-6 text-slate-300">
              <div className="grid grid-cols-2 gap-6 bg-slate-950/50 p-6 rounded-3xl border border-white/5">
                <div>
                  <p className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Deployment Name</p>
                  <p className="text-sm font-bold text-white mt-1 font-mono">{selectedVnf.id}</p>
                </div>
                <div>
                  <p className="text-[10px] font-black text-slate-500 uppercase tracking-wider">K8s Namespace</p>
                  <p className="text-sm font-bold text-white mt-1 font-mono">core-router</p>
                </div>
                <div>
                  <p className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Type / Function</p>
                  <p className="text-sm font-bold text-white mt-1 uppercase tracking-wider">{selectedVnf.data?.role}</p>
                </div>
                <div>
                  <p className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Location / Cluster</p>
                  <p className="text-sm font-bold text-white mt-1 capitalize">
                    {getVnfLocationDisplay(selectedVnf.id, selectedVnf.data?.location)}
                  </p>
                </div>
              </div>

              <div className="space-y-3">
                <p className="text-[10px] font-black text-slate-500 uppercase tracking-wider flex items-center gap-1">
                  <Code size={12} className="text-cyan-400" /> Simulated Manifest Output
                </p>
                <div className="bg-black/50 border border-white/5 p-5 rounded-3xl font-mono text-[10px] leading-relaxed max-h-60 overflow-y-auto text-slate-400 custom-scrollbar">
                  <pre>{`apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${selectedVnf.id}
  namespace: core-router
  labels:
    app: ${selectedVnf.id}
    core-router/role: ${selectedVnf.data?.role}
    core-router/location: ${selectedVnf.data?.location}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ${selectedVnf.id}
  template:
    metadata:
      labels:
        app: ${selectedVnf.id}
    spec:
      containers:
      - name: vnf
        image: 3scom-vnf-${selectedVnf.data?.role}:v1.2.0
        resources:
          requests:
            cpu: "${selectedVnf.cpuAlloc?.split(' ')[0]}"
            memory: "${selectedVnf.ramAlloc?.split(' ')[0]}Gi"
          limits:
            cpu: "${selectedVnf.cpuAlloc?.split(' ')[0]}"
            memory: "${selectedVnf.ramAlloc?.split(' ')[0]}Gi"
---
apiVersion: v1
kind: Service
metadata:
  name: ${selectedVnf.id}-svc
  namespace: core-router
spec:
  type: NodePort
  selector:
    app: ${selectedVnf.id}
  ports:
  - port: 80
    targetPort: 8080
    nodePort: ${30000 + Math.floor(Math.random() * 999)}
    protocol: TCP`}</pre>
                </div>
              </div>
            </div>

            <div className="mt-8 flex justify-end">
              <button
                onClick={() => setSelectedVnf(null)}
                className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-2xl font-black text-xs uppercase tracking-wider transition-all"
              >
                Close View
              </button>
            </div>
          </Motion.div>
        </div>
      )}
    </div>
  );
};

export default VnfManagement;
