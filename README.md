carta-python
------------

This is a prototype of a scripting interface which uses a generic gRPC service in the CARTA backend as a proxy to call actions on the CARTA frontend.

It depends on the `grpcio` and `grpcio-tools` libraries, which you should install with `pip`. See the [gRPC Python Quick Start instructions](https://grpc.io/docs/quickstart/python/) for more detailed information.

Please use the `dev` branches of `carta-backend` and `carta-frontend`.

The protocol buffer definitions and associated files are in a submodule which has to be loaded. Either clone the repository with `--recursive`, or load the submodule afterwards:

    git submodule update --init

To generate the `pb2` files, run the script provided:

    cd carta-scripting-grpc
    ./build_python.sh
    
To perform a basic end-to-end test by opening or appending an image, you can execute the prototype client as a script with commandline parameters. Use `./prototype_client.py --help` to see options.

Some example usage of the client as a module is shown in the Jupyter notebook provided. The client is under rapid development and this API should be considered experimental and subject to change depending on feedback. The current overall design principle considers session and image objects to be lightweight conduits to the frontend. They do not store state and are not guaranteed to be unique or valid connections -- it is the caller's responsibility to manage the objects and store retrieved data as required.
