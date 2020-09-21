import os
import re
import setuptools
from distutils.command.build_py import build_py as build_py_orig

class BuildGrpc(setuptools.Command):
    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import grpc_tools.protoc

        grpc_tools.protoc.main([
            'grpc_tools.protoc',
            '-Icarta-scripting-grpc',
            '--python_out=carta/',
            '--grpc_python_out=carta/',
            'carta-scripting-grpc/carta_service.proto'
        ])
        
        # There seriously isn't a better way to fix this relative import as of time of writing
        with open('carta/carta_service_pb2_grpc.py') as f:
            data = f.read()
        data = re.sub("^import carta_service_pb2", "from . import carta_service_pb2", data, flags=re.MULTILINE)
        with open('carta/carta_service_pb2_grpc.py', 'w') as f:
            f.write(data)
        
class BuildPy (build_py_orig):
    def run(self):
        self.run_command('build_grpc')
        super(BuildPy, self).run()

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="carta",
    version="0.0.1",
    author="Adrianna Pińska",
    author_email="adrianna.pinska@gmail.com",
    description="CARTA scripting wrapper written in Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/idia-astro/carta-python",
    packages=setuptools.find_packages(),
    scripts=["bin/carta_test_client.py"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
        "grpcio>=1.26.0",
    ],
    setup_requires=[
        "grpcio-tools>=1.26.0",
    ],
    cmdclass={
        "build_py": BuildPy,
        "build_grpc": BuildGrpc,
    },
)
