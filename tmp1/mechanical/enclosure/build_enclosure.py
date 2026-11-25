# FreeCAD console script: builds the TMP1 clamshell and exports STEP/STL.
# Run: freecadcmd.exe build_enclosure.py
#
# Coordinate system: kicad-cli board STEP mm (Z up from PCB bottom).
# KiCad PCB Y is downward; the STEP negates Y so FreeCAD TOP matches a real
# PCBA / KiCad 3D. Enclosure features use that same CAD Y (y_cad = -y_pcb).

import os
import FreeCAD as App
import Part
from FreeCAD import Vector, Placement, Rotation, Matrix

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(OUT_DIR, "export")
REF_DIR = os.path.normpath(os.path.join(OUT_DIR, "..", "references"))
os.makedirs(EXPORT_DIR, exist_ok=True)

BOARD_STEP = os.path.join(REF_DIR, "openacqu-tmp1-board.step")
LIGHTPIPE_STEP = os.path.join(REF_DIR, "bivar-PLP1-6MM-F.step")
SCREW_STEP = os.path.join(REF_DIR, "mcmaster-96817A370-M3x12-pan-torx-plus.STEP")


def _cad_y(y_pcb):
    """Map KiCad PCB Y (down) to board-STEP / FreeCAD Y (up, matches KiCad 3D)."""
    return -y_pcb


# --- Board (CAD / STEP frame; comments show KiCad PCB coords) ---
BOARD_X0, BOARD_X1 = 71.0, 138.0
BOARD_Y0, BOARD_Y1 = _cad_y(94.0), _cad_y(56.0)  # PCB Y 56..94 → CAD -94..-56
BOARD_T = 1.6
HOLES = {
    "H1": (77.0, _cad_y(62.0)),   # PCB (77, 62)
    "H2": (77.0, _cad_y(88.0)),   # PCB (77, 88)
    "H3": (132.0, _cad_y(62.0)),  # PCB (132, 62)
    "H4": (132.0, _cad_y(88.0)),  # PCB (132, 88)
}
USB_C = (74.6755, _cad_y(75.0))  # J1 PCB (74.6755, 75)
TYPE_K = (122.0, _cad_y(75.0))  # J4 PCB (122, 75)
LED = (95.0, _cad_y(75.0))  # D1 PCB (95, 75)

# --- Enclosure parameters (2.0 mm walls: PA12-HP / PAC-HP / FDM ABS) ---
WALL = 2.0
CLEAR = 0.5  # PCB edge clearance inside cavity
BOARD_CORNER_R = 6.0  # from Edge.Cuts arcs (center at hole-line intersections)
INNER_CORNER_R = BOARD_CORNER_R + CLEAR  # parallel offset of board outline
OUTER_CORNER_R = INNER_CORNER_R + WALL
FLOOR = 3.0  # 2.5 counterbore + ~0.5 mm shelf under head
CEILING = 2.5  # recess PLP1 tip (2.3) by 0.2 mm
SUPPORT_H = 2.5  # bottom PCB support pads (no threads)
# McMaster 96817A370: M3×12 Torx Plus pan, head Ø5.15×2.3; Plastite-45 style
SCREW_LEN = 12.0  # under-head length
SCREW_HEAD_D = 5.15
SCREW_HEAD_H = 2.3
SCREW_SHANK_D = 3.0
BOSS_OD = 7.5  # 2.5×d (Stanley boss chart 1.8–2.5×d)
BOSS_PILOT = 2.43  # Plastite 45 M3×1.5 @ 70% (~0.81×d; chart 0.70–0.85×d)
# Lead-in at boss tip (PCB face): width ≈ d, depth 0.3–0.5×d for plastic flow
BOSS_CBORE_D = SCREW_SHANK_D  # = d
BOSS_CBORE_H = 0.4 * SCREW_SHANK_D  # mid of 0.3–0.5×d → 1.2 mm
THRU_D = 3.5  # clearance through bottom + PCB (matches 3.5 mm PCB holes)
HEAD_RECESS_D = 5.8  # pan-head counterbore (clearance over Ø5.15)
HEAD_RECESS_H = 2.5  # head (2.3) sits 0.2 mm below outer face
COMPONENT_H = 8.0  # Type-K body height above PCB top (from board STEP)
LID_GAP = 0.5  # minimal air above Type-K to ceiling underside

# USB-C stadium cutout (left wall): rounded rectangle matching the metal shell,
# grown by USB_TOL per side for PCB placement tolerance.
USB_SHELL_W = 11.34  # board STEP shell span along Y
USB_SHELL_H = 3.21  # board STEP shell span along Z
USB_SHELL_ZC = 3.176  # shell center Z relative to PCB bottom (board STEP)
USB_TOL = 0.6  # clearance per side around shell
USB_W = USB_SHELL_W + 2.0 * USB_TOL
USB_H = USB_SHELL_H + 2.0 * USB_TOL
USB_R = USB_H / 2.0  # stadium ends (USB-C profile)
# Outer overmold recess: keeps 2.0 mm walls elsewhere; local remaining ~1.1 mm.
# Effective jack setback ≈ CLEAR+WALL−depth ≈ 1.6 mm (≤ ~1.85 mm USB-C guidance).
USB_RECESS_D = 0.9  # depth from outer face
USB_RECESS_H = 10.0  # Z height of outer overmold pocket
USB_RECESS_CLEAR = (USB_RECESS_H - USB_H) / 2.0  # uniform border around through-hole
USB_RECESS_W = USB_W + 2.0 * USB_RECESS_CLEAR  # match end clearance to top/bottom
USB_RECESS_R = USB_RECESS_H / 2.0

# Type-K: plug openings face +X. Miniature plug ~16 x 8 mm; jack face ~16.6 x 8.0.
# Cutout is plug-sized with light clearance so the chassis masks the jack face.
TK_W = 20.0  # opening span along Y
TK_H = 10.0  # opening span along Z
TK_BODY_ZC = 5.60  # Type-K shell center Z relative to PCB bottom (board STEP)
TK_OPEN_ZC = FLOOR + SUPPORT_H + TK_BODY_ZC  # absolute Z; opening centered here
TK_OPEN_Z0 = TK_OPEN_ZC - TK_H / 2.0

# Bivar PLP1-6MM-F rear panel press-fit (datasheet PLP1-XXX-F)
LED_HOLE_D = 3.10  # recommended Ø0.121 in
PLP_BODY = 6.0  # X = body length below flange toward LED
PLP_FLANGE_T = 1.3  # 0.050 in flange thickness
PLP_PANEL_TIP = 2.3  # 0.090 in from flange seat through panel to outer face

# Outer shell
INNER_X0 = BOARD_X0 - CLEAR
INNER_Y0 = BOARD_Y0 - CLEAR
INNER_X1 = BOARD_X1 + CLEAR
INNER_Y1 = BOARD_Y1 + CLEAR
OUTER_X0 = INNER_X0 - WALL
OUTER_Y0 = INNER_Y0 - WALL
OUTER_X1 = INNER_X1 + WALL
OUTER_Y1 = INNER_Y1 + WALL

PCB_TOP_Z = FLOOR + SUPPORT_H + BOARD_T
CEILING_UNDER_Z = None  # set after OUTER_H
INNER_H = SUPPORT_H + BOARD_T + COMPONENT_H + LID_GAP
OUTER_H = FLOOR + INNER_H + CEILING
CEILING_UNDER_Z = OUTER_H - CEILING
BOSS_H = CEILING_UNDER_Z - PCB_TOP_Z  # top bosses hang down onto PCB top
# Parting line through the USB-C shell horizontal centerline
SPLIT_Z = FLOOR + SUPPORT_H + USB_SHELL_ZC


def rounded_box(x0, y0, z0, x1, y1, z1, radius):
    """Axis-aligned box with vertical-edge fillets."""
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    r = min(radius, dx / 2 - 0.01, dy / 2 - 0.01)
    box = Part.makeBox(dx, dy, dz, Vector(x0, y0, z0))
    if r <= 0:
        return box
    edges = []
    for e in box.Edges:
        v0, v1 = e.Vertexes[0].Point, e.Vertexes[1].Point
        if abs(v0.z - v1.z) > dz - 1e-6 and abs(v0.x - v1.x) < 1e-6 and abs(v0.y - v1.y) < 1e-6:
            edges.append(e)
    try:
        return box.makeFillet(r, edges)
    except Exception:
        return box


def stadium_cutout_x(x0, x1, y_c, z_c, length_y, height_z, end_r):
    """Capsule/stadium extruded along X (USB-C profile in the YZ plane)."""
    r = min(end_r, length_y / 2 - 0.01, height_z / 2 - 0.01)
    span = max(length_y - 2 * r, 0.01)  # distance between end-cylinder axes
    dx = x1 - x0
    c0 = Part.makeCylinder(r, dx, Vector(x0, y_c - span / 2, z_c), Vector(1, 0, 0))
    c1 = Part.makeCylinder(r, dx, Vector(x0, y_c + span / 2, z_c), Vector(1, 0, 0))
    box = Part.makeBox(dx, span, height_z, Vector(x0, y_c - span / 2, z_c - height_z / 2))
    return c0.fuse(c1).fuse(box).removeSplitter()


def _usb_z_c():
    return FLOOR + SUPPORT_H + USB_SHELL_ZC


def usb_stadium_cutter():
    """Full USB-C stadium through the left wall, centered on the jack shell."""
    return stadium_cutout_x(
        OUTER_X0 - 0.2,
        INNER_X0 + CLEAR + 3.0,
        USB_C[1],
        _usb_z_c(),
        USB_W,
        USB_H,
        USB_R,
    )


def usb_overmold_recess_cutter():
    """Outer pocket so the plug overmold clears before the metal is fully home."""
    return stadium_cutout_x(
        OUTER_X0 - 0.2,
        OUTER_X0 + USB_RECESS_D,
        USB_C[1],
        _usb_z_c(),
        USB_RECESS_W,
        USB_RECESS_H,
        USB_RECESS_R,
    )


def _screw_underhead_z(shape):
    """Z of the pan under-head seating face (normal −Z, large annulus)."""
    best = None
    for face in shape.Faces:
        try:
            normal = face.normalAt(0.5, 0.5)
        except Exception:
            continue
        if normal.z > -0.85:
            continue
        if not face.Vertexes:
            continue
        rmax = max((v.Point.x ** 2 + v.Point.y ** 2) ** 0.5 for v in face.Vertexes)
        if rmax < SCREW_HEAD_D * 0.35:
            continue
        score = (rmax, face.Area)
        z = face.CenterOfMass.z
        if best is None or score > best[0]:
            best = (score, z)
    if best is None:
        return shape.BoundBox.ZMin + SCREW_LEN
    return best[1]


def _load_screw_shape():
    """McMaster 96817A370 STEP: axis along +X toward head. Return under-head Z=0, tip -Z."""
    shape = Part.Shape()
    shape.read(SCREW_STEP)
    # Bake pose into geometry (transformShape alone is undone by Part::Feature Placement).
    # (x,y,z) -> (-z,y,x): tip -X becomes tip -Z
    shape = shape.transformGeometry(Rotation(Vector(0, 1, 0), -90).toMatrix())
    under_z = _screw_underhead_z(shape)
    shape = shape.transformGeometry(Placement(Vector(0, 0, -under_z), Rotation()).toMatrix())
    return shape


def make_plp1_flat_step(path):
    """Datasheet PLP1-xxx-F: flange seat on panel inner face; flat face out; flat collector to LED."""
    # Local Z=0 = flange underside (red-arrow seat against ceiling underside).
    # +Z out through panel; -Z toward LED.
    flange_d = 3.8  # Ø0.150 in
    stem_d = 2.8  # Ø0.112 in collector / through stem
    face_d = 3.0  # Ø0.118 in panel section
    flange_t = PLP_FLANGE_T
    tip = PLP_PANEL_TIP
    body = PLP_BODY

    # Flange disk on the cavity side of the seat
    flange = Part.makeCylinder(flange_d / 2, flange_t, Vector(0, 0, -flange_t))
    # Through-panel tip to outer face (0.090 in)
    through = Part.makeCylinder(face_d / 2, tip, Vector(0, 0, 0))
    # Body length X toward LED
    stem = Part.makeCylinder(stem_d / 2, body, Vector(0, 0, -body))
    shape = flange.fuse(through).fuse(stem).removeSplitter()
    shape.exportStep(path)
    return shape


def make_bottom():
    outer = rounded_box(OUTER_X0, OUTER_Y0, 0, OUTER_X1, OUTER_Y1, SPLIT_Z, OUTER_CORNER_R)
    cavity = rounded_box(
        INNER_X0, INNER_Y0, FLOOR,
        INNER_X1, INNER_Y1, SPLIT_Z + 1.0,
        INNER_CORNER_R,
    )
    body = outer.cut(cavity)

    # PCB support pads with screw clearance (threads are in the top bosses)
    for _name, (hx, hy) in HOLES.items():
        pad = Part.makeCylinder(BOSS_OD / 2, SUPPORT_H, Vector(hx, hy, FLOOR))
        body = body.fuse(pad)
        # Counterbore from outside bottom + through clearance
        cbore = Part.makeCylinder(HEAD_RECESS_D / 2, HEAD_RECESS_H + 0.05, Vector(hx, hy, -0.05))
        thru = Part.makeCylinder(
            THRU_D / 2,
            FLOOR + SUPPORT_H + 0.4,
            Vector(hx, hy, -0.1),
        )
        body = body.cut(cbore).cut(thru)

    # USB-C stadium through left wall + outer overmold recess (same tools as top)
    body = body.cut(usb_stadium_cutter())
    body = body.cut(usb_overmold_recess_cutter())

    # Type-K plug opening through right wall
    tk = Part.makeBox(
        WALL + CLEAR + 6.0,
        TK_W,
        TK_H,
        Vector(INNER_X1 - 1.0, TYPE_K[1] - TK_W / 2, TK_OPEN_Z0),
    )
    body = body.cut(tk)

    return body.removeSplitter()


def make_top():
    outer = rounded_box(OUTER_X0, OUTER_Y0, SPLIT_Z, OUTER_X1, OUTER_Y1, OUTER_H, OUTER_CORNER_R)
    cavity = rounded_box(
        INNER_X0, INNER_Y0, SPLIT_Z - 1.0,
        INNER_X1, INNER_Y1, OUTER_H - CEILING,
        INNER_CORNER_R,
    )
    body = outer.cut(cavity)

    # Threaded bosses hang from ceiling underside onto PCB top
    for _name, (hx, hy) in HOLES.items():
        boss = Part.makeCylinder(BOSS_OD / 2, BOSS_H, Vector(hx, hy, PCB_TOP_Z))
        body = body.fuse(boss)
        pilot = Part.makeCylinder(
            BOSS_PILOT / 2,
            BOSS_H + 0.2,
            Vector(hx, hy, PCB_TOP_Z - 0.1),
        )
        # Wider lead-in at boss tip for plastic displacement (Stanley boss counterbore)
        tip_cbore = Part.makeCylinder(
            BOSS_CBORE_D / 2,
            BOSS_CBORE_H + 0.05,
            Vector(hx, hy, PCB_TOP_Z - 0.05),
        )
        body = body.cut(pilot).cut(tip_cbore)

    # PLP1 panel hole
    led = Part.makeCylinder(
        LED_HOLE_D / 2,
        CEILING + 2.0,
        Vector(LED[0], LED[1], OUTER_H - CEILING - 1.0),
    )
    body = body.cut(led)

    # Same full USB-C stadium + overmold recess as bottom
    body = body.cut(usb_stadium_cutter())
    body = body.cut(usb_overmold_recess_cutter())

    tk_top_z1 = TK_OPEN_Z0 + TK_H
    if tk_top_z1 > SPLIT_Z:
        tk = Part.makeBox(
            WALL + CLEAR + 6.0,
            TK_W,
            max(0.1, tk_top_z1 - SPLIT_Z) + 0.5,
            Vector(INNER_X1 - 1.0, TYPE_K[1] - TK_W / 2, SPLIT_Z - 0.25),
        )
        body = body.cut(tk)

    return body.removeSplitter()


def add_params(doc):
    sheet = doc.addObject("Spreadsheet::Sheet", "Params")
    rows = [
        ("wall_mm", WALL, "Shell wall thickness (PAC-HP floor)"),
        ("clearance_mm", CLEAR, "PCB edge clearance"),
        ("board_corner_r_mm", BOARD_CORNER_R, "PCB Edge.Cuts corner radius"),
        ("inner_corner_r_mm", INNER_CORNER_R, "Cavity corner (= board R + clear)"),
        ("outer_corner_r_mm", OUTER_CORNER_R, "Outer shell corner (= inner + wall)"),
        ("floor_mm", FLOOR, "Bottom floor thickness (head recess)"),
        ("ceiling_mm", CEILING, "Top ceiling / PLP1 panel thickness"),
        ("support_h_mm", SUPPORT_H, "Bottom PCB support pad height"),
        ("boss_h_mm", BOSS_H, "Top boss length down to PCB"),
        ("boss_od_mm", BOSS_OD, "Boss / pad outer diameter"),
        ("boss_pilot_mm", BOSS_PILOT, "M2.5 Plastite pilot in top bosses"),
        ("head_recess_d_mm", HEAD_RECESS_D, "Bottom counterbore diameter"),
        ("head_recess_h_mm", HEAD_RECESS_H, "Bottom counterbore depth"),
        ("outer_h_mm", OUTER_H, "Overall enclosure height"),
        ("split_z_mm", SPLIT_Z, "Bottom/top seam Z"),
        ("led_hole_d_mm", LED_HOLE_D, "PLP1 panel hole"),
        ("board_t_mm", BOARD_T, "PCB thickness"),
        ("pcb_top_z_mm", PCB_TOP_Z, "PCB top Z in assembly"),
        ("usb_w_mm", USB_W, "USB-C stadium width (Y)"),
        ("usb_h_mm", USB_H, "USB-C stadium height (Z)"),
        ("usb_tol_mm", USB_TOL, "USB-C clearance per side"),
        ("usb_recess_d_mm", USB_RECESS_D, "Outer overmold recess depth"),
        ("usb_recess_w_mm", USB_RECESS_W, "Outer overmold recess width (Y)"),
        ("usb_recess_h_mm", USB_RECESS_H, "Outer overmold recess height (Z)"),
    ]
    sheet.set("A1", "name")
    sheet.set("B1", "value")
    sheet.set("C1", "note")
    for i, (n, v, note) in enumerate(rows, start=2):
        sheet.set(f"A{i}", n)
        sheet.set(f"B{i}", str(round(v, 4) if isinstance(v, float) else v))
        sheet.set(f"C{i}", note)
    doc.recompute()
    return sheet


def _add_shape(doc, name, shape, placement=None):
    """Add Part::Feature with local geometry; pose on Placement only (FreeCAD 1.1-safe)."""
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    obj.Placement = placement if placement is not None else Placement()
    if hasattr(obj, "ViewObject") and obj.ViewObject is not None:
        obj.ViewObject.Visibility = True
    return obj


def _import_board(doc):
    if not os.path.isfile(BOARD_STEP):
        App.Console.PrintWarning(f"Board STEP missing: {BOARD_STEP}\n")
        return
    try:
        shape = Part.Shape()
        shape.read(BOARD_STEP)
        # Board STEP is the kicad-cli export with degenerate footprint edges
        # remeshed + STEP round-tripped (same cleanup used on the old mirrored
        # copy). Pristine KiCad export: openacqu-tmp1-board.kicad-export.step.
        # PCB bottom (Z=0 in STEP) sits on support pads.
        _add_shape(
            doc,
            "BoardReference",
            shape,
            Placement(Vector(0, 0, FLOOR + SUPPORT_H), Rotation()),
        )
    except Exception as exc:
        App.Console.PrintWarning(f"BoardReference: not linked ({exc})\n")


def _import_lightpipe(doc):
    try:
        make_plp1_flat_step(LIGHTPIPE_STEP)
    except Exception as exc:
        App.Console.PrintWarning(f"Light pipe STEP generate failed: {exc}\n")
        return
    try:
        shape = Part.Shape()
        shape.read(LIGHTPIPE_STEP)
        # Local Z=0 at flange underside → seat on ceiling underside over D1
        _add_shape(
            doc,
            # Z=0 on STEP = flange underside → seat on ceiling underside
            "LightPipe_PLP1_6MMF",
            shape,
            Placement(Vector(LED[0], LED[1], CEILING_UNDER_Z), Rotation()),
        )
    except Exception as exc:
        App.Console.PrintWarning(f"LightPipe_PLP1_6MMF: not linked ({exc})\n")


def _import_screws(doc):
    """McMaster STEP: orient under-head Z=0 tip -Z, then flip tip +Z into top bosses."""
    if not os.path.isfile(SCREW_STEP):
        App.Console.PrintWarning(f"Screw STEP missing: {SCREW_STEP}\n")
        return
    try:
        oriented = _load_screw_shape()
    except Exception as exc:
        App.Console.PrintWarning(f"Screw STEP orient failed: {exc}\n")
        return
    for name, (hx, hy) in HOLES.items():
        try:
            # Under-head on counterbore floor; 180° about X points tip +Z
            _add_shape(
                doc,
                f"Screw_{name}",
                oriented.copy(),
                Placement(
                    Vector(hx, hy, HEAD_RECESS_H),
                    Rotation(Vector(1, 0, 0), 180),
                ),
            )
        except Exception as exc:
            App.Console.PrintWarning(f"Screw_{name}: not linked ({exc})\n")


def main():
    make_plp1_flat_step(LIGHTPIPE_STEP)

    # Save to a temp path first so an open FreeCAD GUI cannot clobber mid-write
    fcstd = os.path.join(OUT_DIR, "openacqu-tmp1-enclosure.FCStd")
    fcstd_tmp = fcstd + ".tmp.FCStd"

    doc = App.newDocument("openacqu_tmp1_enclosure")
    add_params(doc)

    bottom = make_bottom()
    top = make_top()

    bottom_obj = doc.addObject("Part::Feature", "Bottom")
    bottom_obj.Shape = bottom
    top_obj = doc.addObject("Part::Feature", "Top")
    top_obj.Shape = top

    _import_board(doc)
    _import_lightpipe(doc)
    _import_screws(doc)

    doc.recompute()
    doc.saveAs(fcstd_tmp)
    App.closeDocument(doc.Name)

    # Atomic replace of the master FCStd
    if os.path.isfile(fcstd):
        os.replace(fcstd_tmp, fcstd)
    else:
        os.rename(fcstd_tmp, fcstd)

    bottom_step = os.path.join(EXPORT_DIR, "openacqu-tmp1-bottom.step")
    top_step = os.path.join(EXPORT_DIR, "openacqu-tmp1-top.step")
    bottom_stl = os.path.join(EXPORT_DIR, "openacqu-tmp1-bottom.stl")
    top_stl = os.path.join(EXPORT_DIR, "openacqu-tmp1-top.stl")

    bottom.exportStep(bottom_step)
    top.exportStep(top_step)
    bottom.exportStl(bottom_stl)
    top.exportStl(top_stl)

    print("Wrote", fcstd)
    print("Wrote", bottom_step)
    print("Wrote", top_step)
    print("Wrote", bottom_stl)
    print("Wrote", top_stl)
    print(f"Outer AABB: {OUTER_X1-OUTER_X0:.2f} x {OUTER_Y1-OUTER_Y0:.2f} x {OUTER_H:.2f} mm")
    print(f"Split Z: {SPLIT_Z:.2f} mm")
    print(f"PCB top Z: {PCB_TOP_Z:.2f} mm, boss H: {BOSS_H:.2f} mm")
    print(f"Ceiling underside above Type-K: {LID_GAP:.2f} mm")
    print(f"Light pipe clearance to PCB top: {BOSS_H - PLP_BODY:.2f} mm")



main()
