import React, { useState, useRef, useEffect } from 'react';
import { evalCurve } from './geometry';

const Packet = ({ id, waypoints, ptype, sids, encapsulator, onDone }) => {
  const [pos, setPos] = useState({ ...waypoints[0] });
  const [progress, setProgress] = useState(0);
  const [endPhase, setEndPhase] = useState(null);
  const rafRef = useRef(null);
  const t0 = useRef(null);
  
  const DURATION = (waypoints.length) * 1100;

  const interpolatePath = (pts, t) => {
    const n = pts.length - 1;
    if (n <= 0) return pts[0];
    const i = Math.min(Math.floor(t * n), n - 1);
    const localT = t * n - i;
    return evalCurve(pts[i], pts[i + 1], localT);
  };

  useEffect(() => {
    function tick(ts) {
      if (!t0.current) t0.current = ts;
      const p = Math.min((ts - t0.current) / DURATION, 1);
      setProgress(p);
      setPos(interpolatePath(waypoints, p));
      
      if (p < 1) {
        rafRef.current = requestAnimationFrame(tick);
        return;
      }
      
      if (ptype === 'msd_drop' || ptype === 'msd_violation') {
        setEndPhase('explode');
        setTimeout(() => onDone(id), 900);
      } else if (ptype === 'attack') {
        setEndPhase('blocked');
        setTimeout(() => onDone(id), 700);
      } else {
        onDone(id);
      }
    }
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  const segments = waypoints.length - 1;
  const isBeforeIngress = progress < (1 / Math.max(1, segments));
  const isInsideTunnel = segments > 1 && progress >= (1 / segments) && progress < ((segments - 1) / segments);
  const isAfterEgress = segments > 1 && progress >= ((segments - 1) / segments);

  // Determine flash states
  const showEncapFlash = segments > 1 && progress >= (1 / segments) && progress < (1.35 / segments);
  const showPopFlash = segments > 1 && ptype !== 'msd_drop' && progress >= ((segments - 1) / segments) && progress < ((segments - 0.65) / segments);

  let pktColor = '#94a3b8'; // Grey for standard IPv6
  let pktLabel = 'IPv6';
  let showSids = false;

  const currentSegmentIdx = segments > 0 ? Math.min(Math.floor(progress * segments), segments - 1) : 0;
  const nextWp = segments > 0 ? waypoints[currentSegmentIdx + 1] : null;
  const prevWp = segments > 0 ? waypoints[currentSegmentIdx] : null;

  let activeVnf = null;
  if (nextWp && nextWp.type === 'vnf') {
    activeVnf = nextWp.vnfRole;
  } else if (prevWp && prevWp.type === 'vnf' && (progress * segments - currentSegmentIdx) < 0.5) {
    activeVnf = prevWp.vnfRole;
  }

  if (isInsideTunnel) {
    if (activeVnf) {
      const vnfUpper = activeVnf.toUpperCase();
      pktLabel = vnfUpper === 'FIREWALL' ? 'FW' : vnfUpper;
      
      // Dynamic colors for each VNF role
      if (activeVnf === 'firewall') pktColor = '#ef4444'; // Rose Red
      else if (activeVnf === 'idps') pktColor = '#06b6d4'; // Cyan
      else if (activeVnf === 'nat') pktColor = '#f59e0b'; // Amber Gold
      else if (activeVnf === 'lb') pktColor = '#6366f1'; // Indigo
      else if (activeVnf === 'voc') pktColor = '#a855f7'; // Purple
      else if (activeVnf === 'router') pktColor = '#10b981'; // Emerald
      else pktColor = '#06b6d4';
    } else {
      pktColor = ptype === 'attack' ? '#dc2626' : '#6366f1'; // Indigo/red inside SRv6 tunnel
      pktLabel = 'SRv6';
    }
    showSids = sids && sids.length > 0;
  } else if (isAfterEgress) {
    pktColor = ptype === 'attack' ? '#ef4444' : '#10b981'; // Green for delivery or red for blocked attack
    pktLabel = 'IPv6';
  } else if (isBeforeIngress) {
    pktColor = '#94a3b8';
    pktLabel = 'IPv6';
  }

  if (endPhase === 'explode') return (
    <g transform={`translate(${pos.x},${pos.y})`}>
      <circle r={80} fill="#ef4444" opacity={0.08} />
      <circle r={24} fill="#ef4444" opacity={0.60} />
      <text y={-8} textAnchor="middle" fill="white" fontSize={10} fontWeight="900">
        MSD DROP!
      </text>
    </g>
  );

  if (endPhase === 'blocked') return (
    <g transform={`translate(${pos.x},${pos.y})`}>
      <circle r={42} fill="#ef4444" opacity={0.18} />
      <text y={5} textAnchor="middle" fill="#fca5a5" fontSize={10} fontWeight="800">
        BLOCKED
      </text>
    </g>
  );

  return (
    <g transform={`translate(${pos.x},${pos.y})`}>
      {/* SID Stack when in tunnel */}
      {showSids && !showEncapFlash && !showPopFlash && (
        <g>
          {sids.slice(0, 3).map((s, i) => (
            <g key={i} transform={`translate(0,${-32 - i * 14})`}>
              <rect x={-48} y={-10} width={96} height={13} rx={4} fill="#f59e0b" stroke="#e2e8f0" strokeWidth={0.5} />
              <text y={-1} textAnchor="middle" fill="#0f172a" fontSize={7} fontWeight="900" letterSpacing={-0.2}>
                {s}
              </text>
            </g>
          ))}
        </g>
      )}

      {/* Encap / Pop brief flashes */}
      {showEncapFlash && (
        <g transform="translate(0, -28)">
          <rect x={-42} y={-8} width={84} height={13} rx={4} fill="#06b6d4" />
          <text y={1} textAnchor="middle" fill="white" fontSize={7} fontWeight="900" className="animate-pulse">
            +ENCAP SRH
          </text>
        </g>
      )}
      {showPopFlash && (
        <g transform="translate(0, -28)">
          <rect x={-42} y={-8} width={84} height={13} rx={4} fill="#ec4899" />
          <text y={1} textAnchor="middle" fill="white" fontSize={7} fontWeight="900" className="animate-pulse">
            -POP SRH
          </text>
        </g>
      )}

      {/* Glow shadow */}
      <rect 
        x={-28} y={-14} width={56} height={24} rx={8} 
        fill={pktColor} 
        opacity={0.35}
        className="blur-[3px]"
      />
      {/* Main capsule */}
      <rect 
        x={-28} y={-14} width={56} height={24} rx={8} 
        fill={pktColor} 
        stroke="white" 
        strokeWidth={1.5} 
      />
      {/* Text label */}
      <text y={2} textAnchor="middle" fill="white" fontSize={8} fontWeight="900">
        {pktLabel}
      </text>
    </g>
  );
};

export default Packet;
