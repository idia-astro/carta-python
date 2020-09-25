class Colormap:            
    pass

for colormap in ('copper', 'paired', 'gist_heat', 'brg', 'cool', 'summer', 'OrRd', 'tab20c', 'purples', 'gray', 'terrain', 'RdPu', 'set2', 'spring', 'gist_yarg', 'RdYlBu', 'reds', 'winter', 'Wistia', 'rainbow', 'dark2', 'oranges', 'BuPu', 'gist_earth', 'PuBu', 'pink', 'PuOr', 'pastel2', 'PiYG', 'gist_ncar', 'PuRd', 'plasma', 'gist_stern', 'hot', 'PuBuGn', 'YlOrRd', 'accent', 'magma', 'set1', 'GnBu', 'greens', 'CMRmap', 'gist_rainbow', 'prism', 'hsv', 'Blues', 'viridis', 'YlGn', 'spectral', 'RdBu', 'tab20', 'greys', 'flag', 'jet', 'seismic', 'PRGn', 'coolwarm', 'YlOrBr', 'RdYlGn', 'bone', 'autumn', 'BrBG', 'gnuplot2', 'RdGy', 'binary', 'gnuplot', 'BuGn', 'gist_gray', 'nipy_spectral', 'set3', 'tab20b', 'pastel1', 'afmhot', 'cubehelix', 'YlGnBu', 'ocean', 'tab10', 'bwr', 'inferno'):
    setattr(Colormap, colormap.upper(), colormap)


class Scaling:
    LINEAR, LOG, SQRT, SQUARE, POWER, GAMMA = range(6)


class CoordinateSystem:
    pass

for system in ("Auto", "Ecliptic", "FK4", "FK5", "Galactic", "ICRS"):
    setattr(CoordinateSystem, system.upper(), system)


class LabelType:
    INTERNAL = "Internal"
    EXTERNAL = "External"


class BeamType:
    OPEN = "Open"
    SOLID = "Solid"

class PaletteColor:
    BLACK, WHITE, RED, GREEN, BLUE, TURQUOISE, VIOLET, GOLD, GRAY = range(9)


class Overlay:
    BEAM = "beam.settingsForDisplay" # special case: an extra layer of indirection

for component in ("global", "title", "grid", "border", "ticks", "axes", "numbers", "labels"):
    setattr(Overlay, component.upper(), component)

    
class SmoothingMode:
    NO_SMOOTHING, BLOCK_AVERAGE, GAUSSIAN_BLUR = range(3)
    

class ContourDashMode:
    NONE = "None"
    DASHED = "Dashed"
    NEGATIVE_ONLY = "NegativeOnly"
