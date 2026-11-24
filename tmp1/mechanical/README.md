# TMP1 enclosure

Simple two-piece FreeCAD clamshell for the TMP1 PCBA.

## Layout

- `references/openacqu-tmp1-board.step` — board used by `BoardReference` (KiCad export cleaned for FreeCAD)
- `references/openacqu-tmp1-board.kicad-export.step` — pristine `kicad-cli` export; re-clean if you re-export
- `references/bivar-PLP1-6MM-F.step` — Bivar PLP1-6MM-F flat rear panel light pipe (flange seat on ceiling underside)
- `references/mcmaster-90362A146-M2.5x8-pan-torx.STEP` — M2.5×8 pan Torx CAD (McMaster 90362A146)
- `enclosure/openacqu-tmp1-enclosure.FCStd` — FreeCAD master (bottom, top, board, light pipe, screws)
- `enclosure/build_enclosure.py` — regenerates the `.FCStd` and export files
- `enclosure/export/` — STEP and STL for quoting / printing
- `hardware.md` — screw and light-pipe part numbers

## Assembly notes

- Screws enter from the **bottom** into recessed counterbores; Plastite pilots are in the **top** bosses.
- Bottom has PCB support pads only (clearance holes). Board STEP is Y-flipped to match KiCad coordinates.
- Light pipe is a rear panel press-fit in the top cover (not board-mounted).

## Openings

- **Left wall:** USB-C (J1), stadium matching the jack shell + 0.6 mm per side, plus a **0.9 mm outer overmold recess** (~18.1×10 mm, uniform border) so plugs can fully seat without thinning the whole 2.0 mm wall
- **Right wall:** Type-K miniature jack (J4), **20 × 10 mm** opening. Plug openings face the board edge; screw terminals face the board center.
- **Top:** PLP1 panel hole over D1
- Debug header (J2) is enclosed; no access cutout

## Print / quote

One STEP/STL pair is intended for JLCPCB quotes in:

| Material | Notes |
|---|---|
| **PA12-HP (MJF)** | Intended build. Natural gray or dyed black. |
| **PAC-HP (MJF)** | Same geometry; 2.0 mm walls meet the PAC minimum. |
| **FDM ABS** | Same geometry; 2.0 mm walls meet the ABS wall rule. |

Wall thickness is **2.0 mm** so one file clears DFM for all three. Do not thin the walls for PA12-only optimization if you still want PAC-HP quotes from the same upload.

Avoid brittle SLA resin for the shells.

## Rebuild

```text
"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" tmp1\mechanical\enclosure\build_enclosure.py
```

Re-export the board STEP from KiCad when the PCBA changes:

```text
kicad-cli pcb export step --force --drill-origin --no-unspecified --no-dnp --subst-models -o tmp1\mechanical\references\openacqu-tmp1-board.step tmp1\openacqu-tmp1\openacqu-tmp1.kicad_pcb
```
