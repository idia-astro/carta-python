#!/usr/bin/env python3

from concurrent import futures
import json
import grpc

from . import carta_service_pb2
from . import carta_service_pb2_grpc


class CartaDummyServer(carta_service_pb2_grpc.CartaBackendServicer):
    # TODO: add some realistic responses for different actions
    def CallAction(self, request, context):
        success = True
        message = ""
        response = json.dumps({"foo": "bar"})
                
        try:
            parsed_params = json.loads(request.parameters)
            print("""GOT ACTION REQUEST:
\tSESSION ID: {}
\tPATH: {}
\tACTION: {}
\tPARAMETERS: {}
\tASYNC: {}""".format(request.session_id, request.path, request.action, request.parameters, request.async))
            
        except json.decoder.JSONDecodeError as e:
            success = False
            message = "Parameter array is not valid JSON: {}".format(e)
            print(message)
        
        return carta_service_pb2.ActionReply(success=success, message=message, response=response)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    carta_service_pb2_grpc.add_CartaBackendServicer_to_server(CartaDummyServer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    serve()
