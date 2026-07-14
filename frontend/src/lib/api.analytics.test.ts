import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';

function mockFetchOnce(body: unknown, ok = true) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 500,
    statusText: ok ? 'OK' : 'Error',
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('analytics API client', () => {
  it('createProjection posts to /analytics/projections/{graphId} with the given name', async () => {
    const fetchMock = mockFetchOnce({ name: 'p1', graphId: 'g1', nodeCount: 3, edgeCount: 2 });

    const result = await api.createProjection('g1', 'p1');

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/analytics/projections/g1',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ name: 'p1' }) }),
    );
    expect(result.nodeCount).toBe(3);
  });

  it('createProjection defaults name to null when omitted', async () => {
    const fetchMock = mockFetchOnce({ name: 'g1', graphId: 'g1', nodeCount: 1, edgeCount: 0 });

    await api.createProjection('g1');

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/analytics/projections/g1',
      expect.objectContaining({ body: JSON.stringify({ name: null }) }),
    );
  });

  it('listAlgorithms fetches /analytics/algorithms', async () => {
    mockFetchOnce({ algorithms: [{ name: 'degree_centrality', category: 'centrality', params: {} }] });

    const result = await api.listAlgorithms();

    expect(result.algorithms).toHaveLength(1);
    expect(result.algorithms[0]?.name).toBe('degree_centrality');
  });

  it('runAlgorithm posts projection and algorithm to /analytics/run', async () => {
    const fetchMock = mockFetchOnce({
      algorithm: 'degree_centrality', projection: 'p1', nodeScores: { a: 0.5 }, suggestedChart: 'bar',
    });

    const result = await api.runAlgorithm('p1', 'degree_centrality');

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/analytics/run',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ projection: 'p1', algorithm: 'degree_centrality' }) }),
    );
    expect(result.suggestedChart).toBe('bar');
    expect(result.nodeScores.a).toBe(0.5);
  });

  it('persistAlgorithmResult posts to /analytics/persist', async () => {
    const fetchMock = mockFetchOnce({ projection: 'p1', algorithm: 'degree_centrality', propertyName: 'centralityScore', nodeCount: 3 });

    await api.persistAlgorithmResult('p1', 'degree_centrality', 'centralityScore');

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/analytics/persist',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ projection: 'p1', algorithm: 'degree_centrality', propertyName: 'centralityScore' }),
      }),
    );
  });

  it('dropProjection issues a DELETE to /analytics/projections/{name}', async () => {
    const fetchMock = mockFetchOnce({ dropped: true });

    await api.dropProjection('p1');

    expect(fetchMock).toHaveBeenCalledWith('/api/analytics/projections/p1', expect.objectContaining({ method: 'DELETE' }));
  });

  it('propagates a non-ok response as an error, matching the existing json() helper convention', async () => {
    mockFetchOnce({ detail: 'Unknown projection' }, false);

    await expect(api.runAlgorithm('does-not-exist', 'degree_centrality')).rejects.toThrow();
  });
});
