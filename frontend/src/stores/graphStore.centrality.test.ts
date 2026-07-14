import { describe, expect, it } from 'vitest';
import { useGraphStore } from './graphStore';

describe('graphStore centrality toggle', () => {
  it('starts with showCentrality false', () => {
    expect(useGraphStore.getState().showCentrality).toBe(false);
  });

  it('toggleCentrality flips showCentrality', () => {
    useGraphStore.getState().toggleCentrality();
    expect(useGraphStore.getState().showCentrality).toBe(true);

    useGraphStore.getState().toggleCentrality();
    expect(useGraphStore.getState().showCentrality).toBe(false);
  });
});
