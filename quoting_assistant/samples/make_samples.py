"""Generate the 3 sample flat-pattern parts used in tests and demos (all in mm).

1. placa_base_200x150.dxf   base plate 200 x 150, 4 holes Ø12 (closed polyline + circles)
2. escaire_plegat.dxf       bracket 120 x 80 with R5 corners drawn as loose LINEs and ARCs,
                            2 holes Ø8 and 1 bend line on layer BEND
3. brida_160.dxf            flange Ø160 with Ø80 bore and 6 holes Ø10 on a Ø120 circle
"""
import math
from pathlib import Path

import ezdxf

HERE = Path(__file__).resolve().parent


def new_doc():
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # mm
    doc.layers.add("CUT")
    doc.layers.add("BEND")
    doc.layers.add("COTES")
    return doc


def base_plate(path):
    doc = new_doc()
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (200, 0), (200, 150), (0, 150)], close=True, dxfattribs={"layer": "CUT"})
    for x, y in [(20, 20), (180, 20), (180, 130), (20, 130)]:
        msp.add_circle((x, y), 6, dxfattribs={"layer": "CUT"})
    msp.add_text("PLACA BASE S235 3mm", dxfattribs={"layer": "COTES", "height": 5}).set_placement((0, -15))
    doc.saveas(path)


def bracket(path):
    doc = new_doc()
    msp = doc.modelspace()
    W, H, R = 120, 80, 5
    a = {"layer": "CUT"}
    # straight edges, deliberately as separate LINE entities
    msp.add_line((R, 0), (W - R, 0), dxfattribs=a)
    msp.add_line((W, R), (W, H - R), dxfattribs=a)
    msp.add_line((W - R, H), (R, H), dxfattribs=a)
    msp.add_line((0, H - R), (0, R), dxfattribs=a)
    # rounded corners
    msp.add_arc((W - R, R), R, 270, 360, dxfattribs=a)
    msp.add_arc((W - R, H - R), R, 0, 90, dxfattribs=a)
    msp.add_arc((R, H - R), R, 90, 180, dxfattribs=a)
    msp.add_arc((R, R), R, 180, 270, dxfattribs=a)
    for x in (30, 90):
        msp.add_circle((x, 20), 4, dxfattribs=a)
    msp.add_line((0, 40), (W, 40), dxfattribs={"layer": "BEND"})
    doc.saveas(path)


def flange(path):
    doc = new_doc()
    msp = doc.modelspace()
    a = {"layer": "CUT"}
    msp.add_circle((0, 0), 80, dxfattribs=a)
    msp.add_circle((0, 0), 40, dxfattribs=a)
    for k in range(6):
        ang = math.radians(60 * k)
        msp.add_circle((60 * math.cos(ang), 60 * math.sin(ang)), 5, dxfattribs=a)
    doc.saveas(path)


SAMPLES = {
    "placa_base_200x150.dxf": base_plate,
    "escaire_plegat.dxf": bracket,
    "brida_160.dxf": flange,
}

if __name__ == "__main__":
    for name, fn in SAMPLES.items():
        fn(HERE / name)
        print("wrote", HERE / name)
