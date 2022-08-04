import logging
from datetime import datetime
from typing import List, MutableMapping, Optional, Union

from .config import Config
from .connectors import Connector
from .coo import check_equatorial_coordinates, check_horizontal_coordinates

logger = logging.getLogger(__name__)


class Component:
    """Base class for all elements of device tree"""

    def __init__(self, sys_id: str, parent: Union["Component", None]) -> None:
        self.kind = type(self).__name__.lower()
        self.sys_id: str = sys_id
        self.parent: Component = parent
        self.component_options = {}
        self._connector: Optional[Connector] = None
        self.children: dict[str, Component] = {}

    def _setup(self, options: dict):
        self.component_options: MutableMapping = options.copy()
        try:
            self._connector = Connector.create_connector(
                self.component_options["protocol"]
            )
        except KeyError:
            pass
        try:
            child_options = self.component_options.pop("components")
        except KeyError:
            child_options = {}
        for cid, op in child_options.items():
            child = self._create_component(
                kind=op["kind"], sys_id=self.sys_id + "." + cid, parent=self
            )
            self.children[cid] = child
            setattr(self, cid, child)  # allow easy navigation: `parent.child`
            child._setup(op)

    @property
    def connector(self) -> Connector:
        if self._connector is not None:
            return self._connector
        else:
            return self.parent.connector

    def get_option_recursive(self, option):
        try:
            return self.component_options[option]
        except KeyError:
            if self.parent is None:
                return None
            else:
                return self.parent.get_option_recursive(option)

    def children_tree_iter(self):
        """Generator yielding components tree, starting from self"""
        yield self
        for c in self.children.values():
            yield from c.children_tree_iter()

    def children_count(self, recursively=True):
        """gets number of children"""
        n = len(self.children)
        if recursively:
            for c in self.children.values():
                n += c.children_count(recursively=True)
        return n

    def child_by_relative_sys_id(self, sys_id_rel: str):
        """Find child by relative sys_id path"""
        cid, *cpath = sys_id_rel.split(".", 1)
        c = self.children[cid]
        if cpath:
            return c.child_by_relative_sys_id(cpath[0])
        else:
            return c

    def component_by_absolute_sys_id(self, sys_id_abs: str):
        cid, *cpath = sys_id_abs.split(".", 1)
        root = self.root
        if root.sys_id != cid:
            raise IndexError("Absolute sys_id should start from root: %s", root.sys_id)
        if cpath:
            return root.child_by_relative_sys_id(cpath[0])
        else:
            return self

    @property
    def root(self):
        if self.parent is not None:
            return self.parent.root
        else:
            return self

    @classmethod
    def _create_component(
        cls, kind: str, sys_id: str, parent: "Component"
    ) -> "Component":
        return _component_classes[kind](sys_id=sys_id, parent=parent)

    # def __getattribute__(self, name: str) -> Any:
    #     """Access to children as another members"""
    #     try:
    #         return super().__getattribute__(name)
    #     except AttributeError:
    #         return self.children.get(name)

    # @classmethod
    # def class_name(cls):
    #     return cls.__name__
    #
    # @property
    # def kind(self):


class Observatory(Component):
    """Observatory - root device in devices tree

    Attributes:
        configuration (Config): Optional configuration, by default configuration will be loaded from following files:
              ~/ocabox.cfg.yaml
              ./ocabox.cfg.yaml
              <package_path>/astrolive/default.cfg.yaml
            Later overwrites former
    """

    def __init__(self, configuration: Optional[Config] = None):
        if configuration is None:
            configuration = Config.global_instance()
        self.config = configuration
        self.options = None
        self.preset = "default"
        super().__init__("obs", None)

    def connect(self, preset: Optional[str] = "default") -> None:
        """
        Connect to servers if needed, builds Devices tree
        Args:
            preset: name of the preset from config
        """
        if preset is None:
            preset = "default"
        self.preset = preset
        self.options = self.config.data[preset]["observatory"]
        self._setup(self.options)

    def options(self):
        return self.options


class Device(Component):
    """Common methods across all devices.

    Attributes:
        sys_id (str): system ID of device
        parent (Component): The parent component in devices tree
    """

    CURRENT = 0
    PREVIOUS = 1
    READ_TIME = 2
    MODIFY_TIME = 3

    def __init__(self, sys_id: str, parent: Union["Component", None]) -> None:
        """Initialize Device object."""
        super().__init__(sys_id=sys_id, parent=parent)

    def _get(self, attribute: str, **data):
        """Send an request and check response for errors.

        Args:
            attribute (str): Attribute to get from server.
            **data: Data to send with request.

        """
        return self.connector.get(self, attribute, **data)

    def _put(self, attribute: str, **data):
        """Send an HTTP PUT request to an Alpaca server and check response for errors.

        Args:
            attribute (str): Attribute to put to server.
            **data: Data to send with request.

        """
        return self.connector.put(self, attribute, **data)

    def action(self, Action: str, *Parameters):
        """Access functionality beyond the built-in capabilities of the ASCOM device interfaces.

        Args:
            Action (str): A well known name that represents the action to be carried out.
            *Parameters: List of required parameters or empty if none are required.

        """
        return self._put("action", Action=Action, Parameters=Parameters)["Value"]

    def commandblind(self, Command: str, Raw: bool):
        """Transmit an arbitrary string to the device and does not wait for a response.

        Args:
            Command (str): The literal command string to be transmitted.
            Raw (bool): If true, command is transmitted 'as-is'.
                If false, then protocol framing characters may be added prior to
                transmission.

        """
        self._put("commandblind", Command=Command, Raw=Raw)

    def commandbool(self, Command: str, Raw: bool):
        """Transmit an arbitrary string to the device and wait for a boolean response.

        Args:
            Command (str): The literal command string to be transmitted.
            Raw (bool): If true, command is transmitted 'as-is'.
                If false, then protocol framing characters may be added prior to
                transmission.

        """
        return self._put("commandbool", Command=Command, Raw=Raw)["Value"]

    def commandstring(self, Command: str, Raw: bool):
        """Transmit an arbitrary string to the device and wait for a string response.

        Args:
            Command (str): The literal command string to be transmitted.
            Raw (bool): If true, command is transmitted 'as-is'.
                If false, then protocol framing characters may be added prior to
                transmission.

        """
        return self._put("commandstring", Command=Command, Raw=Raw)["Value"]

    def connected(self, Connected: Optional[bool] = None):
        """Retrieve or set the connected state of the device.

        Args:
            Connected (bool): Set True to connect to device hardware.
                Set False to disconnect from device hardware.
                Set None to get connected state (default).

        """
        if Connected is None:
            return self._get("connected")
        self._put("connected", Connected=Connected)

    def description(self) -> str:
        """Get description of the device."""
        return self._get("name")

    def driverinfo(self) -> List[str]:
        """Get information of the device."""
        return [i.strip() for i in self._get("driverinfo").split(",")]

    def driverversion(self) -> str:
        """Get string containing only the major and minor version of the driver."""
        return self._get("driverversion")

    def interfaceversion(self) -> int:
        """ASCOM Device interface version number that this device supports."""
        return self._get("interfaceversion")

    def name(self) -> str:
        """Get name of the device."""
        return self._get("name")

    def supportedactions(self) -> List[str]:
        """Get list of action names supported by this driver."""
        return self._get("supportedactions")


class Switch(Device):
    """Switch specific methods."""

    def maxswitch(self) -> int:
        """Count of switch devices managed by this driver.

        Returns:
            Number of switch devices managed by this driver. Devices are numbered from 0
            to MaxSwitch - 1.

        """
        return self._get("maxswitch")

    def canwrite(self, Id: Optional[int] = 0) -> bool:
        """Indicate whether the specified switch device can be written to.

        Notes:
            Devices are numbered from 0 to MaxSwitch - 1.

        Args:
            Id (int): The device number.

        Returns:
            Whether the specified switch device can be written to, default true. This is
            false if the device cannot be written to, for example a limit switch or a
            sensor.

        """
        return self._get("canwrite", Id=Id)

    def getswitch(self, Id: Optional[int] = 0) -> bool:
        """Return the state of switch device id as a boolean.

        Notes:
            Devices are numbered from 0 to MaxSwitch - 1.

        Args:
            Id (int): The device number.

        Returns:
            State of switch device id as a boolean.

        """
        return self._get("getswitch", Id=Id)

    def getswitchdescription(self, Id: Optional[int] = 0) -> str:
        """Get the description of the specified switch device.

        Notes:
            Devices are numbered from 0 to MaxSwitch - 1.

        Args:
            Id (int): The device number.

        Returns:
            Description of the specified switch device.

        """
        return self._get("getswitchdescription", Id=Id)

    def getswitchname(self, Id: Optional[int] = 0) -> str:
        """Get the name of the specified switch device.

        Notes:
            Devices are numbered from 0 to MaxSwitch - 1.

        Args:
            Id (int): The device number.

        Returns:
            Name of the specified switch device.

        """
        return self._get("getswitchname", Id=Id)

    def getswitchvalue(self, Id: Optional[int] = 0) -> str:
        """Get the value of the specified switch device as a double.

        Notes:
            Devices are numbered from 0 to MaxSwitch - 1.

        Args:
            Id (int): The device number.

        Returns:
            Value of the specified switch device.

        """
        return self._get("getswitchvalue", Id=Id)

    def minswitchvalue(self, Id: Optional[int] = 0) -> str:
        """Get the minimum value of the specified switch device as a double.

        Notes:
            Devices are numbered from 0 to MaxSwitch - 1.

        Args:
            Id (int): The device number.

        Returns:
            Minimum value of the specified switch device as a double.

        """
        return self._get("minswitchvalue", Id=Id)

    def setswitch(self, Id: int, State: bool):
        """Set a switch controller device to the specified state, True or False.

        Notes:
            Devices are numbered from 0 to MaxSwitch - 1.

        Args:
            Id (int): The device number.
            State (bool): The required control state (True or False).

        """
        self._put("setswitch", Id=Id, State=State)

    def setswitchname(self, Id: int, Name: str):
        """Set a switch device name to the specified value.

        Notes:
            Devices are numbered from 0 to MaxSwitch - 1.

        Args:
            Id (int): The device number.
            Name (str): The name of the device.

        """
        self._put("setswitchname", Id=Id, Name=Name)

    def setswitchvalue(self, Id: int, Value: float):
        """Set a switch device value to the specified value.

        Notes:
            Devices are numbered from 0 to MaxSwitch - 1.

        Args:
            Id (int): The device number.
            Value (float): Value to be set, between MinSwitchValue and MaxSwitchValue.

        """
        self._put("setswitchvalue", Id=Id, Value=Value)

    def switchstep(self, Id: Optional[int] = 0) -> str:
        """Return the step size that this device supports.

        Return the step size that this device supports (the difference between
        successive values of the device).

        Notes:
            Devices are numbered from 0 to MaxSwitch - 1.

        Args:
            Id (int): The device number.

        Returns:
            Maximum value of the specified switch device as a double.

        """
        return self._get("switchstep", Id=Id)


class SafetyMonitor(Device):
    """Safety monitor specific methods."""

    def issafe(self) -> bool:
        """Indicate whether the monitored state is safe for use.

        Returns:
            True if the state is safe, False if it is unsafe.

        """
        return self._get("issafe")


class Dome(Device):
    """Dome specific methods."""

    def altitude(self) -> float:
        """Dome altitude.

        Returns:
            Dome altitude (degrees, horizon zero and increasing positive to 90 zenith).

        """
        return self._get("altitude")

    def athome(self) -> bool:
        """Indicate whether the dome is in the home position.

        Notes:
            This is normally used following a findhome() operation. The value is reset
            with any azimuth slew operation that moves the dome away from the home
            position. athome() may also become true durng normal slew operations, if the
            dome passes through the home position and the dome controller hardware is
            capable of detecting that; or at the end of a slew operation if the dome
            comes to rest at the home position.

        Returns:
            True if dome is in the home position.

        """
        return self._get("athome")

    def atpark(self) -> bool:
        """Indicate whether the telescope is at the park position.

        Notes:
            Set only following a park() operation and reset with any slew operation.

        Returns:
            True if the dome is in the programmed park position.

        """
        return self._get("atpark")

    def azimuth(self) -> float:
        """Dome azimuth.

        Returns:
            Dome azimuth (degrees, North zero and increasing clockwise, i.e., 90 East,
            180 South, 270 West).

        """
        return self._get("azimuth")

    def canfindhome(self) -> bool:
        """Indicate whether the dome can find the home position.

        Returns:
            True if the dome can move to the home position.

        """
        return self._get("canfindhome")

    def canpark(self) -> bool:
        """Indicate whether the dome can be parked.

        Returns:
            True if the dome is capable of programmed parking (park() method).

        """
        return self._get("canpark")

    def cansetaltitude(self) -> bool:
        """Indicate whether the dome altitude can be set.

        Returns:
            True if driver is capable of setting the dome altitude.

        """
        return self._get("cansetaltitude")

    def cansetazimuth(self) -> bool:
        """Indicate whether the dome azimuth can be set.

        Returns:
            True if driver is capable of setting the dome azimuth.

        """
        return self._get("cansetazimuth")

    def cansetpark(self) -> bool:
        """Indicate whether the dome park position can be set.

        Returns:
            True if driver is capable of setting the dome park position.

        """
        return self._get("cansetpark")

    def cansetshutter(self) -> bool:
        """Indicate whether the dome shutter can be opened.

        Returns:
            True if driver is capable of automatically operating shutter.

        """
        return self._get("cansetshutter")

    def canslave(self) -> bool:
        """Indicate whether the dome supports slaving to a telescope.

        Returns:
            True if driver is capable of slaving to a telescope.

        """
        return self._get("canslave")

    def cansyncazimuth(self) -> bool:
        """Indicate whether the dome azimuth position can be synched.

        Notes:
            True if driver is capable of synchronizing the dome azimuth position using
            the synctoazimuth(float) method.

        Returns:
            True or False value.

        """
        return self._get("cansyncazimuth")

    def shutterstatus(self) -> int:
        """Status of the dome shutter or roll-off roof.

        Notes:
            0 = Open, 1 = Closed, 2 = Opening, 3 = Closing, 4 = Shutter status error.

        Returns:
            Status of the dome shutter or roll-off roof.

        """
        return self._get("shutterstatus")

    def slaved(self, Slaved: Optional[bool] = None) -> bool:
        """Set or indicate whether the dome is slaved to the telescope.

        Returns:
            True or False value in not set.

        """
        if Slaved is None:
            return self._get("slaved")
        self._put("slaved", Slaved=Slaved)

    def slewing(self) -> bool:
        """Indicate whether the any part of the dome is moving.

        Notes:
            True if any part of the dome is currently moving, False if all dome
            components are steady.

        Return:
            True or False value.

        """
        return self._get("slewing")

    def abortslew(self):
        """Immediately cancel current dome operation.

        Notes:
            Calling this method will immediately disable hardware slewing (Slaved will
            become False).

        """
        self._put("abortslew")

    def closeshutter(self):
        """Close the shutter or otherwise shield telescope from the sky."""
        self._put("closeshutter")

    def findhome(self):
        """Start operation to search for the dome home position.

        Notes:
            After home position is established initializes azimuth to the default value
            and sets the athome flag.

        """
        self._put("findhome")

    def openshutter(self):
        """Open shutter or otherwise expose telescope to the sky."""
        self._put("openshutter")

    def park(self):
        """Rotate dome in azimuth to park position.

        Notes:
            After assuming programmed park position, sets atpark flag.

        """
        self._put("park")

    def setpark(self):
        """Set current azimuth, altitude position of dome to be the park position."""
        self._put("setpark")

    def slewtoaltitude(self, Altitude: float):
        """Slew the dome to the given altitude position."""
        self._put("slewtoaltitude", Altitude=Altitude)

    def slewtoazimuth(self, Azimuth: float):
        """Slew the dome to the given azimuth position.

        Args:
            Azimuth (float): Target dome azimuth (degrees, North zero and increasing
                clockwise. i.e., 90 East, 180 South, 270 West).

        """
        self._put("slewtoazimuth", Azimuth=Azimuth)

    def synctoazimuth(self, Azimuth: float):
        """Synchronize the current position of the dome to the given azimuth.

        Args:
            Azimuth (float): Target dome azimuth (degrees, North zero and increasing
                clockwise. i.e., 90 East, 180 South, 270 West).

        """
        self._put("synctoazimuth", Azimuth=Azimuth)


class ImageArrayElementTypes:
    """The native data type of ImageArray pixels"""

    Unknown = 0
    Int16 = 1
    Int32 = 2
    Double = 3
    Single = 4, "Unused in Alpaca 2022"
    UInt64 = 5, "Unused in Alpaca 2022"
    Byte = 6, "Unused in Alpaca 2022"
    Int64 = 7, "Unused in Alpaca 2022"
    UInt16 = 8, "Unused in Alpaca 2022"


class ImageMetadata:
    """Metadata describing the returned ImageArray data
    Notes:
        * Constructed internally by the library during image retrieval.
        * See https://ascom-standards.org/Developer/AlpacaImageBytes.pdf
    """

    def __init__(
        self,
        metadata_version: int,
        image_element_type: ImageArrayElementTypes,
        transmission_element_type: ImageArrayElementTypes,
        rank: int,
        num_x: int,
        num_y: int,
        num_z: int,
    ):
        self.metavers = metadata_version
        self.imgtype = image_element_type
        self.xmtype = transmission_element_type
        self.rank = rank
        self.x_size = num_x
        self.y_size = num_y
        self.z_size = num_z

    @property
    def MetadataVersion(self):
        """The version of metadata, currently 1"""
        return self.metavers

    @property
    def ImageElementType(self) -> ImageArrayElementTypes:
        """The data type of the pixels in originally acquired image

        Notes:
            Within Python, the returned nested list(s) image pixels themselves
            will be either int or float.
        """
        return self.imgtype

    @property
    def TransmissionElementType(self) -> ImageArrayElementTypes:
        """The ddta type of the pixels in the transmitted image bytes stream
        Notes:
            Within Python, the returned image pixels themselves will be either int or float.
            To save transmission time camera may choose to use a smaller data
            type than the original image if the pixel values would all be
            representative in that data type without a loss of precision.
        """
        return self.xmtype

    @property
    def Rank(self):
        """The matrix rank of the image data (either 2 or 3)"""
        return self.rank

    @property
    def Dimension1(self):
        """The first (X) dimension of the image array"""
        return self.x_size

    @property
    def Dimension2(self):
        """The second (Y) dimension of the image array"""
        return self.y_size

    @property
    def Dimension3(self):
        """The third (Z) dimension of the image array (None or 3)"""
        return self.z_size


class Camera(Device):
    """Camera specific methods."""

    def bayeroffsetx(self) -> int:
        """Return the X offset of the Bayer matrix, as defined in SensorType."""
        return self._get("bayeroffsetx")

    def bayeroffsety(self) -> int:
        """Return the Y offset of the Bayer matrix, as defined in SensorType."""
        return self._get("bayeroffsety")

    def binx(self, BinX: Optional[int] = None) -> int:
        """Set or return the binning factor for the X axis.

        Args:
            BinX (int): The X binning value.

        Returns:
            Binning factor for the X axis.

        """
        if BinX is None:
            return self._get("binx")
        self._put("binx", BinX=BinX)

    def biny(self, BinY: Optional[int] = None) -> int:
        """Set or return the binning factor for the Y axis.

        Args:
            BinY (int): The Y binning value.

        Returns:
            Binning factor for the Y axis.

        """
        if BinY is None:
            return self._get("biny")
        self._put("biny", BinY=BinY)

    def camerastate(self) -> int:
        """Return the camera operational state.

        Notes:
            0 = CameraIdle, 1 = CameraWaiting, 2 = CameraExposing,
            3 = CameraReading, 4 = CameraDownload, 5 = CameraError.

        Returns:
            Current camera operational state as an integer.

        """
        return self._get("camerastate")

    def cameraxsize(self) -> int:
        """Return the width of the CCD camera chip."""
        return self._get("cameraxsize")

    def cameraysize(self) -> int:
        """Return the height of the CCD camera chip."""
        return self._get("cameraysize")

    def canabortexposure(self) -> bool:
        """Indicate whether the camera can abort exposures."""
        return self._get("canabortexposure")

    def canasymmetricbin(self) -> bool:
        """Indicate whether the camera supports asymmetric binning."""
        return self._get("canasymmetricbin")

    def canfastreadout(self) -> bool:
        """Indicate whether the camera has a fast readout mode."""
        return self._get("canfastreadout")

    def cangetcoolerpower(self) -> bool:
        """Indicate whether the camera's cooler power setting can be read."""
        return self._get("cangetcoolerpower")

    def canpulseguide(self) -> bool:
        """Indicate whether this camera supports pulse guiding."""
        return self._get("canpulseguide")

    def cansetccdtemperature(self) -> bool:
        """Indicate whether this camera supports setting the CCD temperature."""
        return self._get("cansetccdtemperature")

    def canstopexposure(self) -> bool:
        """Indicate whether this camera can stop an exposure that is in progress."""
        return self._get("canstopexposure")

    def ccdtemperature(self) -> float:
        """Return the current CCD temperature in degrees Celsius."""
        return self._get("ccdtemperature")

    def cooleron(self, CoolerOn: Optional[bool] = None) -> bool:
        """Turn the camera cooler on and off or return the current cooler on/off state.

        Notes:
            True = cooler on, False = cooler off.

        Args:
            CoolerOn (bool): Cooler state.

        Returns:
            Current cooler on/off state.

        """
        if CoolerOn is None:
            return self._get("cooleron")
        self._put("cooleron", CoolerOn=CoolerOn)

    def coolerpower(self) -> float:
        """Return the present cooler power level, in percent."""
        return self._get("coolerpower")

    def electronsperadu(self) -> float:
        """Return the gain of the camera in photoelectrons per A/D unit."""
        return self._get("electronsperadu")

    def exposuremax(self) -> float:
        """Return the maximum exposure time supported by StartExposure."""
        return self._get("exposuremax")

    def exposuremin(self) -> float:
        """Return the minimum exposure time supported by StartExposure."""
        return self._get("exposuremin")

    def exposureresolution(self) -> float:
        """Return the smallest increment in exposure time supported by StartExposure."""
        return self._get("exposureresolution")

    def fastreadout(self, FastReadout: Optional[bool] = None) -> bool:
        """Set or return whether Fast Readout Mode is enabled.

        Args:
            FastReadout (bool): True to enable fast readout mode.

        Returns:
            Whether Fast Readout Mode is enabled.

        """
        if FastReadout is None:
            return self._get("fastreadout")
        self._put("fastreadout", FastReadout=FastReadout)

    def fullwellcapacity(self) -> float:
        """Report the full well capacity of the camera.

        Report the full well capacity of the camera in electrons, at the current
        camera settings (binning, SetupDialog settings, etc.).

        Returns:
            Full well capacity of the camera.

        """
        return self._get("fullwellcapacity")

    def gain(self, Gain: Optional[int] = None) -> int:
        """Set or return an index into the Gains array.

        Args:
            Gain (int): Index of the current camera gain in the Gains string array.

        Returns:
            Index into the Gains array for the selected camera gain.

        """
        if Gain is None:
            return self._get("gain")
        self._put("gain", Gain=Gain)

    def gainmax(self) -> int:
        """Maximum value of Gain."""
        return self._get("gainmax")

    def gainmin(self) -> int:
        """Minimum value of Gain."""
        return self._get("gainmin")

    def gains(self) -> List[int]:
        """Gains supported by the camera."""
        return self._get("gains")

    def hasshutter(self) -> bool:
        """Indicate whether the camera has a mechanical shutter."""
        return self._get("hasshutter")

    def heatsinktemperature(self) -> float:
        """Return the current heat sink temperature.

        Returns:
            Current heat sink temperature (called "ambient temperature" by some
            manufacturers) in degrees Celsius.

        """
        return self._get("heatsinktemperature")

    def imagearray(self) -> List[int]:
        r"""Return an array of integers containing the exposure pixel values.

        Return an array of 32bit integers containing the pixel values from the last
        exposure. This call can return either a 2 dimension (monochrome images) or 3
        dimension (colour or multi-plane images) array of size NumX * NumY or NumX *
        NumY * NumPlanes. Where applicable, the size of NumPlanes has to be determined
        by inspection of the returned Array. Since 32bit integers are always returned
        by this call, the returned JSON Type value (0 = Unknown, 1 = short(16bit),
        2 = int(32bit), 3 = Double) is always 2. The number of planes is given in the
        returned Rank value. When de-serialising to an object it helps enormously to
        know the array Rank beforehand so that the correct data class can be used. This
        can be achieved through a regular expression or by direct parsing of the
        returned JSON string to extract the Type and Rank values before de-serialising.
        This regular expression accomplishes the extraction into two named groups Type
        and Rank ^*"Type":(?<Type>\d*),"Rank":(?<Rank>\d*) which can then be used to
        select the correct de-serialisation data class.

        Returns:
            Array of integers containing the exposure pixel values.

        """
        # return self._get_imagedata("imagearray")
        return self._get("imagearray")

    def imagearrayvariant(self) -> List[int]:
        r"""Return an array of integers containing the exposure pixel values.

        Return an array of 32bit integers containing the pixel values from the last
        exposure. This call can return either a 2 dimension (monochrome images) or 3
        dimension (colour or multi-plane images) array of size NumX * NumY or NumX *
        NumY * NumPlanes. Where applicable, the size of NumPlanes has to be determined
        by inspection of the returned Array. Since 32bit integers are always returned
        by this call, the returned JSON Type value (0 = Unknown, 1 = short(16bit),
        2 = int(32bit), 3 = Double) is always 2. The number of planes is given in the
        returned Rank value. When de-serialising to an object it helps enormously to
        know the array Rank beforehand so that the correct data class can be used. This
        can be achieved through a regular expression or by direct parsing of the
        returned JSON string to extract the Type and Rank values before de-serialising.
        This regular expression accomplishes the extraction into two named groups Type
        and Rank ^*"Type":(?<Type>\d*),"Rank":(?<Rank>\d*) which can then be used to
        select the correct de-serialisation data class.

        Returns:
            Array of integers containing the exposure pixel values.

        """
        return self._get("imagearrayvariant")

    def imageready(self) -> bool:
        """Indicate that an image is ready to be downloaded."""
        return self._get("imageready")

    def ispulseguiding(self) -> bool:
        """Indicatee that the camera is pulse guideing."""
        return self._get("ispulseguiding")

    def lastexposureduration(self) -> float:
        """Report the actual exposure duration in seconds (i.e. shutter open time)."""
        return self._get("lastexposureduration")

    def lastexposurestarttime(self) -> str:
        """Start time of the last exposure in FITS standard format.

        Reports the actual exposure start in the FITS-standard
        CCYY-MM-DDThh:mm:ss[.sss...] format.

        Returns:
            Start time of the last exposure in FITS standard format.

        """
        return self._get("lastexposurestarttime")

    def maxadu(self) -> int:
        """Camera's maximum ADU value."""
        return self._get("maxadu")

    def maxbinx(self) -> int:
        """Maximum binning for the camera X axis."""
        return self._get("maxbinx")

    def maxbiny(self) -> int:
        """Maximum binning for the camera Y axis."""
        return self._get("maxbiny")

    def numx(self, NumX: Optional[int] = None) -> int:
        """Set or return the current subframe width.

        Args:
            NumX (int): Subframe width, if binning is active, value is in binned
                pixels.

        Returns:
            Current subframe width.

        """
        if NumX is None:
            return self._get("numx")
        self._put("numx", NumX=NumX)

    def numy(self, NumY: Optional[int] = None) -> int:
        """Set or return the current subframe height.

        Args:
            NumY (int): Subframe height, if binning is active, value is in binned
                pixels.

        Returns:
            Current subframe height.

        """
        if NumY is None:
            return self._get("numy")
        self._put("numy", NumY=NumY)

    def percentcompleted(self) -> int:
        """Indicate percentage completeness of the current operation.

        Returns:
            If valid, returns an integer between 0 and 100, where 0 indicates 0%
            progress (function just started) and 100 indicates 100% progress (i.e.
            completion).

        """
        return self._get("percentcompleted")

    def pixelsizex(self):
        """Width of CCD chip pixels (microns)."""
        return self._get("pixelsizex")

    def pixelsizey(self):
        """Height of CCD chip pixels (microns)."""
        return self._get("pixelsizey")

    def readoutmode(self, ReadoutMode: Optional[int] = None) -> int:
        """Indicate the canera's readout mode as an index into the array ReadoutModes."""
        if ReadoutMode is None:
            return self._get("readoutmode")
        self._put("readoutmode", ReadoutMode=ReadoutMode)

    def readoutmodes(self) -> List[int]:
        """List of available readout modes."""
        return self._get("readoutmodes")

    def sensorname(self) -> str:
        """Name of the sensor used within the camera."""
        return self._get("sensorname")

    def sensortype(self) -> int:
        """Type of information returned by the the camera sensor (monochrome or colour).

        Notes:
            0 = Monochrome, 1 = Colour not requiring Bayer decoding, 2 = RGGB Bayer
            encoding, 3 = CMYG Bayer encoding, 4 = CMYG2 Bayer encoding, 5 = LRGB
            TRUESENSE Bayer encoding.

        Returns:
            Value indicating whether the sensor is monochrome, or what Bayer matrix it
            encodes.

        """
        return self._get("sensortype")

    def setccdtemperature(self, SetCCDTemperature: Optional[float] = None) -> float:
        """Set or return the camera's cooler setpoint (degrees Celsius).

        Args:
            SetCCDTemperature (float): 	Temperature set point (degrees Celsius).

        Returns:
            Camera's cooler setpoint (degrees Celsius).

        """
        if SetCCDTemperature is None:
            return self._get("setccdtemperature")
        self._put("setccdtemperature", SetCCDTemperature=SetCCDTemperature)

    def startx(self, StartX: Optional[int] = None) -> int:
        """Set or return the current subframe X axis start position.

        Args:
            StartX (int): The subframe X axis start position in binned pixels.

        Returns:
            Sets the subframe start position for the X axis (0 based) and returns the
            current value. If binning is active, value is in binned pixels.

        """
        if StartX is None:
            return self._get("startx")
        self._put("startx", StartX=StartX)

    def starty(self, StartY: Optional[int] = None) -> int:
        """Set or return the current subframe Y axis start position.

        Args:
            StartY (int): The subframe Y axis start position in binned pixels.

        Returns:
            Sets the subframe start position for the Y axis (0 based) and returns the
            current value. If binning is active, value is in binned pixels.

        """
        if StartY is None:
            return self._get("starty")
        self._put("starty", StartY=StartY)

    def abortexposure(self):
        """Abort the current exposure, if any, and returns the camera to Idle state."""
        self._put("abortexposure")

    def pulseguide(self, Direction: int, Duration: int):
        """Pulse guide in the specified direction for the specified time.

        Args:
            Direction (int): Direction of movement (0 = North, 1 = South, 2 = East,
                3 = West).
            Duration (int): Duration of movement in milli-seconds.

        """
        self._put("pulseguide", Direction=Direction, Duration=Duration)

    def startexposure(self, Duration: float, Light: bool):
        """Start an exposure.

        Notes:
            Use ImageReady to check when the exposure is complete.

        Args:
            Duration (float): Duration of exposure in seconds.
            Light (bool): True if light frame, false if dark frame.

        """
        self._put("startexposure", Duration=Duration, Light=Light)

    def stopexposure(self):
        """Stop the current exposure, if any.

        Notes:
            If an exposure is in progress, the readout process is initiated. Ignored if
            readout is already in process.

        """
        self._put("stopexposure")

    def _get_imagedata(self, attribute: str, **data) -> str:
        """TBD
        Args:
            attribute (str): Attribute to get from server.
            **data: Data to send with request.

        """
        import array

        import requests

        self.base_url = "http://192.168.1.233:11111/api/v1/camera/1/"
        url = f"{self.base_url}/{attribute}"
        hdrs = {"accept": "application/imagebytes"}
        # Make Host: header safe for IPv6
        # if(self.address.startswith('[') and not self.address.startswith('[::1]')):
        #     hdrs['Host'] = f'{self.address.split("%")[0]}]'
        pdata = {"ClientTransactionID": f"4711", "ClientID": f"1"}
        pdata.update(data)
        # try:
        #     Device._ctid_lock.acquire()
        #     response = requests.get("%s/%s" % (self.base_url, attribute), params=pdata, headers=hdrs)
        #     Device._client_trans_id += 1
        # finally:
        #     Device._ctid_lock.release()
        response = requests.get(
            "%s/%s" % (self.base_url, attribute), params=pdata, headers=hdrs
        )

        if response.status_code not in range(200, 204):  # HTTP level errors
            raise Exception(
                response.status_code,
                f"{response.reason}: {response.text} (URL {response.url})",
            )

        ct = response.headers.get("content-type")  # case insensitive
        m = "little"
        #
        # IMAGEBYTES
        #
        if ct == "application/imagebytes":
            b = response.content
            n = int.from_bytes(b[4:8], m)
            if n != 0:
                m = response.text[44:].decode(encoding="UTF-8")
                raise_alpaca_if(n, m)  # Will raise here
            self.img_desc = ImageMetadata(
                int.from_bytes(b[0:4], m),  # Meta version
                int.from_bytes(b[20:24], m),  # Image element type
                int.from_bytes(b[24:28], m),  # Xmsn element type
                int.from_bytes(b[28:32], m),  # Rank
                int.from_bytes(b[32:36], m),  # Dimension 1
                int.from_bytes(b[36:40], m),  # Dimension 2
                int.from_bytes(b[40:44], m),  # Dimension 3
            )
            print(self.img_desc.x_size)
            print(self.img_desc.y_size)
            print(self.img_desc.z_size)
            #
            # Bless you Kelly Bundy and Mark Ransom
            # https://stackoverflow.com/questions/71774719/native-array-frombytes-not-numpy-mysterious-behavior/71776522#71776522
            #
            # if self.img_desc.TransmissionElementType == ImageArrayElementTypes.Int16.value:
            #     tcode = 'h'
            # elif self.img_desc.TransmissionElementType == ImageArrayElementTypes.UInt16.value:
            #     tcode = 'H'
            # elif self.img_desc.TransmissionElementType == ImageArrayElementTypes.Int32.value:
            #     tcode = 'l'
            # elif self.img_desc.TransmissionElementType == ImageArrayElementTypes.Double.value:
            #     tcode = 'd'
            # # Extension types for future. 64-bit pixels are unlikely to be seen on the wire
            # elif self.img_desc.TransmissionElementType == ImageArrayElementTypes.Byte.value:
            #     tcode = 'B'     # Unsigned
            # elif self.img_desc.TransmissionElementType == ImageArrayElementTypes.UInt32.value:
            #     tcode = 'L'
            # else:
            #    raise Exception("Unknown or as-yet unsupported ImageBytes Transmission Array Element Type")
            tcode = "H"
            #
            # Assemble byte stream back into indexable machine data types
            #
            a = array.array(tcode)
            data_start = int.from_bytes(b[16:20], m)
            a.frombytes(
                b[data_start:]
            )  # 'h', 'H', 16-bit ints 2 bytes get turned into Python 32-bit ints
            #
            # Convert to common Python nested list "array".
            #
            l = []
            rows = self.img_desc.Dimension1
            cols = self.img_desc.Dimension2
            if self.img_desc.Rank == 3:
                for i in range(rows):
                    rowidx = i * cols * 3
                    r = []
                    for j in range(cols):
                        colidx = j * 3
                        r.append(a[colidx : colidx + 3])
                    l.append(r)
            else:
                for i in range(rows):
                    rowidx = i * cols
                    l.append(a[rowidx : rowidx + cols])

            return l  # Nested lists
        #
        # JSON IMAGE DATA -> List of Lists (row major)
        #
        else:
            j = response.json()
            n = j["ErrorNumber"]
            m = j["ErrorMessage"]
            # raise Exception(n, m)                   # Raise Alpaca Exception if non-zero Alpaca error
            l = j["Value"]  # Nested lists
            if type(l[0][0]) == list:  # Test & pick up color plane
                r = 3
                d3 = len(l[0][0])
            else:
                r = 2
                d3 = 0
            self.img_desc = ImageMetadata(
                1,  # Meta version
                ImageArrayElementTypes.Int32,  # Image element type
                ImageArrayElementTypes.Int32,  # Xmsn element type
                r,  # Rank
                len(l),  # Dimension 1
                len(l[0]),  # Dimension 2
                d3,  # Dimension 3
            )
            return l


class CameraFile(Device):
    """CameraFile specific methods."""


class FilterWheel(Device):
    """Filter wheel specific methods."""

    def focusoffsets(self) -> List[int]:
        """Filter focus offsets.

        Returns:
            An integer array of filter focus offsets.

        """
        return self._get("focusoffsets")

    def names(self) -> List[str]:
        """Filter wheel filter names.

        Returns:
            Names of the filters.

        """
        return self._get("names")

    def position(self, Position: Optional[int] = None):
        """Set or return the filter wheel position.

        Args:
            Position (int): Number of the filter wheel position to select.

        Returns:
            Returns the current filter wheel position.

        """
        if Position is None:
            return self._get("position")
        self._put("position", Position=Position)


class Telescope(Device):
    """Telescope specific methods."""

    def alignmentmode(self):
        """Return the current mount alignment mode.

        Returns:
            Alignment mode of the mount (Alt/Az, Polar, German Polar).

        """
        return self._get("alignmentmode")

    def altitude(self):
        """Return the mount's Altitude above the horizon.

        Returns:
            Altitude of the telescope's current position (degrees, positive up).

        """
        return self._get("altitude")

    def aperturearea(self):
        """Return the telescope's aperture.

        Returns:
            Area of the telescope's aperture (square meters).

        """
        return self._get("aperturearea")

    def aperturediameter(self):
        """Return the telescope's effective aperture.

        Returns:
            Telescope's effective aperture diameter (meters).

        """
        return self._get("aperturediameter")

    def athome(self):
        """Indicate whether the mount is at the home position.

        Returns:
            True if the mount is stopped in the Home position. Must be False if the
            telescope does not support homing.

        """
        return self._get("athome")

    def atpark(self):
        """Indicate whether the telescope is at the park position.

        Returns:
            True if the telescope has been put into the parked state by the seee park()
            method. Set False by calling the unpark() method.

        """
        return self._get("atpark")

    def azimuth(self):
        """Return the telescope's aperture.

        Return:
            Azimuth of the telescope's current position (degrees, North-referenced,
            positive East/clockwise).

        """
        return self._get("azimuth")

    def canfindhome(self):
        """Indicate whether the mount can find the home position.

        Returns:
            True if this telescope is capable of programmed finding its home position.

        """
        return self._get("canfindhome")

    def canpark(self):
        """Indicate whether the telescope can be parked.

        Returns:
            True if this telescope is capable of programmed parking.

        """
        return self._get("canpark")

    def canpulseguide(self):
        """Indicate whether the telescope can be pulse guided.

        Returns:
            True if this telescope is capable of software-pulsed guiding (via the
            pulseguide(int, int) method).

        """
        return self._get("canpulseguide")

    def cansetdeclinationrate(self):
        """Indicate whether the DeclinationRate property can be changed.

        Returns:
            True if the DeclinationRate property can be changed to provide offset
            tracking in the declination axis.

        """
        return self._get("cansetdeclinationrate")

    def cansetguiderates(self):
        """Indicate whether the DeclinationRate property can be changed.

        Returns:
            True if the guide rate properties used for pulseguide(int, int) can ba
            adjusted.

        """
        return self._get("cansetguiderates")

    def cansetpark(self):
        """Indicate whether the telescope park position can be set.

        Returns:
            True if this telescope is capable of programmed setting of its park position
            (setpark() method).

        """
        return self._get("cansetpark")

    def cansetpierside(self):
        """Indicate whether the telescope SideOfPier can be set.

        Returns:
            True if the SideOfPier property can be set, meaning that the mount can be
            forced to flip.

        """
        return self._get("cansetpierside")

    def cansetrightascensionrate(self):
        """Indicate whether the RightAscensionRate property can be changed.

        Returns:
            True if the RightAscensionRate property can be changed to provide offset
            tracking in the right ascension axis.

        """
        return self._get("cansetrightascensionrate")

    def cansettracking(self):
        """Indicate whether the Tracking property can be changed.

        Returns:
            True if the Tracking property can be changed, turning telescope sidereal
            tracking on and off.

        """
        return self._get("cansettracking")

    def canslew(self):
        """Indicate whether the telescope can slew synchronously.

        Returns:
            True if this telescope is capable of programmed slewing (synchronous or
            asynchronous) to equatorial coordinates.

        """
        return self._get("canslew")

    def canslewaltaz(self):
        """Indicate whether the telescope can slew synchronously to AltAz coordinates.

        Returns:
            True if this telescope is capable of programmed slewing (synchronous or
            asynchronous) to local horizontal coordinates.

        """
        return self._get("canslewaltaz")

    def canslewaltazasync(self):
        """Indicate whether the telescope can slew asynchronusly to AltAz coordinates.

        Returns:
            True if this telescope is capable of programmed asynchronus slewing
            (synchronous or asynchronous) to local horizontal coordinates.

        """
        return self._get("canslewaltazasync")

    def cansync(self):
        """Indicate whether the telescope can sync to equatorial coordinates.

        Returns:
            True if this telescope is capable of programmed synching to equatorial
            coordinates.

        """
        return self._get("cansync")

    def cansyncaltaz(self):
        """Indicate whether the telescope can sync to local horizontal coordinates.

        Returns:
            True if this telescope is capable of programmed synching to local horizontal
            coordinates.

        """
        return self._get("cansyncaltaz")

    def declination(self):
        """Return the telescope's declination.

        Notes:
            Reading the property will raise an error if the value is unavailable.

        Returns:
            The declination (degrees) of the telescope's current equatorial coordinates,
            in the coordinate system given by the EquatorialSystem property.

        """
        return self._get("declination")

    def declinationrate(self, DeclinationRate: Optional[float] = None):
        """Set or return the telescope's declination tracking rate.

        Args:
            DeclinationRate (float): Declination tracking rate (arcseconds per second).

        Returns:
            The declination tracking rate (arcseconds per second) if DeclinatioRate is
            not set.

        """
        if DeclinationRate is None:
            return self._get("declinationrate")
        self._put("declinationrate", DeclinationRate=DeclinationRate)

    def doesrefraction(self, DoesRefraction: Optional[bool] = None):
        """Indicate or determine if atmospheric refraction is applied to coordinates.

        Args:
            DoesRefraction (bool): Set True to make the telescope or driver apply
                atmospheric refraction to coordinates.

        Returns:
            True if the telescope or driver applies atmospheric refraction to
            coordinates.

        """
        if DoesRefraction is None:
            return self._get("doesrefraction")
        self._put("doesrefraction", DoesRefraction=DoesRefraction)

    def equatorialsystem(self):
        """Return the current equatorial coordinate system used by this telescope.

        Returns:
            Current equatorial coordinate system used by this telescope
            (e.g. Topocentric or J2000).

        """
        return self._get("equatorialsystem")

    def focallength(self):
        """Return the telescope's focal length in meters.

        Returns:
            The telescope's focal length in meters.

        """
        return self._get("focallength")

    def guideratedeclination(self, GuideRateDeclination: Optional[float] = None):
        """Set or return the current Declination rate offset for telescope guiding.

        Args:
            GuideRateDeclination (float): Declination movement rate offset
                (degrees/sec).

        Returns:
            Current declination rate offset for telescope guiding if not set.

        """
        if GuideRateDeclination is None:
            return self._get("guideratedeclination")
        self._put("guideratedeclination", GuideRateDeclination=GuideRateDeclination)

    def guideraterightascension(self, GuideRateRightAscension: Optional[float] = None):
        """Set or return the current RightAscension rate offset for telescope guiding.

        Args:
            GuideRateRightAscension (float): RightAscension movement rate offset
                (degrees/sec).

        Returns:
            Current right ascension rate offset for telescope guiding if not set.

        """
        if GuideRateRightAscension is None:
            return self._get("guideraterightascension")
        self._put(
            "guideraterightascension", GuideRateRightAscension=GuideRateRightAscension
        )

    def ispulseguiding(self):
        """Indicate whether the telescope is currently executing a PulseGuide command.

        Returns:
            True if a pulseguide(int, int) command is in progress, False otherwise.

        """
        return self._get("ispulseguiding")

    def rightascension(self):
        """Return the telescope's right ascension coordinate.

        Returns:
            The right ascension (degrees) of the telescope's current equatorial
            coordinates, in the coordinate system given by the EquatorialSystem
            property.

        """
        return self._get("rightascension") / 24 * 360  # hourangle -> deg

    def rightascensionrate(self, RightAscensionRate: Optional[float] = None):
        """Set or return the telescope's right ascension tracking rate.

        Args:
            RightAscensionRate (float): Right ascension tracking rate (arcseconds per
                second).

        Returns:
            Telescope's right ascension tracking rate if not set.

        """
        if RightAscensionRate is None:
            return self._get("rightascensionrate")
        self._put("rightascensionrate", RightAscensionRate=RightAscensionRate)

    def sideofpier(self, SideOfPier: Optional[int] = None):
        """Set or return the mount's pointing state.

        Args:
            SideOfPier (int): New pointing state. 0 = pierEast, 1 = pierWest

        Returns:
            Side of pier if not set.

        """
        if SideOfPier is None:
            return self._get("sideofpier")
        self._put("sideofpier", SideOfPier=SideOfPier)

    def siderealtime(self):
        """Return the local apparent sidereal time.

        Returns:
            The local apparent sidereal time from the telescope's internal clock (hours,
            sidereal).

        """
        return self._get("siderealtime")

    def siteelevation(self, SiteElevation: Optional[float] = None):
        """Set or return the observing site's elevation above mean sea level.

        Args:
            SiteElevation (float): Elevation above mean sea level (metres).

        Returns:
            Elevation above mean sea level (metres) of the site at which the telescope
            is located if not set.

        """
        if SiteElevation is None:
            return self._get("siteelevation")
        self._put("siteelevation", SiteElevation=SiteElevation)

    def sitelatitude(self, SiteLatitude: Optional[float] = None):
        """Set or return the observing site's latitude.

        Args:
            SiteLatitude (float): Site latitude (degrees).

        Returns:
            Geodetic(map) latitude (degrees, positive North, WGS84) of the site at which
            the telescope is located if not set.

        """
        if SiteLatitude is None:
            return self._get("sitelatitude")
        self._put("sitelatitude", SiteLatitude=SiteLatitude)

    def sitelongitude(self, SiteLongitude: Optional[float] = None):
        """Set or return the observing site's longitude.

        Args:
            SiteLongitude (float): Site longitude (degrees, positive East, WGS84)

        Returns:
            Longitude (degrees, positive East, WGS84) of the site at which the telescope
            is located.

        """
        if SiteLongitude is None:
            return self._get("sitelongitude")
        self._put("sitelongitude", SiteLongitude=SiteLongitude)

    def slewing(self):
        """Indicate whether the telescope is currently slewing.

        Returns:
            True if telescope is currently moving in response to one of the Slew methods
            or the moveaxis(int, float) method, False at all other times.

        """
        return self._get("slewing")

    def slewsettletime(self, SlewSettleTime: Optional[int] = None):
        """Set or return the post-slew settling time.

        Args:
            SlewSettleTime (int): Settling time (integer sec.).

        Returns:
            Returns the post-slew settling time (sec.) if not set.

        """
        if SlewSettleTime is None:
            return self._get("slewsettletime")
        self._put("slewsettletime", SlewSettleTime=SlewSettleTime)

    def targetdeclination(self, TargetDeclination: Optional[Union[float, str]] = None):
        """Set or return the target declination of a slew or sync.

        Args:
            TargetDeclination (float): Target declination(degrees)

        Returns:
            Declination (degrees, positive North) for the target of an equatorial slew
            or sync operation.

        """
        if TargetDeclination is None:
            return self._get("targetdeclination")
        _, TargetDeclination = check_equatorial_coordinates(0.0, TargetDeclination)
        self._put("targetdeclination", TargetDeclination=TargetDeclination)

    def targetrightascension(
        self, TargetRightAscension: Optional[Union[float, str]] = None
    ):
        """Set or return the current target right ascension.

        Args:
            TargetRightAscension (float or str): Right Ascension coordinate (degrees if float, hours if str).

        Returns:
            Right ascension (float) for the target of an equatorial slew or sync
            operation (degrees).

        """

        if TargetRightAscension is None:
            return self._get("targetrightascension") / 24 * 360  # hourangle -> deg
        TargetRightAscension, _ = check_equatorial_coordinates(
            TargetRightAscension, 0.0
        )
        TargetRightAscension = TargetRightAscension / 360 * 24  # deg -> hour angle
        self._put("targetrightascension", TargetRightAscension=TargetRightAscension)

    def tracking(self, Tracking: Optional[bool] = None):
        """Enable, disable, or indicate whether the telescope is tracking.

        Args:
            Tracking (bool): Tracking enabled / disabled.

        Returns:
            State of the telescope's sidereal tracking drive.

        """
        if Tracking is None:
            return self._get("tracking")
        self._put("tracking", Tracking=Tracking)

    def trackingrate(self, TrackingRate: Optional[int] = None):
        """Set or return the current tracking rate.

        Args:
            TrackingRate (int): New tracking rate. 0 = driveSidereal, 1 = driveLunar,
                2 = driveSolar, 3 = driveKing.

        Returns:
            Current tracking rate of the telescope's sidereal drive if not set.

        """
        if TrackingRate is None:
            return self._get("trackingrate")
        self._put("trackingrate", TrackingRate=TrackingRate)

    def trackingrates(self):
        """Return a collection of supported DriveRates values.

        Returns:
            List of supported DriveRates values that describe the permissible values of
            the TrackingRate property for this telescope type.

        """
        return self._get("trackingrates")

    def utcdate(self, UTCDate: Optional[Union[str, datetime]] = None):
        """Set or return the UTC date/time of the telescope's internal clock.

        Args:
            UTCDate: UTC date/time as an str or datetime.

        Returns:
            datetime of the UTC date/time if not set.

        """
        if UTCDate is None:
            return self._get("utcdate")

        if type(UTCDate) is str:
            data = UTCDate
        elif type(UTCDate) is datetime:
            data = UTCDate.isoformat()
        else:
            raise TypeError()

        self._put("utcdate", UTCDate=data)

    def abortslew(self):
        """Immediatley stops a slew in progress."""
        self._put("abortslew")

    def axisrates(self, Axis: int):
        """Return rates at which the telescope may be moved about the specified axis.

        Returns:
            The rates at which the telescope may be moved about the specified axis by
            the moveaxis(int, float) method.

        """
        return self._get("axisrates", Axis=Axis)

    def canmoveaxis(self, Axis: int):
        """Indicate whether the telescope can move the requested axis.

        Returns:
            True if this telescope can move the requested axis.

        """
        return self._get("canmoveaxis", Axis=Axis)

    def destinationsideofpier(
        self, RightAscension: Union[float, str], Declination: Union[float, str]
    ):
        """Predict the pointing state after a German equatorial mount slews to given coordinates.

        Args:
            RightAscension (float or str): Right Ascension coordinate (degrees if float, hours if str).
            Declination (float or str): Declination coordinate (degrees).

        Returns:
            Pointing state that a German equatorial mount will be in if it slews to the
            given coordinates. The return value will be one of - 0 = pierEast,
            1 = pierWest, -1 = pierUnknown.

        """

        RightAscension, Declination = check_equatorial_coordinates(
            RightAscension, Declination
        )
        RightAscension = RightAscension / 360 * 24  # deg -> hour angle

        return self._get(
            "destinationsideofpier",
            RightAscension=RightAscension,
            Declination=Declination,
        )

    def findhome(self):
        """Move the mount to the "home" position."""
        self._put("findhome")

    def moveaxis(self, Axis: int, Rate: float):
        """Move a telescope axis at the given rate.

        Args:
            Axis (int): The axis about which rate information is desired.
                0 = axisPrimary, 1 = axisSecondary, 2 = axisTertiary.
            Rate (float): The rate of motion (deg/sec) about the specified axis

        """
        self._put("moveaxis", Axis=Axis, Rate=Rate)

    def park(self):
        """Park the mount."""
        self._put("park")

    def pulseguide(self, Direction: int, Duration: int):
        """Move the scope in the given direction for the given time.

        Notes:
            0 = guideNorth, 1 = guideSouth, 2 = guideEast, 3 = guideWest.

        Args:
            Direction (int): Direction in which the guide-rate motion is to be made.
            Duration (int): Duration of the guide-rate motion (milliseconds).

        """
        self._put("pulseguide", Direction=Direction, Duration=Duration)

    def setpark(self):
        """Set the telescope's park position."""
        self._put("setpark")

    def slewtoaltaz(self, Azimuth: Union[float, str], Altitude: Union[float, str]):
        """Slew synchronously to the given local horizontal coordinates.

        Args:
            Azimuth (float or str): Azimuth coordinate (degrees, North-referenced, positive
                East/clockwise).
            Altitude (float or str): Altitude coordinate (degrees, positive up).

        """
        Azimuth, Altitude = check_horizontal_coordinates(Azimuth, Altitude)
        self._put("slewtoaltaz", Azimuth=Azimuth, Altitude=Altitude)

    def slewtoaltazasync(self, Azimuth: Union[float, str], Altitude: Union[float, str]):
        """Slew asynchronously to the given local horizontal coordinates.

        Args:
            Azimuth (float or str): Azimuth coordinate (degrees, North-referenced, positive
                East/clockwise).
            Altitude (float or str): Altitude coordinate (degrees, positive up).

        """
        Azimuth, Altitude = check_horizontal_coordinates(Azimuth, Altitude)
        self._put("slewtoaltazasync", Azimuth=Azimuth, Altitude=Altitude)

    def slewtocoordinates(
        self, RightAscension: Union[float, str], Declination: Union[float, str]
    ):
        """Slew synchronously to the given equatorial coordinates.

        Args:
            RightAscension (float or str): Right Ascension coordinate (degrees if float, hours if str).
            Declination (float or str): Declination coordinate (degrees).

        """
        RightAscension, Declination = check_equatorial_coordinates(
            RightAscension, Declination
        )
        RightAscension = RightAscension / 360 * 24  # deg -> hour angle
        self._put(
            "slewtocoordinates", RightAscension=RightAscension, Declination=Declination
        )

    def slewtocoordinatesasync(
        self, RightAscension: Union[float, str], Declination: Union[float, str]
    ):
        """Slew asynchronously to the given equatorial coordinates.

        Args:
            RightAscension (float or str): Right Ascension coordinate (degrees if float, hours if str).
            Declination (float or str): Declination coordinate (degrees).

        """
        RightAscension, Declination = check_equatorial_coordinates(
            RightAscension, Declination
        )
        RightAscension = RightAscension / 360 * 24  # deg -> hour angle
        self._put(
            "slewtocoordinatesasync",
            RightAscension=RightAscension,
            Declination=Declination,
        )

    def slewtotarget(self):
        """Slew synchronously to the TargetRightAscension and TargetDeclination coordinates."""
        self._put("slewtotarget")

    def slewtotargetasync(self):
        """Asynchronously slew to the TargetRightAscension and TargetDeclination coordinates."""
        self._put("slewtotargetasync")

    def synctoaltaz(self, Azimuth: Union[float, str], Altitude: Union[float, str]):
        """Sync to the given local horizontal coordinates.

        Args:
            Azimuth (float or str): Azimuth coordinate (degrees, North-referenced, positive
                East/clockwise).
            Altitude (float or str): Altitude coordinate (degrees, positive up).

        """
        Azimuth, Altitude = check_horizontal_coordinates(Azimuth, Altitude)
        self._put("synctoaltaz", Azimuth=Azimuth, Altitude=Altitude)

    def synctocoordinates(
        self, RightAscension: Union[float, str], Declination: Union[float, str]
    ):
        """Sync to the given equatorial coordinates.

        Args:
            RightAscension (float or str): Right Ascension coordinate (degrees if float, hours if str).
            Declination (float or str): Declination coordinate (degrees).

        """
        RightAscension, Declination = check_equatorial_coordinates(
            RightAscension, Declination
        )
        RightAscension = RightAscension / 360 * 24  # deg -> hour angle
        self._put(
            "synctocoordinates", RightAscension=RightAscension, Declination=Declination
        )

    def synctotarget(self):
        """Sync to the TargetRightAscension and TargetDeclination coordinates."""
        self._put("synctotarget")

    def unpark(self):
        """Unpark the mount."""
        self._put("unpark")


class Focuser(Device):
    """Focuser specific methods."""

    def absolute(self) -> bool:
        """Indicates whether the focuser is capable of absolute position

        Returns:
            True if the focuser is capable of absolute position; that is, being commanded to a specific step location.
        """
        return self._get("absolute")

    def ismoving(self) -> bool:
        """Indicates whether the focuser is currently moving

        Returns:
            True if the focuser is currently moving to a new position. False if the focuser is stationary.
        """
        return self._get("ismoving")

    def maxincrement(self) -> int:
        """Returns the focuser's maximum increment size.

        Returns:
            Maximum increment size allowed by the focuser;
            i.e. the maximum number of steps allowed in one move operation.
        """
        return self._get("maxincrement")

    def maxstep(self) -> int:
        """Returns the focuser's maximum step size.

        Returns:
            Maximum step position permitted.
        """
        return self._get("maxstep")

    def position(self) -> int:
        """Returns the focuser's current position.

        Returns:
            Current focuser position, in steps.
        """
        return self._get("position")

    def stepsize(self) -> float:
        """Returns the focuser's step size

        Returns:
            Step size (microns) for the focuser.
        """
        return self._get("stepsize")

    def tempcomp(self, TempComp: Optional[bool] = None) -> Optional[bool]:
        """Set or return the state of temperature compensation mode

        Args:
            TempComp (bool): Set true to enable the focuser's temperature compensation mode,
            otherwise false for normal operation.

        Returns:
            Gets the state of temperature compensation mode (if available), else always False.

        """
        if TempComp is None:
            return self._get("tempcomp")
        self._put("tempcomp", TempComp=TempComp)

    def tempcompavailable(self) -> bool:
        """Indicates whether the focuser has temperature compensation

        Returns:
            True if focuser has temperature compensation available.
        """
        return self._get("tempcompavailable")

    def temperature(self) -> float:
        """Returns the focuser's current temperature

        Returns:
            Current ambient temperature as measured by the focuser.
        """
        return self._get("temperature")

    def halt(self):
        """Immediatley stops focuser motion

        Notes:
            Immediately stop any focuser motion due to a previous move() method call.
        """
        self._put("halt")

    def move(self, Position: int):
        """Moves the focuser to a new position

        Notes:
            Moves the focuser by the specified amount or to the specified position
            depending on the value of the Absolute property.

        Args:
            Position (int): Step distance or absolute position, depending on the value of the Absolute property
        """
        self._put("move", Position=Position)


class Rotator(Device):
    """Rotator specific methods."""

    def canreverse(self) -> bool:
        """Indicates whether the Rotator supports the Reverse method

        Returns:
            True if the Rotator supports the Reverse method.
        """
        return self._get("canreverse")

    def ismoving(self) -> bool:
        """Indicates whether the rotator is currently moving

        Returns:
            True if the rotator is capable of ismoving position; that is, being commanded to a specific step location.
        """
        return self._get("ismoving")

    def mechanicalposition(self) -> float:
        """Returns the rotator's mechanical current position

        Returns:
            Current instantaneous Rotator position, in degrees.
        """
        return self._get("mechanicalposition")

    def position(self) -> float:
        """Returns the rotator's current position

        Returns:
            Returns the raw mechanical position of the rotator in degrees.
        """
        return self._get("position")

    def reverse(self, Reverse: Optional[bool] = None) -> Optional[bool]:
        """Set or return the rotator’s Reverse state

        Args:
            Reverse (bool): True if the rotation and angular direction must
            be reversed to match the optical characteristcs

        Returns:
            Returns the rotator’s Reverse state.
        """
        if Reverse is None:
            return self._get("reverse")
        self._put("reverse", Reverse=Reverse)

    def stepsize(self) -> float:
        """Returns the minimum StepSize

        Returns:
            The minimum StepSize, in degrees.
        """
        return self._get("stepsize")

    def targetposition(self) -> float:
        """Returns the destination position angle

        Returns:
            The destination position angle for Move() and MoveAbsolute().
        """
        return self._get("targetposition")

    def halt(self):
        """Immediatley stops rotator motion

        Notes:
            Immediately stop any Rotator motion due to a previous move() or moveabsolute() method call.
        """
        self._put("halt")

    def move(self, Position: float):
        """Moves the rotator to a new relative position

        Notes:
            Causes the rotator to move Position degrees relative to the current Position value.

        Args:
            Position (float): Relative position to move in degrees from current Position.
        """
        self._put("move", Position=Position)

    def moveabsolute(self, Position: float):
        """Moves the rotator to a new absolute position

        Notes:
            Causes the rotator to move the absolute position of Position degrees.

        Args:
            Position (float): Absolute position in degrees.
        """
        self._put("moveabsolute", Position=Position)

    def movemechanical(self, Position: float):
        """Moves the rotator to a new raw mechanical position

        Notes:
            Causes the rotator to move the mechanical position of Position degrees.

        Args:
            Position (float): Absolute position in degrees.
        """
        self._put("movemechanical", Position=Position)

    def sync(self, Position: float):
        """Syncs the rotator to the specified position angle without moving it

        Notes:
            Causes the rotator to sync to the position of Position degrees.

        Args:
            Position (float): Absolute position in degrees.
        """
        self._put("sync", Position=Position)


_component_classes = {
    "telescope": Telescope,
    "dome": Dome,
    "camera": Camera,
    "filterwheel": FilterWheel,
    "focuser": Focuser,
    "rotator": Rotator,
    "switch": Switch,
    "safetymonitor": SafetyMonitor,
    "file": CameraFile,
}
