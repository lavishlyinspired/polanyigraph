// Domain-agnostic SVG graph canvas with grid, zoom/pan, heatmap toggle,
// proof path highlighting, type legend, and depth display.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ApiEdge } from '../lib/api';
import type { LayoutNode } from '../stores/graphStore';
import { useGraphStore } from '../stores/graphStore';
import { ZoomIn, ZoomOut, Maximize2, Layers, Eye, GitBranch, X, Boxes, Sparkles } from 'lucide-react';

interface GraphCanvasProps {
  nodes: LayoutNode[];
  edges: ApiEdge[];
  selectedNodeId: string | null;
  onSelectNode: (id: string | null) => void;
  onMoveNode: (id: string, x: number, y: number) => void;
}

function hashHue(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i++) hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  return hash % 360;
}

function typeColor(type: string): string {
  return `hsl(${hashHue(type)}, 55%, 55%)`;
}

function typeColorDark(type: string): string {
  return `hsl(${hashHue(type)}, 30%, 18%)`;
}

// UI_PLAN.md §9.5.2: same hash-hue approach applied to communityId (a number,
// not a string) so "color by community" mode reuses the same visual language
// as domain-agnostic type coloring, just keyed on a different node attribute.
function communityColor(communityId: number): string {
  return `hsl(${hashHue(String(communityId))}, 55%, 55%)`;
}

function communityColorDark(communityId: number): string {
  return `hsl(${hashHue(String(communityId))}, 30%, 18%)`;
}

function activationGlow(activation: number): string {
  if (activation <= 0.01) return 'transparent';
  const t = Math.min(activation, 1);
  return `rgba(251, 191, 36, ${0.1 + t * 0.3})`;
}

export function GraphCanvas({ nodes, edges, selectedNodeId, onSelectNode, onMoveNode }: GraphCanvasProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [panning, setPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const {
    zoom, pan, setZoom, setPan, showHeatmap, showProofPath, toggleHeatmap, toggleProofPath,
    linkMode, linkSourceId, setLinkMode, handleCanvasNodeClick,
    pendingFacts, approvedFacts, showCommunities, detectingCommunities, detectCommunities, toggleCommunities,
  } = useGraphStore();

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom(zoom * delta);
  }, [zoom, setZoom]);

  const handleBgMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.target === svgRef.current) {
      setPanning(true);
      setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  }, [pan]);

  useEffect(() => {
    if (!panning) return;
    const handleMove = (e: MouseEvent) => setPan({ x: e.clientX - panStart.x, y: e.clientY - panStart.y });
    const handleUp = () => setPanning(false);
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
  }, [panning, panStart, setPan]);

  useEffect(() => {
    if (!draggingId) return;
    const handleMove = (e: MouseEvent) => {
      if (!svgRef.current) return;
      const rect = svgRef.current.getBoundingClientRect();
      const x = (e.clientX - rect.left - pan.x) / zoom - dragOffset.x;
      const y = (e.clientY - rect.top - pan.y) / zoom - dragOffset.y;
      onMoveNode(draggingId, x, y);
    };
    const handleUp = () => setDraggingId(null);
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
  }, [draggingId, dragOffset, onMoveNode, pan, zoom]);

  const handleMouseDown = (e: React.MouseEvent, node: LayoutNode) => {
    e.stopPropagation();
    if (linkMode) {
      void handleCanvasNodeClick(node.id);
      return;
    }
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const nx = (e.clientX - rect.left - pan.x) / zoom;
    const ny = (e.clientY - rect.top - pan.y) / zoom;
    setDragOffset({ x: nx - node.x, y: ny - node.y });
    setDraggingId(node.id);
    onSelectNode(node.id);
  };

  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  const uniqueTypes = useMemo(() => {
    const set = new Set(nodes.map((n) => n.type));
    return [...set].sort();
  }, [nodes]);

  const uniqueCommunities = useMemo(() => {
    const counts = new Map<number, number>();
    for (const n of nodes) {
      if (n.communityId == null) continue;
      counts.set(n.communityId, (counts.get(n.communityId) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => a[0] - b[0]);
  }, [nodes]);

  // UI_PLAN.md §9.3.4: nodes anchored by a pending or approved implicit fact
  // get a distinct marker, separate from `derived` (an :ImplicitFact is
  // pragmatic/cognitive inference, not a rule-derived fact).
  const implicitFactNodeIds = useMemo(() => {
    const ids = new Set<string>();
    for (const f of [...pendingFacts, ...approvedFacts]) {
      for (const anchorId of f.anchorEntityIds) ids.add(anchorId);
    }
    return ids;
  }, [pendingFacts, approvedFacts]);

  const proofEdgeTypes = useMemo(() => {
    if (!showProofPath) return new Set<string>();
    const types = new Set<string>();
    for (const f of useGraphStore.getState().facts) {
      for (const step of f.proofPath ?? []) types.add(step.edgeType);
    }
    return types;
  }, [showProofPath, nodes]);

  return (
    <div className="relative w-full h-full">
      <svg
        ref={svgRef}
        className="w-full h-full bg-zinc-950"
        onClick={() => onSelectNode(null)}
        onMouseDown={handleBgMouseDown}
        onWheel={handleWheel}
      >
        <defs>
          <pattern id="grid" width={40} height={40} patternUnits="userSpaceOnUse" patternTransform={`translate(${pan.x % (40 * zoom)}, ${pan.y % (40 * zoom)}) scale(${zoom})`}>
            <circle cx={20} cy={20} r={1} fill="#27272a" />
          </pattern>
          <marker id="arrow" viewBox="0 0 10 10" refX={24} refY={5} markerWidth={6} markerHeight={6} orient="auto">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#52525b" />
          </marker>
          <marker id="arrow-active" viewBox="0 0 10 10" refX={24} refY={5} markerWidth={6} markerHeight={6} orient="auto">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#fff" />
          </marker>
          <marker id="arrow-proof" viewBox="0 0 10 10" refX={24} refY={5} markerWidth={6} markerHeight={6} orient="auto">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#8b5cf6" />
          </marker>
        </defs>

        {/* Grid background */}
        <rect width="100%" height="100%" fill="url(#grid)" />

        {/* Transformed content group */}
        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          {/* Heatmap glow circles */}
          {showHeatmap && nodes.map((node) =>
            node.activation && node.activation > 0.01 ? (
              <circle key={`heat-${node.id}`} cx={node.x} cy={node.y} r={60} fill={activationGlow(node.activation)} className="pointer-events-none" />
            ) : null,
          )}

          {/* Edges */}
          {edges.map((edge) => {
            const source = byId.get(edge.source);
            const target = byId.get(edge.target);
            if (!source || !target) return null;
            const isActive = (source.activation ?? 0) > 0.01 || (target.activation ?? 0) > 0.01;
            const isProof = proofEdgeTypes.has(edge.type);
            const midX = (source.x + target.x) / 2;
            const midY = (source.y + target.y) / 2;
            const strokeColor = isProof ? '#8b5cf6' : isActive ? '#fff' : '#3f3f46';
            const markerEnd = isProof ? 'url(#arrow-proof)' : isActive ? 'url(#arrow-active)' : 'url(#arrow)';
            return (
              <g key={edge.id}>
                <line
                  x1={source.x} y1={source.y} x2={target.x} y2={target.y}
                  stroke={strokeColor}
                  strokeWidth={isActive ? 2 : 1}
                  opacity={isProof ? 0.9 : isActive ? 0.8 : 0.5}
                  strokeDasharray={isProof ? '6 3' : undefined}
                  markerEnd={markerEnd}
                />
                <text x={midX} y={midY - 6} textAnchor="middle" className="fill-zinc-600 text-[9px] pointer-events-none select-none">
                  {edge.type}
                </text>
              </g>
            );
          })}

          {/* Nodes */}
          {nodes.map((node) => {
            const isSelected = node.id === selectedNodeId;
            const isLinkSource = node.id === linkSourceId;
            const isProofNode = showProofPath && proofEdgeTypes.size > 0 && edges.some(
              (e) => proofEdgeTypes.has(e.type) && (e.source === node.id || e.target === node.id),
            );
            const hasImplicitFact = implicitFactNodeIds.has(node.id);
            const color = showCommunities && node.communityId != null ? communityColor(node.communityId) : typeColor(node.type);
            const darkColor = showCommunities && node.communityId != null ? communityColorDark(node.communityId) : typeColorDark(node.type);
            const r = 18;
            const activation = node.activation ?? 0;
            const glowOpacity = Math.min(activation, 1);
            return (
              <g
                key={node.id}
                transform={`translate(${node.x}, ${node.y})`}
                onMouseDown={(e) => handleMouseDown(e, node)}
                onClick={(e) => { e.stopPropagation(); onSelectNode(node.id); }}
                style={{ cursor: 'pointer' }}
              >
                {activation > 0.01 && (
                  <>
                    <circle r={r + 16} fill={color} opacity={glowOpacity * 0.08} className="pointer-events-none" />
                    <circle r={r + 10} fill={color} opacity={glowOpacity * 0.15} className="pointer-events-none" />
                    <circle r={r + 5} fill={color} opacity={glowOpacity * 0.25} className="pointer-events-none" />
                  </>
                )}

                {node.derived && (
                  <circle r={r + 7} fill="none" stroke="#fbbf24" strokeWidth={2.5} opacity={0.9} className="pointer-events-none">
                    <animate attributeName="r" values={`${r + 5};${r + 9};${r + 5}`} dur="2s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.9;0.4;0.9" dur="2s" repeatCount="indefinite" />
                  </circle>
                )}

                {isProofNode && (
                  <circle r={r + 11} fill="none" stroke="#a78bfa" strokeWidth={1.5} strokeDasharray="4 3" opacity={0.7} className="pointer-events-none" />
                )}

                {/* UI_PLAN.md §9.3.4: implicit-fact marker, distinct from `derived`
                    (amber) and proof-path (violet dashed) -- violet dot badge. */}
                {hasImplicitFact && (
                  <g transform={`translate(${r - 4}, ${-r + 4})`} className="pointer-events-none">
                    <circle r={6} fill="#a78bfa" stroke="#18181b" strokeWidth={1.5} />
                    <text y={2.5} textAnchor="middle" className="fill-white text-[7px] font-bold select-none">✦</text>
                  </g>
                )}

                <circle
                  r={r}
                  fill={isSelected ? color : '#18181b'}
                  stroke={isSelected || isLinkSource ? '#fff' : darkColor}
                  strokeWidth={isSelected ? 0 : isLinkSource ? 2.5 : 2}
                  opacity={isSelected ? 1 : 0.9}
                />

                <text y={r + 14} textAnchor="middle" className={`text-[10px] font-medium pointer-events-none select-none ${isSelected ? 'fill-white' : 'fill-zinc-300'}`}>
                  {node.label}
                </text>
                <text y={r + 26} textAnchor="middle" className="fill-zinc-600 text-[8px] pointer-events-none select-none">
                  {node.type}
                </text>

                {activation > 0.01 && (
                  <text y={4} textAnchor="middle" className="fill-black text-[9px] font-bold pointer-events-none select-none">
                    {(activation * 100).toFixed(0)}
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
              </g>
            );
          })}
        </g>
      </svg>

      {/* Link mode banner */}
      {linkMode && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 px-4 py-2 rounded-full bg-white text-black text-xs font-medium flex items-center gap-2 shadow-lg">
          <GitBranch className="w-3.5 h-3.5" />
          {linkSourceId ? `Click target node (${linkMode})` : `Click source node (${linkMode})`}
          <button onClick={() => setLinkMode(null)} className="ml-1 hover:opacity-70">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Canvas controls */}
      <div className="absolute top-3 right-3 flex flex-col gap-1">
        <button onClick={() => setZoom(zoom * 1.2)} className="w-7 h-7 bg-zinc-900 border border-zinc-800 rounded flex items-center justify-center text-zinc-400 hover:text-white hover:border-zinc-700 transition-colors" title="Zoom in">
          <ZoomIn className="w-3.5 h-3.5" />
        </button>
        <button onClick={() => setZoom(zoom / 1.2)} className="w-7 h-7 bg-zinc-900 border border-zinc-800 rounded flex items-center justify-center text-zinc-400 hover:text-white hover:border-zinc-700 transition-colors" title="Zoom out">
          <ZoomOut className="w-3.5 h-3.5" />
        </button>
        <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }} className="w-7 h-7 bg-zinc-900 border border-zinc-800 rounded flex items-center justify-center text-zinc-400 hover:text-white hover:border-zinc-700 transition-colors" title="Reset view">
          <Maximize2 className="w-3.5 h-3.5" />
        </button>
        <div className="h-px bg-zinc-800 my-1" />
        <button
          onClick={toggleHeatmap}
          className={`w-7 h-7 rounded flex items-center justify-center transition-colors border ${
            showHeatmap ? 'bg-amber-400/20 border-amber-400/40 text-amber-400' : 'bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-white'
          }`}
          title="Toggle heatmap"
        >
          <Layers className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={toggleProofPath}
          className={`w-7 h-7 rounded flex items-center justify-center transition-colors border ${
            showProofPath ? 'bg-violet-400/20 border-violet-400/40 text-violet-400' : 'bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-white'
          }`}
          title="Toggle proof path"
        >
          <Eye className="w-3.5 h-3.5" />
        </button>
        <div className="h-px bg-zinc-800 my-1" />
        <button
          onClick={() => void detectCommunities()}
          disabled={detectingCommunities || nodes.length === 0}
          className="w-7 h-7 rounded flex items-center justify-center transition-colors border bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-white disabled:opacity-40"
          title="Detect communities (Neo4j GDS Louvain)"
        >
          {detectingCommunities ? (
            <div className="w-3 h-3 border-2 border-zinc-400 border-t-transparent rounded-full animate-spin" />
          ) : (
            <Boxes className="w-3.5 h-3.5" />
          )}
        </button>
        {uniqueCommunities.length > 0 && (
          <button
            onClick={toggleCommunities}
            className={`w-7 h-7 rounded flex items-center justify-center transition-colors border ${
              showCommunities ? 'bg-zinc-800 border-zinc-700 text-zinc-200' : 'bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-white'
            }`}
            title="Toggle color by community"
          >
            <GitBranch className="w-3.5 h-3.5 rotate-90" />
          </button>
        )}
      </div>

      {/* Zoom indicator */}
      <div className="absolute bottom-3 right-3 text-[10px] text-zinc-600 font-mono">
        {(zoom * 100).toFixed(0)}%
      </div>

      {/* Type / Community legend */}
      {showCommunities && uniqueCommunities.length > 0 ? (
        <div className="absolute top-3 left-3 bg-zinc-900/90 border border-zinc-800 rounded p-2 max-w-44">
          <div className="text-[9px] text-zinc-300 uppercase tracking-wider mb-1.5 font-bold flex items-center gap-1">
            <Boxes className="w-2.5 h-2.5" /> Communities
          </div>
          <div className="space-y-1">
            {uniqueCommunities.map(([id, count]) => (
              <div key={id} className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: communityColor(id) }} />
                <span className="text-[9px] text-zinc-400 truncate">Community {id} ({count})</span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        uniqueTypes.length > 0 && (
          <div className="absolute top-3 left-3 bg-zinc-900/90 border border-zinc-800 rounded p-2 max-w-40">
            <div className="text-[9px] text-zinc-500 uppercase tracking-wider mb-1.5 font-bold">Types</div>
            <div className="space-y-1">
              {uniqueTypes.map((t) => (
                <div key={t} className="flex items-center gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: typeColor(t) }} />
                  <span className="text-[9px] text-zinc-400 truncate">{t}</span>
                </div>
              ))}
            </div>
          </div>
        )
      )}

      {/* Implicit-fact legend note, only when relevant */}
      {implicitFactNodeIds.size > 0 && (
        <div className="absolute bottom-3 left-3 bg-zinc-900/90 border border-zinc-800 rounded px-2 py-1.5 flex items-center gap-1.5">
          <Sparkles className="w-3 h-3 text-violet-400" />
          <span className="text-[9px] text-zinc-400">{implicitFactNodeIds.size} node{implicitFactNodeIds.size === 1 ? '' : 's'} with implicit facts</span>
        </div>
      )}
    </div>
  );
}
