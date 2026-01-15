import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Globe, Zap, Cpu, Shield, Box } from 'lucide-react';

const Sidebar = () => {
  const { pathname } = useLocation();
  const menu = [
    { path: '/', icon: Globe, label: 'Topology' },
    { path: '/monitoring', icon: Cpu, label: 'Monitoring' },
    { path: '/pipelines', icon: Zap, label: 'Orchestration' },
    { path: '/security', icon: Shield, label: 'AI Security' },
  ];

  return (
    <div className="w-72 bg-[#020617] border-r border-white/5 flex flex-col z-20">
      <div className="p-8">
        <div className="flex items-center gap-3 mb-1">
          <div className="w-10 h-10 bg-gradient-to-br from-cyan-500 to-blue-600 rounded-xl flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <Box className="text-white w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white leading-none">3S-COM</h1>
            <span className="text-[10px] text-cyan-500 font-bold uppercase tracking-widest">Orchestrator</span>
          </div>
        </div>
      </div>
      <nav className="flex-1 px-4 space-y-2">
        {menu.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={`flex items-center gap-4 px-4 py-3.5 rounded-2xl transition-all duration-300 group ${
              pathname === item.path 
              ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20' 
              : 'text-slate-500 hover:bg-white/5 hover:text-slate-200'
            }`}
          >
            <item.icon size={20} className={pathname === item.path ? 'text-cyan-400' : 'group-hover:text-slate-200'} />
            <span className="font-semibold text-sm">{item.label}</span>
          </Link>
        ))}
      </nav>
    </div>
  );
};

export default Sidebar;