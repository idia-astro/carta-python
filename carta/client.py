import json
import posixpath
import base64

import grpc

from . import carta_service_pb2
from . import carta_service_pb2_grpc
from constants import Colormap, Scaling, CoordinateSystem, LabelType, BeamType, PaletteColor, Overlay, SmoothingMode, ContourDashMode
from util import logger, CartaScriptingException, Macro, CartaEncoder
from validation import validate, String, Number, Color, Constant, Boolean, NoneOr, IterableOf, OneOf
    
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

    @validate(String(), String("\d*"))
    def open_image(self, path, hdu=""):
        return Image.new(self, path, hdu, False)

    @validate(String(), String("\d*"))
    def append_image(self, path, hdu=""):
        return Image.new(self, path, hdu, True)

    def image_list(self):
        return [Image(self, f["value"], f["label"]) for f in self.fetch_parameter("frameNames")]
    
    def active_frame(self):
        frame_info = self.fetch_parameter("activeFrame.frameInfo")
        image_id = frame_info["fileId"]
        file_name = frame_info["fileInfo"]["name"]
        return Image(self, image_id, file_name)
    
    def clear_spatial_reference(self):
        self.call_action("clearSpatialReference")
    
    def clear_spectral_reference(self):
        self.call_action("clearSpectralReference")
        
    # CANVAS AND OVERLAY
    @validate(Number(), Number())
    def set_view_area(self, width, height):
        self.call_action("overlayStore.setViewDimension", width, height)
    
    @validate(Constant(CoordinateSystem))
    def set_coordinate_system(self, system=CoordinateSystem.AUTO):
        self.call_action("overlayStore.global.setSystem", system)
        
    @validate(Constant(LabelType))
    def set_label_type(self, label_type):
        self.call_action("overlayStore.global.setLabelType", label_type)
    
    @validate(NoneOr(String()), NoneOr(String()), NoneOr(String()))
    def set_text(self, title=None, label_x=None, label_y=None):
        if title is not None:
            self.call_action("overlayStore.title.setCustomTitleString", title)
            self.call_action("overlayStore.title.setCustomText", True)
        if label_x is not None:
            self.call_action("overlayStore.labels.setCustomLabelX", label_x)
        if label_y is not None:
            self.call_action("overlayStore.labels.setCustomLabelX", label_y)
        if label_x is not None or label_y is not None:
            self.call_action("overlayStore.labels.setCustomText", True)
    
    def clear_text(self):
        self.call_action("overlayStore.title.setCustomText", False)
        self.call_action("overlayStore.labels.setCustomText", False)
    
    # TODO can we get allowed font names from somewhere?
    @validate(OneOf(Overlay.TITLE, Overlay.NUMBERS, Overlay.LABELS), NoneOr(String()), NoneOr(Number()))
    def set_font(self, component, font=None, font_size=None):
        if font is not None:
            self.call_action(f"overlayStore.{component}.setFont", font)
        if font_size is not None:
            self.call_action(f"overlayStore.{component}.setFontSize", font_size)
        
    @validate(Constant(BeamType), NoneOr(Number()), NoneOr(Number()), NoneOr(Number()))
    def set_beam(self, beam_type, width=None, shift_x=None, shift_y=None):
        self.call_action(f"overlayStore.{Overlay.BEAM}.setBeamType", beam_type)
        if width is not None:
            self.call_action(f"overlayStore.{Overlay.BEAM}.setWidth", width)
        if shift_x is not None:
            self.call_action(f"overlayStore.{Overlay.BEAM}.setShiftX", shift_x)
        if shift_y is not None:
            self.call_action(f"overlayStore.{Overlay.BEAM}.setShiftY", shift_y)
        
    @validate(Constant(PaletteColor), Constant(Overlay))
    def set_color(self, color, component=Overlay.GLOBAL):
        self.call_action(f"overlayStore.{component}.setColor", color)
        if component not in (Overlay.GLOBAL, Overlay.BEAM):
            self.call_action(f"overlayStore.{component}.setCustomColor", True)
    
    @validate(Constant(Overlay)) 
    def clear_color(self, component):
        if component != Overlay.GLOBAL:
            self.call_action(f"overlayStore.{component}.setCustomColor", False)
 
    @validate(Constant(Overlay), Boolean())
    def set_visible(self, component, visible):
        if component == Overlay.TICKS:
            logger.warn("Ticks cannot be shown or hidden.")
            return

        if component != Overlay.GLOBAL:
            self.call_action(f"overlayStore.{component}.setVisible", visible)
    
    @validate(Constant(Overlay)) 
    def show(self, component):
        self.set_visible(component, True)
 
    @validate(Constant(Overlay)) 
    def hide(self, component):
        self.set_visible(component, False)
            
    def toggle_labels(self):
        self.call_action("overlayStore.toggleLabels")
    
    # PROFILES (TODO)
    
    @validate(Number(), Number()) 
    def set_cursor(self, x, y):
        self.active_frame().call_action("regionSet.regions[0].setControlPoint", 0, [x, y])
    
    # SAVE IMAGE
    
    @validate(Color())
    def rendered_view_url(self, background_color=None):
        self.call_action("waitForImageData")
        args = ["getImageDataUrl"]
        if background_color:
            args.append(background_color)
        return self.call_action(*args, response_expected=True)
    
    @validate(Color())
    def rendered_view_data(self, background_color=None):
        uri = self.rendered_view_url(background_color)
        data = uri.split(",")[1]
        return base64.b64decode(data)
    
    @validate(String(), Color())
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
        
    @validate(Boolean())
    def set_spatial_matching(self, state):
        self.session.call_action("setSpatialMatchingEnabled", self._frame, state)
        
    def make_spectral_reference(self):
        self.session.call_action("setSpectralReference", self._frame)
        
    @validate(Boolean())
    def set_spectral_matching(self, state):
        self.session.call_action("setSpectralMatchingEnabled", self._frame, state)

    # NAVIGATION

    # TODO: should we check the channel / stokes range, and if so, should we cache that data?
    @validate(Number(), Number(), Boolean())
    def set_channel_stokes(self, channel=None, stokes=None, recursive=True):
        channel = channel or self.fetch_parameter("requiredChannel")
        stokes = stokes or self.fetch_parameter("requiredStokes")
        self.call_action("setChannels", channel, stokes, recursive)

    @validate(Number(), Number())
    def set_center(self, x, y):
        self.call_action("setCenter", x, y)
        
    def set_zoom(self, zoom, absolute=True):
        self.call_action("setZoom", zoom, absolute)
        
    # STYLE

    @validate(Constant(Colormap), Boolean())
    def set_colormap(self, colormap, invert=False):
        self.call_action("renderConfig.setColorMap", colormap)
        self.call_action("renderConfig.setInverted", invert)
    
    # TODO check whether this works as expected
    @validate(Constant(Scaling), NoneOr(Number()), NoneOr(Number()), NoneOr(Number()), NoneOr(Number()))
    def set_scaling(self, scaling, alpha=None, gamma=None, min=None, max=None):
        self.call_action("renderConfig.setScaling", scaling)
        if scaling in (Scaling.LOG, Scaling.POWER) and alpha is not None:
            self.call_action("renderConfig.setAlpha", alpha)
        elif scaling == Scaling.GAMMA and gamma is not None:
            self.call_action("renderConfig.setGamma", gamma)
        if min is not None and max is not None:
            self.call_action("renderConfig.setCustomScale", min, max)
    
    @validate(Boolean())
    def set_raster_visible(self, state):
        self.call_action("renderConfig.setVisible", state)
        
    def show_raster(self):
        self.set_raster_visible(True)
        
    def hide_raster(self):
        self.set_raster_visible(False)
    
    # CONTOURS
    
    @validate(IterableOf(Number()), Constant(SmoothingMode), Number())
    def configure_contours(self, levels, smoothing_mode=SmoothingMode.GAUSSIAN_BLUR, smoothing_factor=4):
        self.call_action("contourConfig.setContourConfiguration", levels, smoothing_mode, smoothing_factor)
    
    @validate(NoneOr(Constant(ContourDashMode)), NoneOr(Number()))
    def set_contour_dash(self, dash_mode=None, thickness=None):
        if dash_mode is not None:
            self.call_action("contourConfig.setDashMode", dash_mode)
        if thickness is not None:
            self.call_action("contourConfig.setThickness", thickness)
    
    @validate(Color())
    def set_contour_color(self, color):
        self.call_action("contourConfig.setColor", color)
        self.call_action("contourConfig.setColormapEnabled", False)
    
    @validate(Constant(Colormap), NoneOr(Number), NoneOr(Number))
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
    
    @validate(Boolean())
    def set_contours_visible(self, state):
        self.call_action("contourConfig.setVisible", state)
    
    def show_contours(self):
        self.set_contours_visible(True)
        
    def hide_contours(self):
        self.set_contours_visible(False)
    
    # HISTOGRAM (TODO)
    
    @validate(Boolean())
    def use_cube_histogram(self, contours=False):
        self.call_action(f"renderConfig.setUseCubeHistogram{'Contours' if contours else ''}", True)
    
    @validate(Boolean())
    def use_channel_histogram(self, contours=False):
        self.call_action(f"renderConfig.setUseCubeHistogram{'Contours' if contours else ''}", False)
            
    @validate(Number(0, 100))
    def set_percentile_rank(self, rank):
        self.call_action("renderConfig.setPercentileRank", rank)
    
    # CLOSE
    
    def close(self):
        self.session.call_action("closeFile", self._frame)
