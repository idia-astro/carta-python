#!/usr/bin/env python3

import json
import logging
import posixpath
import argparse

import grpc

import carta_service_pb2
import carta_service_pb2_grpc


class CartaScriptingException(Exception):
    pass


class RenderMode:
    RASTER, CONTOUR = range(2)


# TODO: these are placeholders; we should actually get these from the frontend when we create the session object.
class Colormap:
    AFMHOT, BLUES, COOLWARM, CUBEHELIX, GIST_HEAT, GIST_STERN, GNUPLOT, GNUPLOT2, GRAY, GREENS, GREYS, HOT, INFERNO, JET, MAGMA, NIPY_SPECTRAL, PLASMA, RAINBOW, RDBU, RDGY, REDS, SEISMIC, SPECTRAL, TAB10, VIRIDIS = range(25)
    
    #@staticmethod
    #def initialise(session):
        #response = session.call_action("", "fetchParameter", "RenderConfigStore.COLOR_MAPS_SELECTED")
        #print(response)

    
class DirectionRefFrame:
    AUTO, ECLIPTIC, FK4, FK5, GALACTIC, ICRS = range(6)

    
def connect(host, port, session_id, debug=False):
    return Session(host, port, session_id, debug)


class Session:
    def __init__(self, host, port, session_id, debug=False):
        self.log = logging.getLogger("carta_scripting")
        self.log.setLevel(logging.DEBUG if debug else logging.ERROR)
        self.log.addHandler(logging.StreamHandler())
        
        self.uri = "%s:%s" % (host, port)
        self.session_id = session_id
        self.images = []
        
    def call_action(self, path, action, *args, **kwargs):
        self.log.debug("Sending action request to backend; path: %s; action: %s; args: %s, kwargs: %s", path, action, args, kwargs)
        
        # I don't think this can fail
        parameters = json.dumps(args)
        
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
        
        self.log.debug("Got success status: %s; message: %s; response: %s", response.success, response.message, response.response)
        
        if not response.success:
            raise CartaScriptingException("CARTA scripting action failed: %s", response.message)
                
        try:
            decoded_response = json.loads(response.response)
        except json.decoder.JSONDecodeError as e:
            raise CartaScriptingException("Failed to decode CARTA action response.\nResponse string: %r\nError: %s", response.response, e)
        
        return decoded_response

    def open_file(self, path, hdu="", render_mode=RenderMode.RASTER):
        return Image(self, path, hdu, False, render_mode)

    def append_file(self, path, hdu="", render_mode=RenderMode.RASTER):
        return Image(self, path, hdu, True, render_mode)
        

class Image:
    def __init__(self, session, path, hdu, append, render_mode):
        self.session = session
        self.path = path
        
        dirname, filename = posixpath.split(path)
        open_function = "appendFile" if append else "openFile"

        response = self.session.call_action("", open_function, dirname, filename, hdu)
        
        self.session.images.append(self)
        self.file_id = response
        # TODO: how to set render mode in the frontend?
        
    def call_action(self):
        pass # TODO; this forwards file-specific requests and handles errors like the file being closed

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

    def set_colormap(self, colormap=Colormap.INFERNO):
        pass # TODO

    def set_view(self, x_min, x_max, y_min, y_max):
        pass # TODO
    
    def close(self):
        pass # close file on the frontend and invalidate yourself


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='A basic test of the prototype client.')
    parser.add_argument('--host', help='Server host', default="localhost")
    parser.add_argument('--port', help='Server port', type=int, default=50051)
    parser.add_argument('--session', help='Session ID', type=int, required=True)
    parser.add_argument('--image', help='Image name', required=True)
    parser.add_argument('--append', help='Append image', action='store_true')
    
    args = parser.parse_args()

    session = connect(args.host, args.port, args.session, True)
    
    #print("COLORMAP")
    
    #Colormap.initialise(session)
    
    print("OPEN FILE")
    
    image = session.append_file(args.image) if args.append else session.open_file(args.image)
