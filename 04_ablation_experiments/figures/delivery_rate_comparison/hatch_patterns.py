"""Draw finite vector hatches inside each bar and its legend swatch."""
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.legend_handler import HandlerBase
from matplotlib.patches import Circle, Rectangle


def hatch_artists(bounds, pattern, transform, units_per_inch=1, zorder=3.05):
    x, y, width, height = bounds
    if not pattern or width <= 0 or height <= 0:
        return []
    pitch_inches = {"////": .08, "\\\\": .16, "..": .085,
                    "xx": .16, "++": .085, "//": .16, "--": .085}
    pitch = pitch_inches[pattern] * units_per_inch
    segments = []
    if "/" in pattern or "x" in pattern:
        for offset in np.arange(-width, height + pitch, pitch):
            low, high = max(0, -offset), min(width, height - offset)
            if high > low:
                segments.append([(x + low, y + low + offset),
                                 (x + high, y + high + offset)])
    if "\\" in pattern or "x" in pattern:
        for offset in np.arange(0, width + height + pitch, pitch):
            low, high = max(0, offset - height), min(width, offset)
            if high > low:
                segments.append([(x + low, y + offset - low),
                                 (x + high, y + offset - high)])
    if "+" in pattern or "-" in pattern:
        for offset in np.arange(pitch / 2, height, pitch):
            segments.append([(x, y + offset), (x + width, y + offset)])
    if "+" in pattern:
        for offset in np.arange(pitch / 2, width, pitch):
            segments.append([(x + offset, y), (x + offset, y + height)])
    artists = []
    if segments:
        artists.append(LineCollection(segments, colors="white", linewidths=.7,
                                      transform=transform, zorder=zorder,
                                      capstyle="butt", clip_on=False))
    if "." in pattern:
        radius = .009 * units_per_inch
        for col in np.arange(pitch / 2, width - radius, pitch):
            for row in np.arange(pitch / 2, height - radius, pitch):
                artists.append(Circle((x + col, y + row), radius,
                                      facecolor="white", edgecolor="none",
                                      transform=transform, zorder=zorder,
                                      clip_on=False))
    return artists


class VectorHatchHandler(HandlerBase):
    def create_artists(self, legend, orig_handle, xdescent, ydescent,
                       width, height, fontsize, trans):
        bounds = (-xdescent, -ydescent, width, height)
        face = Rectangle(bounds[:2], width, height,
                         facecolor=orig_handle.get_facecolor(),
                         edgecolor="none", transform=trans)
        texture = hatch_artists(bounds, orig_handle.get_hatch(), trans,
                                units_per_inch=72)
        outline = Rectangle(bounds[:2], width, height, facecolor="none",
                            edgecolor="#283744", linewidth=.75, transform=trans)
        return [face, *texture, outline]
