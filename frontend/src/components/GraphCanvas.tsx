// Domain-agnostic SVG graph canvas with grid, zoom/pan, heatmap toggle,
// proof path highlighting, type legend, and depth display.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ApiEdge } from '../lib/api';
import type { LayoutNode } from '../stores/graphStore';
import { useGraphStore } from '../stores/graphStore';
import { useThemeStore } from '../stores/themeStore';
import { ZoomIn, ZoomOut, Maximize2, Layers, Eye, GitBranch, X, Boxes, Sparkles, ChevronDown, ChevronUp, Info, BarChart3 } from 'lucide-react';

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

// Node border (unselected/non-hovered) and fill are tuned by lightness for
// each theme: dark mode wants a near-black fill with a subtly lighter border;
// light mode mirrors that with a near-white pastel fill and a slightly darker
// border, so nodes keep the same "tinted but subtle" read in both themes.
function typeColorDark(type: string, isLight: boolean): string {
  return `hsl(${hashHue(type)}, 30%, ${isLight ? 78 : 18}%)`;
}

// UI_REFACTOR_PLAN.md node polish: a subtly type-tinted fill for the node's
// own circle (not just its border), so every node reads as "belonging" to
// its type even before selection or activation -- mirrors the reference
// mockup's per-type-tinted node fills instead of one flat color for every
// unselected node.
function typeColorFill(type: string, isLight: boolean): string {
  return `hsl(${hashHue(type)}, 45%, ${isLight ? 92 : 8}%)`;
}

// UI_PLAN.md §9.5.2: same hash-hue approach applied to communityId (a number,
// not a string) so "color by community" mode reuses the same visual language
// as domain-agnostic type coloring, just keyed on a different node attribute.
function communityColor(communityId: number): string {
  return `hsl(${hashHue(String(communityId))}, 55%, 55%)`;
}

function communityColorDark(communityId: number, isLight: boolean): string {
  return `hsl(${hashHue(String(communityId))}, 30%, ${isLight ? 78 : 18}%)`;
}

function communityColorFill(communityId: number, isLight: boolean): string {
  return `hsl(${hashHue(String(communityId))}, 45%, ${isLight ? 92 : 8}%)`;
}

// plans/analytical-engine.md Slice 9: same hash-hue-function shape as
// community coloring, but centralityScore is continuous (not a discrete id
// to hash) -- interpolates hue from blue (low) to red (high) instead.
function centralityHue(score: number): number {
  const t = Math.min(Math.max(score, 0), 1);
  return 220 - t * 220;
}

function centralityColor(score: number): string {
  return `hsl(${centralityHue(score)}, 55%, 55%)`;
}

function centralityColorDark(score: number, isLight: boolean): string {
  return `hsl(${centralityHue(score)}, 30%, ${isLight ? 78 : 18}%)`;
}

function centralityColorFill(score: number, isLight: boolean): string {
  return `hsl(${centralityHue(score)}, 45%, ${isLight ? 92 : 8}%)`;
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
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [legendCollapsed, setLegendCollapsed] = useState(false);
  const {
    zoom, pan, setZoom, setPan, showHeatmap, showProofPath, toggleHeatmap, toggleProofPath,
    linkMode, linkSourceId, setLinkMode, handleCanvasNodeClick,
    pendingFacts, approvedFacts, showCommunities, detectingCommunities, detectCommunities, toggleCommunities,
    showCentrality, toggleCentrality,
  } = useGraphStore();
  const isLight = useThemeStore((s) => s.theme === 'light');
  // Neutral canvas tones aren't Tailwind classes (raw SVG attributes), so they
  // need an explicit light/dark pair here -- everything else in this file
  // re-themes for free via the CSS-variable-backed zinc palette. Accent hues
  // (sky/amber) are deliberately unchanged in both themes.
  const gridStroke = isLight ? '#d4d4d9' : '#27272a';
  const arrowDefault = isLight ? '#8d8d94' : '#52525b';
  const strongNeutral = isLight ? '#1a1a1d' : '#fff';
  const pillFillActive = isLight ? '#d4d4d9' : '#27272a';
  const pillFillDefault = isLight ? '#fafafb' : '#09090b';
  const pillFillProof = isLight ? '#e0f2fe' : '#082f49';
  const pillTextProof = isLight ? '#075985' : '#bae6fd';
  const implicitMarkerRing = isLight ? '#d4d4d9' : '#18181b';

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
          <pattern id="grid" width={32} height={32} patternUnits="userSpaceOnUse" patternTransform={`translate(${pan.x % (32 * zoom)}, ${pan.y % (32 * zoom)}) scale(${zoom})`}>
            <path d="M 32 0 L 0 0 0 32" fill="none" stroke={gridStroke} strokeWidth={1} opacity={0.35} />
          </pattern>
          <marker id="arrow" viewBox="0 0 10 10" refX={24} refY={5} markerWidth={6} markerHeight={6} orient="auto">
            <path d="M 0 0 L 10 5 L 0 10 z" fill={arrowDefault} />
          </marker>
          <marker id="arrow-active" viewBox="0 0 10 10" refX={24} refY={5} markerWidth={6} markerHeight={6} orient="auto">
            <path d="M 0 0 L 10 5 L 0 10 z" fill={strongNeutral} />
          </marker>
          <marker id="arrow-proof" viewBox="0 0 10 10" refX={24} refY={5} markerWidth={6} markerHeight={6} orient="auto">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#0ea5e9" />
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

          {/* Edges. Relation-type coloring and the pill-badge label overlay are
              hash-hue based (same `typeColor`/`typeColorFill` used for nodes),
              not a hardcoded per-relation-name palette -- this stays correct
              for whatever ontology is loaded, not just one domain's edge names. */}
          {edges.map((edge) => {
            const source = byId.get(edge.source);
            const target = byId.get(edge.target);
            if (!source || !target) return null;
            const isActive = (source.activation ?? 0) > 0.01 || (target.activation ?? 0) > 0.01;
            const isProof = proofEdgeTypes.has(edge.type);
            const midX = (source.x + target.x) / 2;
            const midY = (source.y + target.y) / 2;
            const relationColor = typeColor(edge.type);
            const strokeColor = isProof ? '#38bdf8' : isActive ? strongNeutral : relationColor;
            const markerEnd = isProof ? 'url(#arrow-proof)' : isActive ? 'url(#arrow-active)' : 'url(#arrow)';
            const pillWidth = Math.max(52, edge.type.length * 5.8 + 12);
            const pillHeight = 15;
            return (
              <g key={edge.id}>
                {/* Glow underlay for active/proof edges */}
                {(isProof || isActive) && (
                  <line
                    x1={source.x} y1={source.y} x2={target.x} y2={target.y}
                    stroke={isProof ? '#38bdf8' : strongNeutral}
                    strokeWidth={isProof ? 4 : 3}
                    opacity={isProof ? 0.15 : 0.08}
                    className="pointer-events-none"
                  />
                )}

                <line
                  x1={source.x} y1={source.y} x2={target.x} y2={target.y}
                  stroke={strokeColor}
                  strokeWidth={isProof ? 1.75 : isActive ? 1.5 : 1}
                  opacity={isProof ? 1 : isActive ? 0.9 : 0.55}
                  strokeDasharray={isProof ? '5 3' : isActive ? '3 3' : undefined}
                  markerEnd={markerEnd}
                >
                  {(isProof || isActive) && (
                    <animate attributeName="stroke-dashoffset" values="60;0" dur={isProof ? '2.5s' : '4s'} repeatCount="indefinite" />
                  )}
                </line>

                {/* Pill/badge overlay for the relation label -- isolates the text
                    from the grid/intersecting lines behind it, unlike bare text
                    floating directly on the canvas. */}
                <g transform={`translate(${midX}, ${midY})`} className="pointer-events-none">
                  <rect
                    x={-pillWidth / 2}
                    y={-pillHeight / 2}
                    width={pillWidth}
                    height={pillHeight}
                    rx={6}
                    fill={isProof ? pillFillProof : isActive ? pillFillActive : pillFillDefault}
                    stroke={isProof ? '#38bdf8' : isActive ? strongNeutral : relationColor}
                    strokeWidth={1.2}
                    strokeOpacity={isProof || isActive ? 0.9 : 0.6}
                  />
                  <text
                    y={0}
                    dominantBaseline="central"
                    textAnchor="middle"
                    style={{ fill: isProof ? pillTextProof : isActive ? strongNeutral : relationColor }}
                    className="text-[8.5px] font-mono font-bold tracking-wider select-none"
                  >
                    {edge.type}
                  </text>
                </g>
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
            const hasCentrality = showCentrality && node.centralityScore != null;
            const hasCommunity = showCommunities && node.communityId != null;
            const color = hasCentrality ? centralityColor(node.centralityScore!) : hasCommunity ? communityColor(node.communityId!) : typeColor(node.type);
            const darkColor = hasCentrality ? centralityColorDark(node.centralityScore!, isLight) : hasCommunity ? communityColorDark(node.communityId!, isLight) : typeColorDark(node.type, isLight);
            const fillColor = hasCentrality ? centralityColorFill(node.centralityScore!, isLight) : hasCommunity ? communityColorFill(node.communityId!, isLight) : typeColorFill(node.type, isLight);
            const isHovered = node.id === hoveredId;
            const r = 20;
            const activation = node.activation ?? 0;
            const glowOpacity = Math.min(activation, 1);
            return (
              <g
                key={node.id}
                transform={`translate(${node.x}, ${node.y})`}
                onMouseDown={(e) => handleMouseDown(e, node)}
                onClick={(e) => { e.stopPropagation(); onSelectNode(node.id); }}
                onMouseEnter={() => setHoveredId(node.id)}
                onMouseLeave={() => setHoveredId((id) => (id === node.id ? null : id))}
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
                  <circle r={r + 13} fill="none" stroke="#38bdf8" strokeWidth={1.5} strokeDasharray="4 3" opacity={0.7} className="pointer-events-none" />
                )}

                {/* Selection halo: a distinct ring (separate from the activation glow,
                    derived-fact pulse, and proof-path dashed ring above) at the node's
                    own type/community color, so "selected" reads clearly at a glance --
                    kept mounted and cross-fades via opacity rather than conditionally
                    rendered, for a smooth transition on click. */}
                <circle
                  r={r + 6}
                  fill="none"
                  stroke={color}
                  strokeWidth={1.5}
                  opacity={isSelected ? 0.55 : 0}
                  className="pointer-events-none transition-opacity duration-200"
                />
                {/* Hover ring: same treatment, one step in from the selection halo, only
                    shown for a non-selected node under the pointer -- the only hover
                    affordance nodes had before was the cursor changing to a pointer. */}
                <circle
                  r={r + 4}
                  fill="none"
                  stroke={color}
                  strokeWidth={1}
                  opacity={isHovered && !isSelected ? 0.45 : 0}
                  className="pointer-events-none transition-opacity duration-150"
                />

                {/* UI_REFACTOR_PLAN.md §4: implicit-fact marker, distinct from `derived`
                    (amber) -- folded into the sky "structural/explain" role since an
                    implicit fact is itself a kind of derivation, same as proof-path. */}
                {hasImplicitFact && (
                  <g transform={`translate(${r - 4}, ${-r + 4})`} className="pointer-events-none">
                    <circle r={6} fill="#38bdf8" stroke={implicitMarkerRing} strokeWidth={1.5} />
                    <text y={2.5} textAnchor="middle" className="fill-onaccent text-[7px] font-bold select-none">✦</text>
                  </g>
                )}

                <circle
                  r={r}
                  fill={isSelected ? color : fillColor}
                  stroke={isSelected || isLinkSource ? strongNeutral : isHovered ? color : darkColor}
                  strokeWidth={isSelected ? 0 : isLinkSource ? 2.5 : isHovered ? 2 : 1.5}
                  opacity={isSelected ? 1 : 0.95}
                  className="transition-colors duration-150"
                />

                <text y={r + 15} textAnchor="middle" className={`text-[10px] font-semibold pointer-events-none select-none ${isSelected || isHovered ? 'fill-white' : 'fill-zinc-300'}`}>
                  {node.label}
                </text>
                <text y={r + 27} textAnchor="middle" fill={color} opacity={0.8} className="text-[8px] font-mono pointer-events-none select-none">
                  {node.type}
                </text>

                {activation > 0.01 && (
                  // Unselected nodes' own fill is near-black in dark theme (typeColorFill,
                  // 8% lightness) -- fixed-dark badgeink text was invisible against it.
                  // Selected nodes' fill is mid-lightness (~55%) in both themes, and
                  // unselected fill is light (92%) in light theme -- badgeink stays
                  // readable there, so only the unselected+dark case needs white text.
                  <text
                    y={4}
                    textAnchor="middle"
                    className={`text-[9px] font-bold pointer-events-none select-none ${
                      !isSelected && !isLight ? 'fill-white' : 'fill-badgeink'
                    }`}
                  >
                    {(activation * 100).toFixed(0)}
                  </text>
                )}

                {node.derived && (
                  <g transform={`translate(0, ${-r - 12})`}>
                    <rect x={-26} y={-7} width={52} height={14} rx={7} fill="#fbbf24" className="pointer-events-none" />
                    <text y={3} textAnchor="middle" className="fill-badgeink text-[8px] font-bold pointer-events-none select-none">
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

      {/* Interaction hint, top-left */}
      <div className="absolute top-3 left-3 z-10 flex items-center gap-2 px-2.5 py-1.5 rounded bg-zinc-900/90 border border-zinc-800/80 text-[10px] text-zinc-400">
        <Info className="w-3.5 h-3.5 text-blue-400 shrink-0" />
        <span>Click nodes to select. Hold drag to pan. Zoom with sidebar toolbar or scroll wheel.</span>
      </div>

      {/* Canvas controls: floating pill, bottom-center, horizontal */}
      <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-1 p-1 rounded-lg bg-zinc-900/90 backdrop-blur border border-zinc-800 shadow-lg">
        <button onClick={() => setZoom(zoom * 1.2)} className="w-7 h-7 rounded flex items-center justify-center text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors" title="Zoom in">
          <ZoomIn className="w-3.5 h-3.5" />
        </button>
        <button onClick={() => setZoom(zoom / 1.2)} className="w-7 h-7 rounded flex items-center justify-center text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors" title="Zoom out">
          <ZoomOut className="w-3.5 h-3.5" />
        </button>
        <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }} className="w-7 h-7 rounded flex items-center justify-center text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors" title="Reset view">
          <Maximize2 className="w-3.5 h-3.5" />
        </button>
        <div className="w-px h-5 bg-zinc-800 mx-0.5" />
        <button
          onClick={toggleHeatmap}
          className={`w-7 h-7 rounded flex items-center justify-center transition-colors ${
            showHeatmap ? 'bg-amber-400/20 text-amber-400' : 'text-zinc-500 hover:text-white hover:bg-zinc-800'
          }`}
          title="Toggle heatmap"
        >
          <Layers className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={toggleProofPath}
          className={`w-7 h-7 rounded flex items-center justify-center transition-colors ${
            showProofPath ? 'bg-sky-400/20 text-sky-400' : 'text-zinc-500 hover:text-white hover:bg-zinc-800'
          }`}
          title="Toggle proof path"
        >
          <Eye className="w-3.5 h-3.5" />
        </button>
        <div className="w-px h-5 bg-zinc-800 mx-0.5" />
        <button
          onClick={() => void detectCommunities()}
          disabled={detectingCommunities || nodes.length === 0}
          className="w-7 h-7 rounded flex items-center justify-center transition-colors text-zinc-500 hover:text-white hover:bg-zinc-800 disabled:opacity-40"
          title="Detect communities (Louvain)"
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
            className={`w-7 h-7 rounded flex items-center justify-center transition-colors ${
              showCommunities ? 'bg-blue-400/20 text-blue-400' : 'text-zinc-500 hover:text-white hover:bg-zinc-800'
            }`}
            title="Toggle color by community"
          >
            <GitBranch className="w-3.5 h-3.5 rotate-90" />
          </button>
        )}
        {nodes.some((n) => n.centralityScore != null) && (
          <button
            onClick={toggleCentrality}
            className={`w-7 h-7 rounded flex items-center justify-center transition-colors ${
              showCentrality ? 'bg-violet-400/20 text-violet-400' : 'text-zinc-500 hover:text-white hover:bg-zinc-800'
            }`}
            title="Toggle color by centrality score"
          >
            <BarChart3 className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Type / Community legend + zoom indicator, stacked bottom-right.
          The legend is collapsible (chevron toggle) so it can be tucked out
          of the way without losing the zoom%, which always stays visible. */}
      <div className="absolute bottom-3 right-3 flex flex-col items-end gap-1.5">
        {showCommunities && uniqueCommunities.length > 0 ? (
          <div className="bg-zinc-900/90 border border-zinc-800 rounded max-w-44">
            <button
              onClick={() => setLegendCollapsed((v) => !v)}
              className="w-full flex items-center justify-between gap-2 p-2 text-[9px] text-zinc-300 uppercase tracking-wider font-bold"
            >
              <span className="flex items-center gap-1">
                <Boxes className="w-2.5 h-2.5" /> Communities
              </span>
              {legendCollapsed ? <ChevronUp className="w-3 h-3 text-zinc-500" /> : <ChevronDown className="w-3 h-3 text-zinc-500" />}
            </button>
            {!legendCollapsed && (
              <div className="space-y-1 px-2 pb-2">
                {uniqueCommunities.map(([id, count]) => (
                  <div key={id} className="flex items-center gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: communityColor(id) }} />
                    <span className="text-[9px] text-zinc-400 truncate">Community {id} ({count})</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          uniqueTypes.length > 0 && (
            <div className="bg-zinc-900/90 border border-zinc-800 rounded max-w-40">
              <button
                onClick={() => setLegendCollapsed((v) => !v)}
                className="w-full flex items-center justify-between gap-2 p-2 text-[9px] text-zinc-500 uppercase tracking-wider font-bold"
              >
                <span>Types</span>
                {legendCollapsed ? <ChevronUp className="w-3 h-3 text-zinc-500" /> : <ChevronDown className="w-3 h-3 text-zinc-500" />}
              </button>
              {!legendCollapsed && (
                <div className="space-y-1 px-2 pb-2">
                  {uniqueTypes.map((t) => (
                    <div key={t} className="flex items-center gap-1.5">
                      <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: typeColor(t) }} />
                      <span className="text-[9px] text-zinc-400 truncate">{t}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        )}

        <div className="text-[10px] text-zinc-600 font-mono">{(zoom * 100).toFixed(0)}%</div>
      </div>

      {/* Implicit-fact legend note, only when relevant */}
      {implicitFactNodeIds.size > 0 && (
        <div className="absolute bottom-3 left-3 bg-zinc-900/90 border border-zinc-800 rounded px-2 py-1.5 flex items-center gap-1.5">
          <Sparkles className="w-3 h-3 text-sky-400" />
          <span className="text-[9px] text-zinc-400">{implicitFactNodeIds.size} node{implicitFactNodeIds.size === 1 ? '' : 's'} with implicit facts</span>
        </div>
      )}
    </div>
  );
}
