import { useRef, useEffect, useState } from 'react';
import type { GraphNode, GraphEdge } from '../types';
import { KIND_COLORS } from '../lib/graph-data';

interface GraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId: string | null;
  linkMode: string | null;
  linkSource: string | null;
  heatmapOn: boolean;
  showProofPaths: boolean;
  pathHighlight: string[] | null;
  onSelectNode: (id: string) => void;
  onMoveNode: (id: string, x: number, y: number) => void;
}

export function GraphCanvas({ nodes, edges, selectedNodeId, linkMode, linkSource, heatmapOn, showProofPaths, pathHighlight, onSelectNode, onMoveNode }: GraphCanvasProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  useEffect(() => {
    if (!draggingId) return;
    const handleMove = (e: MouseEvent) => {
      if (!svgRef.current) return;
      const rect = svgRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left - dragOffset.x;
      const y = e.clientY - rect.top - dragOffset.y;
      onMoveNode(draggingId, x, y);
    };
    const handleUp = () => setDraggingId(null);
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
  }, [draggingId, dragOffset, onMoveNode]);

  const handleMouseDown = (e: React.MouseEvent, node: GraphNode) => {
    e.stopPropagation();
    if (linkMode) {
      onSelectNode(node.id);
      return;
    }
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    setDragOffset({ x: e.clientX - rect.left - node.x, y: e.clientY - rect.top - node.y });
    setDraggingId(node.id);
    onSelectNode(node.id);
  };

  const handleBgClick = () => {
    if (!linkMode) onSelectNode('');
  };

  const getActivationColor = (activation: number): string => {
    if (activation <= 0) return 'transparent';
    const intensity = Math.min(activation, 1);
    if (intensity > 0.5) {
      const t = (intensity - 0.5) / 0.5;
      const r = Math.round(251 + (255 - 251) * t);
      const g = Math.round(191 + (255 - 191) * t);
      const b = Math.round(36 + (255 - 36) * t);
      return `rgba(${r}, ${g}, ${b}, ${0.15 + intensity * 0.25})`;
    } else {
      const t = intensity / 0.5;
      const r = Math.round(39 + (251 - 39) * t);
      const g = Math.round(39 + (191 - 39) * t);
      const b = Math.round(39 + (36 - 42) * t);
      return `rgba(${r}, ${g}, ${b}, ${0.05 + intensity * 0.2})`;
    }
  };

  const pathSet = new Set(pathHighlight || []);
  const proofPathEdges = new Set<string>();
  if (showProofPaths) {
    for (const node of nodes) {
      if (node.proofPath && node.proofPath.length > 0) {
        for (const edge of edges) {
          const source = nodes.find((n) => n.id === edge.source);
          const target = nodes.find((n) => n.id === edge.target);
          if (!source || !target) continue;
          for (const step of node.proofPath) {
            if (step.sourceLabel === source.label && step.targetLabel === target.label && step.edgeLabel === edge.label) {
              proofPathEdges.add(edge.id);
            }
          }
        }
      }
    }
  }

  return (
    <svg ref={svgRef} className="w-full h-full" onClick={handleBgClick}>
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#52525b" />
        </marker>
        <marker id="arrow-active" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#fff" />
        </marker>
        <marker id="arrow-derived" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#fbbf24" />
        </marker>
        <marker id="arrow-proof" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#a78bfa" />
        </marker>
        <marker id="arrow-path" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#22d3ee" />
        </marker>
      </defs>

      <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
        <circle cx="0" cy="0" r="1" fill="#27272a" />
      </pattern>
      <rect width="100%" height="100%" fill="url(#grid)" />

      {heatmapOn && nodes.map((node) => {
        if (node.activation <= 0.01) return null;
        return (
          <circle key={`heat-${node.id}`} cx={node.x} cy={node.y} r={70} fill={getActivationColor(node.activation)} className="pointer-events-none" />
        );
      })}

      {edges.map((edge) => {
        const source = nodes.find((n) => n.id === edge.source);
        const target = nodes.find((n) => n.id === edge.target);
        if (!source || !target) return null;
        const isActive = source.activation > 0.01 || target.activation > 0.01;
        const isDerived = target.derived && target.derivedFrom?.includes(`fact-${edge.label}-${edge.id}`);
        const isProofPath = proofPathEdges.has(edge.id);
        const isPathHighlight = pathSet.has(edge.id);
        const midX = (source.x + target.x) / 2;
        const midY = (source.y + target.y) / 2;

        let stroke = '#3f3f46';
        let strokeWidth = 1;
        let marker = 'url(#arrow)';
        let opacity = 0.5;

        if (isPathHighlight) {
          stroke = '#22d3ee';
          strokeWidth = 3.5;
          marker = 'url(#arrow-path)';
          opacity = 1;
        } else if (isProofPath) {
          stroke = '#a78bfa';
          strokeWidth = 3;
          marker = 'url(#arrow-proof)';
          opacity = 0.9;
        } else if (isDerived) {
          stroke = '#fbbf24';
          strokeWidth = 2.5;
          marker = 'url(#arrow-derived)';
          opacity = 0.9;
        } else if (isActive) {
          stroke = '#fff';
          strokeWidth = 2;
          marker = 'url(#arrow-active)';
          opacity = 0.8;
        }

        return (
          <g key={edge.id}>
            <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} stroke={stroke} strokeWidth={strokeWidth} markerEnd={marker} opacity={opacity} />
            <text x={midX} y={midY - 6} textAnchor="middle" className="fill-zinc-600 text-[9px] pointer-events-none select-none">
              {edge.label}
            </text>
          </g>
        );
      })}

      {nodes.map((node) => {
        const isSelected = node.id === selectedNodeId;
        const isLinkSource = node.id === linkSource;
        const isInPath = pathHighlight?.includes(node.id);
        const r = 18;
        const glowOpacity = Math.min(node.activation, 1);
        const kindHex = KIND_COLORS[node.kind];
        const hasProof = node.proofPath && node.proofPath.length > 0;
        return (
          <g key={node.id} transform={`translate(${node.x}, ${node.y})`} onMouseDown={(e) => handleMouseDown(e, node)} onClick={(e) => { e.stopPropagation(); onSelectNode(node.id); }} style={{ cursor: 'pointer' }}>
            {node.activation > 0.01 && (
              <>
                <circle r={r + 16} fill={kindHex} opacity={glowOpacity * 0.08} className="pointer-events-none" />
                <circle r={r + 10} fill={kindHex} opacity={glowOpacity * 0.15} className="pointer-events-none" />
                <circle r={r + 5} fill={kindHex} opacity={glowOpacity * 0.25} className="pointer-events-none" />
              </>
            )}

            {node.derived && (
              <circle r={r + 7} fill="none" stroke="#fbbf24" strokeWidth={2.5} opacity={0.9} className="pointer-events-none">
                <animate attributeName="r" values={`${r + 5};${r + 9};${r + 5}`} dur="2s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.9;0.4;0.9" dur="2s" repeatCount="indefinite" />
              </circle>
            )}

            {hasProof && showProofPaths && (
              <circle r={r + 11} fill="none" stroke="#a78bfa" strokeWidth={1.5} strokeDasharray="4 3" opacity={0.7} className="pointer-events-none" />
            )}

            {isInPath && (
              <circle r={r + 9} fill="none" stroke="#22d3ee" strokeWidth={2} opacity={0.8} className="pointer-events-none">
                <animate attributeName="r" values={`${r + 7};${r + 11};${r + 7}`} dur="1.5s" repeatCount="indefinite" />
              </circle>
            )}

            <circle r={r} fill={isSelected ? kindHex : '#18181b'} stroke={isSelected ? '#fff' : isLinkSource ? '#fff' : isInPath ? '#22d3ee' : kindHex} strokeWidth={isSelected ? 0 : 2} opacity={isSelected ? 1 : 0.9} />

            <text y={r + 14} textAnchor="middle" className={`text-[10px] font-medium pointer-events-none select-none ${isSelected ? 'fill-white' : 'fill-zinc-300'}`}>
              {node.label}
            </text>

            {node.activation > 0.01 && (
              <text y={4} textAnchor="middle" className="fill-black text-[9px] font-bold pointer-events-none select-none">
                {(node.activation * 100).toFixed(0)}
              </text>
            )}

            {node.derived && (
              <g transform={`translate(0, ${-r - 12})`}>
                <rect x={-26} y={-7} width={52} height={14} rx={7} fill="#fbbf24" className="pointer-events-none" />
                <text y={3} textAnchor="middle" className="fill-black text-[8px] font-bold pointer-events-none select-none">
                  DERIVED
                </text>
              </g>
            )}

            {node.depth > 0 && node.activation > 0.01 && (
              <text y={r + 26} textAnchor="middle" className="fill-zinc-600 text-[8px] pointer-events-none select-none">
                depth {node.depth}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}