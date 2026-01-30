# -*- coding: utf-8 -*-
"""
FreeCAD script: 3D Sequoia 41 yurt-style house from perimeter drawing 41.pdf.

Reference: Smiling Woods Yurts - Sequoia Forty One (www.smilingwoodsyurts.com)
Drawing: 41 Sequoia_Base Sketch-Wall Layout (dimensions in inches).

Dimensions from drawing:
  - Interior diameter (wall to wall): 475.3522" (~39'-7 3/8")
  - Exterior corner-to-corner sheathing: 489.7103" (~40'-9 11/16")
  - Center to outside of wall: 244.8551" (~20'-4 7/8")
  - Wall panel: 48" (4'-0")
  - 14' walls, 24" eaves; loft at 9' (user spec)

Run in FreeCAD:
  - Macro: File -> Macro -> Macros -> paste path to this file, then Execute
  - Console: exec(open("/path/to/freecad_sequoia41_yurt.py").read())
"""

import FreeCAD
import Part
import math

# --- Dimensions from 41.pdf (inches); convert to mm for FreeCAD ---
INCH_TO_MM = 25.4

# Perimeter / base (drawing)
INTERIOR_DIAMETER_IN = 475.3522  # wall to opposite wall
EXTERIOR_CORNER_TO_CORNER_IN = 489.7103
CENTER_TO_OUTSIDE_WALL_IN = 244.8551
WALL_PANEL_WIDTH_IN = 48.0

# Kit specs (Smiling Woods Sequoia 41) + user: 14' walls, loft
WALL_HEIGHT_FT = 14.0
EAVE_OVERHANG_IN = 24.0
LOFT_HEIGHT_FT = 9.0  # loft floor above main floor
LOFT_DECK_THICKNESS_MM = 200.0  # loft deck (joists + decking)
# Loft floor radius: interior (slightly inside wall); full circle or partial
LOFT_RADIUS_FRACTION = 0.85  # 85% of interior radius so loft doesn't touch walls

# Derived
interior_radius_mm = (INTERIOR_DIAMETER_IN / 2.0) * INCH_TO_MM
exterior_radius_mm = CENTER_TO_OUTSIDE_WALL_IN * INCH_TO_MM
wall_height_mm = WALL_HEIGHT_FT * 12 * INCH_TO_MM
eave_mm = EAVE_OVERHANG_IN * INCH_TO_MM
loft_height_mm = LOFT_HEIGHT_FT * 12 * INCH_TO_MM
loft_radius_mm = interior_radius_mm * LOFT_RADIUS_FRACTION

# Roof: conical; crown ring at top, rafters to wall top. Typical roof slope ~22.5 deg.
ROOF_SLOPE_DEG = 22.5
# Crown ring radius (small circle at top of cone) - approximate
CROWN_RING_RADIUS_MM = 400.0

# Perimeter polygon: corner-to-corner = 489.7103"; panel width 48" -> n sides
# Circumference ~ pi * interior_diam; n = circumference / panel_width
_circumference_in = math.pi * INTERIOR_DIAMETER_IN
NUM_WALL_PANELS = max(8, int(round(_circumference_in / WALL_PANEL_WIDTH_IN)))
# Exterior corner-to-corner (drawing): use as polygon circumradius or half diagonal
# For regular polygon: corner_to_corner = 2 * R * sin(pi/n); R = corner_to_corner / (2*sin(pi/n))
exterior_corner_to_corner_mm = EXTERIOR_CORNER_TO_CORNER_IN * INCH_TO_MM
polygon_radius_mm = (exterior_corner_to_corner_mm / 2.0) / math.sin(
    math.pi / NUM_WALL_PANELS
)


def get_doc():
    """Return active document or create one."""
    if FreeCAD.ActiveDocument is None:
        FreeCAD.newDocument("Sequoia41_Yurt")
    return FreeCAD.ActiveDocument


def make_polygon_wire(radius_mm, num_sides, center=FreeCAD.Vector(0, 0, 0)):
    """Wire for a regular polygon (perimeter from drawing: corner-to-corner)."""
    points = []
    for i in range(num_sides + 1):
        angle = 2 * math.pi * i / num_sides - (math.pi / 2)  # first vertex at top
        x = center.x + radius_mm * math.cos(angle)
        y = center.y + radius_mm * math.sin(angle)
        points.append(FreeCAD.Vector(x, y, center.z))
    edges = [Part.makeLine(points[i], points[i + 1]) for i in range(num_sides)]
    return Part.Wire(edges)


def make_floor_disk(doc, radius_mm, name="Floor", use_polygon=False):
    """Floor from perimeter: circle or polygon (drawing corner-to-corner)."""
    if use_polygon:
        wire = make_polygon_wire(polygon_radius_mm, NUM_WALL_PANELS)
    else:
        circle = Part.makeCircle(radius_mm)
        wire = Part.Wire([circle])
    face = Part.Face(wire)
    slab = face.extrude(FreeCAD.Vector(0, 0, 20))  # 20 mm thick
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = slab
    return obj


def make_wall_cylinder(doc, radius_mm, height_mm, name="Wall"):
    """Cylindrical wall (ring) from floor to wall top."""
    outer = Part.makeCylinder(radius_mm, height_mm)
    wall_thickness_mm = 150.0
    inner_r = max(0, radius_mm - wall_thickness_mm)
    if inner_r > 0:
        inner = Part.makeCylinder(inner_r, height_mm)
        wall = outer.cut(inner)
    else:
        wall = outer
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = wall
    return obj


def make_wall_polygon(doc, radius_mm, height_mm, num_sides, name="Wall"):
    """Polygonal wall extruded from perimeter (matches drawing layout)."""
    wire = make_polygon_wire(radius_mm, num_sides)
    face = Part.Face(wire)
    wall_thickness_mm = 150.0
    # Extrude outer perimeter up, then subtract inner (smaller radius) extrusion
    outer = face.extrude(FreeCAD.Vector(0, 0, height_mm))
    inner_wire = make_polygon_wire(max(0, radius_mm - wall_thickness_mm), num_sides)
    inner_face = Part.Face(inner_wire)
    inner = inner_face.extrude(FreeCAD.Vector(0, 0, height_mm))
    wall = outer.cut(inner)
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = wall
    return obj


def make_roof_cone(doc, base_radius_mm, top_radius_mm, height_mm, name="Roof"):
    """Conical roof (crown at top, base at wall top + overhang)."""
    # Cone: Radius1 = base (at eave), Radius2 = crown ring, Height = roof height
    cone = Part.makeCone(base_radius_mm, top_radius_mm, height_mm)
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = cone
    return obj


def place_roof_over_wall(roof_obj, wall_height_mm):
    """Move roof so its base sits at wall top (z = wall_height_mm)."""
    roof_obj.Placement.Base = FreeCAD.Vector(0, 0, wall_height_mm)


def main():
    doc = get_doc()

    # 1) Floor: polygon from drawing perimeter (corner-to-corner exterior sheathing)
    floor = make_floor_disk(doc, polygon_radius_mm, "Yurt_Floor", use_polygon=True)
    floor.Placement.Base = FreeCAD.Vector(0, 0, 0)

    # 2) Wall: polygonal from perimeter (corner-to-corner)
    wall = make_wall_polygon(
        doc, polygon_radius_mm, wall_height_mm, NUM_WALL_PANELS, "Yurt_Wall"
    )
    wall.Placement.Base = FreeCAD.Vector(0, 0, 20)  # on top of floor slab

    # 3) Loft: deck at 9' (floor slab top + loft height)
    loft_circle = Part.makeCircle(loft_radius_mm)
    loft_wire = Part.Wire([loft_circle])
    loft_face = Part.Face(loft_wire)
    loft_slab = loft_face.extrude(FreeCAD.Vector(0, 0, LOFT_DECK_THICKNESS_MM))
    loft_obj = doc.addObject("Part::Feature", "Yurt_Loft")
    loft_obj.Shape = loft_slab
    loft_obj.Placement.Base = FreeCAD.Vector(0, 0, 20 + loft_height_mm)

    # 4) Roof: base at wall top + overhang (polygon radius + eave); cone to crown
    roof_base_radius_mm = polygon_radius_mm + eave_mm
    roof_height_mm = (roof_base_radius_mm - CROWN_RING_RADIUS_MM) / math.tan(
        math.radians(ROOF_SLOPE_DEG)
    )
    roof = make_roof_cone(
        doc,
        roof_base_radius_mm,
        CROWN_RING_RADIUS_MM,
        roof_height_mm,
        "Yurt_Roof",
    )
    roof.Placement.Base = FreeCAD.Vector(0, 0, 20 + wall_height_mm)

    # 5) Crown ring (small cylinder at peak)
    crown = Part.makeCylinder(CROWN_RING_RADIUS_MM + 50, 80)
    crown_z = 20 + wall_height_mm + roof_height_mm - 40
    crown_obj = doc.addObject("Part::Feature", "Yurt_CrownRing")
    crown_obj.Shape = crown
    crown_obj.Placement.Base = FreeCAD.Vector(0, 0, crown_z)

    doc.recompute()
    return doc


if __name__ == "__main__":
    # When run inside FreeCAD: File -> Macro -> Macros -> run this script
    # Or in FreeCAD Python console: exec(open("/path/to/freecad_sequoia41_yurt.py").read())
    main()
