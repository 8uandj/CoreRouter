import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';
import { Activity, Server, TrendingUp, GitBranch, Settings, ShieldAlert, ChevronRight } from 'lucide-react';
import Topology from './views/Topology';
import VnfManagement from './views/VnfManagement';
import Telemetry from './views/Telemetry';
import TektonDashboard from './views/TektonDashboard';
import { vnfService } from './services/api';

const App = () => {
  const [vnfs, setVnfs] = useState({ nodes: [] });
  const [isNavOpen, setIsNavOpen] = useState(false);

  const fetchData = async () => {
    try {
      const data = await vnfService.fetchVnfs();
      setVnfs(data);
    } catch {
      // API unreachable, fallback to empty or mock
    }
  };

  const handleDeploy = async (formData) => {
    try {
      const res = await vnfService.deployVnf(formData);
      alert(res.message || 'Deployment initiated.');
      fetchData();
    } catch (e) {
      const detail = e.response?.data?.detail;
      const msg = Array.isArray(detail) ? detail.map(d => d.msg).join(', ') : (detail || e.message);
      alert(`Deploy Error: ${msg}`);
    }
  };

  const handleDelete = async (vnfName) => {
    if (!window.confirm(`Delete VNF: ${vnfName}?`)) return;
    try {
      await vnfService.deleteVnf(vnfName);
      fetchData();
    } catch (e) {
      alert(`Delete failed: ${e.message}`);
    }
  };

  useEffect(() => {
    queueMicrotask(fetchData);
    const t = setInterval(fetchData, 5000);
    return () => clearInterval(t);
  }, []);

  const navItems = [
    { path: '/', label: 'Topology Map', icon: <Activity size={18} />, sub: 'Hybrid JO-VPPM Visualizer' },
    { path: '/vnf-management', label: 'VNF Instances', icon: <Server size={18} />, sub: 'Registry & Configuration' },
    { path: '/telemetry', label: 'Network Telemetry', icon: <TrendingUp size={18} />, sub: 'Smart Admission & Performance' },
    { path: '/tekton', label: 'Tekton Pipelines', icon: <GitBranch size={18} />, sub: 'K8s Pipeline Execution (MBB)' },
  ];

  return (
    <Router>
      <div className="w-screen h-screen overflow-hidden bg-[#020617] font-sans flex text-white relative">
        {/* Floating Menu Tab on the left edge when sidebar is closed */}
        {!isNavOpen && (
          <div 
            onMouseEnter={() => setIsNavOpen(true)}
            className="fixed left-0 top-1/2 -translate-y-1/2 w-5 h-20 bg-indigo-600/20 hover:bg-indigo-600/40 border border-l-0 border-indigo-500/30 rounded-r-2xl flex items-center justify-center cursor-pointer z-[45] transition-all duration-300 shadow-lg shadow-indigo-500/10"
            title="Hover to expand menu"
          >
            <ChevronRight className="text-indigo-400 animate-pulse" size={14} />
          </div>
        )}

        {/* Hover trigger zone at the left edge */}
        <div 
          onMouseEnter={() => setIsNavOpen(true)}
          className="fixed left-0 top-0 w-3 h-full z-40 bg-gradient-to-r from-indigo-500/5 to-transparent hover:from-indigo-500/10 transition-all duration-300 cursor-pointer"
        />

        {/* Sleek Sidebar with Glassmorphism and Neon highlights - Auto Hiding */}
        <aside 
          onMouseEnter={() => setIsNavOpen(true)}
          onMouseLeave={() => setIsNavOpen(false)}
          className={`fixed left-0 top-0 h-full w-80 border-r border-white/10 bg-[#030b18]/95 backdrop-blur-xl flex flex-col z-50 transition-transform duration-300 ease-in-out shadow-2xl ${
            isNavOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
        >
          {/* Logo & Brand */}
          <div className="h-20 border-b border-white/10 px-6 flex items-center gap-3 shrink-0">
            <div className="p-2.5 bg-indigo-600/20 border border-indigo-500/30 rounded-2xl flex items-center justify-center shadow-lg shadow-indigo-500/10">
              <ShieldAlert className="text-indigo-400 animate-pulse" size={24} />
            </div>
            <div>
              <h1 className="text-base font-black tracking-tight leading-none uppercase">
                3S-COM <span className="text-indigo-400">CORE</span>
              </h1>
              <p className="text-[9px] font-black text-indigo-400/70 tracking-[0.15em] uppercase mt-1">
                Orchestrator v1.2.0
              </p>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="flex-1 px-4 py-8 space-y-2 overflow-y-auto custom-scrollbar">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={() => setIsNavOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-4 px-5 py-4 rounded-2xl border transition-all duration-200 select-none ${
                    isActive
                      ? 'bg-indigo-600/15 border-indigo-500/30 text-white shadow-lg shadow-indigo-600/5'
                      : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/5'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <div className={`p-2 rounded-xl transition-colors ${isActive ? 'bg-indigo-500/20 text-indigo-400' : 'bg-slate-900/60 text-slate-400'}`}>
                      {item.icon}
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-black tracking-tight leading-tight">{item.label}</p>
                      <p className="text-[9px] font-bold text-slate-500 truncate mt-0.5">{item.sub}</p>
                    </div>
                  </>
                )}
              </NavLink>
            ))}
          </nav>

          {/* Sidebar Footer */}
          <div className="p-6 border-t border-white/10 bg-[#020712]/30 shrink-0 text-slate-500 text-[10px] font-black flex items-center justify-between">
            <span className="flex items-center gap-1.5 uppercase">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
              Hybrid Brain Online
            </span>
            <span className="font-mono text-slate-600">v1.2.0-beta</span>
          </div>
        </aside>

        {/* Main Content Area - Expands fully */}
        <main className="flex-1 h-full min-w-0 overflow-hidden relative">
          <Routes>
            <Route path="/" element={<Topology vnfs={vnfs} onDeploy={handleDeploy} onDelete={handleDelete} />} />
            <Route path="/vnf-management" element={<VnfManagement vnfs={vnfs} onDelete={handleDelete} />} />
            <Route path="/telemetry" element={<Telemetry />} />
            <Route path="/tekton" element={<TektonDashboard />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
};

export default App;
