import React from 'react';
import { Terminal, CheckCircle2, Loader2, Activity } from 'lucide-react';

const ActivityPanel = ({ pipelineProgress }) => {
  // Debug: Nếu dòng này hiện "undefined" trong F12, thì lỗi nằm ở Layout.jsx
  console.log("ActivityPanel check:", pipelineProgress);

  return (
    <div className="w-80 bg-[#020617] border-l border-white/5 flex flex-col h-full shadow-2xl">
      <div className="p-6 border-b border-white/5 bg-slate-900/10">
        <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 flex items-center gap-2">
          <Terminal size={14} className="text-violet-500" /> System Activity
        </h3>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
        {pipelineProgress && pipelineProgress.tasks && pipelineProgress.tasks.length > 0 ? (
          <div className="space-y-6">
            <div className="pb-4 border-b border-white/5">
              <p className="text-[9px] font-mono text-violet-400 truncate mb-1">{pipelineProgress.name}</p>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold text-emerald-500 uppercase tracking-tighter">
                   {pipelineProgress.overallStatus}
                </span>
              </div>
            </div>

            {pipelineProgress.tasks.map((task, idx) => (
              <div key={idx} className="relative flex gap-3 group">
                {/* Line nối giữa các Task */}
                {idx !== pipelineProgress.tasks.length - 1 && (
                  <div className="absolute left-[7px] top-5 w-[1px] h-8 bg-slate-800" />
                )}

                <div className="relative z-10 mt-1">
                  {task.status === 'Succeeded' ? (
                    <CheckCircle2 size={15} className="text-emerald-500 bg-[#020617]" />
                  ) : (
                    <Loader2 size={15} className="text-violet-500 animate-spin bg-[#020617]" />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <h4 className="text-[11px] font-medium text-slate-300 group-hover:text-white transition-colors">
                    {task.name}
                  </h4>
                  <p className="text-[8px] font-bold text-slate-600 uppercase tracking-widest">
                    {task.status}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center opacity-20">
            <Activity size={32} className="mb-4 text-slate-700" />
            <p className="text-[10px] font-mono text-slate-600 italic">No Task Active</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ActivityPanel;