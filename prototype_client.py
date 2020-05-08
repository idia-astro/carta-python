#!/usr/bin/env python3

import json
import logging
import posixpath
import argparse

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
    
    def image(self, file_id, file_name):
        return Image(self, file_id, file_name)

    def open_image(self, path, hdu="", render_mode=RenderMode.RASTER):
        return Image.new(self, path, hdu, False, render_mode)

    def append_image(self, path, hdu="", render_mode=RenderMode.RASTER):
        return Image.new(self, path, hdu, True, render_mode)

    def image_list(self):
        return {f["value"]: self.image(f["value"], f["label"]) for f in self.fetch_parameter("frameNames")}

# TODO: transparently cache immutable values on the image object

class Image:    
    def __init__(self, session, file_id, file_name):
        self.session = session
        self.file_id = file_id
        self.file_name = file_name
    
    @classmethod
    def new(cls, session, path, hdu, append, render_mode):
        # TODO: how to set render mode in the frontend?
        directory, file_name = posixpath.split(path)
        file_id = session.call_action("", "appendFile" if append else "openFile", directory, file_name, hdu)
        
        return cls(session, file_id, file_name)
        
    def __repr__(self):
        return f"{self.session.session_id}:{self.file_id}:{self.file_name}"
    
    def call_action(self, path, action, *args, **kwargs):
        return self.session.call_action(f"frameMap[{self.file_id}].{path}", action, *args, **kwargs)
    
    def fetch_parameter(self, path):
        return self.session.fetch_parameter(f"frameMap[{self.file_id}].{path}")
    
    def directory(self):
        return self.fetch_parameter("frameInfo.directory")
    
    def header(self):
        return self.fetch_parameter("frameInfo.fileInfoExtended.headerEntries")
    
    def shape(self):
        info = self.fetch_parameter("frameInfo.fileInfoExtended")
        return list(reversed([info["width"], info["height"], info["depth"], info["stokes"]][:info["dimensions"]]))
        
    def get_rendered_image(self):
        pass # TODO

    def save(self):
        pass # TODO

    def set_coordinate_system(self, direction_ref_frame=DirectionRefFrame.AUTO):
        pass # TODO
 
    def show_grid(self, show=False):
        pass # TODO

    def set_channel_stokes(self, channel, stokes):
        pass # TODO

    def set_colormap(self, colormap):
        self.call_action("renderConfig", "setColorMapIndex", colormap)

    def set_view(self, x_min, x_max, y_min, y_max):
        pass # TODO
    
    def close(self):
        self.session.call_action("", "closeFile", Macro("", f"frameMap[{self.file_id}]"))


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
