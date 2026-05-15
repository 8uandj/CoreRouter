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

  const tVal = encapsulator === 's1' ? 0.08 : 0.15;
  const showSids = ptype === 'normal' && progress > tVal && sids.length > 0;

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
      {showSids && sids.slice(0, 3).map((s, i) => (
        <g key={i} transform={`translate(0,${-30 - i * 14})`}>
          <rect x={-48} y={-10} width={96} height={13} rx={4} fill="#f59e0b" />
          <text y={1} textAnchor="middle" fill="#0f172a" fontSize={7} fontWeight="700">
            {s}
          </text>
        </g>
      ))}
      <rect 
        x={-28} y={-14} width={56} height={24} rx={8} 
        fill={ptype === 'normal' ? '#4338ca' : '#dc2626'} 
        stroke="white" strokeWidth={1.5} 
      />
      <text y={3} textAnchor="middle" fill="white" fontSize={8} fontWeight="900">
        {ptype.toUpperCase().slice(0, 3)}
      </text>
    </g>
  );
};

export default Packet;
