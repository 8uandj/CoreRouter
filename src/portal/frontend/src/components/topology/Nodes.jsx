import React from 'react';

const NR = 68;
const VR = 44;

export const BackboneNode = ({ n, active, telemetry, dcWidth = 380, dcHeight = 250, switchWidth = 82, switchHeight = 42, onDragStart }) => {
  const cpu = Math.round(telemetry?.cpu_util || 0);
  const msd = Math.round(telemetry?.msd_util || 0);
  const alert = Boolean(telemetry?.alert);
  const isDataCenter = Boolean(n.switch && n.k8sHostname);
  const ingress = { x: -dcWidth / 2 + 66, y: 78 };
  const egress = { x: dcWidth / 2 - 66, y: 78 };

  if (isDataCenter) {
    return (
      <g
        transform={`translate(${n.x},${n.y})`}
        onMouseDown={onDragStart}
        style={{ cursor: 'grab' }}
      >
        {active && <rect x={-dcWidth / 2 - 10} y={-dcHeight / 2 - 10} width={dcWidth + 20} height={dcHeight + 20} rx={18} fill={n.color} opacity={0.12} />}
        <rect
          x={-dcWidth / 2}
          y={-dcHeight / 2}
          width={dcWidth}
          height={dcHeight}
          rx={16}
          fill="#07111f"
          stroke={alert ? '#ef4444' : n.color}
          strokeWidth={active || alert ? 3 : 2}
        />
        <rect x={-dcWidth / 2 + 14} y={-dcHeight / 2 + 14} width={dcWidth - 28} height={54} rx={10} fill={n.color} opacity={0.09} />
        <text x={-dcWidth / 2 + 28} y={-dcHeight / 2 + 38} fill="#f8fafc" fontSize={18} fontWeight="900">{n.label}</text>
        <text x={-dcWidth / 2 + 28} y={-dcHeight / 2 + 59} fill={n.color} fontSize={11} fontWeight="800">
          {n.switch.toUpperCase()} | {n.role.toUpperCase()} | MSD {n.msd} | {n.k8sHostname}
        </text>
        <text x={dcWidth / 2 - 28} y={-dcHeight / 2 + 39} textAnchor="end" fill="#94a3b8" fontSize={10} fontWeight="800">
          CPU {cpu}% / MSD {msd}%
        </text>

        <rect x={-dcWidth / 2 + 28} y={-74} width={dcWidth - 56} height={160} rx={14} fill="#020617" stroke="#1e293b" strokeDasharray="8,6" />
        <text x={-dcWidth / 2 + 46} y={-49} fill="#64748b" fontSize={10} fontWeight="900">VNF RACK SPACE</text>
        <text x={-dcWidth / 2 + 46} y={-30} fill="#334155" fontSize={9} fontWeight="700">capacity view: 6 VNFs plus headroom</text>

        <line x1={ingress.x + switchWidth / 2} y1={ingress.y} x2={egress.x - switchWidth / 2} y2={egress.y} stroke="#475569" strokeWidth={4} strokeDasharray="10,7" opacity={0.65} />
        <rect x={ingress.x - switchWidth / 2} y={ingress.y - switchHeight / 2} width={switchWidth} height={switchHeight} rx={8} fill="#0f172a" stroke="#f43f5e" strokeWidth={2.5} />
        <rect x={egress.x - switchWidth / 2} y={egress.y - switchHeight / 2} width={switchWidth} height={switchHeight} rx={8} fill="#0f172a" stroke="#10b981" strokeWidth={2.5} />
        <text x={ingress.x} y={ingress.y - 3} textAnchor="middle" fill="#fecdd3" fontSize={10} fontWeight="900">INGRESS</text>
        <text x={ingress.x} y={ingress.y + 12} textAnchor="middle" fill="#64748b" fontSize={8} fontWeight="800">{n.switch}-in</text>
        <text x={egress.x} y={egress.y - 3} textAnchor="middle" fill="#bbf7d0" fontSize={10} fontWeight="900">EGRESS</text>
        <text x={egress.x} y={egress.y + 12} textAnchor="middle" fill="#64748b" fontSize={8} fontWeight="800">{n.switch}-out</text>
      </g>
    );
  }

  return (
    <g
      transform={`translate(${n.x},${n.y})`}
      onMouseDown={!n.fixed ? onDragStart : undefined}
      style={{ cursor: n.fixed ? 'default' : 'grab' }}
    >
      {active && <circle r={NR + 18} fill={n.color} opacity={0.18} />}
      {alert && <circle r={NR + 22} fill="#ef4444" opacity={0.12} />}
      <circle r={NR + 10} fill={n.color} opacity={0.08} />
      <circle r={NR} fill="#0f172a" stroke={alert ? '#ef4444' : n.color} strokeWidth={active || alert ? 4 : 3} />
      <text y={-12} textAnchor="middle" fill={n.color} fontSize={15} fontWeight="900">{n.icon}</text>
      <text y={10} textAnchor="middle" fill="#f8fafc" fontSize={13} fontWeight="900">{n.switch?.toUpperCase() || n.label}</text>
      <text y={29} textAnchor="middle" fill="#cbd5e1" fontSize={11} fontWeight="800">{n.label}</text>
      <text y={NR + 21} textAnchor="middle" fill={n.color} fontSize={10} fontWeight="800">{n.sub}</text>
      {n.k8sHostname && (
        <text y={NR + 38} textAnchor="middle" fill="#64748b" fontSize={9} fontWeight="700">
          {n.k8sHostname} | CPU {cpu}% | MSD {msd}%
        </text>
      )}
    </g>
  );
};

export const VNFNode = ({ id, role, status, x, y, size = VR, autoDeployed, onDelete, isMbbTarget, isMbbOld }) => {
  let color = role === 'firewall' ? '#ef4444' : role === 'idps' ? '#06b6d4' : role === 'router' ? '#10b981' : '#f59e0b';
  let icon = role === 'firewall' ? 'FW' : role === 'idps' ? 'IDPS' : role === 'router' ? 'RTR' : 'VNF';
  
  if (role === 'nat') icon = 'NAT';
  if (role === 'lb') icon = 'LB';
  if (role === 'voc') icon = 'VOC';

  if (isMbbTarget) {
    color = '#f59e0b'; // Amber for new target
  } else if (isMbbOld) {
    color = '#ec4899'; // Pink/Rose for old tearing-down VNF
  }

  const isRunning = status === 'Running' && !isMbbTarget && !isMbbOld;
  const statusLabel = isMbbTarget ? 'MAKE (Deploying)' : isMbbOld ? 'BREAK (Terminating)' : status;

  return (
    <g 
      transform={`translate(${x},${y})`}
      className={`${isMbbTarget ? 'animate-mbb-pulse' : ''} ${isMbbOld ? 'animate-mbb-break' : ''}`}
    >
      {autoDeployed && (
        <text y={-size - 22} textAnchor="middle" fill="#a78bfa" fontSize={9} fontWeight="800" className="uppercase tracking-widest">
          AI-Scaled
        </text>
      )}
      
      {/* Outer Status Ring */}
      <circle 
        r={size + 6} 
        fill="none" 
        stroke={color} 
        strokeWidth={isMbbTarget || isMbbOld ? 3 : 2} 
        strokeDasharray={isRunning ? 'none' : '5,3'} 
        className={isMbbTarget ? 'animate-spin' : ''}
        style={{ transformOrigin: 'center', animationDuration: '6s' }}
        opacity={0.8} 
      />

      {/* Main Node Body */}
      <circle 
        r={size} 
        fill="#080e1a" 
        stroke={color} 
        strokeWidth={3} 
        style={{
          filter: isMbbTarget ? 'drop-shadow(0 0 12px rgba(245, 158, 11, 0.6))' : isMbbOld ? 'drop-shadow(0 0 12px rgba(236, 72, 153, 0.6))' : 'none'
        }}
      />
      
      <text y={4} textAnchor="middle" fill="#f8fafc" fontSize={size > 34 ? 12 : 9} fontWeight="900">{icon}</text>
      
      {/* Label Identity */}
      <text y={size + 15} textAnchor="middle" fill="#f1f5f9" fontSize={9} fontWeight="900" className="drop-shadow-md">
        {id.length > 14 ? id.slice(0, 13) + '...' : id}
      </text>

      {/* Lifecycle Status Text Overlay */}
      <text y={size + 27} textAnchor="middle" fill={isMbbTarget ? '#f59e0b' : isMbbOld ? '#ec4899' : '#64748b'} fontSize={8} fontWeight="855" className="uppercase tracking-wider">
        {statusLabel}
      </text>
      
      {!isMbbTarget && !isMbbOld && (
        <g 
          onClick={() => onDelete(id)} 
          style={{ cursor: 'pointer' }} 
          transform={`translate(${size}, ${-size})`}
          className="hover:scale-110 transition-transform"
        >
          <circle r={8} fill="#ef4444" stroke="#ffffff" strokeWidth={1} />
          <text y={2.5} textAnchor="middle" fill="white" fontSize={8} fontWeight="900">×</text>
        </g>
      )}
    </g>
  );
};
