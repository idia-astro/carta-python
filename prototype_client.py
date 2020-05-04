#!/usr/bin/env python3

import json
import logging
import posixpath

import grpc

import carta_service_pb2
import carta_service_pb2_grpc


class CartaBackendingException(Exception):
    pass


class RenderMode:
    RASTER, CONTOUR = range(2)


# TODO: these are placeholders; we should actually get these from the frontend when we create the session object.
class Colormap:
    AFMHOT, BLUES, COOLWARM, CUBEHELIX, GIST_HEAT, GIST_STERN, GNUPLOT, GNUPLOT2, GRAY, GREENS, GREYS, HOT, INFERNO, JET, MAGMA, NIPY_SPECTRAL, PLASMA, RAINBOW, RDBU, RDGY, REDS, SEISMIC, SPECTRAL, TAB10, VIRIDIS = range(25)

    
class DirectionRefFrame:
    AUTO, ECLIPTIC, FK4, FK5, GALACTIC, ICRS = range(6)

    
def connect(host, port, session_id, debug=False):
    return Session(host, port, session_id, debug)


class Session:
    def __init__(self, host, port, session_id, debug=False):
        self.log = logging.getLogger("carta_scripting")
        self.log.setLevel(logging.DEBUG if debug else logging.ERROR)
        
        self.uri = "%s:%s" % (host, port)
        self.session_id = session_id
        
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
            raise CartaBackendingException("CARTA scripting action failed: %s", response.message)
                
        try:
            decoded_response = json.loads(response.response)
        except json.decoder.JSONDecodeError as e:
            raise CartaBackendingException("Failed to decode CARTA action response.\nResponse string: %r\nError: %s", response.response, e)
        
        return decoded_response

    def open_file(self, path, hdu="", render_mode=RenderMode.RASTER):
        return Image(self, path, hdu, render_mode)
        

class Image:
    def __init__(self, session, path, hdu, render_mode):
        self.session = session
        
        dirname, filename = posixpath.split(path)
        response = self.session.call_action("", "openFile", dirname, filename, hdu)
        # TODO: and then what? do we get back an ID for this file?
        #self.file_id = response["id"]
        # TODO: how to set render mode in the frontend?

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


if __name__ == '__main__':
    # TODO: when this is actually hooked up, we should pass the session parameters in with argparse
    session = connect("localhost", 50051, 12345, True)
    image = session.open_file("/foo/bar/baz/myimage.fits")
