#!/usr/bin/env python3

import json
import logging
import posixpath
import argparse
import base64
import re

import grpc

import carta_service_pb2
import carta_service_pb2_grpc


logger = logging.getLogger("carta_scripting")
logger.setLevel(logging.ERROR)
logger.addHandler(logging.StreamHandler())


class CartaScriptingException(Exception):
    pass


class Macro:
    def __init__(self, target, variable):
        self.target = target
        self.variable = variable
        
    def __repr__(self):
        return f"Macro('{self.target}', '{self.variable}')"


class CartaEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Macro):
            return {"macroTarget" : obj.target, "macroVariable" : obj.variable}
        if type(obj).__module__ == "numpy" and type(obj).__name__ == "ndarray":
            # The condition is a workaround to avoid importing numpy
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)


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


class Color:
    BLACK, WHITE, RED, GREEN, BLUE, TURQUOISE, VIOLET, GOLD, GRAY = range(9)


class Overlay:
    pass

for component in ("global", "title", "grid", "border", "ticks", "axes", "numbers", "labels", "beam"):
    setattr(Overlay, component.upper(), component)

    
class SmoothingMode:
    NO_SMOOTHING, BLOCK_AVERAGE, GAUSSIAN_BLUR = range(3)
    

class ContourDashMode:
    NONE = "None"
    DASHED = "Dashed"
    NEGATIVE_ONLY = "NegativeOnly"

    
# TODO: profiles -- need to wait for refactoring to make tsv and png profiles accessible
# TODO: histograms -- also need access to urls for exporting histograms
# TODO: preferences -- generic get and set for now
# TODO: regions
# TODO: add docstrings and autogenerate documentation


class Session:    
    def __init__(self, host, port, session_id, browser=None):
        self.uri = "%s:%s" % (host, port)
        self.session_id = session_id
        self._browser = browser
        
    def __repr__(self):
        return f"Session(session_id={self.session_id}, uri={self.uri})"
    
    def split_path(self, path):
        parts = path.split('.')
        return '.'.join(parts[:-1]), parts[-1]
        
    def call_action(self, path, *args, **kwargs):
        response_expected = kwargs.pop("response_expected", False)
        path, action = self.split_path(path)
        
        logger.debug(f"Sending action request to backend; path: {path}; action: {action}; args: {args}, kwargs: {kwargs}")
        
        # I don't think this can fail
        parameters = json.dumps(args, cls=CartaEncoder)
        
        carta_action_description = f"CARTA scripting action {path}.{action} called with parameters {parameters}"
        
        try:
            request_kwargs = {
                "session_id": self.session_id,
                "path": path,
                "action": action,
                "parameters": parameters,
                "async": kwargs.get("async", False)
            }
            
            with grpc.insecure_channel(self.uri) as channel:
                stub = carta_service_pb2_grpc.CartaBackendStub(channel)
                response = stub.CallAction(
                    carta_service_pb2.ActionRequest(**request_kwargs)
                )
        except grpc.RpcError as e:
            raise CartaScriptingException(f"{carta_action_description} failed: {e.details()}") from e
        
        logger.debug(f"Got success status: {response.success}; message: {response.message}; response: {response.response}")
        
        if not response.success:
            raise CartaScriptingException(f"{carta_action_description} failed: {response.message}")
        
        if response.response == '':
            if response_expected:
                raise CartaScriptingException(f"{carta_action_description} expected a response, but did not receive one.")
            return None
        
        try:
            decoded_response = json.loads(response.response)
        except json.decoder.JSONDecodeError as e:
            raise CartaScriptingException(f"{carta_action_description} received a response which could not be decoded.\nResponse string: {repr(response.response)}\nError: {e}")
        
        return decoded_response

    def fetch_parameter(self, path):
        path, parameter = self.split_path(path)
        macro = Macro(path, parameter)
        return self.call_action("fetchParameter", macro, response_expected=True)
    
    # IMAGES
    
    def image(self, image_id, file_name):
        return Image(self, image_id, file_name)

    def open_image(self, path, hdu=""):
        return Image.new(self, path, hdu, False)

    def append_image(self, path, hdu=""):
        return Image.new(self, path, hdu, True)

    def image_list(self):
        return [self.image(f["value"], f["label"]) for f in self.fetch_parameter("frameNames")]
    
    def active_frame(self):
        frame_info = self.fetch_parameter("activeFrame.frameInfo")
        image_id = frame_info["fileId"]
        file_name = frame_info["fileInfo"]["name"]
        return self.image(image_id, file_name)
    
    def clear_spatial_reference(self):
        self.call_action("clearSpatialReference")
    
    def clear_spectral_reference(self):
        self.call_action("clearSpectralReference")
        
    # CANVAS AND OVERLAY
        
    def set_view_area(self, width, height):
        self.call_action("overlayStore.setViewDimension", width, height)
    
    def set_coordinate_system(self, system=CoordinateSystem.AUTO):
        self.call_action("overlayStore.global.setSystem", system)
        
    def set_label_type(self, label_type):
        self.call_action("overlayStore.global.setLabelType", label_type)
        
    def set_color(self, color, component=Overlay.GLOBAL):
        self.call_action(f"overlayStore.{component}.setColor", color)
        if component != Overlay.GLOBAL:
            self.call_action(f"overlayStore.{component}.setCustomColor", True)
        
    def clear_color(self, component):
        if component != Overlay.GLOBAL:
            self.call_action(f"overlayStore.{component}.setCustomColor", False)
 
    def set_visible(self, component, visible):
        if component == Overlay.TICKS:
            logger.warn("Ticks cannot be shown or hidden.")
            return

        if component != Overlay.GLOBAL:
            self.call_action(f"overlayStore.{component}.setVisible", visible)
    
    def show(self, component):
        self.set_visible(component, True)
 
    def hide(self, component):
        self.set_visible(component, False)
            
    def toggle_labels(self):
        self.call_action("overlayStore.toggleLabels")
    
    # PROFILES (TODO)
    
    def set_cursor(self, x, y):
        self.active_frame().call_action("regionSet.regions[0].setControlPoint", 0, [x, y])
    
    # SAVE IMAGE
    
    def rendered_view_url(self, background_color=None):
        self.call_action("waitForImageData")
        args = ["getImageDataUrl"]
        if background_color:
            args.append(background_color)
        return self.call_action(*args, response_expected=True)
    
    def rendered_view_data(self, background_color=None):
        uri = self.rendered_view_url(background_color)
        data = uri.split(",")[1]
        return base64.b64decode(data)
    
    def save_rendered_view(self, file_name, background_color=None):
        with open(file_name, 'wb') as f:
            f.write(self.rendered_view_data(background_color))


class Image:    
    def __init__(self, session, image_id, file_name):
        self.session = session
        self.image_id = image_id
        self.file_name = file_name
        
        self._base_path = f"frameMap[{image_id}]"
        self._frame = Macro("", self._base_path)
    
    @classmethod
    def new(cls, session, path, hdu, append):
        directory, file_name = posixpath.split(path)
        image_id = session.call_action("appendFile" if append else "openFile", directory, file_name, hdu)
        
        return cls(session, image_id, file_name)
        
    def __repr__(self):
        return f"{self.session.session_id}:{self.image_id}:{self.file_name}"
    
    def call_action(self, path, *args, **kwargs):
        return self.session.call_action(f"{self._base_path}.{path}", *args, **kwargs)
    
    def fetch_parameter(self, path):
        return self.session.fetch_parameter(f"{self._base_path}.{path}")
    
    # METADATA

    def directory(self):
        return self.fetch_parameter("frameInfo.directory")
    
    def header(self):
        return self.fetch_parameter("frameInfo.fileInfoExtended.headerEntries")
    
    def shape(self):
        info = self.fetch_parameter("frameInfo.fileInfoExtended")
        return list(reversed([info["width"], info["height"], info["depth"], info["stokes"]][:info["dimensions"]]))
    
    # SELECTION
    
    def make_active(self):
        self.session.call_action("setActiveFrame", self._frame)
        
    def make_spatial_reference(self):
        self.session.call_action("setSpatialReference", self._frame)
        
    def set_spatial_matching(self, state):
        self.session.call_action("setSpatialMatchingEnabled", self._frame, state)
        
    def make_spectral_reference(self):
        self.session.call_action("setSpectralReference", self._frame)
        
    def set_spectral_matching(self, state):
        self.session.call_action("setSpectralMatchingEnabled", self._frame, state)

    # NAVIGATION

    def set_channel_stokes(self, channel=None, stokes=None, recursive=True):
        channel = channel or self.fetch_parameter("requiredChannel")
        stokes = stokes or self.fetch_parameter("requiredStokes")
        self.call_action("setChannels", channel, stokes, recursive)

    def set_center(self, x, y):
        self.call_action("setCenter", x, y)
        
    def set_zoom(self, zoom, absolute=True):
        self.call_action("setZoom", zoom, absolute)
        
    # STYLE

    def set_colormap(self, colormap, invert=False):
        self.call_action("renderConfig.setColorMap", colormap)
        self.call_action("renderConfig.setInverted", invert)
        
    def set_scaling(self, scaling, **kwargs):
        self.call_action("renderConfig.setScaling", scaling)
        if scaling in (Scaling.LOG, Scaling.POWER) and "alpha" in kwargs:
            self.call_action("renderConfig.setAlpha", kwargs["alpha"])
        elif scaling == Scaling.GAMMA and "gamma" in kwargs:
            self.call_action("renderConfig.setGamma", kwargs["gamma"])
        if "min" in kwargs and "max" in kwargs:
            self.call_action("renderConfig.setCustomScale", kwargs["min"], kwargs["max"])
        
    def set_raster_visible(self, state):
        self.call_action("renderConfig.setVisible", state)
        
    def show_raster(self):
        self.set_raster_visible(True)
        
    def hide_raster(self):
        self.set_raster_visible(False)
    
    # CONTOURS
    
    def configure_contours(self, levels, smoothing_mode=SmoothingMode.GAUSSIAN_BLUR, smoothing_factor=4):
        self.call_action("contourConfig.setContourConfiguration", levels, smoothing_mode, smoothing_factor)
    
    def set_contour_dash(self, dash_mode=None, thickness=None):
        if dash_mode is not None:
            self.call_action("contourConfig.setDashMode", dash_mode)
        if thickness is not None:
            self.call_action("contourConfig.setThickness", thickness)
    
    def set_contour_color(self, color):
        self.call_action("contourConfig.setColor", color)
        self.call_action("contourConfig.setColormapEnabled", False)
    
    def set_contour_colormap(self, colormap, bias=None, contrast=None):
        self.call_action("contourConfig.setColormap", colormap)
        self.call_action("contourConfig.setColormapEnabled", True)
        if bias is not None:
            self.call_action("contourConfig.setColormapBias", bias)
        if contrast is not None:
            self.call_action("contourConfig.setColormapContrast", contrast)
    
    def apply_contours(self):
        self.call_action("applyContours")
    
    def clear_contours(self):
        self.call_action("clearContours", True)
    
    def set_contours_visible(self, state):
        self.call_action("contourConfig.setVisible", state)
    
    def show_contours(self):
        self.set_contours_visible(True)
        
    def hide_contours(self):
        self.set_contours_visible(False)
    
    # HISTOGRAM (TODO)
    
    def use_cube_histogram(self, contours=False):
        self.call_action(f"renderConfig.setUseCubeHistogram{'Contours' if contours else ''}", True)
    
    def use_channel_histogram(self, contours=False):
        self.call_action(f"renderConfig.setUseCubeHistogram{'Contours' if contours else ''}", False)
            
    def set_percentile_rank(self, rank):
        self.call_action("renderConfig.setPercentileRank", rank)
    
    # CLOSE
    
    def close(self):
        self.session.call_action("closeFile", self._frame)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='A basic test of the prototype client.')
    parser.add_argument('--host', help='Server host', default="localhost")
    parser.add_argument('--port', help='Server port', type=int, default=50051)
    parser.add_argument('--session', help='Session ID', type=int, required=True)
    parser.add_argument('--image', help='Image name', required=True)
    parser.add_argument('--append', help='Append image', action='store_true')
    parser.add_argument('--debug', help='Log gRPC requests and responses', action='store_true')
    
    args = parser.parse_args()
    
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)

    session = Session(args.host, args.port, args.session)

    image = session.append_image(args.image) if args.append else session.open_image(args.image)

    Colormap.fetch(session)
    image.set_colormap(Colormap.VIRIDIS)
    
    logger.info(f"Image shape is {image.shape()}")
    logger.info(f"Image name is {image.file_name}")
            
    #image.close()
