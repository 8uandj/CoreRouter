import React from 'react';

// --- Shared Helper for Curves ---
export function getCurve(a, b, raA = 0, raB = 0) {
  const dx = b.x - a.x, dy = b.y - a.y;
  const isHoriz = Math.abs(dx) >= Math.abs(dy);
  let sx = a.x, sy = a.y, ex = b.x, ey = b.y;
  if (raA > 0 || raB > 0) {
    if (isHoriz) {
      const dir = Math.sign(dx) || 1;
      sx += dir * raA;
      ex -= dir * raB;
    } else {
      const dir = Math.sign(dy) || 1;
      sy += dir * raA;
      ey -= dir * raB;
    }
  }
  const cp1x = isHoriz ? (sx + ex) / 2 : sx;
  const cp1y = isHoriz ? sy : (sy + ey) / 2;
  const cp2x = isHoriz ? (sx + ex) / 2 : ex;
  const cp2y = isHoriz ? ey : (sy + ey) / 2;
  return { sx, sy, ex, ey, cp1x, cp1y, cp2x, cp2y, isHoriz };
}

export function evalCurve(a, b, t) {
  const c = getCurve(a, b, 0, 0);
  const _1t = 1 - t;
  const x = Math.pow(_1t, 3) * c.sx + 3 * Math.pow(_1t, 2) * t * c.cp1x + 3 * _1t * Math.pow(t, 2) * c.cp2x + Math.pow(t, 3) * c.ex;
  const y = Math.pow(_1t, 3) * c.sy + 3 * Math.pow(_1t, 2) * t * c.cp1y + 3 * _1t * Math.pow(t, 2) * c.cp2y + Math.pow(t, 3) * c.ey;
  return { x, y };
}

const Edge = ({ ax, ay, bx, by, color = '#334155', dash = null, raA = 68, raB = 68 }) => {
  const c = getCurve({ x: ax, y: ay }, { x: bx, y: by }, raA, raB);
  const d = `M ${c.sx} ${c.sy} C ${c.cp1x} ${c.cp1y}, ${c.cp2x} ${c.cp2y}, ${c.ex} ${c.ey}`;
  return (
    <path
      d={d}
      fill="none"
      stroke={color}
      strokeWidth={dash ? 3 : 5}
      strokeDasharray={dash || 'none'}
      markerEnd="url(#arr)"
      opacity={0.6}
      style={{ transition: 'all 0.3s ease' }}
    />
  );
};

export default Edge;
