class Colormap:
    # TODO at the moment this data can only be fetched if a file is open
    # But we can store the constants in an independent place somewhere
    @classmethod
    def fetch(cls, session):
        response = session.fetch_parameter("activeFrame.renderConfig.constructor.COLOR_MAPS_ALL")
        
        for colormap in response:
            setattr(cls, colormap.upper(), colormap)


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
