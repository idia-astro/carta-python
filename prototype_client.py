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
    @classmethod
    def initialise(cls, session):
        response = session.fetch_parameter("activeFrame.renderConfig.constructor.COLOR_MAPS_ALL")
        
        for i, colormap in enumerate(response):
            setattr(cls, colormap.upper(), i)

    
class DirectionRefFrame:
    # TODO: load these dynamically?
    AUTO, ECLIPTIC, FK4, FK5, GALACTIC, ICRS = range(6)

# TODO: connect to existing list of files
class Session:
    def __init__(self, host, port, session_id):
        self.uri = "%s:%s" % (host, port)
        self.session_id = session_id
        self.images = []
        
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
    
    #def fetch_files(self):
        #response = self.fetch_parameter("frameMap")
        #print(response)

    def open_file(self, path, hdu="", render_mode=RenderMode.RASTER):
        return Image.from_session(self, path, hdu, False, render_mode)

    def append_file(self, path, hdu="", render_mode=RenderMode.RASTER):
        return Image.from_session(self, path, hdu, True, render_mode)
        

class Image:
    def __init__(self, session, path, file_id):
        self.session = session
        self.path = path
        self.file_id = file_id
    
    @classmethod
    def from_session(cls, session, path, hdu, append, render_mode):
        # TODO: how to set render mode in the frontend?
        
        dirname, filename = posixpath.split(path)
        open_function = "appendFile" if append else "openFile"
        response = session.call_action("", open_function, dirname, filename, hdu)
        
        file_id = response
        
        image = cls(session, path, file_id)
        session.images.append(image)
        return image

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
        self.session.call_action(f"frameMap[{self.file_id}].renderConfig", "setColorMapIndex", colormap)

    def set_view(self, x_min, x_max, y_min, y_max):
        pass # TODO
    
    def close(self):
        # close the file in the browser and invalidate yourself
        try:
            self.session.call_action("", "closeFile", Macro("", f"frameMap[{self.file_id}]"))
            self.session.images.remove(self)
        except CartaScriptingException as e:
            logger.warn(f"Could not close file {self.path} in the browser: ", e)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='A basic test of the prototype client.')
    parser.add_argument('--host', help='Server host', default="localhost")
    parser.add_argument('--port', help='Server port', type=int, default=50051)
    parser.add_argument('--session', help='Session ID', type=int, required=True)
    parser.add_argument('--image', help='Image name', required=True)
    parser.add_argument('--append', help='Append image', action='store_true')
    
    args = parser.parse_args()
    
    logger.setLevel(logging.DEBUG)

    session = Session(args.host, args.port, args.session)

        
    image = session.append_file(args.image) if args.append else session.open_file(args.image)
    
    
    #session.fetch_files()

    Colormap.initialise(session)
    image.set_colormap(Colormap.VIRIDIS)
        
    #image.close()
