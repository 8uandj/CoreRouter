import React from 'react';

const NR = 68;
const VR = 44;

export const BackboneNode = ({ n, active, onDragStart }) => (
  <g 
    transform={`translate(${n.x},${n.y})`} 
    onMouseDown={!n.fixed ? onDragStart : undefined} 
    style={{ cursor: n.fixed ? 'default' : 'grab' }}
  >
    {active && <circle r={NR + 15} fill={n.color} opacity={0.18} />}
    <circle r={NR + 10} fill={n.color} opacity={0.08} />
    <circle r={NR} fill="#0f172a" stroke={n.color} strokeWidth={active ? 4 : 3} />
    <text y={10} textAnchor="middle" fontSize={32}>{n.icon}</text>
    <text y={NR + 22} textAnchor="middle" fill="#f1f5f9" fontSize={14} fontWeight="800">{n.label}</text>
    <text y={NR + 38} textAnchor="middle" fill={n.color} fontSize={10} fontWeight="600">{n.sub}</text>
  </g>
);

export const VNFNode = ({ id, role, status, x, y, autoDeployed, onDelete }) => {
  const color = role === 'firewall' ? '#ef4444' : role === 'idps' ? '#06b6d4' : role === 'router' ? '#10b981' : '#f59e0b';
  const icon = role === 'firewall' ? '🛡️' : role === 'idps' ? '🔍' : role === 'router' ? '🔀' : '📦';
  const isRunning = status === 'Running';

  return (
    <g transform={`translate(${x},${y})`}>
      {autoDeployed && (
        <text y={-VR - 18} textAnchor="middle" fill="#a78bfa" fontSize={10} fontWeight="800">
          AI-Scaled
        </text>
      )}
      <circle 
        r={VR + 6} 
        fill="none" 
        stroke={color} 
        strokeWidth={2} 
        strokeDasharray={isRunning ? 'none' : '6,3'} 
        opacity={0.7} 
      />
      <circle r={VR} fill="#0f172a" stroke={color} strokeWidth={3} />
      <text y={8} textAnchor="middle" fontSize={24}>{icon}</text>
      <text y={VR + 22} textAnchor="middle" fill="#e2e8f0" fontSize={11} fontWeight="800">
        {id.length > 13 ? id.slice(0, 12) + '…' : id}
      </text>
      <g 
        onClick={() => onDelete(id)} 
        style={{ cursor: 'pointer' }} 
        transform={`translate(${VR}, ${-VR})`}
      >
        <circle r={10} fill="#ef4444" />
        <text y={3} textAnchor="middle" fill="white" fontSize={8} fontWeight="900">X</text>
      </g>
    </g>
  );
};
