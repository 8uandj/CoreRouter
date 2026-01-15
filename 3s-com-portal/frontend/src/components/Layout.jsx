import React from 'react';
import Sidebar from './Sidebar';
import ActivityPanel from './ActivityPanel';

const Layout = ({ children, pipelineProgress }) => (
  <div className="flex h-screen w-screen bg-[#020617] text-slate-200 overflow-hidden font-sans">
    <Sidebar />
    <main className="flex-1 flex flex-col relative overflow-hidden border-r border-white/5">
      {children}
    </main>
    {/* BẮT BUỘC phải truyền xuống cho ActivityPanel */}
    <ActivityPanel pipelineProgress={pipelineProgress} />
  </div>
);
export default Layout;