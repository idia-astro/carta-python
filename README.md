carta-python
------------

This is a prototype of a scripting interface which uses a generic gRPC service in the CARTA backend to call actions on the CARTA frontend.

The corresponding `carta-protobuf` branch is `confluence/scripting_interface`. To generate the `pb2` files, run the script provided.
    
    git submodule init
    git submodule update
    cd carta-protobuf
    ./build_python.sh
