# Capacity probe: what one more slot a day gains (M8-4)

Script: `docs/evidence_checks/capacity_probe.py`. Same method as the dashboard's table (add one slot a day to one resource through `resource_overrides`, same patients), run on six cohorts (seeds 301 to 306) so each row carries its range, and on both today's pathway and the accepted pathway. The dashboard's column is the mean of two cohorts (301, 302).

| Resource | Slots now | Today: gain in share within 90 d, pp (mean, range over 6 cohorts) | Dashboard (2 cohorts) | After the suggested change: gain, pp (mean, range) |
|---|---|---|---|---|
| `pet_scanner` | 1 | +8.1 (+2.1 to +14.2) | +9.7 | +10.4 (+3.3 to +20.9) |
| `bronchoscopy` | 1 | +3.4 (+0.8 to +8.3) | +3.6 | +3.6 (+0.4 to +6.4) |
| `ct_scanner` | 3 | +1.8 (+0.4 to +2.9) | +1.1 | +1.2 (-0.4 to +2.9) |
| `ttnb_slot` | 1 | +0.9 (-1.1 to +3.7) | +1.5 | +0.9 (+0.0 to +2.5) |
| `nurse_appt` | 35 | +0.4 (+0.0 to +0.8) | +0.6 | -0.2 (-1.9 to +0.8) |
| `xray` | 24 | +0.3 (-0.8 to +1.2) | +0.2 | +0.1 (-0.8 to +0.4) |
| `treatment_slot` | 2 | +0.3 (+0.0 to +0.4) | +0.4 | +0.3 (+0.0 to +1.5) |
| `clinic` | 7 | -0.1 (-0.4 to +0.0) | +0.0 | +0.2 (-0.4 to +0.8) |
| `gp_appt` | 74 | -0.1 (-0.4 to +0.0) | -0.4 | -0.1 (-0.8 to +0.7) |

- The ranking at the top is stable: the PET-CT scanner first, bronchoscopy second, in the mean, and the same two after the suggested change. The size of any single gain is not: one cohort can show several points more or fewer, and rows within about 1 pp of zero are noise.
- Reading for the pitch: "one more slot at the PET-CT scanner is worth about the same as the two reorders' gain, and the reorders need no slot" would overstate it; the honest line is that the PET-CT scanner and bronchoscopy are the capacity-limited steps in our synthetic county, and the capacities are our assumptions.
