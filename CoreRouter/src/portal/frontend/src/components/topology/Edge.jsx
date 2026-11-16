import React from 'react';
import { getCurve } from './geometry';

const Edge = ({ ax, ay, bx, by, color = '#334155', dash = null, raA = 68, raB = 68, opacity = 0.6, strokeWidth, showMarker = true }) => {
  const c = getCurve({ x: ax, y: ay }, { x: bx, y: by }, raA, raB);
  const d = `M ${c.sx} ${c.sy} C ${c.cp1x} ${c.cp1y}, ${c.cp2x} ${c.cp2y}, ${c.ex} ${c.ey}`;
  return (
    <path
      d={d}
      fill="none"
      stroke={color}
      strokeWidth={strokeWidth || (dash ? 3 : 5)}
      strokeDasharray={dash || 'none'}
      markerEnd={showMarker ? 'url(#arr)' : undefined}
      opacity={opacity}
      style={{ transition: 'all 0.3s ease' }}
    />
  );
};

export default Edge;
