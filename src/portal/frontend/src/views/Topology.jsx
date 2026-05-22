import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { AnimatePresence } from 'framer-motion';
import { ZoomIn, ZoomOut, Brain, Play, ShieldAlert, CheckCircle, Flame, HelpCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

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
  nat: '2001:db8:NAT::4',
  lb: '2001:db8:LB::5',
  voc: '2001:db8:VOC::6',
};

const REQUEST_PROFILES = {
  clean: { cpu_req: 4, ram_req: 2, msd_req: 1, service_type: 'Data', alert_flag: false },
  suspicious: { cpu_req: 12, ram_req: 6, msd_req: 2, service_type: 'Data', alert_flag: false },
  corporate: { cpu_req: 16, ram_req: 8, msd_req: 2, service_type: 'VoIP', alert_flag: false },
  ddos: { cpu_req: 70, ram_req: 35, msd_req: 4, service_type: 'Attack', alert_flag: true },
  deep_inspect: { cpu_req: 35, ram_req: 18, msd_req: 5, service_type: 'Video', alert_flag: false },
};

const CITY_TO_SWITCH = {
  hanoi: 's1', hn: 's1',
  haiphong: 's2', hp: 's2',
  ninhbinh: 's3', nb: 's3',
  vinh: 's4',
  hue: 's5',
  danang: 's6', dn: 's6',
  quynhon: 's7', qn: 's7',
  nhatrang: 's8', nt: 's8',
  hochiminh: 's9', hcm: 's9',
  cantho: 's10', ct: 's10',
};

const normalizeLocation = value => String(value || '').trim().toLowerCase().replace(/[\s_-]+/g, '');
const hashToIndex = value => String(value).split('').reduce((sum, char) => sum + char.charCodeAt(0), 0) % VIETNAM_NODES.length;
const nodeBySwitch = switchId => VIETNAM_NODES.find(node => node.switch === switchId) || VIETNAM_NODES[0];
const edgeKey = (a, b) => `${a}-${b}`;
const dcIngressPoint = node => ({ x: node.x - DC_WIDTH / 2 + 86, y: node.y + 128 });
const dcEgressPoint = node => ({ x: node.x + DC_WIDTH / 2 - 86, y: node.y + 128 });

const resolveLocationSwitch = (location, vnfId = '') => {
  const locNorm = normalizeLocation(location);
  const idNorm = normalizeLocation(vnfId);

  // 1. Check if location or id is directly a switch ID
  if (/^s(10|[1-9])$/.test(locNorm)) return locNorm;
  if (/^s(10|[1-9])$/.test(idNorm)) return idNorm;

  // 2. Search vnfId first for specific city identifiers (sorted by descending length)
  const sortedCities = Object.keys(CITY_TO_SWITCH).sort((a, b) => b.length - a.length);

  for (const city of sortedCities) {
    if (idNorm.endsWith(city) || idNorm.includes(`-${city}`) || idNorm.includes(`_${city}`)) {
      return CITY_TO_SWITCH[city];
    }
  }

  // 3. Search location string for specific city identifiers
  for (const city of sortedCities) {
    if (locNorm.includes(city)) {
      return CITY_TO_SWITCH[city];
    }
  }

  // 4. Check for cluster keywords as fallback
  if (locNorm.includes('hanoi') || locNorm.includes('master') || locNorm.includes('hn')) return 's1';
  if (locNorm.includes('danang') || locNorm.includes('worker1') || locNorm.includes('dn')) return 's6';
  if (locNorm.includes('hcm') || locNorm.includes('worker2') || locNorm.includes('hochi')) return 's9';

  // 5. Default fallback using hash
  return VIETNAM_NODES[hashToIndex(vnfId || location)].switch;
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
  const navigate = useNavigate();
  const [nodePos, setNodePos] = useState({ ...BACKBONE });
  const [vp, setVp] = useState({ x: 0, y: 0, scale: 0.35 });
  const [packets, setPackets] = useState([]);
  const [routeTrace, setRouteTrace] = useState([]);
  const [logs, setLogs] = useState([
    { id: 0, msg: '> Vietnam 10-node physical testbed initialized.', color: '#34d399' },
    { id: 1, msg: '> Hybrid Brain (JO-VPPM + Heuristic) standby.', color: '#a78bfa' },
  ]);
  const [encapsulator, setEncapsulator] = useState(null);
  const [isBuffering, setIsBuffering] = useState(false);
  const [simVnfs, setSimVnfs] = useState([]);
  const [isTelemetryOpen, setIsTelemetryOpen] = useState(true);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [routingMode, setRoutingMode] = useState('hybrid');
  
  const [hybridStatus, setHybridStatus] = useState({
    branch: 'heuristic',
    method: 'Hybrid:Heuristic',
    globalUtilization: 0.24,
    avgCpu: 0.18,
    avgMsdUsage: 0.3,
    alertFlag: false,
    nodes: [],
  });

  // Make-Before-Break state
  const [mbbState, setMbbState] = useState({
    active: false,
    step: 'none', // 'make' | 'wait' | 'steer' | 'break'
    progress: 0,
    oldVnf: null,
    newVnf: null,
    oldLoc: null,
    newLoc: null,
  });

  const vnfLocMemo = useRef({});
  const [vnfLocations, setVnfLocations] = useState(() => {
    try {
      const saved = localStorage.getItem('vnf_locations');
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });
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
    setVnfLocations(prev => {
      const next = { ...prev, [id]: location };
      try {
        localStorage.setItem('vnf_locations', JSON.stringify(next));
      } catch (e) {}
      return next;
    });
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
          method: data.mode === 'drl' ? 'Hybrid:JO-VPPM' : 'Hybrid:Heuristic',
          globalUtilization: data.global_utilization ?? prev.globalUtilization,
          avgCpu: data.avg_cpu ?? prev.avgCpu,
          avgMsdUsage: data.avg_msd_usage ?? prev.avgMsdUsage,
          alertFlag: Boolean(data.alert_flag),
          nodes: data.nodes || [],
        }));
      } catch {
        // Fallback or offline simulation
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
      const loc = vnfLocations[v.id] || v.data?.location || 'auto';
      const switchId = resolveLocationSwitch(loc, v.id);
      groups[switchId]?.push(v);
    });
    return groups;
  }, [activeVnfs, vnfLocations]);

  const grouped = getGroupedVnfs();

  const getVnfPos = useCallback((vid) => {
    const activeLoc = activeVnfs.find(x => x.id === vid)?.data?.location;
    const switchId = resolveLocationSwitch(vnfLocations[vid] || activeLoc, vid);
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
  }, [grouped, nodePos, vnfLocations, activeVnfs]);

  // Physical path waypoint generator
  const buildPhysicalWaypoints = useCallback((srcSw, dstSw, selectedVnfs, isViolation = false, violationSw = null) => {
    // Collect switches where VNFs are located, in sequence
    const vnfSwitches = selectedVnfs.map(v => resolveLocationSwitch(vnfLocations[v.id] || v.data?.location, v.id));
    
    // Build a segment list of nodes
    const segments = [srcSw, ...vnfSwitches, dstSw];
    
    // Resolve shortest paths between consecutive segment switches
    const switchSequence = [];
    for (let i = 0; i < segments.length - 1; i++) {
      const pathSegment = directPath(segments[i], segments[i + 1]);
      // Merge path segments without consecutive duplicates
      for (const sw of pathSegment) {
        if (switchSequence.length === 0 || switchSequence[switchSequence.length - 1] !== sw) {
          switchSequence.push(sw);
        }
      }
    }

    const waypoints = [userNodes.src];
    
    for (const sw of switchSequence) {
      const node = nodePos[sw];
      if (!node) continue;

      if (isViolation && sw === violationSw) {
        // Exceeded MSD capacity, add ingress then terminate with offset explosion point
        waypoints.push(dcIngressPoint(node));
        waypoints.push({ x: node.x, y: node.y - 20 });
        break;
      }

      waypoints.push(dcIngressPoint(node));
      
      // Inject VNFs situated on this switch that are selected for this route
      const vnfsAtSw = selectedVnfs.filter(v => resolveLocationSwitch(vnfLocations[v.id] || v.data?.location, v.id) === sw);
      vnfsAtSw.forEach(v => {
        waypoints.push(getVnfPos(v.id));
      });
      
      waypoints.push(dcEgressPoint(node));
    }

    if (!isViolation) {
      waypoints.push(userNodes.dest);
    }
    return waypoints;
  }, [getVnfPos, nodePos, vnfLocations]);

  const sourceNode = nodeBySwitch(srcDc);
  const targetNode = nodeBySwitch(dstDc);

  const userNodes = useMemo(() => ({
    src: { x: nodePos[srcDc].x - DC_WIDTH / 2 - 150, y: nodePos[srcDc].y + 128, label: `SRC ${sourceNode.host.toUpperCase()}`, sub: sourceNode.label, icon: 'SRC', color: '#f43f5e', fixed: true },
    dest: { x: nodePos[dstDc].x + DC_WIDTH / 2 + 150, y: nodePos[dstDc].y + 128, label: `DST ${targetNode.host.toUpperCase()}`, sub: targetNode.label, icon: 'DST', color: '#10b981', fixed: true },
  }), [dstDc, nodePos, sourceNode.host, sourceNode.label, srcDc, targetNode.host, targetNode.label]);

  const previewRouteTrace = useMemo(() => {
    return buildPhysicalWaypoints(srcDc, dstDc, []);
  }, [buildPhysicalWaypoints, srcDc, dstDc]);

  const displayRouteTrace = routeTrace.length > 1 ? routeTrace : previewRouteTrace;

  // Make-Before-Break Simulation Trigger
  const handleSimulateMbb = useCallback(async () => {
    if (mbbState.active) return;
    pushLog(`> [MBB] Init Make-Before-Break migration workflow...`, '#a78bfa');

    // Pick old VNF or bootstrap a temporary old VNF at Hanoi (s1)
    let oldVnf = activeVnfs.find(v => v.data?.role === 'firewall');
    let oldId = oldVnf?.id;
    if (!oldVnf) {
      oldId = 'vnf-legacy-fw';
      rememberVnfLocation(oldId, 'hn');
      setSimVnfs(prev => [
        ...prev,
        { id: oldId, data: { role: 'firewall', status: 'Running', location: 'hn' } }
      ]);
      pushLog(`> [MBB] Created legacy firewall instance '${oldId}' at Hanoi (s1)`, '#64748b');
      await new Promise(resolve => setTimeout(resolve, 800));
    } else {
      pushLog(`> [MBB] Target firewall selected for migration: '${oldId}'`, '#38bdf8');
    }

    const newId = `vnf-migrated-fw-${Math.floor(Math.random() * 100)}`;
    rememberVnfLocation(newId, 'dn'); // Target is DaNang (s6)

    // Phase 1: MAKE
    setMbbState({
      active: true,
      step: 'make',
      progress: 15,
      oldVnf: oldId,
      newVnf: newId,
      oldLoc: 'hn',
      newLoc: 'dn'
    });
    setSimVnfs(prev => [
      ...prev,
      { id: newId, data: { role: 'firewall', status: 'Pending', location: 'dn' } }
    ]);
    pushLog(`> [MBB] Phase 1/4 (MAKE): Allocating resources at Da Nang. Deployment pipeline created.`, '#facc15');
    pushLog(`> [TEKTON] PipelineRun 'mbb-sfc-migration-pipeline' created. Running Task: deploy-pod`, '#94a3b8');

    // Phase 2: WAIT
    await new Promise(resolve => setTimeout(resolve, 3000));
    setMbbState(prev => ({ ...prev, step: 'wait', progress: 48 }));
    pushLog(`> [MBB] Phase 2/4 (WAIT): Pod running. Awaiting Kubernetes readiness check...`, '#facc15');
    pushLog(`> [TEKTON] Task check-readiness: probe returned HTTP 200 OK.`, '#94a3b8');

    // Phase 3: STEER
    await new Promise(resolve => setTimeout(resolve, 3000));
    setMbbState(prev => ({ ...prev, step: 'steer', progress: 75 }));
    pushLog(`> [MBB] Phase 3/4 (STEER): Swapping active routing tables. Traffic re-directed.`, '#38bdf8');
    pushLog(`> [SRv6] Swapped segment SID 2001:db8:FW::1 from Hanoi to Da Nang.`, '#34d399');
    
    // Set target VNF to Running
    setSimVnfs(prev => prev.map(v => v.id === newId ? { ...v, data: { ...v.data, status: 'Running' } } : v));

    // Phase 4: BREAK
    await new Promise(resolve => setTimeout(resolve, 3000));
    setMbbState(prev => ({ ...prev, step: 'break', progress: 95 }));
    pushLog(`> [MBB] Phase 4/4 (BREAK): Demolishing old firewall instance at Hanoi...`, '#ec4899');
    pushLog(`> [TEKTON] Task clean-up-old: deleted Deployment/Service resources.`, '#94a3b8');

    // Tear down completion
    await new Promise(resolve => setTimeout(resolve, 2000));
    setSimVnfs(prev => prev.filter(v => v.id !== oldId));
    setMbbState({
      active: false,
      step: 'none',
      progress: 100,
      oldVnf: null,
      newVnf: null,
      oldLoc: null,
      newLoc: null,
    });
    pushLog(`> [MBB] Make-Before-Break migration completed successfully. Zero packet loss.`, '#10b981');
  }, [activeVnfs, mbbState.active, pushLog, rememberVnfLocation]);

  // Main SRv6 Optimization Handler
  const handleOptimize = useCallback(async () => {
    if (isBuffering) return;

    let srcSwitch = srcDc;
    let dstSwitch = dstDc;
    let selectedVnfs = [];
    let policyRoles = [];

    // Intercept with Static Routing Presets
    if (routingMode === 'security') {
      srcSwitch = 's1'; // Hanoi
      dstSwitch = 's9'; // HCM
      setSrcDc('s1');
      setDstDc('s9');
      policyRoles = ['firewall', 'idps', 'router'];
      pushLog(`> [STATIC RULE] Security Chain active: Hanoi (FW) -> DaNang (IDPS) -> HCM (RTR)`, '#f59e0b');

      // Guarantee required VNFs exist in simVnfs
      const addedSim = [];
      const hasFw = activeVnfs.some(v => v.data?.role === 'firewall' && resolveLocationSwitch(vnfLocations[v.id] || v.data?.location, v.id) === 's1');
      const hasIdps = activeVnfs.some(v => v.data?.role === 'idps' && resolveLocationSwitch(vnfLocations[v.id] || v.data?.location, v.id) === 's6');
      const hasRouter = activeVnfs.some(v => v.data?.role === 'router' && resolveLocationSwitch(vnfLocations[v.id] || v.data?.location, v.id) === 's9');

      if (!hasFw) {
        rememberVnfLocation('vnf-fw-s1', 'hn');
        addedSim.push({ id: 'vnf-fw-s1', data: { role: 'firewall', status: 'Running', location: 'hn' } });
      }
      if (!hasIdps) {
        rememberVnfLocation('vnf-idps-s6', 'dn');
        addedSim.push({ id: 'vnf-idps-s6', data: { role: 'idps', status: 'Running', location: 'dn' } });
      }
      if (!hasRouter) {
        rememberVnfLocation('vnf-rtr-s9', 'hcm');
        addedSim.push({ id: 'vnf-rtr-s9', data: { role: 'router', status: 'Running', location: 'hcm' } });
      }
      if (addedSim.length > 0) {
        setSimVnfs(prev => [...prev, ...addedSim]);
      }
      
      // Wait a tick for local state sync or construct manually
      selectedVnfs = [
        { id: 'vnf-fw-s1', data: { role: 'firewall', location: 'hn' } },
        { id: 'vnf-idps-s6', data: { role: 'idps', location: 'dn' } },
        { id: 'vnf-rtr-s9', data: { role: 'router', location: 'hcm' } }
      ];
    } else if (routingMode === 'voice') {
      srcSwitch = 's2'; // HaiPhong
      dstSwitch = 's10'; // CanTho
      setSrcDc('s2');
      setDstDc('s10');
      policyRoles = ['nat', 'voc', 'lb'];
      pushLog(`> [STATIC RULE] VoIP Quality Chain active: HaiPhong (NAT) -> Hue (VOC) -> CanTho (LB)`, '#38bdf8');

      const addedSim = [];
      const hasNat = activeVnfs.some(v => v.data?.role === 'nat' && resolveLocationSwitch(vnfLocations[v.id] || v.data?.location, v.id) === 's2');
      const hasVoc = activeVnfs.some(v => v.data?.role === 'voc' && resolveLocationSwitch(vnfLocations[v.id] || v.data?.location, v.id) === 's5');
      const hasLb = activeVnfs.some(v => v.data?.role === 'lb' && resolveLocationSwitch(vnfLocations[v.id] || v.data?.location, v.id) === 's10');

      if (!hasNat) {
        rememberVnfLocation('vnf-nat-s2', 'hp');
        addedSim.push({ id: 'vnf-nat-s2', data: { role: 'nat', status: 'Running', location: 'hp' } });
      }
      if (!hasVoc) {
        rememberVnfLocation('vnf-voc-s5', 'hue');
        addedSim.push({ id: 'vnf-voc-s5', data: { role: 'voc', status: 'Running', location: 'hue' } });
      }
      if (!hasLb) {
        rememberVnfLocation('vnf-lb-s10', 'ct');
        addedSim.push({ id: 'vnf-lb-s10', data: { role: 'lb', status: 'Running', location: 'ct' } });
      }
      if (addedSim.length > 0) {
        setSimVnfs(prev => [...prev, ...addedSim]);
      }

      selectedVnfs = [
        { id: 'vnf-nat-s2', data: { role: 'nat', location: 'hp' } },
        { id: 'vnf-voc-s5', data: { role: 'voc', location: 'hue' } },
        { id: 'vnf-lb-s10', data: { role: 'lb', location: 'ct' } }
      ];
    } else if (routingMode === 'bypass') {
      pushLog(`> [STATIC RULE] SFC Bypass engaged. Traversing direct physical path.`, '#10b981');
      selectedVnfs = [];
    } else {
      // Dynamic Hybrid Mode
      const policy = TRAFFIC_POLICY[trafficOpt];
      const profile = REQUEST_PROFILES[trafficOpt] || REQUEST_PROFILES.clean;
      policyRoles = policy.roles;
      pushLog(`> Hybrid Optimization request: ${sourceNode.label} -> ${targetNode.label} [${trafficOpt.toUpperCase()}]`, '#facc15');

      let placementSwitch = srcDc;
      let routeSwitch = dstDc;
      let sidStack = [];

      try {
        const decision = await vnfService.orchestrateSfc({
          ...profile,
          msd_req: Math.max(profile.msd_req, policy.roles.length || 1),
          is_ddos_spike: trafficOpt === 'ddos',
          source_node: sourceNode.id,
          destination_node: targetNode.id,
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
          `> Hybrid Core Decision: ${nextStatus.method} | Global Util: ${Math.round(nextStatus.globalUtilization * 100)}%`,
          nextStatus.branch === 'drl' ? '#ec4899' : '#34d399'
        );
      } catch (e) {
        pushLog(`> Hybrid brain API unavailable. Falling back to local heuristics...`, '#f97316');
      }

      // Find best VNFs using Heuristics model
      const C_INST = 5000;
      const W_PENALTY = 1200;
      const requiredScaleOuts = [];

      for (const role of policyRoles) {
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
          const vId = `scale-${role}-${Math.floor(Math.random() * 100)}`;
          rememberVnfLocation(vId, placementSwitch);
          requiredScaleOuts.push({ id: vId, role, loc: placementSwitch });
          selectedVnfs.push({ id: vId, data: { role, status: 'Pending', location: placementSwitch } });
          pushLog(`> Dynamic scale-out: Provisioning ${role} instance at ${nodePos[placementSwitch].label}`, '#a78bfa');
        } else {
          selectedVnfs.push(bestChoice);
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
        await new Promise(resolve => setTimeout(resolve, 1400));
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
    }

    // Evaluate MSD limits along the path of transit switches
    const pathSwitches = directPath(srcSwitch, dstSwitch);
    const totalSids = policyRoles.length + 1;
    
    // Find the first switch that violates the MSD limit
    let isMsdViolation = false;
    let violatingSwitch = null;
    let lowestMsdLimit = 10;
    
    for (const sw of pathSwitches) {
      const msdCap = nodePos[sw]?.msd || 10;
      if (totalSids > msdCap) {
        isMsdViolation = true;
        violatingSwitch = sw;
        lowestMsdLimit = msdCap;
        break;
      }
    }

    // Build the exact physical linked waypoints
    const finalWaypoints = buildPhysicalWaypoints(srcSwitch, dstSwitch, selectedVnfs, isMsdViolation, violatingSwitch);
    setRouteTrace(finalWaypoints);

    if (isMsdViolation) {
      pushLog(`> [MSD DROP] Packet dropped at switch ${violatingSwitch.toUpperCase()} (${nodePos[violatingSwitch]?.label}). Path SID depth (${totalSids}) exceeds node MSD capacity (${lowestMsdLimit})`, '#ef4444');
    } else {
      setEncapsulator(srcSwitch);
      pushLog(`> Route path approved. SID depth ${totalSids} accepted. Waypoints registered.`, '#38bdf8');
    }

    // Inject active packet
    setPackets(prev => [
      ...prev,
      {
        id: `pkt-${Date.now()}`,
        waypoints: finalWaypoints,
        ptype: isMsdViolation ? 'msd_drop' : (trafficOpt === 'ddos' ? 'attack' : 'normal'),
        sids: policyRoles.map(r => SID_MAP[r] || '2001:db8::1'),
        encapsulator: srcSwitch,
      }
    ]);
  }, [activeVnfs, dstDc, isBuffering, nodePos, onDeploy, pushLog, rememberVnfLocation, routingMode, srcDc, trafficOpt, userNodes, vnfLocations, buildPhysicalWaypoints]);

  // Keep sending packets along current trace automatically to feel interactive
  useEffect(() => {
    if (routeTrace.length < 2) return;
    const interval = setInterval(() => {
      // Determine if trace has MSD Drop (it doesn't end at the Destination node coordinates)
      const lastWp = routeTrace[routeTrace.length - 1];
      const reachesDest = Math.abs(lastWp.x - userNodes.dest.x) < 5 && Math.abs(lastWp.y - userNodes.dest.y) < 5;
      
      const finalPtype = reachesDest ? (trafficOpt === 'ddos' ? 'attack' : 'normal') : 'msd_drop';
      const activeRoles = TRAFFIC_POLICY[trafficOpt].roles;

      setPackets(prev => [
        ...prev.slice(-15),
        {
          id: `pkt-${Date.now()}`,
          waypoints: routeTrace,
          ptype: finalPtype,
          sids: activeRoles.map(r => SID_MAP[r] || '2001:db8::1'),
          encapsulator: srcDc,
        }
      ]);
    }, 3200);
    return () => clearInterval(interval);
  }, [routeTrace, trafficOpt, srcDc, userNodes.dest]);

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
    <div className="flex flex-col w-full h-full bg-[#020617] text-white overflow-hidden select-none font-sans relative">
      <ControlHeader
        srcDc={srcDc} setSrcDc={setSrcDc}
        dstDc={dstDc} setDstDc={setDstDc}
        trafficOpt={trafficOpt} setTrafficOpt={setTrafficOpt}
        routingMode={routingMode} setRoutingMode={setRoutingMode}
        onOptimize={handleOptimize} isBuffering={isBuffering}
        onOpenModal={() => setIsModalOpen(true)}
        activeVnfCount={activeVnfs.length}
        dcs={BACKBONE} trafficPolicies={TRAFFIC_POLICY}
        hybridStatus={hybridStatus}
        onSimulateMbb={handleSimulateMbb}
      />

      {/* Floating MBB Progress HUD Overlay */}
      {mbbState.active && (
        <div className="absolute top-28 left-1/2 transform -translate-x-1/2 z-50 bg-[#030b18]/90 backdrop-blur-xl border border-amber-500/30 p-6 rounded-[2rem] w-full max-w-xl shadow-[0_20px_50px_rgba(245,158,11,0.2)]">
          <div className="flex justify-between items-center mb-3">
            <div>
              <span className="text-[10px] font-black text-amber-500 uppercase tracking-widest block flex items-center gap-1.5 animate-pulse">
                <Brain size={12}/> ACTIVE MIGRATION PIPELINE
              </span>
              <h4 className="text-sm font-black text-white uppercase mt-0.5">Make-Before-Break (MBB)</h4>
            </div>
            <div className="text-right">
              <span className="text-[10px] font-bold text-slate-400 uppercase">PROGRESS</span>
              <span className="text-sm font-mono font-black text-amber-400 block">{mbbState.progress}%</span>
            </div>
          </div>
          
          <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden mb-4 border border-white/5">
            <div 
              className="h-full bg-gradient-to-r from-amber-500 to-indigo-500 transition-all duration-500" 
              style={{ width: `${mbbState.progress}%` }}
            />
          </div>

          <div className="grid grid-cols-4 gap-2 text-center text-[9px] font-black uppercase">
            <div className={`p-2.5 rounded-xl border ${mbbState.step === 'make' ? 'bg-amber-500/20 border-amber-500/40 text-amber-300' : 'bg-slate-900/60 border-transparent text-slate-500'}`}>
              1. MAKE (Deploy)
            </div>
            <div className={`p-2.5 rounded-xl border ${mbbState.step === 'wait' ? 'bg-amber-500/20 border-amber-500/40 text-amber-300' : 'bg-slate-900/60 border-transparent text-slate-500'}`}>
              2. WAIT (Probe)
            </div>
            <div className={`p-2.5 rounded-xl border ${mbbState.step === 'steer' ? 'bg-indigo-500/20 border-indigo-500/40 text-indigo-300' : 'bg-slate-900/60 border-transparent text-slate-500'}`}>
              3. STEER (Swap)
            </div>
            <div className={`p-2.5 rounded-xl border ${mbbState.step === 'break' ? 'bg-pink-500/20 border-pink-500/40 text-pink-300' : 'bg-slate-900/60 border-transparent text-slate-500'}`}>
              4. BREAK (Demolish)
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between text-[10px] font-bold text-slate-400">
            <span>Migrating: <span className="text-white font-mono">{mbbState.oldVnf}</span> ({mbbState.oldLoc?.toUpperCase()}) &rarr; <span className="text-white font-mono">{mbbState.newVnf}</span> ({mbbState.newLoc?.toUpperCase()})</span>
            <button 
              onClick={() => navigate('/tekton')} 
              className="text-indigo-400 hover:text-indigo-300 underline font-black uppercase cursor-pointer flex items-center gap-1"
            >
              View Tekton Pipelines &rarr;
            </button>
          </div>
        </div>
      )}

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
                Physical Topology | Packets trace exact optical links and internal VNF rack paths
              </text>

              {/* Physical Cables / Edges */}
              {BACKBONE_EDGES.map(([a, b]) => (
                <Edge
                  key={`${a}-${b}`}
                  ax={dcEgressPoint(nodePos[a]).x}
                  ay={dcEgressPoint(nodePos[a]).y}
                  bx={dcIngressPoint(nodePos[b]).x}
                  by={dcIngressPoint(nodePos[b]).y}
                  color={FAST_EDGES.has(edgeKey(a, b)) ? '#f59e0b' : '#1e293b'}
                  dash={FAST_EDGES.has(edgeKey(a, b)) ? '16,10' : null}
                  raA={20}
                  raB={20}
                />
              ))}

              <Edge ax={userNodes.src.x} ay={userNodes.src.y} bx={dcIngressPoint(nodePos[srcDc]).x} by={dcIngressPoint(nodePos[srcDc]).y} color="#f43f5e" dash="12,8" raA={20} raB={20} />
              <Edge ax={dcEgressPoint(nodePos[dstDc]).x} ay={dcEgressPoint(nodePos[dstDc]).y} bx={userNodes.dest.x} by={userNodes.dest.y} color="#10b981" dash="12,8" raA={20} raB={20} />

              {/* Active Route Trace (Yellow Waypoints) */}
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

              {/* internal switch-VNF links */}
              {activeVnfs.map(v => {
                const pos = getVnfPos(v.id);
                const switchId = resolveLocationSwitch(vnfLocations[v.id] || v.data?.location, v.id);
                const srcNode = nodePos[switchId] || nodePos.s1;
                
                // If it is MBB target / old, color the internal links amber or pink
                const isTarget = mbbState.active && mbbState.newVnf === v.id;
                const isOld = mbbState.active && mbbState.oldVnf === v.id;
                const linkColor = isTarget ? '#f59e0b' : isOld ? '#ec4899' : '#06b6d4';

                return (
                  <g key={`l-${v.id}`}>
                    <Edge ax={dcIngressPoint(srcNode).x} ay={dcIngressPoint(srcNode).y} bx={pos.x} by={pos.y} color={linkColor} dash="8,8" raA={18} raB={32} />
                    <Edge ax={pos.x} ay={pos.y} bx={dcEgressPoint(srcNode).x} by={dcEgressPoint(srcNode).y} color="#10b981" dash="8,8" raA={32} raB={18} />
                  </g>
                );
              })}

              {/* Backbone switches */}
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

              {/* VNFs Nodes */}
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
                  isMbbTarget={mbbState.active && mbbState.newVnf === v.id}
                  isMbbOld={mbbState.active && mbbState.oldVnf === v.id}
                  onDelete={id => {
                    setSimVnfs(prev => prev.filter(x => x.id !== id));
                    setAutoDeployedIds(prev => {
                      const next = new Set(prev);
                      next.delete(id);
                      return next;
                    });
                    setVnfLocations(prev => {
                      const next = { ...prev };
                      delete next[id];
                      try {
                        localStorage.setItem('vnf_locations', JSON.stringify(next));
                      } catch (e) {}
                      return next;
                    });
                    onDelete(id);
                  }}
                />
              ))}

              {/* Moving Packets */}
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
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          formData={formData}
          setFormData={setFormData}
          onSubmit={data => {
            const loc = data.location || 'auto';
            rememberVnfLocation(data.name, loc);
            pushLog(`> Initiating deployment of ${data.type.toUpperCase()} at ${loc.toUpperCase()}...`, '#a78bfa');
            onDeploy(data);
            setIsModalOpen(false);
          }}
        />
      </AnimatePresence>

      <div className="absolute bottom-5 right-[440px] z-10 flex gap-2">
        <button onClick={() => setVp(v => ({ ...v, scale: Math.min(2.5, v.scale * 1.2) }))} className="w-10 h-10 bg-slate-800/80 rounded-lg flex items-center justify-center border border-white/10 hover:bg-slate-700 transition-colors cursor-pointer"><ZoomIn size={16} /></button>
        <button onClick={() => setVp(v => ({ ...v, scale: Math.max(0.1, v.scale / 1.2) }))} className="w-10 h-10 bg-slate-800/80 rounded-lg flex items-center justify-center border border-white/10 hover:bg-slate-700 transition-colors cursor-pointer"><ZoomOut size={16} /></button>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 10px; }
        .glass-btn { position: relative; background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(10px); }
        
        @keyframes mbb-pulse-stroke {
          0%, 100% { stroke-width: 3px; opacity: 0.7; }
          50% { stroke-width: 6px; opacity: 1; filter: drop-shadow(0 0 8px rgba(245,158,11,0.8)); }
        }
        .animate-mbb-pulse circle {
          animation: mbb-pulse-stroke 1.2s infinite ease-in-out;
        }

        @keyframes mbb-break-pulse {
          0%, 100% { stroke-width: 3px; opacity: 0.5; }
          50% { stroke-width: 5px; opacity: 1; filter: drop-shadow(0 0 8px rgba(236,72,153,0.8)); }
        }
        .animate-mbb-break circle {
          animation: mbb-break-pulse 0.8s infinite ease-in-out;
        }
      `}} />
    </div>
  );
}
