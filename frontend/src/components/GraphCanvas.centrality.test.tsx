import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { GraphCanvas } from './GraphCanvas';
import { useGraphStore } from '../stores/graphStore';
import { useThemeStore } from '../stores/themeStore';

vi.mock('../stores/graphStore', () => ({ useGraphStore: vi.fn() }));
vi.mock('../stores/themeStore', () => ({ useThemeStore: vi.fn() }));

const mockedUseGraphStore = vi.mocked(useGraphStore);
const mockedUseThemeStore = vi.mocked(useThemeStore);

function baseStore(overrides: Record<string, unknown> = {}) {
  return {
    zoom: 1, pan: { x: 0, y: 0 }, setZoom: vi.fn(), setPan: vi.fn(),
    showHeatmap: false, showProofPath: false, toggleHeatmap: vi.fn(), toggleProofPath: vi.fn(),
    linkMode: false, linkSourceId: null, setLinkMode: vi.fn(), handleCanvasNodeClick: vi.fn(),
    pendingFacts: [], approvedFacts: [],
    showCommunities: false, detectingCommunities: false, detectCommunities: vi.fn(), toggleCommunities: vi.fn(),
    showCentrality: false, toggleCentrality: vi.fn(),
    ...overrides,
  };
}

const NODE = { id: 'n1', label: 'Hub Corp', type: 'organization', x: 100, y: 100, centralityScore: 0.9 };

function renderCanvas(storeOverrides: Record<string, unknown>) {
  mockedUseGraphStore.mockReturnValue(baseStore(storeOverrides) as unknown as ReturnType<typeof useGraphStore>);
  mockedUseThemeStore.mockImplementation((selector) => selector({ theme: 'dark', setTheme: vi.fn(), toggleTheme: vi.fn() }));
  const { container } = render(
    <GraphCanvas nodes={[NODE]} edges={[]} selectedNodeId={null} onSelectNode={vi.fn()} onMoveNode={vi.fn()} />,
  );
  return container.querySelector('circle[fill]:last-of-type') as SVGCircleElement;
}

describe('GraphCanvas centrality coloring', () => {
  it('colors a node by type (unchanged) when showCentrality is off', () => {
    const circle = renderCanvas({ showCentrality: false });
    expect(circle.getAttribute('fill')).toMatch(/^hsl\(/);
  });

  it('colors a node differently by centralityScore when showCentrality is on', () => {
    const typeColored = renderCanvas({ showCentrality: false });
    const centralityColored = renderCanvas({ showCentrality: true });

    expect(centralityColored.getAttribute('fill')).not.toBe(typeColored.getAttribute('fill'));
  });

  it('falls back to type coloring for a node with no centralityScore even when showCentrality is on', () => {
    mockedUseGraphStore.mockReturnValue(baseStore({ showCentrality: true }) as unknown as ReturnType<typeof useGraphStore>);
    mockedUseThemeStore.mockImplementation((selector) => selector({ theme: 'dark', setTheme: vi.fn(), toggleTheme: vi.fn() }));
    const nodeWithoutScore = { id: 'n2', label: 'No Score', type: 'organization', x: 50, y: 50 };
    const { container: withScore } = render(
      <GraphCanvas nodes={[NODE]} edges={[]} selectedNodeId={null} onSelectNode={vi.fn()} onMoveNode={vi.fn()} />,
    );
    const { container: withoutScore } = render(
      <GraphCanvas nodes={[nodeWithoutScore]} edges={[]} selectedNodeId={null} onSelectNode={vi.fn()} onMoveNode={vi.fn()} />,
    );

    const scoredFill = withScore.querySelector('circle[fill]:last-of-type')?.getAttribute('fill');
    const unscoredFill = withoutScore.querySelector('circle[fill]:last-of-type')?.getAttribute('fill');
    // Same type ('organization'), no score -> falls back to the same type color
    // a plain type-colored node would get.
    const typeOnlyFill = renderCanvas({ showCentrality: false }).getAttribute('fill');
    expect(unscoredFill).toBe(typeOnlyFill);
    expect(scoredFill).not.toBe(unscoredFill);
  });
});
