import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Activity, Cpu } from 'lucide-react';

const Monitoring = () => {
  const [data, setData] = useState([]);

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await axios.get("http://localhost:8001/api/metrics/router");
        setData(prev => [...prev, res.data].slice(-30));
      } catch (e) { console.error(e); }
    };
    const t = setInterval(fetch, 3000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="flex-1 flex flex-col h-full bg-[#020617]">
      <header className="h-20 px-8 flex items-center border-b border-white/5 bg-[#020617]/50">
        <h2 className="text-xl font-bold text-white">System Analytics</h2>
      </header>
      
      <div className="flex-1 p-8 grid grid-cols-1 lg:grid-cols-2 gap-8 overflow-y-auto">
        {/* CPU Chart */}
        <div className="bg-slate-900/40 border border-white/5 p-8 rounded-[2rem] backdrop-blur-xl">
          <h3 className="text-cyan-400 font-black text-xs uppercase tracking-widest mb-8 flex items-center gap-2">
            <Activity size={16} /> CPU Utilization
          </h3>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                <XAxis dataKey="timestamp" hide />
                <YAxis stroke="#475569" fontSize={10} domain={[0, 100]} />
                <Tooltip contentStyle={{backgroundColor: '#020617', border: '1px solid #ffffff10', borderRadius: '12px'}} />
                <Line type="monotone" dataKey="cpu" stroke="#06b6d4" strokeWidth={4} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Memory Chart */}
        <div className="bg-slate-900/40 border border-white/5 p-8 rounded-[2rem] backdrop-blur-xl">
          <h3 className="text-emerald-400 font-black text-xs uppercase tracking-widest mb-8 flex items-center gap-2">
            <Cpu size={16} /> Memory Allocation
          </h3>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                <XAxis dataKey="timestamp" hide />
                <YAxis stroke="#475569" fontSize={10} />
                <Tooltip contentStyle={{backgroundColor: '#020617', border: '1px solid #ffffff10', borderRadius: '12px'}} />
                <Line type="monotone" dataKey="memory" stroke="#10b981" strokeWidth={4} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Monitoring;