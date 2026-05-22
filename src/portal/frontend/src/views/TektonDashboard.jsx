import React, { useState, useEffect, useRef } from 'react';
import { motion as Motion, AnimatePresence } from 'framer-motion';
import { Terminal, Play, CheckCircle2, XCircle, Loader2, ArrowRight, GitBranch, RefreshCw, Calendar, Clock } from 'lucide-react';
import { vnfService } from '../services/api';

const MOCK_RUNS = [
  {
    name: "mig-vnf-firewall-hanoi-a982",
    pipelineName: "vnf-migrate-single",
    overallStatus: "Succeeded",
    startTime: "2026-05-21T21:20:10Z",
    completionTime: "2026-05-21T21:20:19Z",
    tasks: [
      { name: "workspace-setup", status: "Succeeded" },
      { name: "fetch-manifests", status: "Succeeded" },
      { name: "deploy-target-vnf", status: "Succeeded" }, // MAKE
      { name: "wait-target-ready", status: "Succeeded" }, // WAIT
      { name: "sdn-steer-traffic", status: "Succeeded" }, // STEER
      { name: "break-legacy-vnf", status: "Succeeded" }   // BREAK
    ],
    logs: [
      "[1] Initializing workspace PVC: storage 50Mi...",
      "[2] Fetching manifest file 'vnf-firewall.yaml'...",
      "[3] MAKE Phase: Deploying VNF 'vnf-firewall-a982' at location 'hanoi-1'...",
      "[4] Pod creation requested on Kubernetes API.",
      "[5] WAIT Phase: Waiting for Pod readiness probes...",
      "[6] Pod 'vnf-firewall-a982-8cddf76-sjk7c' ready state: 1/1.",
      "[7] STEER Phase: Signaling P4 Controller to update rules...",
      "[8] P4Runtime injected SRv6 Segment list: ['2001:db8:00:01::1', '2001:db8:01:02::1'].",
      "[9] SDN steer verified: confirm_steer_done=true.",
      "[10] BREAK Phase: Deleting legacy deployment 'vnf-firewall-old'...",
      "[11] Cleaned up legacy services. Pipeline run SUCCEEDED."
    ]
  },
  {
    name: "instantiate-sfc-cantho-023c",
    pipelineName: "vnf-lcm-fast",
    overallStatus: "Succeeded",
    startTime: "2026-05-21T21:10:02Z",
    completionTime: "2026-05-21T21:10:08Z",
    tasks: [
      { name: "workspace-setup", status: "Succeeded" },
      { name: "fetch-manifests", status: "Succeeded" },
      { name: "deploy-target-vnf", status: "Succeeded" },
      { name: "wait-target-ready", status: "Succeeded" }
    ],
    logs: [
      "[1] Initializing workspace PVC: storage 50Mi...",
      "[2] Fetching manifest file 'vnf-router.yaml'...",
      "[3] Deploying VNF 'vnf-router-023c' at location 'hcm-1'...",
      "[4] Pod 'vnf-router-023c-74dcbfd-jklf8' ready state: 1/1.",
      "[5] Creation successful."
    ]
  },
  {
    name: "terminate-vnf-vinh-829d",
    pipelineName: "vnf-terminate",
    overallStatus: "Succeeded",
    startTime: "2026-05-21T20:45:00Z",
    completionTime: "2026-05-21T20:45:04Z",
    tasks: [
      { name: "delete-vnf-deployment", status: "Succeeded" },
      { name: "delete-vnf-service", status: "Succeeded" }
    ],
    logs: [
      "[1] Initiated VNF termination sequence...",
      "[2] Removed deployment 'vnf-router-vinh-829d' from namespace 'core-router'...",
      "[3] Removed service endpoint 'vnf-router-vinh-829d-svc'...",
      "[4] VNF resources successfully freed."
    ]
  }
];

const TektonDashboard = () => {
  const [runs, setRuns] = useState(MOCK_RUNS);
  const [selectedRun, setSelectedRun] = useState(MOCK_RUNS[0]);
  const [loading, setLoading] = useState(false);
  const logEndRef = useRef(null);

  const fetchLatestRun = async () => {
    setLoading(true);
    try {
      const res = await vnfService.getSimulationStatus(); // /orchestrate/status in api.js?
      // Wait, in api.js, getSimulationStatus points to /ai/status. But we can call status directly.
      const statusRes = await vnfService.getSimulationStatus().catch(() => null);
      
      // Let's call the actual orchestrate status endpoint if possible
      const axios = (await import('axios')).default;
      const apiBase = import.meta.env.VITE_API_BASE || `http://${window.location.hostname}:8000/api`;
      const statusResponse = await axios.get(`${apiBase}/orchestrate/status`).catch(() => null);
      
      if (statusResponse && statusResponse.data?.latest_pipeline) {
        const latest = statusResponse.data.latest_pipeline;
        if (latest && latest.name && latest.name !== "No Run Found") {
          // Map backend Tekton status to our shape
          const isSucceeded = latest.overallStatus === "Succeeded";
          const newRun = {
            name: latest.name,
            pipelineName: latest.name.startsWith("mig") ? "vnf-migrate-single" : latest.name.startsWith("deploy") ? "vnf-lcm-fast" : "vnf-terminate",
            overallStatus: latest.overallStatus || "Running",
            startTime: new Date().toISOString(),
            completionTime: isSucceeded ? new Date().toISOString() : null,
            tasks: latest.tasks || [],
            logs: latest.logs || [
              `[1] Fetched latest PipelineRun state from K8s...`,
              `[2] Name: ${latest.name}`,
              `[3] Overall Status: ${latest.overallStatus}`,
              `[4] Active tasks monitored: ${JSON.stringify(latest.tasks)}`
            ]
          };
          
          setRuns(prev => {
            const exists = prev.some(r => r.name === newRun.name);
            if (exists) {
              return prev.map(r => r.name === newRun.name ? { ...r, overallStatus: newRun.overallStatus, tasks: newRun.tasks } : r);
            }
            return [newRun, ...prev];
          });
          setSelectedRun(newRun);
        }
      }
    } catch (e) {
      console.error("Failed to load live Tekton runs:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLatestRun();
    const interval = setInterval(fetchLatestRun, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [selectedRun?.logs]);

  const getStatusIcon = (status) => {
    switch (status?.toLowerCase()) {
      case 'succeeded':
        return <CheckCircle2 size={16} className="text-emerald-400" />;
      case 'failed':
        return <XCircle size={16} className="text-rose-400" />;
      case 'running':
        return <Loader2 size={16} className="text-cyan-400 animate-spin" />;
      default:
        return <RefreshCw size={16} className="text-slate-500" />;
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#020617] overflow-hidden select-none">
      {/* Header */}
      <header className="h-20 px-8 flex items-center justify-between border-b border-white/10 bg-[#030b18]/60 backdrop-blur-md shrink-0">
        <div>
          <p className="text-[10px] font-black text-indigo-400 uppercase tracking-[0.2em]">
            Kubernetes CI/CD Pipeline Dashboard
          </p>
          <h2 className="text-xl font-black italic tracking-tight text-white uppercase flex items-center gap-2">
            Tekton <span className="text-indigo-500">Pipeline Runs</span>
          </h2>
        </div>
        <button 
          onClick={fetchLatestRun}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-slate-900 border border-white/10 hover:border-indigo-500/40 text-slate-300 hover:text-white rounded-xl text-xs font-black transition-all uppercase"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          {loading ? 'Refreshing...' : 'Refresh Status'}
        </button>
      </header>

      {/* Main Grid split */}
      <div className="flex-1 p-8 grid grid-cols-1 lg:grid-cols-3 gap-8 min-h-0">
        
        {/* Left column: PipelineRuns List */}
        <div className="bg-[#030b18]/40 border border-white/5 rounded-[2.5rem] p-6 flex flex-col min-h-0">
          <h4 className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-4 flex items-center gap-1.5">
            <GitBranch size={13} className="text-indigo-400" /> Pipeline Run History
          </h4>
          <div className="flex-1 overflow-y-auto space-y-3 pr-1 custom-scrollbar">
            {runs.map((run) => (
              <div 
                key={run.name}
                onClick={() => setSelectedRun(run)}
                className={`p-4 rounded-3xl border cursor-pointer transition-all ${
                  selectedRun?.name === run.name
                    ? 'bg-indigo-600/10 border-indigo-500/50 shadow-lg shadow-indigo-600/5'
                    : 'bg-white/5 border-white/5 hover:bg-white/10 hover:border-white/10'
                }`}
              >
                <div className="flex justify-between items-start mb-2">
                  <span className="text-[9px] font-black text-slate-500 uppercase tracking-wide font-mono bg-slate-900/60 px-2 py-0.5 rounded-md border border-white/5">
                    {run.pipelineName}
                  </span>
                  <div className="flex items-center gap-1">
                    {getStatusIcon(run.overallStatus)}
                    <span className={`text-[8px] font-black uppercase ${
                      run.overallStatus === 'Succeeded' ? 'text-emerald-400' : run.overallStatus === 'Failed' ? 'text-rose-400' : 'text-cyan-400'
                    }`}>
                      {run.overallStatus}
                    </span>
                  </div>
                </div>
                <h5 className="text-xs font-black text-white truncate mb-3" title={run.name}>
                  {run.name}
                </h5>
                <div className="flex justify-between items-center text-[10px] font-bold text-slate-500">
                  <span className="flex items-center gap-1">
                    <Calendar size={11} /> {new Date(run.startTime).toLocaleDateString()}
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock size={11} /> {new Date(run.startTime).toLocaleTimeString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right column: DAG Visualization and CLI Terminal */}
        <div className="lg:col-span-2 flex flex-col gap-8 min-h-0">
          
          {/* Top Panel: Task DAG Visualizer */}
          <div className="bg-[#030b18]/40 border border-white/5 rounded-[2.5rem] p-6">
            <h4 className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-6">
              Task Execution Flow (DAG)
            </h4>
            <div className="flex flex-wrap items-center gap-3 p-6 bg-slate-950/40 rounded-3xl border border-white/5 overflow-x-auto">
              {selectedRun?.tasks?.length === 0 ? (
                <p className="text-xs font-bold text-slate-500 mx-auto">No task references loaded for this PipelineRun.</p>
              ) : selectedRun?.tasks?.map((task, idx) => (
                <React.Fragment key={task.name}>
                  <div className="flex items-center gap-2 px-4 py-3 bg-white/5 border border-white/10 rounded-2xl">
                    <div className="shrink-0">{getStatusIcon(task.status)}</div>
                    <span className="text-xs font-bold text-slate-300 font-mono">{task.name}</span>
                  </div>
                  {idx < selectedRun.tasks.length - 1 && (
                    <ArrowRight size={14} className="text-slate-600 shrink-0" />
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>

          {/* Bottom Panel: Live Terminal Logs */}
          <div className="flex-1 bg-black rounded-[2.5rem] border border-white/10 flex flex-col overflow-hidden shadow-2xl relative min-h-0">
            <div className="px-6 py-4 bg-[#090e1d] border-b border-white/10 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2">
                <Terminal size={14} className="text-cyan-400" />
                <h4 className="text-[10px] font-black text-slate-300 tracking-wider uppercase font-mono">Console Logs: {selectedRun?.name}</h4>
              </div>
              <span className="text-[9px] font-bold text-slate-500 font-mono">STDOUT / STDERR</span>
            </div>
            
            <div className="flex-1 p-6 overflow-y-auto font-mono text-xs leading-relaxed text-slate-400 space-y-2 custom-scrollbar bg-black/90">
              {selectedRun?.logs?.map((log, index) => {
                const color = log.includes('SUCCEEDED') || log.includes('passed') || log.includes('success')
                  ? 'text-emerald-400' 
                  : log.includes('MAKE') || log.includes('WAIT') || log.includes('STEER') || log.includes('BREAK')
                  ? 'text-indigo-400 font-black'
                  : log.includes('injected') || log.includes('P4')
                  ? 'text-cyan-400'
                  : 'text-slate-400';
                return (
                  <div key={index} className={`py-0.5 border-b border-white/5 pb-1 ${color}`}>
                    {log}
                  </div>
                );
              })}
              <div ref={logEndRef} />
            </div>
          </div>

        </div>

      </div>
    </div>
  );
};

export default TektonDashboard;
