"""Review rotated text using recovered PDF quadrilaterals rather than AABBs."""
from pathlib import Path
from itertools import combinations
import json
import fitz

OUT = Path(__file__).resolve().parent
PREFIX = "three_panel_8x3p6"

def separated(a, b):
    # Separating-axis theorem for two convex text quadrilaterals.
    for polygon in (a, b):
        for p, q in zip(polygon, polygon[1:] + polygon[:1]):
            normal = (-(q[1] - p[1]), q[0] - p[0])
            pa = [v[0] * normal[0] + v[1] * normal[1] for v in a]
            pb = [v[0] * normal[0] + v[1] * normal[1] for v in b]
            if max(pa) <= min(pb) or max(pb) <= min(pa):
                return True
    return False

doc = fitz.open(OUT / f"{PREFIX}.pdf")
page = doc[0]
spans = []
for block in page.get_text("dict")["blocks"]:
    for line in block.get("lines", []):
        for span in line["spans"]:
            if not span["text"].strip():
                continue
            quad = fitz.recover_quad(line["dir"], span)
            points = [(p.x, p.y) for p in [quad.ul, quad.ur, quad.lr, quad.ll]]
            spans.append({"text": span["text"], "polygon": points})
overlaps = []
for a, b in combinations(spans, 2):
    if not separated(a["polygon"], b["polygon"]):
        overlaps.append([a["text"], b["text"]])
clipped = [s["text"] for s in spans if any(
    x < 0 or x > page.rect.width or y < 0 or y > page.rect.height
    for x, y in s["polygon"])]
raw = json.loads((OUT / f"{PREFIX}.collision-audit.json").read_text())
report = {
    "method": "PDF recovered text quadrilaterals and separating-axis theorem",
    "text_span_count": len(spans), "overlaps": overlaps, "clipped_text": clipped,
    "verdict": "PASS" if not overlaps and not clipped else "FIX BEFORE DELIVERY",
    "axis_aligned_audit_disposition": (
        "Rotated label bounding rectangles overlap; actual oriented text rectangles "
        "are checked here. Original unmodified report retained for traceability."
    ),
}
(OUT / f"{PREFIX}.oriented-text-audit.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
if overlaps or clipped:
    raise SystemExit(1)
