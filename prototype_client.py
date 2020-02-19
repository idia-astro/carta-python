#!/usr/bin/env python3

import grpc
import json
import carta_script_pb2
import carta_script_pb2_grpc

def run():
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = carta_script_pb2_grpc.CartaScriptStub(channel)
        response = stub.CallAction(
            carta_script_pb2.ActionRequest(
                session_id=12345,
                path="",
                action="openFile",
                parameters=json.dumps(["", "foobar.fits", ""]),
                async=True
            )
        )
    print("Got success status: {}; message: {}; response: {}".format(response.success, response.message, response.response))

if __name__ == '__main__':
    run()
