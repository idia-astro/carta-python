"""
This is the main module of the CARTA Python wrapper. It comprises a `Session` class and an `Image` class.

The session object can be connected to an existing frontend session. It can also create a new session, for example in a headless browser, using a browser class from :obj:`carta.browser`. Please see that module's documentation for more information about the additional dependencies which are required for this.

Image objects should not be instantiated directly, and should only be created through methods on the session object.

Usage example::

    session = Session.connect("localhost", 50051, 1)

    for img in session.image_list():
        img.close()

    img = session.open_image("/full/path/to/image.fits")
    img2 = session.append_image("/path/to/another/image.fits")

    img.set_channel_stokes(10, 0, True)
    img.set_colormap(Colormap.VIRIDIS)

    y, x = img.shape[-2:]
    img.set_center(x/2, y/2)
    img.set_zoom(4)
"""

import json
import posixpath
import base64

import grpc

from cartaproto import carta_service_pb2
from cartaproto import carta_service_pb2_grpc
from .constants import Colormap, Scaling, CoordinateSystem, LabelType, BeamType, PaletteColor, Overlay, SmoothingMode, ContourDashMode
from .util import logger, CartaActionFailed, CartaBadResponse, Macro, CartaEncoder, cached
from .validation import validate, String, Number, Color, Constant, Boolean, NoneOr, IterableOf, OneOf, Evaluate, Attr
    
# TODO: profiles -- need to wait for refactoring to make tsv and png profiles accessible
# TODO: histograms -- also need access to urls for exporting histograms
# TODO: preferences -- generic get and set for now
# TODO: regions

class Session:
    """This object corresponds to a CARTA frontend session.
    
    This class provides the core generic method for calling actions on the frontend (through the backend), as well as convenience methods which wrap this generic method and provide a more intuitive and user-friendly interface to frontend functionality associated with the session as a whole.
    
    The session object can be used to create image objects, which provide analogous convenience methods for functionality associated with individual images.
    
    Parameters
    ----------
    host : string
        The address of the host where the CARTA backend is running.
    port : number
        The gRPC port on which the CARTA backend is listening.
    session_id : number
        The ID of an existing CARTA frontend session connected to this CARTA backend.
    
    Attributes
    ----------
    uri : string
        The URI of the CARTA backend's gRPC interface, constructed from the host and port parameters.
    session_id : number
        The ID of the CARTA frontend session associated with this object.
    """
    def __init__(self, host, port, session_id, browser=None):
        self.uri = "%s:%s" % (host, port)
        self.session_id = session_id
        
        self._browser = browser
        
    def __del__(self):
        self.close()
    
    @classmethod
    def connect(cls, host, port, session_id):
        """Connect to an existing frontend session.
        
        Parameters
        ----------
        host : string
            The address of the host where the CARTA backend is running.
        port : number
            The gRPC port on which the CARTA backend is listening.
        session_id : number
            The ID of an existing CARTA frontend session connected to this CARTA backend.
            
        Returns
        -------
        :obj:`carta.client.Session`
            A session object connected to the frontend session provided.
        """
        return cls(host, port, session_id)
    
    @classmethod
    def new(cls, browser, frontend_url, grpc_port):
        """Create a new frontend session.
        
        Parameters
        ----------
        browser : :obj:`carta.browser.Browser`
            The browser to use to open the frontend.
        frontend_url : string
            The URL of the frontend.
        grpc_port : number
            The gRPC port on which the CARTA backend is listening. TODO: this should be deprecated when the frontend logs the gRPC port.
            
        Returns
        -------
        :obj:`carta.client.Session`
            A session object connected to a new frontend session running in the browser provided.
        """
        return browser.new_session(frontend_url, grpc_port)
        
    def __repr__(self):
        return f"Session(session_id={self.session_id}, uri={self.uri})"
    
    def split_path(self, path):
        """Extract a path to a frontend object store and an action from a combined path.
        
        Parameters
        ----------
        path : string
            A dot-separated path to an action on a frontend object store.
            
        Returns
        -------
        string
            The dot-separated path to the object store.
        string
            The name of the action.
        """
        parts = path.split('.')
        return '.'.join(parts[:-1]), parts[-1]
        
    def call_action(self, path, *args, **kwargs):
        """Call an action on the frontend through the backend's gRPC interface.
        
        This method is the core of the session class, and provides a generic interface for calling any action on the frontend. This is exposed as a public method to give developers the option of writing experimental functionality; wherever possible script writers should instead use the more user-friendly methods on the session and image objects which wrap this method.
        
        Parameters
        ----------
        path : string
            The full dot-separated path to a frontend action.
        *args
            A variable-length list of parameters to pass to the action. :obj:`carta.util.Macro` objects may be used to refer to frontend objects which will be evaluated dynamically. This parameter list will be serialized into a JSON string with :obj:`carta.util.CartaEncoder`.
        **kwargs
            Arbitrary keyword arguments. At present only two are used: `async` (boolean) is passed in the gRPC message to indicate that an action is asynchronous (but this currently has no effect); and `response_expected` (boolean) indicates that the action should return a JSON object.
        
        Returns
        -------
        None or an object
            If the action returns a JSON object, this method will return that response deserialized into a Python object.
        
        Raises
        ------
        CartaActionFailed
            If a :obj:`grpc.RpcError` occurs, or if the gRPC request fails.
        CartaBadResponse    
            If a request which was expected to have a JSON response did not have one, or if a JSON response could not be decoded.
        """
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
            self.close()
            raise CartaActionFailed(f"{carta_action_description} failed: {e.details()}") from e
        
        logger.debug(f"Got success status: {response.success}; message: {response.message}; response: {response.response}")
        
        if not response.success:
            self.close()
            raise CartaActionFailed(f"{carta_action_description} failed: {response.message}")
        
        if response.response == '':
            if response_expected:
                self.close()
                raise CartaBadResponse(f"{carta_action_description} expected a response, but did not receive one.")
            return None
        
        try:
            decoded_response = json.loads(response.response)
        except json.decoder.JSONDecodeError as e:
            self.close()
            raise CartaBadResponse(f"{carta_action_description} received a response which could not be decoded.\nResponse string: {repr(response.response)}\nError: {e}") from e
        
        return decoded_response

    def get_value(self, path):
        """Get the value of an attribute from a frontend store.
        
        Like the `call_action` method, this is exposed in the public API but is not intended to be used directly under normal circumstances.
        
        Parameters
        ----------
        path : string
            The full path to the attribute.
        
        Returns
        -------
        object
            The value of the attribute, deserialized from a JSON string.
        """
        path, parameter = self.split_path(path)
        macro = Macro(path, parameter)
        return self.call_action("fetchParameter", macro, response_expected=True)
    
    # FILE BROWSING
    
    def resolve_file_path(self, path):
        """Convert a file path to an absolute path.
        
        Parameters
        ----------
        path : string
            The file path, which may be absolute or relative to the current directory.
            
        Returns
        -------
        string
            The absolute file path, relative to the CARTA backend's root.
        """
        if path.startswith('/'):
            return path
        else:
            return f"{self.pwd()}/{path}"
    
    def pwd(self):
        """The current directory.
        
        Returns
        -------
        string
            The session's current directory. 
        """
        self.call_action("fileBrowserStore.getFileList", Macro("fileBrowserStore", "startingDirectory"))
        directory = self.get_value("fileBrowserStore.fileList.directory")
        return f"/{directory}"
    
    def ls(self):
        """The current directory listing.
        
        Returns
        -------
        list
            The list of files and subdirectories in the session's current directory. 
        """
        self.call_action("fileBrowserStore.getFileList", Macro("fileBrowserStore", "startingDirectory"))
        file_list = self.get_value("fileBrowserStore.fileList")
        items = []
        if "files" in file_list:
            items.extend([f["name"] for f in file_list["files"]])
        if "subdirectories" in file_list:
            items.extend([f"{d}/" for d in file_list["subdirectories"]])
        return sorted(items)
    
    def cd(self, path):
        """Change the current directory
        
        TODO: .. is not supported. If the directory doesn't exist, the frontend attribute is set, and subsequent file list actions seem to fail silently. We attempt to recover from this and restore the attribute to its previous valid state.
        
        Parameters
        ----------
        path : string
            The path to the new directory, which may be relative to the current directory or absolute (relative to the CARTA backend root).
        """
        full_path = self.resolve_file_path(path)
        self.call_action("fileBrowserStore.saveStartingDirectory", full_path)
        pwd = self.pwd()
        if pwd != full_path:
            self.call_action("fileBrowserStore.saveStartingDirectory", pwd)
            print(f"Warning: could not change directory to {full_path}.")
    
    # IMAGES

    @validate(String(), String("\d+"))
    def open_image(self, path, hdu=""):
        """Open a new image, replacing any existing images.
        
        Parameters
        ----------
        path : {0}
            The path to the image file, either relative to the session's current directory or an absolute path relative to the CARTA backend's root directory.
        hdu : {1}
            The HDU to select inside the file.
        """
        return Image.new(self, path, hdu, False)

    @validate(String(), String("\d+"))
    def append_image(self, path, hdu=""):
        """Append a new image, keeping any existing images.
        
        Parameters
        ----------
        path : {0}
            The path to the image file, either relative to the session's current directory or an absolute path relative to the CARTA backend's root directory.
        hdu : {1}
            The HDU to select inside the file.
        """
        return Image.new(self, path, hdu, True)

    def image_list(self):
        """Return the list of currently open images.
        
        Returns
        -------
        list of :obj:`carta.client.Image` objects.
        """
        return Image.from_list(self, self.get_value("frameNames"))
    
    def active_frame(self):
        """Return the currently active image.
        
        Returns
        -------
        :obj:`carta.client.Image`
            The currently active image.
        """
        frame_info = self.get_value("activeFrame.frameInfo")
        image_id = frame_info["fileId"]
        file_name = frame_info["fileInfo"]["name"]
        return Image(self, image_id, file_name)
    
    def clear_spatial_reference(self):
        """Clear the spatial reference."""
        self.call_action("clearSpatialReference")
    
    def clear_spectral_reference(self):
        """Clear the spectral reference."""
        self.call_action("clearSpectralReference")
        
    # CANVAS AND OVERLAY
    @validate(Number(), Number())
    def set_view_area(self, width, height):
        """Set the dimensions of the view area.
        
        TODO: we need a way to set the real pixel value. Simplest solution: expose the pixel ratio on the frontend and divide by it. Fractional values work as expected.
        
        Parameters
        ----------
        width : {0}
            The new width, in pixels divided by the browser's pixel ratio.
        height : {1}
            The new height, in pixels divided by the browser's pixel ratio.
        """
        self.call_action("overlayStore.setViewDimension", width, height)
    
    @validate(Constant(CoordinateSystem))
    def set_coordinate_system(self, system=CoordinateSystem.AUTO):
        """Set the coordinate system.
        
        Parameters
        ----------
        system : {0}
            The coordinate system.
        """
        self.call_action("overlayStore.global.setSystem", system)
        
    @validate(Constant(LabelType))
    def set_label_type(self, label_type):
        """Set the label type.
        
        Parameters
        ----------
        label_type : {0}
            The label type.
        """
        self.call_action("overlayStore.global.setLabelType", label_type)
    
    @validate(NoneOr(String()), NoneOr(String()), NoneOr(String()))
    def set_text(self, title=None, label_x=None, label_y=None):
        """Set custom title and/or the axis label text.
        
        Parameters
        ----------
        title : {0}
            The title text.
        label_x : {1}
            The X-axis text.
        label_y : {2}
            The Y-axis text.
        """
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
        """Clear all custom title and axis text."""
        self.call_action("overlayStore.title.setCustomText", False)
        self.call_action("overlayStore.labels.setCustomText", False)
    
    @validate(OneOf(Overlay.TITLE, Overlay.NUMBERS, Overlay.LABELS), NoneOr(String()), NoneOr(Number()))
    def set_font(self, component, font=None, font_size=None):
        """Set the font and/or font size of an overlay component.
        
        TODO: can we get the allowed font names from somewhere?
        
        Parameters
        ----------
        component : {0}
            The overlay component.
        font : {1}
            The font name.
        font_size : {2}
            The font size.
        """
        if font is not None:
            self.call_action(f"overlayStore.{component}.setFont", font)
        if font_size is not None:
            self.call_action(f"overlayStore.{component}.setFontSize", font_size)
        
    @validate(NoneOr(Constant(BeamType)), NoneOr(Number()), NoneOr(Number()), NoneOr(Number()))
    def set_beam(self, beam_type=None, width=None, shift_x=None, shift_y=None):
        """Set the beam properties.
        
        Parameters
        ----------
        beam_type : {0}
            The beam type.
        width : {1}
            The beam width.
        shift_x : {2}
            The X position.
        shift_y : {3}
            The Y position.
        """
        if beam_type is not None:
            self.call_action(f"overlayStore.{Overlay.BEAM}.setBeamType", beam_type)
        if width is not None:
            self.call_action(f"overlayStore.{Overlay.BEAM}.setWidth", width)
        if shift_x is not None:
            self.call_action(f"overlayStore.{Overlay.BEAM}.setShiftX", shift_x)
        if shift_y is not None:
            self.call_action(f"overlayStore.{Overlay.BEAM}.setShiftY", shift_y)
        
    @validate(Constant(PaletteColor), Constant(Overlay))
    def set_color(self, color, component=Overlay.GLOBAL):
        """Set the custom color on an overlay component, or the global color.
                
        Parameters
        ----------
        color : {0}
            The color.
        component : {1}
            The overlay component.
        """
        self.call_action(f"overlayStore.{component}.setColor", color)
        if component not in (Overlay.GLOBAL, Overlay.BEAM):
            self.call_action(f"overlayStore.{component}.setCustomColor", True)
    
    @validate(Constant(Overlay)) 
    def clear_color(self, component):
        """Clear the custom color from an overlay component.
        
        Parameters
        ----------
        component : {0}
            The overlay component.
        """
        if component != Overlay.GLOBAL:
            self.call_action(f"overlayStore.{component}.setCustomColor", False)
 
    @validate(Constant(Overlay), Boolean())
    def set_visible(self, component, visible):
        """Set the visibility of an overlay component.
        
        Ticks cannot be shown or hidden in AST.
        
        Parameters
        ----------
        component : {0}
            The overlay component.
        visible : {1}
            The visibility state.
        """
        if component == Overlay.TICKS:
            logger.warn("Ticks cannot be shown or hidden.")
            return

        if component != Overlay.GLOBAL:
            self.call_action(f"overlayStore.{component}.setVisible", visible)
    
    @validate(Constant(Overlay)) 
    def show(self, component):
        """Show an overlay component.
        
        Parameters
        ----------
        component : {0}
            The overlay component.
        """
        self.set_visible(component, True)
 
    @validate(Constant(Overlay)) 
    def hide(self, component):
        """Hide an overlay component.
        
        Parameters
        ----------
        component : {0}
            The overlay component.
        """
        self.set_visible(component, False)
            
    def toggle_labels(self):
        """Toggle the overlay labels."""
        self.call_action("overlayStore.toggleLabels")
    
    # PROFILES (TODO)
    
    @validate(Number(), Number()) 
    def set_cursor(self, x, y):
        """Set the curson position.
        
        TODO: this is a precursor to makinf z-profiles available, but currently the relevant functionality is not exposed by the frontend.
        
        Parameters
        ----------
        x : {0}
            The X position.
        y : {1}
            The Y position.
        
        """
        self.active_frame().call_action("regionSet.regions[0].setControlPoint", 0, [x, y])
    
    # SAVE IMAGE
    
    @validate(NoneOr(Color()))
    def rendered_view_url(self, background_color=None):
        """Get a data URL of the rendered active image.
        
        Parameters
        ----------
        background_color : {0}
            The background color. By default the background will be transparent.
            
        Returns
        -------
        string
            A data URL for the rendered image in PNG format, base64-encoded.
        
        """
        self.call_action("waitForImageData")
        args = ["getImageDataUrl"]
        if background_color:
            args.append(background_color)
        return self.call_action(*args, response_expected=True)
    
    @validate(Color())
    def rendered_view_data(self, background_color=None):
        """Get the decoded data of the rendered active image.
        
        Parameters
        ----------
        background_color : {0}
            The background color. By default the background will be transparent.
            
        Returns
        -------
        bytes
            The decoded PNG image data.
        
        """
        uri = self.rendered_view_url(background_color)
        data = uri.split(",")[1]
        return base64.b64decode(data)
    
    @validate(String(), Color())
    def save_rendered_view(self, file_name, background_color=None):
        """Save the decoded data of the rendered active image to a file.
        
        Parameters
        ----------
        file_name : {0}
            The name of the file.
        background_color : {1}
            The background color. By default the background will be transparent.
        """
        with open(file_name, 'wb') as f:
            f.write(self.rendered_view_data(background_color))
            
    def close(self):
        """Close the browser session, if applicable.
        
        If this session was created with the `new` method and a browser, close the browser session. If this session was connected to an existing external browser session, this method has no effect.
        """
        
        if self._browser is not None:
            self._browser.close()


class Image:
    """This object corresponds to an image open in a CARTA frontend session.
    
    This class should not be instantiated directly. Instead, use the session object's methods for opening new images or retrieving existing images.
    
    Parameters
    ----------
    session : :obj:`carta.client.Session`
        The session object associated with this image.
    image_id : integer
        The ID identifying this image within the session. This is a unique number which is not reused, not the index of the image within the list of currently open images.
    file_name : string
        The file name of the image. This is not a full path.
    
    Attributes
    ----------
    session : :obj:`carta.client.Session`
        The session object associated with this image.
    image_id : integer
        The ID identifying this image within the session.
    file_name : string
        The file name of the image.
    
    """
    def __init__(self, session, image_id, file_name):
        self.session = session
        self.image_id = image_id
        self.file_name = file_name
        
        self._base_path = f"frameMap[{image_id}]"
        self._frame = Macro("", self._base_path)
    
    @classmethod
    def new(cls, session, path, hdu, append):
        """Open or append a new image in the session and return an image object associated with it.
        
        This method should not be used directly. It is wrapped by the `open_image` and `append_image` methods of the session object.
        
        Parameters
        ----------
        session : :obj:`carta.client.Session`
            The session object.
        path : string
            The path to the image file, either relative to the session's current directory or an absolute path relative to the CARTA backend's root directory.
        hdu : string
            The HDU to open.
        append : boolean
            Whether the image should be appended. By default it is not, and all other open images are closed.
        
        Returns
        -------
        :obj:`carta.client.Image`
            A new image object.
        """
        path = session.resolve_file_path(path)
        directory, file_name = posixpath.split(path)
        saved_pwd = session.pwd()
        image_id = session.call_action("appendFile" if append else "openFile", directory, file_name, hdu)
        session.cd(saved_pwd)
        
        return cls(session, image_id, file_name)
    
    @classmethod
    def from_list(cls, session, image_list):
        """Create a list of image objects from a list of open images retrieved from the frontend.
        
        This method should not be used directly. It is wrapped by the `image_list` method of the session object.
        
        Parameters
        ----------
        session : :obj:`carta.client.Session`
            The session object.
        image_list : list of dicts
            The JSON object representing frame names retrieved from the frontend.
            
        Returns
        -------
        list of :obj:`carta.client.Image`
            A list of new image objects.
        """
        return [cls(session, f["value"], f["label"].split(":")[1].strip()) for f in image_list]
        
    def __repr__(self):
        return f"{self.session.session_id}:{self.image_id}:{self.file_name}"
    
    def call_action(self, path, *args, **kwargs):
        """Convenience wrapper for the session object's generic action method.
        
        This method calls :obj:`carta.client.Session.call_action` after prepending this image's base path to the path parameter.
        
        Parameters
        ----------
        path : string
            The path to an action relative to this image's frame store.
        *args
            A variable-length list of parameters. These are passed unmodified to the session method.
        **kwargs
            Arbitrary keyword parameters. These are passed unmodified to the session method.
        
        Returns
        -------
            object or None
                The unmodified return value of the session method.
        """
        return self.session.call_action(f"{self._base_path}.{path}", *args, **kwargs)
    
    def get_value(self, path):
        """Convenience wrapper for the session object's generic method for retrieving attribute values.
        
        This method calls :obj:`carta.client.Session.get_value` after prepending this image's base path to the path parameter.
        
        Parameters
        ----------
        path : string
            The path to an attribute relative to this image's frame store.
        
        Returns
        -------
            object
                The unmodified return value of the session method.
        """
        return self.session.get_value(f"{self._base_path}.{path}")
    
    # METADATA
    
    @property
    @cached
    def directory(self):
        """The path to the directory containing the image."""
        return self.get_value("frameInfo.directory")
    
    @property
    @cached
    def header(self):
        """The header of the image."""
        return self.get_value("frameInfo.fileInfoExtended.headerEntries")
    
    @property
    @cached
    def shape(self):
        """The shape of the image."""
        return list(reversed([self.width, self.height, self.depth, self.stokes][:self.ndim]))
    
    @property
    @cached
    def width(self):
        """The width of the image."""
        return self.get_value("frameInfo.fileInfoExtended.width")
    
    @property
    @cached
    def height(self):
        """The height of the image."""
        return self.get_value("frameInfo.fileInfoExtended.height")
    
    @property
    @cached
    def depth(self):
        """The depth of the image."""
        return self.get_value("frameInfo.fileInfoExtended.depth")
    
    @property
    @cached
    def stokes(self):
        """The number of Stokes parameters of the image."""
        return self.get_value("frameInfo.fileInfoExtended.stokes")
    
    @property
    @cached
    def ndim(self):
        """The number of dimensions of the image."""
        return self.get_value("frameInfo.fileInfoExtended.dimensions")
    
    # SELECTION
    
    def make_active(self):
        """Make this the active image."""
        self.session.call_action("setActiveFrame", self._frame)
        
    def make_spatial_reference(self):
        """Make this image the spatial reference."""
        self.session.call_action("setSpatialReference", self._frame)
        
    @validate(Boolean())
    def set_spatial_matching(self, state):
        """Enable or disable spatial matching.
        
        Parameters
        ----------
        state : boolean
            The desired spatial matching state.
        """
        self.session.call_action("setSpatialMatchingEnabled", self._frame, state)
        
    def make_spectral_reference(self):
        """Make this image the spectral reference."""
        self.session.call_action("setSpectralReference", self._frame)
        
    @validate(Boolean())
    def set_spectral_matching(self, state):
        """Enable or disable spectral matching.
        
        Parameters
        ----------
        state : boolean
            The desired spectral matching state.
        """
        self.session.call_action("setSpectralMatchingEnabled", self._frame, state)

    # NAVIGATION

    @validate(Evaluate(Number, 0, Attr("depth"), Number.INCLUDE_MIN), Evaluate(Number, 0, Attr("stokes"), Number.INCLUDE_MIN), Boolean())
    def set_channel_stokes(self, channel=None, stokes=None, recursive=True):
        """Set the channel and/or Stokes.
        
        Parameters
        ----------
        channel : {0}
            The desired channel. Defaults to the current channel.
        stokes : {1}
            The desired stokes. Defaults to the current Stokes.
        recursive : {2}
            Whether to perform the same change on all spectrally matched images. Defaults to True.
        """
        channel = channel or self.get_value("requiredChannel")
        stokes = stokes or self.get_value("requiredStokes")
        self.call_action("setChannels", channel, stokes, recursive)

    @validate(Number(), Number())
    def set_center(self, x, y):
        """Set the center position.
        
        TODO: what are the units?
        
        Parameters
        ----------
        x : {0}
            The X position.
        y : {1}
            The Y position.
        """
        self.call_action("setCenter", x, y)
        
    def set_zoom(self, zoom, absolute=True):
        """Set the zoom level.
        
        TODO: explain this more rigorously.
        
        Parameters
        ----------
        zoom : {0}
            The zoom level.
        absolute : {1}
            Whether the zoom level should be treated as absolute. By default it is adjusted by a scaling factor.
        """
        self.call_action("setZoom", zoom, absolute)
        
    # STYLE

    @validate(Constant(Colormap), Boolean())
    def set_colormap(self, colormap, invert=False):
        """Set the colormap.
        
        Parameters
        ----------
        colormap : {0}
            The colormap.
        invert : {1}
            Whether the colormap should be inverted.
        """
        self.call_action("renderConfig.setColorMap", colormap)
        self.call_action("renderConfig.setInverted", invert)
    
    # TODO check whether this works as expected
    @validate(Constant(Scaling), NoneOr(Number()), NoneOr(Number()), NoneOr(Number()), NoneOr(Number()))
    def set_scaling(self, scaling, alpha=None, gamma=None, min=None, max=None):
        """Set the colormap scaling.
        
        Parameters
        ----------
        scaling : {0}
            The scaling type.
        alpha : {1}
            The alpha value (only applicable to `LOG` and `POWER` scaling types).
        gamma : {2}
            The gamma value (only applicable to the `GAMMA` scaling type).
        min : {3}
            The minimum of the scale. Only used if both `min` and `max` are set.
        max : {4}
            The maximum of the scale. Only used if both `min` and `max` are set.
        """
        self.call_action("renderConfig.setScaling", scaling)
        if scaling in (Scaling.LOG, Scaling.POWER) and alpha is not None:
            self.call_action("renderConfig.setAlpha", alpha)
        elif scaling == Scaling.GAMMA and gamma is not None:
            self.call_action("renderConfig.setGamma", gamma)
        if min is not None and max is not None:
            self.call_action("renderConfig.setCustomScale", min, max)
    
    @validate(Boolean())
    def set_raster_visible(self, state):
        """Set the raster image visibility.
        
        Parameters
        ----------
        state : {0}
            The desired visibility state.
        """
        self.call_action("renderConfig.setVisible", state)
        
    def show_raster(self):
        """Show the raster image."""
        self.set_raster_visible(True)
        
    def hide_raster(self):
        """Hide the raster image."""
        self.set_raster_visible(False)
    
    # CONTOURS
    
    @validate(IterableOf(Number()), Constant(SmoothingMode), Number())
    def configure_contours(self, levels, smoothing_mode=SmoothingMode.GAUSSIAN_BLUR, smoothing_factor=4):
        """Configure contours.
        
        Parameters
        ----------
        levels : {0}
            The contour levels. This may be a numeric numpy array; e.g. the output of `arange`.
        smoothing_mode : {1}
            The smoothing mode.
        smoothing_factor : {2}
            The smoothing factor.
        """
        self.call_action("contourConfig.setContourConfiguration", levels, smoothing_mode, smoothing_factor)
    
    @validate(NoneOr(Constant(ContourDashMode)), NoneOr(Number()))
    def set_contour_dash(self, dash_mode=None, thickness=None):
        """Set the contour dash style.
        
        Parameters
        ----------
        dash_mode : {0}
            The dash mode.
        thickness : {1}
            The dash thickness.
        """
        if dash_mode is not None:
            self.call_action("contourConfig.setDashMode", dash_mode)
        if thickness is not None:
            self.call_action("contourConfig.setThickness", thickness)
    
    @validate(Color())
    def set_contour_color(self, color):
        """Set the contour color.
        
        This automatically disables use of the contour colormap.
        
        Parameters
        ----------
        color : {0}
            The color.
        """
        self.call_action("contourConfig.setColor", color)
        self.call_action("contourConfig.setColormapEnabled", False)
    
    @validate(Constant(Colormap), NoneOr(Number()), NoneOr(Number()))
    def set_contour_colormap(self, colormap, bias=None, contrast=None):
        """Set the contour colormap.
        
        This automatically enables use of the contour colormap.
        
        Parameters
        ----------
        colormap : {0}
            The colormap.
        bias : {1}
            The colormap bias.
        contrast : {2}
            The colormap contrast.
        """
        self.call_action("contourConfig.setColormap", colormap)
        self.call_action("contourConfig.setColormapEnabled", True)
        if bias is not None:
            self.call_action("contourConfig.setColormapBias", bias)
        if contrast is not None:
            self.call_action("contourConfig.setColormapContrast", contrast)
    
    def apply_contours(self):
        """Apply the contour configuration."""
        self.call_action("applyContours")
    
    def clear_contours(self):
        """Clear the contours."""
        self.call_action("clearContours", True)
    
    @validate(Boolean())
    def set_contours_visible(self, state):
        """Set the contour visibility.
        
        Parameters
        ----------
        state : {0}
            The desired visibility state.
        """
        self.call_action("contourConfig.setVisible", state)
    
    def show_contours(self):
        """Show the contours."""
        self.set_contours_visible(True)
        
    def hide_contours(self):
        """Hide the contours."""
        self.set_contours_visible(False)
    
    # HISTOGRAM
    
    @validate(Boolean())
    def use_cube_histogram(self, contours=False):
        """Use the cube histogram.
        
        Parameters
        ----------
        contours : {0}
            Apply to the contours. By default this is applied to the raster image.
        """
        self.call_action(f"renderConfig.setUseCubeHistogram{'Contours' if contours else ''}", True)
    
    @validate(Boolean())
    def use_channel_histogram(self, contours=False):
        """Use the channel histogram.
        
        Parameters
        ----------
        contours : {0}
            Apply to the contours. By default this is applied to the raster image.
        """
        self.call_action(f"renderConfig.setUseCubeHistogram{'Contours' if contours else ''}", False)
            
    @validate(Number(0, 100))
    def set_percentile_rank(self, rank):
        """Set the percentile rank.
        
        Parameters
        ----------
        rank : {0}
            The percentile rank.
        """
        self.call_action("renderConfig.setPercentileRank", rank)
    
    # CLOSE
    
    def close(self):
        """Close this image."""
        self.session.call_action("closeFile", self._frame)
