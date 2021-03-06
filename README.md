# leaflet
Dead simple I2P SAM library. Download now and enjoy Garlic Routing today!

```bash
pip install leaflet
```

## How to use

```python
def hello_server(server_addr='server.b32.i2p'):
    # test SAM connection
    controller = Controller()

    # create our "IP Address"
    with controller.create_dest() as our_dest:
        # connect to a remote destination and send our message
        sock = our_dest.connect(server_addr)
        # SAM will give us response headers when the connection is successful
        sam_reply = sock.parse_headers()
        # now we can send data
        sock.sendall(b'Hello, there!')
        # receive reply
        real_reply = sock.recv(4096)

        print(sam_reply, real_reply)
        sock.close()
```

[Create identities, connect to a remote destination and accept data streams.](leaflet/examples/basic.py)

[Write a datagram client and a datagram server.](leaflet/examples/datagram.py)

[Class reference](https://leaflet.readthedocs.io/)

## Examples to play with

To run the demo, make sure you have two terminal windows open.

__Hello, how are you?__

Script for terminal window #1.

```bash
python3 -m leaflet.examples.basic server
# it will print out its server address
```

Script for terminal window #2.

```python
python3 -m leaflet.examples.basic client serveraddress.b32.i2p
```

__Nevermind, you probably wouldn't get it.__

Script for terminal window #1

```python
python3 -m leaflet.examples.datagram server
# wait until it prints out its server address
```

Script for terminal window #2:

```python
python3 -m leaflet.examples.datagram client serveraddress.b32.i2p
```

## Caveat

- Python 3 only. Nobody writes new code in Python 2 in 2017.

- Leaflet is based on `i2p.socket` but it is no longer a drop-in socket module replacement. If you like to monkey-patch your modules, then you are on your own.

- No RAW socket support. You aren't gonna need it anyway.
