import React, { useState, useRef, useCallback, useEffect } from 'react';
import { AnimatePresence } from 'framer-motion';
import { ZoomIn, ZoomOut } from 'lucide-react';

// --- Sub-components ---
import Edge from '../components/topology/Edge';
import { BackboneNode, VNFNode } from '../components/topology/Nodes';
import Packet from '../components/topology/Packet';
import ControlHeader from '../components/topology/ControlHeader';
import Sidebar from '../components/topology/Sidebar';
import ProvisionModal from '../components/topology/ProvisionModal';
import TelemetryPanel from '../components/topology/TelemetryPanel';
import { vnfService } from '../services/api';

// --- Testbed DCs: khớp với label core-router/location trong K8s ---
const DCS = {
  'hanoi-1':  { id:'hanoi-1',  name:'Hanoi Edge DC',       x:400,  y:300, w:660, h:360, color:'#f43f5e', icon:'🏹️' },
  'danang-1': { id:'danang-1', name:'Da Nang Core DC',      x:1570, y:300, w:660, h:360, color:'#8b5cf6', icon:'🌉' },
  'hcm-1':    { id:'hcm-1',    name:'Ho Chi Minh Edge DC',  x:2740, y:300, w:660, h:360, color:'#6366f1', icon:'🌇' },
};

const INIT_BACKBONE = {
  s1: { x: 1100, y: 1250, label: 'Ingress S1', sub: 'MSD = 3', icon: '⚡', color: '#f59e0b' },
  s2: { x: 1900, y: 1250, label: 'Core S2',    sub: 'MSD = 6', icon: '⚙️', color: '#8b5cf6' },
  s3: { x: 2700, y: 1250, label: 'Egress S3',  sub: 'MSD = 3', icon: '⚡', color: '#f59e0b' },
};

const MSD = { s1: 3, s2: 6 };

const TRAFFIC_POLICY = {
  clean: { roles: [] },
  suspicious: { roles: ['firewall'] },
  corporate: { roles: ['idps'] },
  ddos: { roles: ['firewall', 'idps'] },
  deep_inspect: { roles: ['firewall', 'idps', 'router'] }
};

const SID_MAP = {
  firewall: '2001:db8:FW::1',
  idps: '2001:db8:IDPS::2',
  router: '2001:db8:VR::3',
};

const REQUEST_PROFILES = {
  clean:        { cpu_req: 4,  ram_req: 2,  msd_req: 1, service_type: 'Data',   alert_flag: false },
  suspicious:   { cpu_req: 12, ram_req: 6,  msd_req: 2, service_type: 'Data',   alert_flag: false },
  corporate:    { cpu_req: 16, ram_req: 8,  msd_req: 2, service_type: 'VoIP',   alert_flag: false },
  ddos:         { cpu_req: 70, ram_req: 35, msd_req: 4, service_type: 'Attack', alert_flag: true },
  deep_inspect: { cpu_req: 35, ram_req: 18, msd_req: 5, service_type: 'Video',  alert_flag: false }
};

export default function Topology({ vnfs, onDeploy, onDelete }) {
  // State
  const [nodePos, setNodePos] = useState({ ...INIT_BACKBONE });
  const [vp, setVp] = useState({ x: 0, y: 0, scale: 0.35 });
  const [packets, setPackets] = useState([]);
  const [logs, setLogs] = useState([
    { id: 0, msg: '> System Ready. Code Refactor Complete.', color: '#34d399' },
    { id: 1, msg: '> AI Multi-Node Orchestrator Standby.', color: '#a78bfa' },
  ]);
  const [encapsulator, setEncapsulator] = useState(null);
  const [isBuffering, setIsBuffering] = useState(false);
  const [simVnfs, setSimVnfs] = useState([]);
  const [isTelemetryOpen, setIsTelemetryOpen] = useState(true);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [hybridStatus, setHybridStatus] = useState({
    branch: 'heuristic',
    method: 'Decoupled Heuristic',
    globalUtilization: 0,
    avgCpu: 0,
    avgMsdUsage: 0,
    alertFlag: false
  });

  // Constants / Refs
  const vnfLocMemo = useRef({});
  const rrTrackers = useRef({});
  const autoDeployedIds = useRef(new Set());
  const logId = useRef(2);
  const logEndRef = useRef(null);
  const svgRef = useRef(null);
  const dragRef = useRef(null);
  const panRef = useRef(null);

  // Form
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState({ name: 'vnf-node-1', type: 'firewall', profile: 'standard', location: 'auto' });
  const [srcDc, setSrcDc] = useState('hanoi-1');
  const [dstDc, setDstDc] = useState('hcm-1');
  const [trafficOpt, setTrafficOpt] = useState('clean');

  const activeVnfs = [...(vnfs?.nodes || []), ...simVnfs];

  // Sync Locations
  useEffect(() => {
    vnfs?.nodes?.forEach(v => {
      if (v.data?.location) vnfLocMemo.current[v.id] = v.data.location;
    });
  }, [vnfs]);

  // Viewport Init
  useEffect(() => {
    if (!svgRef.current) return;
    const r = svgRef.current.getBoundingClientRect();
    const sc = 0.38;
    setVp({ x: r.width / 2 - 1900 * sc, y: r.height / 2 - 1250 * sc, scale: sc });
  }, []);

  const pushLog = useCallback((msg, color = '#94a3b8') => {
    setLogs(p => [...p.slice(-80), { id: logId.current++, msg, color }]);
  }, []);
  useEffect(() => { logEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [logs]);

  // Derived Values
  const getGroupedVnfs = useCallback(() => {
    const g = {}; Object.keys(DCS).forEach(k => g[k] = []);
    activeVnfs.forEach(v => {
      let loc = v.data?.location || vnfLocMemo.current[v.id];
      if (!loc || loc === 'auto') {
        const h = v.id.split('').reduce((a, b) => a + b.charCodeAt(0), 0);
        loc = Object.keys(DCS)[h % Object.keys(DCS).length];
        vnfLocMemo.current[v.id] = loc;
      }
      if (g[loc]) g[loc].push(v);
    });
    return g;
  }, [activeVnfs]);

  const grouped = getGroupedVnfs();

  const getVnfPos = useCallback((vid) => {
    const loc = vnfLocMemo.current[vid] || 'hanoi-1';
    const dc = DCS[loc] || DCS['hanoi-1'];
    const list = grouped[loc];
    if (!list) return { x: dc.x + dc.w / 2, y: dc.y + dc.h / 2 };
    const idx = list.findIndex(v => v.id === vid);
    if (idx === -1) return { x: dc.x + dc.w / 2, y: dc.y + dc.h / 2 };
    const maxCols = 3, cellW = 180, cellH = 150;
    const c = idx % maxCols, r = Math.floor(idx / maxCols);
    const padX = (dc.w - (Math.min(list.length, maxCols) - 1) * cellW) / 2;
    return { x: dc.x + padX + c * cellW, y: dc.y + 110 + r * cellH };
  }, [grouped]);

  const userNodes = {
    h1: { x: DCS[srcDc].x - 100, y: DCS[srcDc].y - 120, label: `SOURCE (${srcDc.toUpperCase()})`, icon: '📡', color: '#8b5cf6', fixed: true },
    dest: { x: DCS[dstDc].x - 100, y: DCS[dstDc].y - 120, label: `TARGET (${dstDc.toUpperCase()})`, icon: '📡', color: '#10b981', fixed: true }
  };

  // Optimization Logic
  const handleOptimize = useCallback(async () => {
    if (isBuffering) return;
    const policy = TRAFFIC_POLICY[trafficOpt];
    pushLog(`> Flow Optimization: ${srcDc.toUpperCase()} → ${dstDc.toUpperCase()}`, '#facc15');

    const profile = REQUEST_PROFILES[trafficOpt] || REQUEST_PROFILES.clean;
    try {
      const decision = await vnfService.orchestrateSfc({
        ...profile,
        msd_req: Math.max(profile.msd_req, policy.roles.length || 1),
        is_ddos_spike: trafficOpt === 'ddos',
        source_node: srcDc,
        destination_node: dstDc,
      });
      const data = decision.data || {};
      const nextStatus = {
        branch: data.hybrid_branch || 'heuristic',
        method: data.method_used || decision.method_used || 'Decoupled Heuristic',
        globalUtilization: data.global_utilization || 0,
        avgCpu: data.avg_cpu || 0,
        avgMsdUsage: data.avg_msd_usage || 0,
        alertFlag: Boolean(data.alert_flag)
      };
      setHybridStatus(nextStatus);
      pushLog(
        `> Hybrid Gate: ${nextStatus.method} | U=${Math.round(nextStatus.globalUtilization * 100)}%`,
        nextStatus.branch === 'drl' ? '#f87171' : '#34d399'
      );
    } catch (e) {
      const detail = e.response?.data?.detail;
      const msg = detail?.message || detail || e.message;
      pushLog(`> Hybrid API unavailable: ${msg}`, '#f97316');
    }

    const C_INST = 5000, W_PENALTY = 1200;
    let matchedInstances = [], requiredScaleOuts = [];

    for (const role of policy.roles) {
      const candidates = activeVnfs.filter(v => v.data?.role === role);
      let bestChoice = null, minCost = Infinity;

      candidates.forEach(v => {
        const loc = vnfLocMemo.current[v.id] || 'paris';
        const dist = Math.hypot(DCS[loc].x - DCS[srcDc].x, DCS[loc].y - DCS[srcDc].y);
        const load = rrTrackers.current[v.id] || 0;
        const cost = dist * 1.2 + load * W_PENALTY;
        if (cost < minCost) { minCost = cost; bestChoice = v; }
      });

      if (!bestChoice || minCost > C_INST) {
        const vId = `ai-scaled-${role}-${Math.floor(Math.random() * 1000)}`;
        vnfLocMemo.current[vId] = srcDc;
        requiredScaleOuts.push({ id: vId, role, loc: srcDc });
        matchedInstances.push({ id: vId, data: { role, status: 'Pending' } });
        pushLog(`> Trade-off decision: Instantiate new node (Cost ${Math.round(minCost)})`, '#c084fc');
      } else {
        matchedInstances.push(bestChoice);
        rrTrackers.current[bestChoice.id] = (rrTrackers.current[bestChoice.id] || 0) + 1;
        setTimeout(() => { if (rrTrackers.current[bestChoice.id]) rrTrackers.current[bestChoice.id]--; }, 8000);
      }
    }

    if (requiredScaleOuts.length > 0) {
      setIsBuffering(true);
      setSimVnfs(s => [...s, ...requiredScaleOuts.map(r => ({ id: r.id, data: { role: r.role, status: 'Pending', location: r.loc } }))]);
      await new Promise(r => setTimeout(r, 2000));
      requiredScaleOuts.forEach(r => {
        autoDeployedIds.current.add(r.id);
        onDeploy({ name: r.id, type: r.role, location: r.loc, profile: 'performance' });
      });
      setSimVnfs(s => s.map(v => requiredScaleOuts.find(r => r.id === v.id) ? { ...v, data: { ...v.data, status: 'Running' } } : v));
      setIsBuffering(false);
    }

    const posArr = matchedInstances.map(v => getVnfPos(v.id));
    const totalSids = matchedInstances.length + 1;
    const violation = totalSids > MSD.s2;
    let path = [userNodes.h1], enc = null;

    if (violation) {
      path.push(nodePos.s1, { x: nodePos.s1.x + 100, y: nodePos.s1.y - 100 });
      pushLog(`> Violation: Chain depth ${totalSids} rejected.`, '#ef4444');
    } else {
      if (totalSids === 1) path.push(nodePos.s1, nodePos.s2, nodePos.s3, userNodes.dest);
      else if (totalSids <= MSD.s1) { enc = 's1'; path.push(nodePos.s1, ...posArr, nodePos.s3, userNodes.dest); }
      else { enc = 's2'; path.push(nodePos.s1, nodePos.s2, ...posArr, nodePos.s3, userNodes.dest); }
    }
    setEncapsulator(enc);
    setPackets(p => [...p, { id: `pkt-${Date.now()}`, waypoints: path, ptype: violation ? 'msd_drop' : 'normal', sids: matchedInstances.map(v => SID_MAP[v.data.role]), encapsulator: enc }]);
  }, [activeVnfs, nodePos, trafficOpt, srcDc, dstDc, getVnfPos, onDeploy, isBuffering, pushLog]);

  // Event Handlers
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const handleW = e => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      const cx = e.clientX - r.left, cy = e.clientY - r.top, f = e.deltaY < 0 ? 1.1 : 0.9;
      setVp(v => {
        const ns = Math.min(2.5, Math.max(0.1, v.scale * f));
        return { scale: ns, x: cx - (cx - v.x) * (ns / v.scale), y: cy - (cy - v.y) * (ns / v.scale) };
      });
    };
    el.addEventListener('wheel', handleW, { passive: false });
    return () => el.removeEventListener('wheel', handleW);
  }, []);

  const svgXY = e => {
    const r = svgRef.current.getBoundingClientRect();
    return { x: (e.clientX - r.left - vp.x) / vp.scale, y: (e.clientY - r.top - vp.y) / vp.scale };
  };
  const onMouseMove = e => {
    if (dragRef.current) {
      const c = svgXY(e);
      setNodePos(p => ({ ...p, [dragRef.current.nodeId]: { ...p[dragRef.current.nodeId], x: dragRef.current.ox + (c.x - dragRef.current.sx), y: dragRef.current.oy + (c.y - dragRef.current.sy) } }));
    } else if (panRef.current) {
      const p = panRef.current;
      setVp(v => ({ ...v, x: p.ox + (e.clientX - p.sx), y: p.oy + (e.clientY - p.sy) }));
    }
  };
  const onNodeDragStart = (e, id) => {
    e.stopPropagation(); dragRef.current = { nodeId: id, sx: svgXY(e).x, sy: svgXY(e).y, ox: nodePos[id].x, oy: nodePos[id].y };
  };
  const onCanvasDragStart = e => { panRef.current = { sx: e.clientX, sy: e.clientY, ox: vp.x, oy: vp.y }; };
  const onMouseUp = () => { dragRef.current = null; panRef.current = null; };

  return (
    <div className="flex flex-col w-full h-full bg-[#020617] text-white overflow-hidden select-none font-sans">
      <ControlHeader 
        srcDc={srcDc} setSrcDc={setSrcDc} 
        dstDc={dstDc} setDstDc={setDstDc} 
        trafficOpt={trafficOpt} setTrafficOpt={setTrafficOpt}
        onOptimize={handleOptimize} isBuffering={isBuffering}
        onOpenModal={() => setIsModalOpen(true)}
        activeVnfCount={activeVnfs.length}
        dcs={DCS} trafficPolicies={TRAFFIC_POLICY}
        hybridStatus={hybridStatus}
      />

      <div className="flex flex-1 min-h-0 relative">
        <div className="flex-1 overflow-hidden bg-[#020617] cursor-grab active:cursor-grabbing relative"
             onMouseMove={onMouseMove} onMouseUp={onMouseUp} onMouseLeave={onMouseUp}>
          
          <TelemetryPanel isOpen={isTelemetryOpen} setIsOpen={setIsTelemetryOpen} hybridStatus={hybridStatus} />

          <svg ref={svgRef} width="100%" height="100%" onMouseDown={onCanvasDragStart}>
            <defs>
              <marker id="arr" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="#475569"/></marker>
              <pattern id="grid" width="120" height="120" patternUnits="userSpaceOnUse"><path d="M 120 0 L 0 0 0 120" fill="none" stroke="#1e293b" strokeWidth="1" opacity="0.4"/></pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />
            <g transform={`translate(${vp.x},${vp.y}) scale(${vp.scale})`}>
              {Object.values(DCS).map(dc => (
                <g key={dc.id} transform={`translate(${dc.x},${dc.y})`}>
                  <rect width={dc.w} height={dc.h} rx={32} fill="rgb(15 23 42 / 0.4)" stroke={dc.color} strokeWidth={2.5} strokeDasharray="12,12" opacity={0.6}/>
                  <text x={25} y={35} fill={dc.color} fontSize={28} fontWeight="900" opacity={0.9}>{dc.name.split(' ')[0].toUpperCase()}</text>
                  <text x={25} y={60} fill="#64748b" fontSize={14} fontWeight="700" opacity={0.7}>{dc.name.split(' ').slice(1).join(' ')}</text>
                </g>
              ))}
              <Edge ax={userNodes.h1.x} ay={userNodes.h1.y} bx={nodePos.s1.x} by={nodePos.s1.y} dash="14,14" />
              <Edge ax={nodePos.s1.x} ay={nodePos.s1.y} bx={nodePos.s2.x} by={nodePos.s2.y} dash="14,14" />
              <Edge ax={nodePos.s2.x} ay={nodePos.s2.y} bx={nodePos.s3.x} by={nodePos.s3.y} dash="14,14" />
              <Edge ax={nodePos.s3.x} ay={nodePos.s3.y} bx={userNodes.dest.x} by={userNodes.dest.y} dash="14,14" />
              
              {activeVnfs.map(v => {
                const pos = getVnfPos(v.id), srcNode = nodePos[encapsulator] || nodePos.s2;
                return (
                  <g key={`l-${v.id}`}>
                    <Edge ax={srcNode.x} ay={srcNode.y} bx={pos.x} by={pos.y} color="#f59e0b" dash="12,6" />
                    <Edge ax={pos.x} ay={pos.y} bx={nodePos.s3.x} by={nodePos.s3.y} color="#10b981" dash="12,6" />
                  </g>
                );
              })}
              
              {Object.entries(nodePos).map(([id, n]) => <BackboneNode key={id} n={n} active={id === encapsulator} onDragStart={e => onNodeDragStart(e, id)} />)}
              <BackboneNode key="h1" n={userNodes.h1} />
              <BackboneNode key="dest" n={userNodes.dest} />
              {activeVnfs.map(v => <VNFNode key={v.id} id={v.id} role={v.data?.role || 'router'} status={v.data?.status || 'Pending'} x={getVnfPos(v.id).x} y={getVnfPos(v.id).y} autoDeployed={autoDeployedIds.current.has(v.id)} onDelete={id => { setSimVnfs(s => s.filter(x => x.id !== id)); autoDeployedIds.current.delete(id); onDelete(id); }} />)}
              {packets.map(p => <Packet key={p.id} {...p} onDone={id => setPackets(q => q.filter(x => x.id !== id))} />)}
            </g>
          </svg>
        </div>

        <Sidebar 
          isOpen={isSidebarOpen} setIsOpen={setIsSidebarOpen}
          activeVnfs={activeVnfs} vnfLocMemo={vnfLocMemo} rrTrackers={rrTrackers}
          logs={logs} logEndRef={logEndRef}
        />
      </div>

      <AnimatePresence>
        <ProvisionModal 
          isOpen={isModalOpen} onClose={() => setIsModalOpen(false)}
          formData={formData} setFormData={setFormData}
          dcs={DCS}
          onSubmit={e => {
            e.preventDefault();
            const loc = formData.location === 'auto' ? 'hn' : formData.location;
            vnfLocMemo.current[formData.name] = loc;
            pushLog(`> Initiating deployment of ${formData.type.toUpperCase()} at ${loc.toUpperCase()}...`, '#a78bfa');
            onDeploy(formData); setIsModalOpen(false);
          }}
        />
      </AnimatePresence>

      <div className="absolute bottom-5 right-[440px] z-10 flex gap-2">
         <button onClick={()=>setVp(v=>({...v,scale:Math.min(2.5,v.scale*1.2)}))} className="w-10 h-10 bg-slate-800/80 rounded-xl flex items-center justify-center border border-white/10"><ZoomIn size={16}/></button>
         <button onClick={()=>setVp(v=>({...v,scale:Math.max(0.1,v.scale/1.2)}))} className="w-10 h-10 bg-slate-800/80 rounded-xl flex items-center justify-center border border-white/10"><ZoomOut size={16}/></button>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        .custom-scrollbar::-webkit-scrollbar { width: 3px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.05); border-radius: 10px; }
        .glass-btn { position: relative; background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(10px); }
      `}} />
    </div>
  );
}
