#!/usr/bin/env python3

import json
import logging
import posixpath
import argparse
import base64

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
        return json.JSONEncoder.default(self, obj)


class RenderMode:
    RASTER, CONTOUR = range(2)


class Colormap:
    # TODO at the moment this data can only be fetched if a file is open
    # But we can store the constants in an independent place somewhere
    @classmethod
    def fetch(cls, session):
        response = session.fetch_parameter("activeFrame.renderConfig.constructor.COLOR_MAPS_ALL")
        
        for i, colormap in enumerate(response):
            setattr(cls, colormap.upper(), i)

    
class DirectionRefFrame:
    # TODO: load these dynamically
    AUTO, ECLIPTIC, FK4, FK5, GALACTIC, ICRS = range(6)

class Session:    
    def __init__(self, host, port, session_id):
        self.uri = "%s:%s" % (host, port)
        self.session_id = session_id        
        
    def __repr__(self):
        return f"Session(session_id={self.session_id}, uri={self.uri})"
        
    def call_action(self, path, action, *args, **kwargs):
        logger.debug("Sending action request to backend; path: %s; action: %s; args: %s, kwargs: %s", path, action, args, kwargs)
        
        # I don't think this can fail
        parameters = json.dumps(args, cls=CartaEncoder)
        
        with grpc.insecure_channel(self.uri) as channel:
            stub = carta_service_pb2_grpc.CartaBackendStub(channel)
            response = stub.CallAction(
                carta_service_pb2.ActionRequest(
                    session_id=self.session_id,
                    path=path,
                    action=action,
                    parameters=parameters,
                    async=kwargs.get("async", False)
                )
            )
        
        logger.debug("Got success status: %s; message: %s; response: %s", response.success, response.message, response.response)
        
        if not response.success:
            raise CartaScriptingException("CARTA scripting action failed: %s", response.message)
        
        if response.response == '':
            return None
        
        try:
            decoded_response = json.loads(response.response)
        except json.decoder.JSONDecodeError as e:
            raise CartaScriptingException("Failed to decode CARTA action response.\nResponse string: %r\nError: %s", response.response, e)
        
        return decoded_response

    def fetch_parameter(self, path):
        parts = path.split('.')
        macro = Macro('.'.join(parts[:-1]), parts[-1])
        return self.call_action("", "fetchParameter", macro)
    
    def image(self, image_id, file_name):
        return Image(self, image_id, file_name)

    def open_image(self, path, hdu="", render_mode=RenderMode.RASTER):
        return Image.new(self, path, hdu, False, render_mode)

    def append_image(self, path, hdu="", render_mode=RenderMode.RASTER):
        return Image.new(self, path, hdu, True, render_mode)

    def image_list(self):
        return [self.image(f["value"], f["label"]) for f in self.fetch_parameter("frameNames")]
    
    def active_frame(self):
        frame_info = self.fetch_parameter("activeFrame.frameInfo")
        image_id = frame_info["fileId"]
        file_name = frame_info["fileInfo"]["name"]
        return self.image(image_id, file_name)
    
    def clear_spatial_reference(self):
        self.call_action("", "clearSpatialReference")
    
    def clear_spectral_reference(self):
        self.call_action("", "clearSpectralReference")
    
    def rendered_view_url(self, background_color=None):
        args = ["", "getImageDataUrl"]
        if background_color:
            args.append(background_color)
        return self.call_action(*args)
    
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
    def new(cls, session, path, hdu, append, render_mode):
        # TODO: how to set render mode in the frontend?
        directory, file_name = posixpath.split(path)
        image_id = session.call_action("", "appendFile" if append else "openFile", directory, file_name, hdu)
        
        return cls(session, image_id, file_name)
        
    def __repr__(self):
        return f"{self.session.session_id}:{self.image_id}:{self.file_name}"
    
    def _resolve_path(self, path):
        return f"{self._base_path}.{path}" if path else self._base_path
    
    def call_action(self, path, action, *args, **kwargs):
        return self.session.call_action(self._resolve_path(path), action, *args, **kwargs)
    
    def fetch_parameter(self, path):
        return self.session.fetch_parameter(self._resolve_path(path))

    def directory(self):
        return self.fetch_parameter("frameInfo.directory")
    
    def header(self):
        return self.fetch_parameter("frameInfo.fileInfoExtended.headerEntries")
    
    def shape(self):
        info = self.fetch_parameter("frameInfo.fileInfoExtended")
        return list(reversed([info["width"], info["height"], info["depth"], info["stokes"]][:info["dimensions"]]))
    
    def make_active(self):
        self.session.call_action("", "setActiveFrame", self._frame)
        
    def make_spatial_reference(self):
        self.session.call_action("", "setSpatialReference", self._frame)
        
    def set_spatial_matching(self, state):
        self.session.call_action("", "setSpatialMatchingEnabled", self._frame, state)
        
    def make_spectral_reference(self):
        self.session.call_action("", "setSpectralReference", self._frame)
        
    def set_spectral_matching(self, state):
        self.session.call_action("", "setSpectralMatchingEnabled", self._frame, state)
    
    def set_coordinate_system(self, direction_ref_frame=DirectionRefFrame.AUTO):
        pass # TODO
 
    def show_grid(self, show=False):
        pass # TODO this and a bunch of other overlay options

    def set_channel_stokes(self, channel=None, stokes=None, recursive=True):
        channel = channel or self.fetch_parameter("requiredChannel")
        stokes = stokes or self.fetch_parameter("requiredStokes")
        self.call_action("", "setChannels", channel, stokes, recursive)

    def set_colormap(self, colormap):
        self.call_action("renderConfig", "setColorMapIndex", colormap)

    def set_center(self, x, y):
        self.call_action("", "setCenter", x, y)
        
    def set_zoom(self, zoom, absolute=True):
        self.call_action("", "setZoom", zoom, absolute)
    
    def close(self):
        self.session.call_action("", "closeFile", self._frame)


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
    logger.info(f"Image name is {image.name()}")
            
    #image.close()
