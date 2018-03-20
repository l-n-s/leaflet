import sys
import logging
import asyncio

from leaflet.samtools import Dest   
from leaflet.async import ControlSocket, StreamConnect, StreamAccept

class DebugController(ControlSocket):
    """Example controller prints our destination"""

    async def session_created(self, dest):
        d = Dest(dest, "base64", sig_type=7, private=True)
        print("Accepting on {}.b32.i2p".format(d.base32))


class PingPongClient(StreamConnect):
    """Example implementing ping-pong client"""

    async def stream_connection_made(self):
        self.transport.write(b"PING")

    async def stream_data_received(self, data):
        print("--->", data)
        self.transport.close()

    async def stream_connection_lost(self, exc):
        self.log.debug("Closing connection")
        self.loop.stop() # Close SAM control connection


class PingPongServer(StreamAccept):
    """Example implementing ping-pong client"""

    async def stream_data_received(self, data):
        print("<---", data)
        self.transport.write(b"PONG")


class IRCBot(StreamConnect):
    """Example implementing basic IRC bot"""

    def __init__(self, nickname, channel, *args, **kwargs):
        super(IRCBot, self).__init__(*args, **kwargs)
        self.nickname = nickname
        self.channel = channel

    async def stream_connection_made(self):
        self.transport.write("NICK {}\n".format(self.nickname).encode())
        self.transport.write(b"USER async async async :async\n")

    async def stream_data_received(self, data):
        lines = data.decode()
        for line in lines.split("\n"):
            line = line.strip()
            if line:
                if line.startswith('PING :'):
                    self.transport.write(
                            'PONG :{}\n'.format(line.split(":")[1]).encode())
                elif line[0] == ":":
                    """Server sent some message"""
                    words = line.split()
                    if words[1] == '422' or words[1] == '376':
                        """End of MOTD, joining channel"""
                        self.transport.write(
                                "JOIN #{}\n".format(self.channel).encode())
                    if words[1] == 'PRIVMSG':
                        message = line.split(":", 2)[2].strip()
                        if words[2].startswith("#") and \
                                message.startswith("!ping"):
                            self.transport.write(
                                "PRIVMSG {} :pong\n".format(words[2]).encode())

def irc_bot(loop, remote_destination):
    """IRC bot example"""
    SESSION_READY = asyncio.Event()
    SAM_HOST = ('127.0.0.1', 7656)
    SESSION_NAME = "ircbot"

    coro = loop.create_connection(
        lambda: ControlSocket(SESSION_NAME, SESSION_READY, loop=loop),
        SAM_HOST[0], SAM_HOST[1]
    )

    coro2 = loop.create_connection(
        lambda: IRCBot("aiobot", "0", SESSION_NAME, SESSION_READY, remote_destination, loop=loop),
        SAM_HOST[0], SAM_HOST[1]
    )

    loop.run_until_complete(coro)
    loop.run_until_complete(coro2)

def ping_pong_client(loop, remote_destination):
    """Ping Pong client example"""
    SESSION_READY = asyncio.Event()
    SAM_HOST = ('127.0.0.1', 7656)
    SESSION_NAME = "pingclient"

    coro = loop.create_connection(
        lambda: ControlSocket(SESSION_NAME, SESSION_READY, loop=loop),
        SAM_HOST[0], SAM_HOST[1]
    )
    loop.run_until_complete(coro)

    coro2 = loop.create_connection(
        lambda: PingPongClient(SESSION_NAME, SESSION_READY, remote_destination, loop=loop),
        SAM_HOST[0], SAM_HOST[1]
    )

    loop.run_until_complete(coro2)



def ping_pong_server(loop):
    """Ping Pong server example"""
    SESSION_READY = asyncio.Event()
    LISTENING = asyncio.Lock()
    SAM_HOST = ('127.0.0.1', 7656)
    SESSION_NAME = "pingserver"

    coro = loop.create_connection(
        lambda: DebugController(SESSION_NAME, SESSION_READY, loop=loop),
        SAM_HOST[0], SAM_HOST[1]
    )

    async def server_loop(loop, listening):
        while True:
            coro2 = loop.create_connection(
                lambda: PingPongServer(SESSION_NAME, SESSION_READY, listening=listening, loop=loop),
                SAM_HOST[0], SAM_HOST[1]
            )
            await listening.acquire()
            asyncio.ensure_future(coro2)

    loop.run_until_complete(coro)
    loop.run_until_complete(server_loop(loop, LISTENING))


if __name__ == '__main__':
    help_doc = '\n'.join((
        'Usage:',
        '    python3 -m leaflet.examples.async_stream ping_pong_server',
        '    python3 -m leaflet.examples.async_stream ping_pong_client <server.i2p>',
        '    python3 -m leaflet.examples.async_stream irc_bot <irc.server.i2p>',))
    if len(sys.argv) == 1:
        print(help_doc)
    else:
        action = sys.argv[1]

        logging.basicConfig(level=logging.DEBUG)
        loop = asyncio.get_event_loop()
        loop.set_debug(True)

        if action == 'irc_bot':
            irc_bot(loop, sys.argv[2])
        elif action == 'ping_pong_client':
            ping_pong_client(loop, sys.argv[2])
        elif action == 'ping_pong_server':
            ping_pong_server(loop)

        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            loop.close()
