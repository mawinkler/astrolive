# AstroLive

**~ WILL BE RELEASED SHORTLY ~**

Connector for the ASCOM Alpaca REST API designed to work with [Home Assistant](https://www.home-assistant.io/).

![alt text](images/console-log.png "Live")

Integration to Home Assistant is implemented via MQTT for sensor and camera entities. MQTT autodiscovery in Home Assistant for the devices is supported.

My current stargazing dashboard in Home Assistant:

![alt text](images/stargarzing-live.png "Live")

AstroLive uses the nice ALPACA implementation of the [OCA Box](https://github.com/araucaria-project/ocaboxapi.git) classes for ASCOM Alpaca API.

## Core Functionality

- Connects via ASCOM Alpaca API to your observatory
- As of now the following components are supported:
  - Telescope
  - Camera via ASCOM
  - Camera via File
  - Focuser
  - Switch
- Autodiscovery in Home Assistant is supported
- Captured FITS images are autostretched and downsized
- Runs as a container to be deployed on a dedicated host or next to Home Assistant

## Requirements

- [ASCOMRemote](https://github.com/ASCOMInitiative/ASCOMRemote/releases).
- Container runtime engine (e.g. Docker)
- MQTT Broker

## Status

I'm currently testing it as often as the sky (and my time) allows it. As soon as I have the feeling that it is stable it will show up here.
