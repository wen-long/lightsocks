#!/usr/bin/env python

# Copyright (c) 2013 clowwindy
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import sys

try:
    import gevent
    import gevent.monkey
    gevent.monkey.patch_all(dns=gevent.version_info[0] >= 1)
except ImportError:
    gevent = None
    print >>sys.stderr, 'warning: gevent not found, using threading instead'

import socket
import select
import SocketServer
import struct
import os
import json
import logging


def send_all(sock, data):
    bytes_sent = 0
    while True:
        r = sock.send(data[bytes_sent:])
        if r < 0:
            return r
        bytes_sent += r
        if bytes_sent == len(data):
            return bytes_sent


class ThreadingTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    allow_reuse_address = True


class Socks5Server(SocketServer.StreamRequestHandler):
    def handle_tcp(self, sock, remote):
        try:
            fdset = [sock, remote]
            while True:
                r, w, e = select.select(fdset, [], [])
                if sock in r:
                    data = self.encrypt(sock.recv(4096))
                    if len(data) <= 0:
                        break
                    result = send_all(remote, data)
                    if result < len(data):
                        raise Exception('failed to send all data')

                if remote in r:
                    data = self.decrypt(remote.recv(4096))
                    if len(data) <= 0:
                        break
                    result = send_all(sock, data)
                    if result < len(data):
                        raise Exception('failed to send all data')
        finally:
            sock.close()
            remote.close()

    def encrypt(self, data):
        return self.encryptor.encrypt(data)

    def decrypt(self, data):
        return self.encryptor.decrypt(data)

    def send_encrypt(self, sock, data):
        sock.send(self.encrypt(data))

    def handle(self):
        try:
            try:
                logging.info('connecting')
                self.encryptor = encrypt.Encryptor(KEY, METHOD)
                remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                remote.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                remote.connect((SERVER, REMOTE_PORT))
            except socket.error, e:
                # Connection refused
                logging.warn(e)
                return
            self.send_encrypt(remote, header)
            self.handle_tcp(self.connection, remote)
        except socket.error, e:
            logging.warn(e)

if __name__ == '__main__':
    os.chdir(os.path.dirname(__file__) or '.')
    print 'lightsocks v1.1'
    sys.path.append('./shadowsocks')
    try:
        import encrypt
    except ImportError:
        logging.error('shadowsocks.encrypt not found. Please run git submodule init; git submodule update')
        sys.exit(1)

    with open('config.json', 'rb') as f:
        config = json.load(f)
    SERVER = config['server']
    REMOTE_PORT = config['server_port']
    PORT = config['local_port']
    KEY = config['password']
    METHOD = config['method']
    TARGET_SERVER = config['target_server']
    TARGET_PORT = config['target_port']

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S', filemode='a+')

    header = '\x03' + chr(len(TARGET_SERVER)) + str(TARGET_SERVER) + struct.pack('>H', TARGET_PORT)

    encrypt.init_table(KEY, METHOD)
    try:
        server = ThreadingTCPServer(('', PORT), Socks5Server)
        logging.info("starting lightsocks at port %d ..." % PORT)
        server.serve_forever()
    except socket.error, e:
        logging.error(e)
