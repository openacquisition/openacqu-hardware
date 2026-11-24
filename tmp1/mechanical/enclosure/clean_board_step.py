# Remesh degenerate footprint solids in the KiCad board STEP, then STEP
# round-trip (same cleanup that cleared FreeCAD's floating-ring ghost).
# Run: freecadcmd.exe clean_board_step.py
#
# Reads:  references/openacqu-tmp1-board.kicad-export.step (or .step if no backup)
# Writes: references/openacqu-tmp1-board.step

import os
import shutil
import FreeCAD as App
import Part
import MeshPart

REF_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references")
)
BOARD_STEP = os.path.join(REF_DIR, "openacqu-tmp1-board.step")
KICAD_EXPORT = os.path.join(REF_DIR, "openacqu-tmp1-board.kicad-export.step")


def _edge_ok(edge):
    try:
        _ = edge.Curve
        return True
    except Exception:
        return False


def main():
    if not os.path.isfile(KICAD_EXPORT):
        if not os.path.isfile(BOARD_STEP):
            raise SystemExit(f"Missing board STEP: {BOARD_STEP}")
        shutil.copy2(BOARD_STEP, KICAD_EXPORT)
        print("Backed up", KICAD_EXPORT)

    shape = Part.Shape()
    shape.read(KICAD_EXPORT)

    fixed = []
    remeshed = 0
    for solid in shape.Solids:
        if all(_edge_ok(e) for e in solid.Edges):
            fixed.append(solid)
            continue
        mesh = MeshPart.meshFromShape(
            Shape=solid, LinearDeflection=0.05, AngularDeflection=0.5
        )
        meshed = Part.Shape()
        meshed.makeShapeFromMesh(mesh.Topology, 0.1)
        if meshed.Solids:
            fixed.append(max(meshed.Solids, key=lambda s: s.Volume))
        elif meshed.Shells:
            fixed.append(Part.Solid(meshed.Shells[0]))
        remeshed += 1

    compound = Part.makeCompound(fixed)
    # Round-trip through STEP like the old mirrored-file fix
    tmp = BOARD_STEP + ".roundtrip.step"
    compound.exportStep(tmp)
    out = Part.Shape()
    out.read(tmp)
    out.exportStep(BOARD_STEP)
    os.remove(tmp)

    undef = sum(1 for e in out.Edges if not _edge_ok(e))
    bb = out.BoundBox
    print(f"Remeshed {remeshed} solids; undef edges={undef}; solids={len(out.Solids)}")
    print(
        f"AABB=({bb.XMin:.2f},{bb.YMin:.2f},{bb.ZMin:.2f})-"
        f"({bb.XMax:.2f},{bb.YMax:.2f},{bb.ZMax:.2f})"
    )
    print("Wrote", BOARD_STEP)


main()
