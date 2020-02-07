#!/usr/bin/env python3

import grpc
import json
import action_pb2
import action_pb2_grpc

def run():
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = carta_scripting_pb2_grpc.ActionStub(channel)
        response = stub.CallAction(
            carta_scripting_pb2.ActionRequest(
                session_id="12345",
                path="",
                action="openFile",
                parameters=json.dumps(["", "foobar.fits", ""]),
                async=True
            )
        )
    print("Got success status: {}; message: {}; response: {}".format(response.success, response.message, response.response))

if __name__ == '__main__':
    run()
