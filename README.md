carta-python
------------

This is a prototype of a scripting interface which uses a generic gRPC service in the CARTA backend as a proxy to call actions on the CARTA frontend.

It can be installed as a package from PyPi with `pip` (the package name is `carta`).

Some example usage of the client as a module is shown in the Jupyter notebook provided. The client is under rapid development and this API should be considered experimental and subject to change depending on feedback. The current overall design principle considers session and image objects to be lightweight conduits to the frontend. They do not store state and are not guaranteed to be unique or valid connections -- it is the caller's responsibility to manage the objects and store retrieved data as required.
