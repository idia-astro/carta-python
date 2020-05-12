carta-python
------------

This is a prototype of a scripting interface which uses a generic gRPC service in the CARTA backend as a proxy to call actions on the CARTA frontend.

Until the corresponding CARTA repository branches have been merged into `dev`, please use the following:

* For `carta-backend`: `confluence/generic_scripting`. Run the backend executable with a `-grpc_port` parameter. The value should match the `port` value that you supply to the client below.
* For `carta-protobuf`: `angus/generic_scripting`
* For `carta-frontend`: `angus/test_debug_execution`

To generate the `pb2` files, run the script provided:

    cd cartavis
    ./build_python.sh
    
To perform a basic end-to-end test by opening or appending an image, you can execute the prototype client as a script with commandline parameters. Use `./prototype_client.py --help` to see options.

Some example usage of the client as a module is shown in the Jupyter notebook provided. The client is under rapid development and this API should be considered experimental and subject to change depending on feedback. The current overall design principle considers session and image objects to be lightweight conduits to the frontend. They do not store state and are not guaranteed to be unique or valid connections -- it is the caller's responsibility to manage the objects and store retrieved data as required.
