import { gridAxes, N_LOAD, N_RPM } from './grid';

describe('gridAxes', () => {
  it('spans idle to maximum speed and no load to full load', () => {
    const { rpms, loads } = gridAxes({ idle_rpm: 800, max_rpm: 4600 });
    expect(rpms.length).toBe(N_RPM);
    expect(loads.length).toBe(N_LOAD);
    expect(rpms[0]).toBe(800);
    expect(rpms[N_RPM - 1]).toBe(4600);
    expect(loads[0]).toBe(0);
    expect(loads[N_LOAD - 1]).toBe(1);
  });

  it('uses the same float operations as the native reference (e2e/native_grid.py)', () => {
    // a + (b - a) * i / (n - 1), evaluated left to right, as Python does
    const { rpms } = gridAxes({ idle_rpm: 800, max_rpm: 4600 });
    expect(rpms[3]).toBe(800 + (4600 - 800) * 3 / 7);
  });
});
