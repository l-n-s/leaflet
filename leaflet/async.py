import asyncio
import logging

from leaflet.samtools import Dest, sam_parse_reply

__all__ = ['SAMConnection', 'ControlSocket', 'StreamConnect', 'StreamAccept']

class SAMConnection(asyncio.Protocol):
    """Generic SAM connection"""

    def __init__(self, loop=None):
        self.handshake = asyncio.Event()
        self.loop = loop
        self.log = logging.getLogger(__name__)

    def connection_made(self, transport):
        self.transport = transport
        transport.write("HELLO VERSION\n".encode())

    def data_received(self, data):
        self.log.debug('Data received: {!r}'.format(data.decode()))
        if not self.handshake.is_set():
            reply = self.parse_reply(data)
            if reply.cmd == "HELLO" and reply.ok: self.handshake.set()

    def parse_reply(self, data):
        """SAMReply from raw socket reply"""
        return sam_parse_reply(data.decode().strip())

    async def new_connection(self):
        """Initiate a new SAM API connection for utility functions"""
        host, port = self.transport.get_extra_info("peername")
        reader, writer = await asyncio.open_connection(
                host, port, loop=self.loop)
        writer.write("HELLO VERSION\n".encode())
        data = await reader.read(4096)
        self.log.debug('Data received: {!r}'.format(data.decode()))
        return (reader, writer)

    async def dest_lookup(self, name):
        """I2P address to destination object"""
        reader, writer = await self.new_connection()
        writer.write("NAMING LOOKUP NAME={}\n".format(name).encode())
        data = await reader.read(4096)
        self.log.debug('Data received: {!r}'.format(data.decode()))
        reply = self.parse_reply(data)
        writer.close()
        return Dest(reply["VALUE"], "base64")

    async def new_destination(self, signature_type=Dest.default_sig_type):
        """Generate new I2P destination"""
        reader, writer = await self.new_connection()
        writer.write("DEST GENERATE SIGNATURE_TYPE={}\n".format(
            signature_type).encode())
        data = await reader.read(4096)
        self.log.debug('Data received: {!r}'.format(data.decode()))
        reply = self.parse_reply(data)
        writer.close()
        return reply["PRIV"]


class ControlSocket(SAMConnection):

    def __init__(self, session_name, session_ready, destination="TRANSIENT",
            dest_generate=False, signature_type=Dest.default_sig_type,
            *args, **kwargs):
        """SAM session socket aka control socket

        Arguments:

        * session_name:   name of SAM session

        * session_ready:  asyncio.Event instance to notify other coroutines when
                          session becomes ready for usage

        * destination:    String whith Base64-encoded I2P destination or 
                          "TRANSIENT". "TRANSIENT" by default.

        * dest_generate:  do we need to generate new destination?

        * signature_type: destination signature type
        """
        super(ControlSocket, self).__init__(*args, **kwargs)
        self.session_name = session_name
        self.session_ready = session_ready
        self.destination = destination
        self.dest_generate = dest_generate
        self.signature_type = signature_type

    def connection_made(self, transport):
        super(ControlSocket, self).connection_made(transport)
        asyncio.ensure_future(self.session_create())

    async def session_create(self):
        await self.handshake.wait()
        if self.dest_generate:
            self.destination = await self.new_destination()

        self.transport.write(
            "SESSION CREATE STYLE={} ID={} DESTINATION={} SIGNATURE_TYPE={}\n".format(
                "STREAM", self.session_name, self.destination, 
                self.signature_type).encode())

    def data_received(self, data):
        super(ControlSocket, self).data_received(data)
        if not self.session_ready.is_set():
            reply = self.parse_reply(data)
            if reply.cmd == "SESSION" and reply.ok: 
                self.session_ready.set()
                asyncio.ensure_future(
                        self.session_created(reply["DESTINATION"]))

    async def session_created(self, dest):
        """Executed after session is created, dest is b64 destination"""
        pass


class StreamConnect(SAMConnection):

    def __init__(self, session_name, session_ready, destination, 
                 *args, **kwargs):
        """Stream connect method

        Arguments:

        * session_name:   name of SAM session

        * session_ready:  asyncio.Event instance to get notication when control
                          session becomes ready for usage

        * destination:    I2P destination to connect to. Can be  
                          Base64-encoded destination, .b32.i2p pseudo-domain,
                          .i2p domain or leaflet.samtools.Dest instance.

        """
        super(StreamConnect, self).__init__(*args, **kwargs)
        self.session_name = session_name
        self.session_ready = session_ready
        self.stream_ready = False

        if isinstance(destination, Dest):
            self.remote_destination = destination
        elif destination.endswith(".i2p"):
            self.remote_destination = destination
        else:
            self.remote_destination = Dest(destination, "base64")


    def connection_made(self, transport):
        super(StreamConnect, self).connection_made(transport)
        asyncio.ensure_future(self.stream_connect())

    async def stream_connect(self):
        if isinstance(self.remote_destination, str):
            self.remote_destination = await self.dest_lookup(
                                                       self.remote_destination)
        await self.handshake.wait()
        await self.session_ready.wait()

        self.transport.write(
            "STREAM CONNECT ID={} DESTINATION={} SILENT=false\n".format(
                self.session_name, self.remote_destination.base64).encode())

    def data_received(self, data):
        super(StreamConnect, self).data_received(data)

        if not self.stream_ready:
            reply = self.parse_reply(data)

            if reply.cmd == "STREAM" and reply.ok:
                self.stream_ready = True
                asyncio.ensure_future(self.stream_connection_made())
        else:
            asyncio.ensure_future(self.stream_data_received(data))

    def connection_lost(self, exc):
        if not exc:
            self.log.debug("Connection is closed by remote destination")
        else:
            self.log.debug("Connection is lost due to exception", exc)

        asyncio.ensure_future(self.stream_connection_lost(exc))

    async def stream_connection_made(self):
        """Executed after stream is connected to remote destination"""
        pass

    async def stream_data_received(self, data):
        """Executed when data is received from remote destination"""
        pass

    async def stream_connection_lost(self, exc):
        """Executed when connection is closed/lost"""
        pass


class StreamAccept(SAMConnection):

    def __init__(self, session_name, session_ready, listening=None,
                 *args, **kwargs):
        """Stream accept method

        Arguments:

        * session_name:   name of SAM session

        * session_ready:  asyncio.Event instance to get notication when control
                          session becomes ready for usage

        * listening:      asyncio.Lock instance or None. Can be used to lock 
                          server loop until remote client is connected.

        """
        super(StreamAccept, self).__init__(*args, **kwargs)
        self.session_name = session_name
        self.session_ready = session_ready
        self.listening = listening
        self.stream_ready = False
        self.remote_destination = None

    def connection_made(self, transport):
        super(StreamAccept, self).connection_made(transport)
        asyncio.ensure_future(self.stream_accept())

    async def stream_accept(self):
        await self.handshake.wait()
        await self.session_ready.wait()

        self.transport.write(
            "STREAM ACCEPT ID={} SILENT=false\n".format(
                self.session_name).encode())

    def data_received(self, data):
        super(StreamAccept, self).data_received(data)

        if not self.stream_ready:
            reply = self.parse_reply(data)

            if reply.cmd == "STREAM" and reply.ok:
                self.stream_ready = True
                asyncio.ensure_future(self.stream_connection_made())
        elif not self.remote_destination:
            """Data and destination may come in one chunk"""
            dest, data = data.split(b"\n", 1)
            self.remote_destination = dest.decode()
            if self.listening: self.listening.release()

            if data:
                asyncio.ensure_future(self.stream_data_received(data))
        else:
            asyncio.ensure_future(self.stream_data_received(data))

    def connection_lost(self, exc):
        if not exc:
            self.log.debug("Connection is closed by remote destination")
        else:
            self.log.debug("Connection is lost due to exception", exc)

        asyncio.ensure_future(self.stream_connection_lost(exc))

    async def stream_connection_made(self):
        """Executed after stream is ready to accept data"""
        pass

    async def stream_data_received(self, data):
        """Executed when data is received from client"""
        pass

    async def stream_connection_lost(self, exc):
        """Executed when connection is closed/lost"""
        pass

