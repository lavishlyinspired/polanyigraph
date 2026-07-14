import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AnalyticsPage } from './AnalyticsPage';
import { api } from '../../lib/api';
import { useGraphStore } from '../../stores/graphStore';

vi.mock('../../stores/graphStore', () => ({
  useGraphStore: vi.fn(),
}));

vi.mock('../../lib/api', () => ({
  api: {
    listAlgorithms: vi.fn(),
    createProjection: vi.fn(),
    runAlgorithm: vi.fn(),
    persistAlgorithmResult: vi.fn(),
  },
}));

const mockedUseGraphStore = vi.mocked(useGraphStore);
const mockedApi = vi.mocked(api);

function setupStore(graphId = 'g1') {
  mockedUseGraphStore.mockReturnValue({ graphId } as unknown as ReturnType<typeof useGraphStore>);
}

afterEach(() => {
  vi.clearAllMocks();
});

describe('AnalyticsPage', () => {
  it('lists available algorithms on mount', async () => {
    setupStore();
    mockedApi.listAlgorithms.mockResolvedValue({
      algorithms: [
        { name: 'degree_centrality', category: 'centrality', params: {} },
        { name: 'pagerank', category: 'centrality', params: { alpha: 0.85 } },
      ],
    });

    render(<AnalyticsPage />);

    expect(await screen.findByText('degree_centrality')).toBeInTheDocument();
    expect(screen.getByText('pagerank')).toBeInTheDocument();
  });

  it('runs the selected algorithm and shows ranked results', async () => {
    setupStore();
    mockedApi.listAlgorithms.mockResolvedValue({
      algorithms: [{ name: 'degree_centrality', category: 'centrality', params: {} }],
    });
    mockedApi.createProjection.mockResolvedValue({ name: 'g1', graphId: 'g1', nodeCount: 2, edgeCount: 1 });
    mockedApi.runAlgorithm.mockResolvedValue({
      algorithm: 'degree_centrality',
      projection: 'g1',
      nodeScores: { hub: 0.8, leaf: 0.2 },
      suggestedChart: 'bar',
    });

    render(<AnalyticsPage />);
    await screen.findByText('degree_centrality');

    await userEvent.click(screen.getByRole('button', { name: /run/i }));

    await waitFor(() => expect(mockedApi.createProjection).toHaveBeenCalledWith('g1'));
    expect(mockedApi.runAlgorithm).toHaveBeenCalledWith('g1', 'degree_centrality');
    expect(await screen.findByText('hub')).toBeInTheDocument();
    expect(screen.getByText('leaf')).toBeInTheDocument();
    expect(screen.getByText('0.800')).toBeInTheDocument();

    // hub (0.8) must be ranked before leaf (0.2), highest score first
    const rows = screen.getAllByRole('row').slice(1); // drop header row
    const rowText = rows.map((r) => r.textContent);
    expect(rowText[0]).toContain('hub');
    expect(rowText[1]).toContain('leaf');
  });

  it('offers write-back after a successful run, and calls persist when clicked', async () => {
    setupStore();
    mockedApi.listAlgorithms.mockResolvedValue({
      algorithms: [{ name: 'degree_centrality', category: 'centrality', params: {} }],
    });
    mockedApi.createProjection.mockResolvedValue({ name: 'g1', graphId: 'g1', nodeCount: 1, edgeCount: 0 });
    mockedApi.runAlgorithm.mockResolvedValue({
      algorithm: 'degree_centrality', projection: 'g1', nodeScores: { a: 1 }, suggestedChart: 'bar',
    });
    mockedApi.persistAlgorithmResult.mockResolvedValue({
      projection: 'g1', algorithm: 'degree_centrality', propertyName: 'centralityScore', nodeCount: 1,
    });

    render(<AnalyticsPage />);
    await screen.findByText('degree_centrality');
    await userEvent.click(screen.getByRole('button', { name: /run/i }));
    await screen.findByText('a');

    await userEvent.click(screen.getByRole('button', { name: /write back/i }));

    // Fixed "centralityScore" property name, not per-algorithm -- this is
    // what GraphCanvas.tsx's showCentrality mode and get_graph()'s
    // centralityScore field read back, matching communityId's shared,
    // single-property convention (see graph_service.py's GraphNodeRecord).
    await waitFor(() => expect(mockedApi.persistAlgorithmResult).toHaveBeenCalledWith('g1', 'degree_centrality', 'centralityScore'));
  });

  it('shows a graceful message when the algorithm run fails', async () => {
    setupStore();
    mockedApi.listAlgorithms.mockResolvedValue({
      algorithms: [{ name: 'degree_centrality', category: 'centrality', params: {} }],
    });
    mockedApi.createProjection.mockResolvedValue({ name: 'g1', graphId: 'g1', nodeCount: 1, edgeCount: 0 });
    mockedApi.runAlgorithm.mockRejectedValue(new Error('404 Not Found'));

    render(<AnalyticsPage />);
    await screen.findByText('degree_centrality');
    await userEvent.click(screen.getByRole('button', { name: /run/i }));

    expect(await screen.findByText(/404 not found/i)).toBeInTheDocument();
  });
});
