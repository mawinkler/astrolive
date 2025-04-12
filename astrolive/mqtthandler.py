"""Handler for MQTT communication"""

import json
import logging
import queue
import random
import ssl
import string
from time import sleep
from typing import Callable, Iterable, Tuple

import paho.mqtt.client as mqtt

from .const import (
    STATE_OFF,
    STATE_ON,
)
from .observatory import Component

_LOGGER = logging.getLogger(__name__)


class Connector:
    """Connector class"""

    @classmethod
    def create_connector(cls, protocol: str, *args, **kwargs) -> "Connector":
        """Factory method, crates specialized Connector instance"""
        connector = _connector_classes[protocol](*args, **kwargs)
        return connector

    def on_log(self, client, userdata, level, buf):
        """MQTT logging"""

        # _LOGGER.debug("%s", buf)

    def on_connect(self, client, userdata, flags, rc, properties):
        """Connected to MQTT"""

        if flags.get("session_present"):
            _LOGGER.debug("MQTT session present")

        if rc == 0:
            _LOGGER.debug("MQTT success connect")
            client.publish(
                "astrolive/lwt",
                "ON",
            )
        else:
            _LOGGER.debug("MQTT success not successful")

    def on_disconnect(self, client, userdata, flags, rc, properties):
        """Disconnecting from MQTT"""

        # client.publish(
        #     "astrolive/lwt",
        #     "OFF",
        # )

    def get(self, component: "Component", variable: str, **data):
        """Not implemented"""

        raise NotImplementedError

    def put(self, component: "Component", variable: str, **data):
        """Not implemented"""

        raise NotImplementedError

    def call(self, component: "Component", function: str, **data):
        """Not implemented"""

        raise NotImplementedError

    def subscribe(self, variables: Iterable[Tuple[str, str]], callback: Callable):
        """Not implemented"""

        raise NotImplementedError


class MqttHandler(Connector):
    """Specialized MQTT Connector"""

    def __init__(self, *args, **kwargs) -> None:
        options = args[0]
        self._publisher = kwargs["publisher"]
        self._client = None
        unique_id = "".join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(12))
        if self._publisher is None:
            proto = mqtt.MQTTv5
            self._client = mqtt.Client(client_id=f"{options['mqtt']['client']}-{unique_id}", protocol=proto)
            self._client.on_message = self.on_message
            self._client.on_log = self.on_log
            self._client.on_connect = self.on_connect
            self._client.on_disconnect = self.on_disconnect
            self._client.will_set("astrolive/lwt", payload="OFF")

            if options["mqtt"]["tls"]["enabled"] is True:
                self._client.tls_set(
                    options["mqtt"]["tls"]["ca"],
                    tls_version=ssl.PROTOCOL_TLSv1_2,
                )
                self._client.tls_insecure_set(options["mqtt"]["tls"]["insecure"])

            if options["mqtt"]["username"] != "":
                _LOGGER.info("MQTT Connector using username password")
                self._client.username_pw_set(options["mqtt"]["username"], options["mqtt"]["password"])

            self._client.connect(options["mqtt"]["broker"], options["mqtt"]["port"])
            self._client.loop_start()
            self._client.subscribe("astrolive/command")

            _LOGGER.info(
                "MQTT Connector created, ClientId=%s-%s",
                options["mqtt"]["client"],
                unique_id,
            )
        else:
            _LOGGER.info("MQTT Connector already exists")

        self._on_command = None
        self._messages = queue.Queue()

        super().__init__()

    def connect(self, *args, **kwargs):
        """Connect"""

    def configure_components(self):
        """Configure Components"""

    def on_command(self, client, userdata, command):
        """If implemented, called when a command has been received on a topic
        that the client subscribes to."""

    # define callbacks
    def on_message(self, client, userdata, message):
        """Called when we receive a command to process"""

        fail_command = False
        # Catch JSON decode errors here
        payload = message.payload.decode("utf-8")
        topic = message.topic
        command = {}
        if payload in (STATE_ON, STATE_OFF):
            # Are we switching a switch?
            if "astrolive/switch/" in topic:
                _LOGGER.info("On/Off command for a switch")
                # dissecting astrolive/switch/obs_telescope_switch/set_switch_X
                command["component"] = topic.split("/")[2].replace("_", ".")
                command["id"] = topic.split("/")[3].split("_")[-1]
                command["command"] = payload
        else:
            # Any other command
            try:
                command = json.loads(message.payload.decode("utf-8"))
            except json.decoder.JSONDecodeError as jsonde:
                fail_command = True
                _LOGGER.error(message.payload.decode("utf-8"))
                _LOGGER.error("%s", jsonde.msg)
                # return None
        _LOGGER.debug(message.payload.decode("utf-8"))

        # Test for keys
        if "component" not in command:
            fail_command = True
            _LOGGER.error("No component in command set")
        if "command" not in command:
            fail_command = True
            _LOGGER.error("No command in command set")
        if not fail_command:
            self.on_command(self, userdata, command)

    # @property
    # def on_command(self):
    #     """If implemented, called when a command has been received on a topic
    #     that the client subscribes to.

    #     This callback will be called for every command received. Use
    #     message_callback_add() to define multiple callbacks that will be called
    #     for specific topic filters."""

    #     return self._on_command

    # @on_command.setter
    # def on_command(self, func):
    #     """Define the command received callback implementation.

    #     Expected signature is:
    #         on_message_callback(client, userdata, message)

    #     client:     the client instance for this callback
    #     userdata:   the private user data as set in Client() or userdata_set()
    #     message:    an instance of MQTTMessage.
    #                 This is a class with members topic, payload, qos, retain.

    #     Decorator: @client.message_callback() (```client``` is the name of the
    #         instance which this callback is being attached to)

    #     """

    #     # with self._callback_mutex:
    #     self._on_command = func

    async def publish_mqtt(self, topic, message, qos=0, retain=False):
        """Queue a MQTT message

        Args:
            topic (string): Topic of the message.
            message (string): The message.
        """

        self._messages.put([topic, message, qos, retain])

    async def subsribe_mqtt(self, topic):
        """Subscribe to a MQTT topic

        Args:
            topic (string): Topic of the message.
        """

        self._client.subscribe(topic)

    async def looper(self):
        """Send a MQTT message one by one"""

        while True:
            if self._client.is_connected is False:
                _LOGGER.warning("Reconnecting to MQTT Broker")
                self._client.reconnect()

            # if len(self._messages) > 0:
            if not self._messages.empty():
                message = self._messages.get()
                if message:
                    response = self._client.publish(message[0], message[1], message[2], message[3])
                    # _LOGGER.debug(
                    #     "MQTT publish ratain: %s, %s, %s",
                    #     message[0],
                    #     message[2],
                    #     message[3],
                    # )
                    if response[0]:
                        _LOGGER.warning("MQTT failure: %s", response[0])
            sleep(0.1)


class MqttListener(Connector):
    """Specialized MQTT Connector"""

    def __init__(self, *args, **kwargs) -> None:
        options = args[0]
        self._listener = kwargs["listener"]
        self._client = None
        unique_id = "".join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(12))
        if self._listener is None:
            proto = mqtt.MQTTv311
            self._client = mqtt.Client(f"{options['mqtt']['client']}-{unique_id}", proto)
            self._client.on_message = self.on_message
            self._client.on_log = self.on_log
            self._client.on_connect = self.on_connect
            self._client.on_disconnect = self.on_disconnect
            self._client.will_set("astrolive/lwt", payload="OFF")

            if options["mqtt"]["tls"]["enabled"] is True:
                self._client.tls_set(
                    options["mqtt"]["tls"]["ca"],
                    tls_version=ssl.PROTOCOL_TLSv1_2,
                )
                self._client.tls_insecure_set(options["mqtt"]["tls"]["insecure"])

            if options["mqtt"]["username"] != "":
                _LOGGER.info("MQTT Connector using username password")
                self._client.username_pw_set(options["mqtt"]["username"], options["mqtt"]["password"])

            self._client.connect(options["mqtt"]["broker"], options["mqtt"]["port"])
            _LOGGER.info("Listener loop_start")
            self._client.loop_start()  # start the loop
            self._client.subscribe("astrolive/command")
            _LOGGER.info(
                "MQTT Connector created, ClientId=%s-%s",
                options["mqtt"]["client"],
                unique_id,
            )
        else:
            _LOGGER.info("MQTT Connector already exists")

        self._messages = []

        super().__init__()

    def connect(self, *args, **kwargs):
        """Connect"""

    def configure_components(self):
        """Configure Components"""

    def on_message(self, client, userdata, message):
        """Called when we receive a command to process"""

    async def publish_mqtt(self, topic, message):
        """Queue a MQTT message

        Args:
            topic (string): Topic of the message.
            message (string): The message.
        """

        self._messages.append([topic, message])

    async def looper(self):
        """Send a MQTT message one by one"""

        while True:
            if self._client.is_connected is False:
                _LOGGER.warning("Reconnecting to MQTT Broker")
                self._client.reconnect()

            if self._messages:
                _LOGGER.debug("Queue length: %d", len(self._messages))
                message = self._messages.pop(0)
                if message:
                    response = self._client.publish(message[0], message[1])
                    if response[0]:
                        _LOGGER.warning("MQTT failure: %s", response[0])
            sleep(0.1)


_connector_classes = {
    "handler": MqttHandler,
}
