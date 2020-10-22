#!/usr/bin/env python3

import argparse
import logging

from carta.client import Session, Colormap, logger

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='A basic test of the prototype client.')
    parser.add_argument('--host', help='Server host', default="localhost")
    parser.add_argument('--port', help='Server port', type=int, default=50051)
    parser.add_argument('--session', help='Session ID', type=int, required=True)
    parser.add_argument('--image', help='Image name', required=True)
    parser.add_argument('--append', help='Append image', action='store_true')
    parser.add_argument('--debug', help='Log gRPC requests and responses', action='store_true')
    
    args = parser.parse_args()
    
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)

    session = Session.connect(args.host, args.port, args.session)
    image = session.append_image(args.image) if args.append else session.open_image(args.image)
    image.set_colormap(Colormap.VIRIDIS)
    
    logger.info(f"Image shape is {image.shape()}")
    logger.info(f"Image name is {image.file_name}")
