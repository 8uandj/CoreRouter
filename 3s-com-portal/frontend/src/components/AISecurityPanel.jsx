import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import axios from 'axios';
import { Shield, Play, Square, ChevronDown, ChevronUp, AlertTriangle, Activity } from 'lucide-react'; 
// Đừng quên cài lucide-react nếu chưa có: npm install lucide-react

const AISecurityPanel = () => {
  const location = useLocation();
  
  // 1. Chỉ hiển thị khi đang ở trang chủ (Topology)
  const isVisible = location.pathname === '/';
  
  // State quản lý thu nhỏ/phóng to
  const [isMinimized, setIsMinimized] = useState(false);
  
  const [status, setStatus] = useState({
    running: false, 
    current_score: 0.0,
    status: 'NORMAL',
    logs: []
  });

  // Polling dữ liệu
  useEffect(() => {
    if (!isVisible) return; // Không ở trang topology thì không polling để tiết kiệm

    const interval = setInterval(async () => {
      try {
        const res = await axios.get('http://localhost:8001/api/ai/status');
        setStatus(res.data);
      } catch (err) {}
    }, 1000);
    return () => clearInterval(interval);
  }, [isVisible]);

  // Handler buttons
  const handleStart = async () => { try { await axios.post('http://localhost:8001/api/ai/simulation/start'); } catch (e){} };
  const handleStop = async () => { try { await axios.post('http://localhost:8001/api/ai/simulation/stop'); } catch (e){} };

  // Logic hiển thị
  const isAttack = status.status === 'ATTACK';
  const scoreVal = typeof status.current_score === 'number' ? status.current_score : 0;
  const scorePercent = Math.min(scoreVal * 1000, 100);

  // Nếu không phải trang Topology -> Biến mất hoàn toàn
  if (!isVisible) return null;

  // --- GIAO DIỆN KHI THU NHỎ (MINIMIZED) ---
  if (isMinimized) {
    return (
      <div 
        onClick={() => setIsMinimized(false)}
        className={`absolute bottom-5 left-5 z-[9999] cursor-pointer 
          flex items-center gap-3 px-4 py-3 rounded-xl shadow-2xl border transition-all duration-300 hover:scale-105
          ${isAttack 
            ? 'bg-red-900/90 border-red-500 animate-pulse text-white' 
            : 'bg-slate-900/90 border-slate-700 text-slate-300'
          }`}
      >
        {isAttack ? <AlertTriangle size={24} /> : <Shield size={24} className="text-cyan-400"/>}
        <div>
          <h4 className="font-bold text-sm">AI Sentinel</h4>
          <p className="text-[10px] opacity-80">{status.status}</p>
        </div>
        <ChevronUp size={16} className="ml-2 opacity-50"/>
      </div>
    );
  }

  // --- GIAO DIỆN FULL (EXPANDED) ---
  return (
    <div className={`absolute bottom-5 left-5 z-[9999] w-[380px] 
      backdrop-blur-xl rounded-2xl border shadow-2xl transition-all duration-500
      ${isAttack 
        ? 'bg-red-950/90 border-red-500 shadow-red-900/50' 
        : 'bg-slate-950/90 border-slate-700 shadow-black/50'
      }`}
    >
      {/* Header Bar */}
      <div className="flex items-center justify-between p-4 border-b border-white/10">
        <div className="flex items-center gap-2">
          <Shield size={18} className={isAttack ? 'text-red-400' : 'text-cyan-400'} />
          <span className="font-bold text-slate-100 text-sm tracking-wide">AI SENTINEL ENGINE</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
            isAttack 
            ? 'bg-red-500/20 border-red-500 text-red-200 animate-pulse' 
            : 'bg-emerald-500/20 border-emerald-500 text-emerald-300'
          }`}>
            {status.status}
          </span>
          <button onClick={() => setIsMinimized(true)} className="p-1 hover:bg-white/10 rounded text-slate-400">
            <ChevronDown size={16} />
          </button>
        </div>
      </div>

      {/* Body Content */}
      <div className="p-4 space-y-4">
        
        {/* Anomaly Gauge */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs text-slate-400 font-medium">
            <span className="flex items-center gap-1"><Activity size={12}/> Threat Level (MSE)</span>
            <span className="font-mono text-slate-200">{scoreVal.toFixed(4)}</span>
          </div>
          <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
            <div 
              className={`h-full transition-all duration-500 ease-out ${isAttack ? 'bg-gradient-to-r from-orange-500 to-red-600' : 'bg-emerald-500'}`}
              style={{ width: `${scorePercent}%` }}
            />
          </div>
        </div>

        {/* Console Logs */}
        <div className="bg-black/40 rounded-lg p-3 h-32 overflow-y-auto border border-white/5 font-mono text-[10px] leading-relaxed scrollbar-thin scrollbar-thumb-slate-700">
          {(!status.logs || status.logs.length === 0) 
            ? <span className="text-slate-600 italic">System ready. Waiting for traffic...</span> 
            : status.logs.slice().reverse().map((log, idx) => (
                <div key={idx} className={`border-l-2 pl-2 mb-1 ${log.includes('ATTACK') ? 'border-red-500 text-red-300' : 'border-emerald-500 text-emerald-300/80'}`}>
                  {log}
                </div>
              ))
          }
        </div>

        {/* Action Buttons */}
        <div className="grid grid-cols-2 gap-3 pt-2">
          <button 
            onClick={handleStart} 
            disabled={status.running}
            className={`flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-bold transition-all
              ${status.running 
                ? 'bg-slate-800 text-slate-500 cursor-not-allowed' 
                : 'bg-cyan-600 hover:bg-cyan-500 text-white shadow-lg shadow-cyan-900/20 active:scale-95'
              }`}
          >
            <Play size={14} fill="currentColor" />
            SIMULATE ATTACK
          </button>
          
          <button 
            onClick={handleStop} 
            disabled={!status.running}
            className={`flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-bold transition-all
              ${!status.running 
                ? 'bg-slate-800 text-slate-500 cursor-not-allowed' 
                : 'bg-slate-700 hover:bg-slate-600 text-white active:scale-95'
              }`}
          >
            <Square size={14} fill="currentColor" />
            STOP
          </button>
        </div>
      </div>
    </div>
  );
};

export default AISecurityPanel;