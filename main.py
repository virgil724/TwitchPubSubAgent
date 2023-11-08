import json
import argparse
import sys

from autobahn.twisted.websocket import (
    WebSocketClientFactory,
    connectWS,
    WebSocketClientProtocol,
)

from twisted.python import log
from twisted.internet import reactor, ssl
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.web.client import Agent

from upload_event import (
    BitsEvent,
    SubEvent,
    upload_bits_event,
    upload_subscription,
    refresh_token,
)


class TwitchPubSubProtocol(WebSocketClientProtocol):
    def customize(self, channelId, auth_token):
        self.channelId = channelId
        self.auth_token = auth_token
        self.topic_list = {
            "Bits": {
                "topic": f"channel-bits-events-v2.{channelId}",
                "scope": "bits:read",
                "func": upload_bits_event,
                "model": BitsEvent,
            },
            "Bits Badge": {
                "topic": f"channel-bits-badge-unlocks.{channelId}",
                "scope": "bits:read",
            },
            "Channel Points": {
                "topic": f"channel-points-channel-v1.{channelId}",
                "scope": "channel:read:redemptions",
            },
            "Channel Subscriptions": {
                "topic": f"channel-subscribe-events-v1.{channelId}",
                "scope": "channel:read:subscriptions",
                "func": upload_subscription,
                "model": SubEvent,
            },
        }
        self.topic_dict = {}

        for topic_info in self.topic_list.values():
            topic = topic_info["topic"]
            if "func" in topic_info and "model" in topic_info:
                self.topic_dict[topic] = {
                    "func": topic_info["func"],
                    "model": topic_info["model"],
                }

    def onOpen(self):
        print("WebSocket connection open.")

        def addSub():
            req = {
                "type": "LISTEN",
                "data": {
                    "topics": [v["topic"] for _, v in self.topic_list.items()],
                    "auth_token": self.auth_token,
                },
            }
            print(req)
            print(f"Subscrbe {[k for k in self.topic_list]}")
            self.sendMessage(json.dumps(req).encode("utf-8"))

        def heartbeat():
            ping = {"type": "PING"}
            self.sendMessage(json.dumps(ping).encode("utf-8"))
            self.factory.reactor.callLater(300, heartbeat)

        addSub()
        heartbeat()

    def onClose(self, wasClean, code, reason):
        if not self.factory.continueTrying:
            reactor.stop()

    def onMessage(self, payload, isBinary):
        agent = Agent(reactor)

        if isBinary:
            print("Binary message received: {0} bytes".format(len(payload)))
        else:
            print("Text message received: {0}".format(payload.decode("utf8")))
            data = json.loads(payload.decode("utf-8"))

            if data["type"] == "MESSAGE":
                try:
                    topic = data["data"]["topic"]
                    handler = self.topic_dict[topic]["func"]
                    model = self.topic_dict[topic]["model"]
                    message = json.loads(data["data"]["message"])
                    if "channel-bits-events-v2" in topic:
                        message = message["data"]
                    handler(self.factory.reactor, model(**message))
                except Exception as e:
                    print(f"Error Message: {e}")
                    pass
            elif data["type"] == "PONG":
                pass
            elif data["type"] == "RESPONSE":
                if data["error"] == "ERR_BADAUTH":
                    self.factory.NotReconnect()
                    refresh_token(self.factory.reactor, token=self.auth_token)
                pass
            elif data["type"] == "RECONNECT":
                self.factory.reconnect()
            elif data["type"] == "AUTH_REVOKED":
                self.factory.NotReconnect()
                # TODO 晚點再做
                pass
      
            else:
                self.factory.NotReconnect()


from autobahn.websocket import protocol


class CustomWebSocketFactory(WebSocketClientFactory, ReconnectingClientFactory):
    def __init__(self, *args, **kwargs):
        """

        .. note::
            In addition to all arguments to the constructor of
            :func:`autobahn.websocket.interfaces.IWebSocketClientChannelFactory`,
            you can supply a ``reactor`` keyword argument to specify the
            Twisted reactor to be used.
        """
        # lazy import to avoid reactor install upon module import
        self.authToken = kwargs.pop("authToken", None)
        self.channelId = kwargs.pop("channelId", None)
        reactor = kwargs.pop("reactor", None)
        if reactor is None:
            from twisted.internet import reactor
        self.reactor = reactor

        protocol.WebSocketClientFactory.__init__(self, *args, **kwargs)
        # we must up-call *before* we set up the contextFactory
        # because we need self.host etc to be set properly.
        if self.isSecure and self.proxy is not None:
            # if we have a proxy, then our factory will be used to
            # create the connection after CONNECT and if it's doing
            # TLS it needs a contextFactory
            from twisted.internet import ssl

            self.contextFactory = ssl.optionsForClientTLS(self.host)
        # NOTE: there's thus no way to send in our own
        # context-factory, nor any TLS options.

        # Possibly we should allow 'proxy' to contain an actual
        # IStreamClientEndpoint instance instead of configuration for
        # how to make one

    def buildProtocol(self, addr):
        """
        Create an instance of a subclass of Protocol.

        The returned instance will handle input on an incoming server
        connection, and an attribute "factory" pointing to the creating
        factory.

        Alternatively, L{None} may be returned to immediately close the
        new connection.

        Override this method to alter how Protocol instances get created.

        @param addr: an object implementing L{IAddress}
        """
        assert self.protocol is not None
        p = self.protocol()
        p.customize(self.channelId, self.authToken)
        p.factory = self
        return p

    def reconnect(self):
        print("Received reconnect request, reconnecting...")

        self.continueTrying = 1

    def NotReconnect(self):
        print("Problem Occur Not Reconnected")

        self.continueTrying = 0


if __name__ == "__main__":
    log.startLogging(sys.stdout)

    parser = argparse.ArgumentParser(description="Twitch PubSub WebSocket Script")
    parser.add_argument("channelId", type=str, help="Twitch Channel ID")
    parser.add_argument("auth_token", type=str, help="Twitch Auth Token")
    args = parser.parse_args()

    factory = CustomWebSocketFactory(
        "wss://pubsub-edge.twitch.tv",
        channelId=args.channelId,
        authToken=args.auth_token,
    )
    factory.setProtocolOptions(autoPingInterval=300)
    factory.protocol = TwitchPubSubProtocol

    contextFactory = ssl.ClientContextFactory()
    connectWS(factory, contextFactory)
    reactor.run()
