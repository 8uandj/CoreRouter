import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { AnimatePresence } from 'framer-motion';
import { ZoomIn, ZoomOut } from 'lucide-react';

import Edge from '../components/topology/Edge';
import { BackboneNode, VNFNode } from '../components/topology/Nodes';
import Packet from '../components/topology/Packet';
import ControlHeader from '../components/topology/ControlHeader';
import Sidebar from '../components/topology/Sidebar';
import ProvisionModal from '../components/topology/ProvisionModal';
import TelemetryPanel from '../components/topology/TelemetryPanel';
import { vnfService } from '../services/api';

const VIETNAM_NODES = [
  { id: 0, switch: 's1', host: 'h1', name: 'Hanoi', label: 'Hanoi', role: 'core', msd: 10, lat: 21.0285, lon: 105.8542, k8sHostname: 'k8s-master', location: 'hn', x: 900, y: 300, color: '#22c55e' },
  { id: 1, switch: 's2', host: 'h2', name: 'HaiPhong', label: 'Hai Phong', role: 'core', msd: 10, lat: 20.8449, lon: 106.6881, k8sHostname: 'k8s-master', location: 'hp', x: 1700, y: 760, color: '#22c55e' },
  { id: 2, switch: 's3', host: 'h3', name: 'NinhBinh', label: 'Ninh Binh', role: 'edge', msd: 5, lat: 20.2541, lon: 105.9750, k8sHostname: 'k8s-master', location: 'nb', x: 940, y: 1220, color: '#38bdf8' },
  { id: 3, switch: 's4', host: 'h4', name: 'Vinh', label: 'Vinh', role: 'edge', msd: 5, lat: 18.6796, lon: 105.6813, k8sHostname: 'worker1', location: 'vinh', x: 1240, y: 1680, color: '#38bdf8' },
  { id: 4, switch: 's5', host: 'h5', name: 'Hue', label: 'Hue', role: 'edge', msd: 4, lat: 16.4637, lon: 107.5909, k8sHostname: 'worker1', location: 'hue', x: 1650, y: 2140, color: '#f59e0b' },
  { id: 5, switch: 's6', host: 'h6', name: 'DaNang', label: 'Da Nang', role: 'core', msd: 8, lat: 16.0544, lon: 108.2022, k8sHostname: 'worker1', location: 'dn', x: 2320, y: 2140, color: '#a78bfa' },
  { id: 6, switch: 's7', host: 'h7', name: 'QuyNhon', label: 'Quy Nhon', role: 'edge', msd: 4, lat: 13.7830, lon: 109.2196, k8sHostname: 'worker2', location: 'qn', x: 2630, y: 2600, color: '#f59e0b' },
  { id: 7, switch: 's8', host: 'h8', name: 'NhaTrang', label: 'Nha Trang', role: 'edge', msd: 5, lat: 12.2388, lon: 109.1967, k8sHostname: 'worker2', location: 'nt', x: 2300, y: 3060, color: '#38bdf8' },
  { id: 8, switch: 's9', host: 'h9', name: 'HoChiMinh', label: 'Ho Chi Minh', role: 'core', msd: 10, lat: 10.8231, lon: 106.6297, k8sHostname: 'worker2', location: 'hcm', x: 1700, y: 3520, color: '#22c55e' },
  { id: 9, switch: 's10', host: 'h10', name: 'CanTho', label: 'Can Tho', role: 'edge', msd: 5, lat: 10.0452, lon: 105.7469, k8sHostname: 'worker2', location: 'ct', x: 1050, y: 3980, color: '#38bdf8' },
];

const DC_WIDTH = 560;
const DC_HEIGHT = 380;
const SWITCH_W = 104;
const SWITCH_H = 48;

const BACKBONE = Object.fromEntries(
  VIETNAM_NODES.map(node => [
    node.switch,
    {
      ...node,
      sub: `${node.role.toUpperCase()} | MSD ${node.msd}`,
      icon: node.role === 'core' ? 'CORE' : 'EDGE',
    },
  ])
);

const BACKBONE_EDGES = [
  ['s1', 's2'], ['s1', 's3'], ['s3', 's4'], ['s4', 's5'],
  ['s5', 's6'], ['s6', 's7'], ['s7', 's8'], ['s8', 's9'],
  ['s9', 's10'], ['s1', 's6'], ['s6', 's9'],
];

const FAST_EDGES = new Set(['s1-s6', 's6-s9']);

const DEPLOY_LOCATIONS = {
  auto: { id: 'auto', name: 'Auto Scheduler' },
  hn: { id: 'hn', name: 'North Cluster (HN)' },
  dn: { id: 'dn', name: 'Central Cluster (DN)' },
  hcm: { id: 'hcm', name: 'South Cluster (HCM)' },
};

const CLUSTER_FALLBACK = { hn: 's1', dn: 's6', hcm: 's9' };

const TRAFFIC_POLICY = {
  clean: { label: 'Traffic Data', roles: [] },
  suspicious: { label: 'Data + Firewall', roles: ['firewall'] },
  corporate: { label: 'VoIP + IDPS', roles: ['idps'] },
  ddos: { label: 'Attack Mitigation', roles: ['firewall', 'idps'] },
  deep_inspect: { label: 'Video Deep Inspect', roles: ['firewall', 'idps', 'router'] },
};

const SID_MAP = {
  firewall: '2001:db8:FW::1',
  idps: '2001:db8:IDPS::2',
  router: '2001:db8:VR::3',
};

const REQUEST_PROFILES = {
  clean: { cpu_req: 4, ram_req: 2, msd_req: 1, service_type: 'Data', alert_flag: false },
  suspicious: { cpu_req: 12, ram_req: 6, msd_req: 2, service_type: 'Data', alert_flag: false },
  corporate: { cpu_req: 16, ram_req: 8, msd_req: 2, service_type: 'VoIP', alert_flag: false },
  ddos: { cpu_req: 70, ram_req: 35, msd_req: 4, service_type: 'Attack', alert_flag: true },
  deep_inspect: { cpu_req: 35, ram_req: 18, msd_req: 5, service_type: 'Video', alert_flag: false },
};

const normalizeLocation = value => String(value || '').trim().toLowerCase().replace(/[\s_-]+/g, '');
const hashToIndex = value => String(value).split('').reduce((sum, char) => sum + char.charCodeAt(0), 0) % VIETNAM_NODES.length;
const nodeBySwitch = switchId => VIETNAM_NODES.find(node => node.switch === switchId) || VIETNAM_NODES[0];
const edgeKey = (a, b) => `${a}-${b}`;
const dcIngressPoint = node => ({ x: node.x - DC_WIDTH / 2 + 86, y: node.y + 128 });
const dcEgressPoint = node => ({ x: node.x + DC_WIDTH / 2 - 86, y: node.y + 128 });

const expandSwitchPath = (switchIds, nodesBySwitch) => (
  switchIds.flatMap(switchId => {
    const node = nodesBySwitch[switchId];
    return node ? [dcIngressPoint(node), dcEgressPoint(node)] : [];
  })
);

const resolveLocationSwitch = (location, fallbackId = '') => {
  const normalized = normalizeLocation(location);
  if (!normalized || normalized === 'auto') {
    return VIETNAM_NODES[hashToIndex(fallbackId)].switch;
  }

  if (CLUSTER_FALLBACK[normalized]) return CLUSTER_FALLBACK[normalized];

  const exact = VIETNAM_NODES.find(node => (
    normalizeLocation(node.switch) === normalized
    || normalizeLocation(node.host) === normalized
    || normalizeLocation(node.name) === normalized
    || normalizeLocation(node.label) === normalized
    || normalizeLocation(node.location) === normalized
  ));
  return exact?.switch || VIETNAM_NODES[hashToIndex(fallbackId || normalized)].switch;
};

const directPath = (srcSwitch, dstSwitch) => {
  if (srcSwitch === dstSwitch) return [srcSwitch];
  if (srcSwitch === 's1' && dstSwitch === 's9') return ['s1', 's6', 's9'];
  if (srcSwitch === 's9' && dstSwitch === 's1') return ['s9', 's6', 's1'];

  const adjacency = BACKBONE_EDGES.reduce((acc, [a, b]) => {
    acc[a] = [...(acc[a] || []), b];
    acc[b] = [...(acc[b] || []), a];
    return acc;
  }, {});
  const queue = [[srcSwitch]];
  const seen = new Set([srcSwitch]);
  while (queue.length > 0) {
    const path = queue.shift();
    const last = path[path.length - 1];
    for (const next of adjacency[last] || []) {
      if (seen.has(next)) continue;
      const nextPath = [...path, next];
      if (next === dstSwitch) return nextPath;
      seen.add(next);
      queue.push(nextPath);
    }
  }
  return [srcSwitch, dstSwitch];
};

export default function Topology({ vnfs, onDeploy, onDelete }) {
  const [nodePos, setNodePos] = useState({ ...BACKBONE });
  const [vp, setVp] = useState({ x: 0, y: 0, scale: 0.35 });
  const [packets, setPackets] = useState([]);
  const [routeTrace, setRouteTrace] = useState([]);
  const [logs, setLogs] = useState([
    { id: 0, msg: '> Vietnam 10-node Backbone ready.', color: '#34d399' },
    { id: 1, msg: '> Hybrid JO-VPPM telemetry standby.', color: '#a78bfa' },
  ]);
  const [encapsulator, setEncapsulator] = useState(null);
  const [isBuffering, setIsBuffering] = useState(false);
  const [simVnfs, setSimVnfs] = useState([]);
  const [isTelemetryOpen, setIsTelemetryOpen] = useState(true);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [hybridStatus, setHybridStatus] = useState({
    branch: 'heuristic',
    method: 'Hybrid:Heuristic',
    globalUtilization: 0,
    avgCpu: 0,
    avgMsdUsage: 0,
    alertFlag: false,
    nodes: [],
  });

  const vnfLocMemo = useRef({});
  const [vnfLocations, setVnfLocations] = useState({});
  const rrTrackers = useRef({});
  const [autoDeployedIds, setAutoDeployedIds] = useState(new Set());
  const logId = useRef(2);
  const logEndRef = useRef(null);
  const svgRef = useRef(null);
  const dragRef = useRef(null);
  const panRef = useRef(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState({ name: 'vnf-node-1', type: 'firewall', profile: 'standard', location: 'auto' });
  const [srcDc, setSrcDc] = useState('s1');
  const [dstDc, setDstDc] = useState('s9');
  const [trafficOpt, setTrafficOpt] = useState('clean');

  const activeVnfs = useMemo(() => [...(vnfs?.nodes || []), ...simVnfs], [simVnfs, vnfs]);
  const sidebarVnfLocMemo = useMemo(() => ({ current: vnfLocations }), [vnfLocations]);

  const rememberVnfLocation = useCallback((id, location) => {
    vnfLocMemo.current[id] = location;
    setVnfLocations(prev => ({ ...prev, [id]: location }));
  }, []);

  const pushLog = useCallback((msg, color = '#94a3b8') => {
    setLogs(prev => [...prev.slice(-80), { id: logId.current++, msg, color }]);
  }, []);

  useEffect(() => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const scale = rect.width < 900 ? 0.16 : 0.24;
    setVp({ x: rect.width / 2 - 1750 * scale, y: rect.height / 2 - 2180 * scale, scale });
  }, []);

  useEffect(() => { logEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [logs]);

  useEffect(() => {
    let mounted = true;
    const syncHybridState = async () => {
      try {
        const response = await vnfService.getHybridState();
        const data = response.data || response;
        if (!mounted) return;
        setHybridStatus(prev => ({
          ...prev,
          branch: data.mode || prev.branch,
          method: data.mode === 'drl' ? 'Hybrid:DRL' : 'Hybrid:Heuristic',
          globalUtilization: data.global_utilization ?? prev.globalUtilization,
          avgCpu: data.avg_cpu ?? prev.avgCpu,
          avgMsdUsage: data.avg_msd_usage ?? prev.avgMsdUsage,
          alertFlag: Boolean(data.alert_flag),
          nodes: data.nodes || [],
        }));
      } catch {
        // Dashboard remains usable as a topology demo when backend is offline.
      }
    };
    syncHybridState();
    const timer = setInterval(syncHybridState, 5000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  const getGroupedVnfs = useCallback(() => {
    const groups = Object.fromEntries(VIETNAM_NODES.map(node => [node.switch, []]));
    activeVnfs.forEach(v => {
      const loc = v.data?.location || vnfLocations[v.id] || 'auto';
      const switchId = resolveLocationSwitch(loc, v.id);
      groups[switchId]?.push(v);
    });
    return groups;
  }, [activeVnfs, vnfLocations]);

  const grouped = getGroupedVnfs();

  const getVnfPos = useCallback((vid) => {
    const switchId = resolveLocationSwitch(vnfLocations[vid], vid);
    const node = nodePos[switchId] || nodePos.s1;
    const list = grouped[switchId] || [];
    const idx = Math.max(0, list.findIndex(v => v.id === vid));
    const cols = 4;
    const col = idx % cols;
    const row = Math.floor(idx / cols);
    const cellW = 112;
    const cellH = 92;
    return {
      x: node.x - 168 + col * cellW,
      y: node.y - 48 + row * cellH,
    };
  }, [grouped, nodePos, vnfLocations]);

  const sourceNode = nodeBySwitch(srcDc);
  const targetNode = nodeBySwitch(dstDc);
  const userNodes = useMemo(() => ({
    src: { x: nodePos[srcDc].x - DC_WIDTH / 2 - 150, y: nodePos[srcDc].y + 128, label: `SRC ${sourceNode.host.toUpperCase()}`, sub: sourceNode.label, icon: 'SRC', color: '#f43f5e', fixed: true },
    dest: { x: nodePos[dstDc].x + DC_WIDTH / 2 + 150, y: nodePos[dstDc].y + 128, label: `DST ${targetNode.host.toUpperCase()}`, sub: targetNode.label, icon: 'DST', color: '#10b981', fixed: true },
  }), [dstDc, nodePos, sourceNode.host, sourceNode.label, srcDc, targetNode.host, targetNode.label]);
  const previewRouteTrace = useMemo(() => [
    userNodes.src,
    ...expandSwitchPath(directPath(srcDc, dstDc), nodePos),
    userNodes.dest,
  ], [dstDc, nodePos, srcDc, userNodes]);
  const displayRouteTrace = routeTrace.length > 1 ? routeTrace : previewRouteTrace;

  const handleOptimize = useCallback(async () => {
    if (isBuffering) return;

    const policy = TRAFFIC_POLICY[trafficOpt];
    const profile = REQUEST_PROFILES[trafficOpt] || REQUEST_PROFILES.clean;
    const srcNode = nodeBySwitch(srcDc);
    const dstNode = nodeBySwitch(dstDc);
    pushLog(`> Flow Optimization: ${srcNode.label} -> ${dstNode.label}`, '#facc15');

    let placementSwitch = srcDc;
    let routeSwitch = dstDc;
    let sidStack = [];

    try {
      const decision = await vnfService.orchestrateSfc({
        ...profile,
        msd_req: Math.max(profile.msd_req, policy.roles.length || 1),
        is_ddos_spike: trafficOpt === 'ddos',
        source_node: srcNode.id,
        destination_node: dstNode.id,
      });
      const data = decision.data || decision;
      placementSwitch = VIETNAM_NODES[data.placement_node?.id]?.switch || placementSwitch;
      routeSwitch = VIETNAM_NODES[data.routing_node?.id]?.switch || routeSwitch;
      sidStack = data.srv6_segment_list || [];
      const nextStatus = {
        branch: data.hybrid_branch || 'heuristic',
        method: data.method_used || 'Hybrid:Heuristic',
        globalUtilization: data.global_utilization ?? hybridStatus.globalUtilization,
        avgCpu: data.avg_cpu ?? hybridStatus.avgCpu,
        avgMsdUsage: data.avg_msd_usage ?? hybridStatus.avgMsdUsage,
        alertFlag: Boolean(data.alert_flag),
        nodes: data.state?.nodes || hybridStatus.nodes,
      };
      setHybridStatus(nextStatus);
      pushLog(
        `> Hybrid Gate: ${nextStatus.method} | U=${Math.round(nextStatus.globalUtilization * 100)}%`,
        nextStatus.branch === 'drl' ? '#f87171' : '#34d399'
      );
      if (data.migration_result?.status) {
        pushLog(`> MBB migration: ${data.migration_result.status}`, '#a78bfa');
      }
    } catch (e) {
      const detail = e.response?.data?.detail;
      const msg = detail?.message || detail || e.message;
      pushLog(`> Hybrid API unavailable: ${msg}`, '#f97316');
    }

    const matchedInstances = [];
    const requiredScaleOuts = [];
    const C_INST = 5000;
    const W_PENALTY = 1200;

    for (const role of policy.roles) {
      const candidates = activeVnfs.filter(v => v.data?.role === role);
      let bestChoice = null;
      let minCost = Infinity;

      candidates.forEach(v => {
        const switchId = resolveLocationSwitch(vnfLocations[v.id] || v.data?.location, v.id);
        const dist = Math.hypot(nodePos[switchId].x - nodePos[placementSwitch].x, nodePos[switchId].y - nodePos[placementSwitch].y);
        const load = rrTrackers.current[v.id] || 0;
        const cost = dist * 1.2 + load * W_PENALTY;
        if (cost < minCost) {
          minCost = cost;
          bestChoice = v;
        }
      });

      if (!bestChoice || minCost > C_INST) {
        const vId = `ai-scaled-${role}-${Math.floor(Math.random() * 1000)}`;
        rememberVnfLocation(vId, placementSwitch);
        requiredScaleOuts.push({ id: vId, role, loc: placementSwitch });
        matchedInstances.push({ id: vId, data: { role, status: 'Pending' } });
        pushLog(`> Placement: instantiate ${role} near ${nodePos[placementSwitch].label}`, '#c084fc');
      } else {
        matchedInstances.push(bestChoice);
        rrTrackers.current[bestChoice.id] = (rrTrackers.current[bestChoice.id] || 0) + 1;
        setTimeout(() => { if (rrTrackers.current[bestChoice.id]) rrTrackers.current[bestChoice.id]--; }, 8000);
      }
    }

    if (requiredScaleOuts.length > 0) {
      setIsBuffering(true);
      setSimVnfs(prev => [
        ...prev,
        ...requiredScaleOuts.map(r => ({ id: r.id, data: { role: r.role, status: 'Pending', location: r.loc } })),
      ]);
      await new Promise(resolve => setTimeout(resolve, 1600));
      requiredScaleOuts.forEach(r => {
        setAutoDeployedIds(prev => new Set(prev).add(r.id));
        onDeploy({ name: r.id, type: r.role, location: nodePos[r.loc]?.location || 'auto', profile: 'performance' });
      });
      setSimVnfs(prev => prev.map(v => (
        requiredScaleOuts.find(r => r.id === v.id)
          ? { ...v, data: { ...v.data, status: 'Running' } }
          : v
      )));
      setIsBuffering(false);
    }

    const sourcePath = expandSwitchPath(directPath(srcDc, placementSwitch), nodePos);
    const targetPath = expandSwitchPath(directPath(routeSwitch, dstDc), nodePos);
    const placementNode = nodePos[placementSwitch] || nodePos[srcDc];
    const routeNode = nodePos[routeSwitch] || nodePos[dstDc];
    const vnfPositions = matchedInstances.map(v => getVnfPos(v.id));
    const totalSids = Math.max(sidStack.length, matchedInstances.length + 1);
    const msdLimit = Math.min(placementNode.msd, routeNode.msd);
    const violation = totalSids > msdLimit;

    let path = [userNodes.src, ...sourcePath];
    if (violation) {
      path.push({ x: placementNode.x + DC_WIDTH / 2 - 20, y: placementNode.y - 30 });
      pushLog(`> MSD violation rejected: SID depth ${totalSids} > MSD ${msdLimit}`, '#ef4444');
    } else {
      path = [
        ...path,
        ...vnfPositions,
        ...targetPath.slice(routeSwitch === placementSwitch ? 2 : 0),
        userNodes.dest,
      ];
      pushLog(`> SRv6 SID depth ${totalSids}/${msdLimit} accepted.`, '#38bdf8');
    }

    setRouteTrace(path);
    setEncapsulator(placementSwitch);
    setPackets(prev => [
      ...prev,
      {
        id: `pkt-${Date.now()}`,
        waypoints: path,
        ptype: violation ? 'msd_drop' : trafficOpt === 'ddos' ? 'attack' : 'normal',
        sids: sidStack.length ? sidStack : matchedInstances.map(v => SID_MAP[v.data.role]),
        encapsulator: placementSwitch,
      },
    ]);
  }, [activeVnfs, dstDc, getVnfPos, hybridStatus, isBuffering, nodePos, onDeploy, pushLog, rememberVnfLocation, srcDc, trafficOpt, userNodes, vnfLocations]);

  useEffect(() => {
    const el = svgRef.current;
    if (!el) return undefined;
    const handleWheel = e => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const cx = e.clientX - rect.left;
      const cy = e.clientY - rect.top;
      const factor = e.deltaY < 0 ? 1.1 : 0.9;
      setVp(v => {
        const nextScale = Math.min(2.5, Math.max(0.1, v.scale * factor));
        return { scale: nextScale, x: cx - (cx - v.x) * (nextScale / v.scale), y: cy - (cy - v.y) * (nextScale / v.scale) };
      });
    };
    el.addEventListener('wheel', handleWheel, { passive: false });
    return () => el.removeEventListener('wheel', handleWheel);
  }, []);

  const svgXY = e => {
    const rect = svgRef.current.getBoundingClientRect();
    return { x: (e.clientX - rect.left - vp.x) / vp.scale, y: (e.clientY - rect.top - vp.y) / vp.scale };
  };

  const onMouseMove = e => {
    if (dragRef.current) {
      const current = svgXY(e);
      setNodePos(prev => ({
        ...prev,
        [dragRef.current.nodeId]: {
          ...prev[dragRef.current.nodeId],
          x: dragRef.current.ox + (current.x - dragRef.current.sx),
          y: dragRef.current.oy + (current.y - dragRef.current.sy),
        },
      }));
    } else if (panRef.current) {
      const p = panRef.current;
      setVp(v => ({ ...v, x: p.ox + (e.clientX - p.sx), y: p.oy + (e.clientY - p.sy) }));
    }
  };
  const onNodeDragStart = (e, id) => {
    e.stopPropagation();
    dragRef.current = { nodeId: id, sx: svgXY(e).x, sy: svgXY(e).y, ox: nodePos[id].x, oy: nodePos[id].y };
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
        dcs={BACKBONE} trafficPolicies={TRAFFIC_POLICY}
        hybridStatus={hybridStatus}
      />

      <div className="flex flex-1 min-h-0 relative">
        <div
          className="flex-1 overflow-hidden bg-[#020617] cursor-grab active:cursor-grabbing relative"
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseUp}
        >
          <TelemetryPanel isOpen={isTelemetryOpen} setIsOpen={setIsTelemetryOpen} hybridStatus={hybridStatus} />

          <svg ref={svgRef} width="100%" height="100%" onMouseDown={onCanvasDragStart}>
            <defs>
              <marker id="arr" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                <polygon points="0 0,10 3.5,0 7" fill="#475569" />
              </marker>
              <pattern id="grid" width="120" height="120" patternUnits="userSpaceOnUse">
                <path d="M 120 0 L 0 0 0 120" fill="none" stroke="#1e293b" strokeWidth="1" opacity="0.4" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />
            <g transform={`translate(${vp.x},${vp.y}) scale(${vp.scale})`}>
              <text x={560} y={20} fill="#94a3b8" fontSize={34} fontWeight="900" letterSpacing={0}>
                Vietnam Backbone 10-node SRv6/P4 Testbed
              </text>
              <text x={560} y={62} fill="#475569" fontSize={16} fontWeight="700" letterSpacing={0}>
                S-shaped geographic layout | dashed amber path shows packet traversal
              </text>

              {BACKBONE_EDGES.map(([a, b]) => (
                <Edge
                  key={`${a}-${b}`}
                  ax={dcEgressPoint(nodePos[a]).x}
                  ay={dcEgressPoint(nodePos[a]).y}
                  bx={dcIngressPoint(nodePos[b]).x}
                  by={dcIngressPoint(nodePos[b]).y}
                  color={FAST_EDGES.has(edgeKey(a, b)) ? '#f59e0b' : '#334155'}
                  dash={FAST_EDGES.has(edgeKey(a, b)) ? '16,10' : null}
                  raA={20}
                  raB={20}
                />
              ))}

              <Edge ax={userNodes.src.x} ay={userNodes.src.y} bx={dcIngressPoint(nodePos[srcDc]).x} by={dcIngressPoint(nodePos[srcDc]).y} color="#f43f5e" dash="12,8" raA={20} raB={20} />
              <Edge ax={dcEgressPoint(nodePos[dstDc]).x} ay={dcEgressPoint(nodePos[dstDc]).y} bx={userNodes.dest.x} by={userNodes.dest.y} color="#10b981" dash="12,8" raA={20} raB={20} />

              {displayRouteTrace.slice(0, -1).map((point, idx) => {
                const next = displayRouteTrace[idx + 1];
                return (
                  <Edge
                    key={`trace-${idx}`}
                    ax={point.x}
                    ay={point.y}
                    bx={next.x}
                    by={next.y}
                    color="#facc15"
                    dash="22,14"
                    raA={14}
                    raB={14}
                    opacity={0.45}
                    strokeWidth={5}
                    showMarker={false}
                  />
                );
              })}

              {activeVnfs.map(v => {
                const pos = getVnfPos(v.id);
                const switchId = resolveLocationSwitch(vnfLocations[v.id] || v.data?.location, v.id);
                const srcNode = nodePos[switchId] || nodePos.s1;
                return (
                  <g key={`l-${v.id}`}>
                    <Edge ax={dcIngressPoint(srcNode).x} ay={dcIngressPoint(srcNode).y} bx={pos.x} by={pos.y} color="#06b6d4" dash="8,8" raA={18} raB={32} />
                    <Edge ax={pos.x} ay={pos.y} bx={dcEgressPoint(srcNode).x} by={dcEgressPoint(srcNode).y} color="#10b981" dash="8,8" raA={32} raB={18} />
                  </g>
                );
              })}

              {Object.entries(nodePos).map(([id, n]) => (
                <BackboneNode
                  key={id}
                  n={n}
                  active={id === encapsulator}
                  telemetry={hybridStatus.nodes?.[n.id]}
                  dcWidth={DC_WIDTH}
                  dcHeight={DC_HEIGHT}
                  switchWidth={SWITCH_W}
                  switchHeight={SWITCH_H}
                  onDragStart={e => onNodeDragStart(e, id)}
                />
              ))}
              <BackboneNode key="src" n={userNodes.src} />
              <BackboneNode key="dest" n={userNodes.dest} />
              {activeVnfs.map(v => (
                <VNFNode
                  key={v.id}
                  id={v.id}
                  role={v.data?.role || 'router'}
                  status={v.data?.status || 'Pending'}
                  x={getVnfPos(v.id).x}
                  y={getVnfPos(v.id).y}
                  size={30}
                  autoDeployed={autoDeployedIds.has(v.id)}
                  onDelete={id => {
                    setSimVnfs(prev => prev.filter(x => x.id !== id));
                    setAutoDeployedIds(prev => {
                      const next = new Set(prev);
                      next.delete(id);
                      return next;
                    });
                    onDelete(id);
                  }}
                />
              ))}
              {packets.map(p => <Packet key={p.id} {...p} onDone={id => setPackets(prev => prev.filter(x => x.id !== id))} />)}
            </g>
          </svg>
        </div>

        <Sidebar
          isOpen={isSidebarOpen} setIsOpen={setIsSidebarOpen}
          activeVnfs={activeVnfs} vnfLocMemo={sidebarVnfLocMemo} rrTrackers={rrTrackers}
          logs={logs} logEndRef={logEndRef}
        />
      </div>

      <AnimatePresence>
        <ProvisionModal
          isOpen={isModalOpen} onClose={() => setIsModalOpen(false)}
          formData={formData} setFormData={setFormData}
          dcs={DEPLOY_LOCATIONS}
          onSubmit={e => {
            e.preventDefault();
            const loc = formData.location || 'auto';
            rememberVnfLocation(formData.name, loc);
            pushLog(`> Initiating deployment of ${formData.type.toUpperCase()} at ${loc.toUpperCase()}...`, '#a78bfa');
            onDeploy(formData);
            setIsModalOpen(false);
          }}
        />
      </AnimatePresence>

      <div className="absolute bottom-5 right-[440px] z-10 flex gap-2">
        <button onClick={() => setVp(v => ({ ...v, scale: Math.min(2.5, v.scale * 1.2) }))} className="w-10 h-10 bg-slate-800/80 rounded-lg flex items-center justify-center border border-white/10"><ZoomIn size={16} /></button>
        <button onClick={() => setVp(v => ({ ...v, scale: Math.max(0.1, v.scale / 1.2) }))} className="w-10 h-10 bg-slate-800/80 rounded-lg flex items-center justify-center border border-white/10"><ZoomOut size={16} /></button>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        .custom-scrollbar::-webkit-scrollbar { width: 3px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.05); border-radius: 10px; }
        .glass-btn { position: relative; background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(10px); }
      `}} />
    </div>
  );
}
