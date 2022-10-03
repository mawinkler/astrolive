"""Constant Definitions for AstroLive."""

MANUFACTURER = "AstroLive 0.1"
API_ENDPOINT = "http://localhost:11111/api/v1"
CLIENT_ID = 1

REQUESTS_TIMEOUTS = (2, 30)

COLOR_BLACK = "1;30"
COLOR_RED = "1;31"
COLOR_GREEN = "1;32"
COLOR_BROWN = "1;33"
COLOR_BLUE = "1;34"
COLOR_PURPLE = "1;35"
COLOR_CYAN = "1;36"
COLOR_STD = "0"

DEVICE_TYPE_OBSERVATORY = "observatory"
DEVICE_TYPE_TELESCOPE = "telescope"
DEVICE_TYPE_CAMERA = "camera"
DEVICE_TYPE_CAMERA_FILE = "camerafile"
DEVICE_TYPE_SWITCH = "switch"
DEVICE_TYPE_FOCUSER = "focuser"
DEVICE_TYPE_FILTERWHEEL = "filterwheel"

IMAGE_PUBLISH_DIMENSIONS = (1024, 685)
IMAGE_STRETCH_FUNCTION = "asinh"
IMAGE_MINMAX_PERCENT = [15, 95]  # [0.5, 95]
IMAGE_MINMAX_VALUE = None
IMAGE_INVERT = False

FUNCTIONS = {
    DEVICE_TYPE_TELESCOPE: (
        "At home",
        "At park",
        "Altitude",
        "Azimuth",
        "Declination",
        "Declination rate",
        "Guiderate declination",
        "Right ascension",
        "Right ascension rate",
        "Guiderate right ascension",
        "Side of pier",
        "Site elevation",
        "Site Latitude",
        "Site Longitude",
        "Slewing",
    ),
    DEVICE_TYPE_CAMERA: (
        "Camera state",
        "CCD Temperature",
        "Cooler on",
        "Cooler Power",
        "Image array",
        "Image ready",
        "Last exposure duration",
        "Last exposure start time",
        "Percent completed",
        "Readout mode",
        "Readout modes",
        "Sensor type",
    ),
    DEVICE_TYPE_CAMERA_FILE: (
        "Image Type",  # IMAGETYP
        "Exposure Duration",  # EXPOSURE
        "Time of observation",  # DATE-OBS
        "X axis binning",  # XBINNING
        "Y axis binning",  # YBINNING
        "Gain",  # GAIN
        "Offset",  # OFFSET
        "Pixel X axis size",  # XPIXSZ
        "Pixel Y axis size",  # YPIXSZ
        "Imaging instrument",  # INSTRUME
        "CCD temperature",  # CCD-TEMP
        "Filter",  # FILTER
        "Sensor readout mode",  # READOUTM
        "Sensor Bayer pattern",  # BAYERPAT
        "Telescope",  # TELESCOP
        "Focal length",  # FOCALLEN
        "RA of telescope",  # RA
        "Declination of telescope",  # DEC
        "Altitude of telescope",  # CENTALT
        "Azimuth of telescope",  # CENTAZ
        "Object of interest",  # OBJECT
        "RA of imaged object",  # OBJCTRA
        "Declination of imaged object",  # OBJCTDEC
        "Rotation of imaged object",  # OBJCTROT
        "Software",  # SWCREATE
    ),
    DEVICE_TYPE_FOCUSER: (
        "Position",
        "Is moving",
    ),
    DEVICE_TYPE_SWITCH: ("Max switch",),
    DEVICE_TYPE_FILTERWHEEL: (
        "Names",
        "Position",
        "Current",
    ),
}

ICONS = {
    DEVICE_TYPE_TELESCOPE: "mdi:telescope",
    DEVICE_TYPE_CAMERA: "mdi:camera",
    DEVICE_TYPE_CAMERA_FILE: "mdi:camera",
    DEVICE_TYPE_FOCUSER: "mdi:focus-auto",
    DEVICE_TYPE_SWITCH: "mdi:hubspot",
    DEVICE_TYPE_FILTERWHEEL: "mdi:image-filter-black-white",
}

CAMERA_STATES = [
    "Camera idle",
    "Camera waiting",
    "Camera exposing",
    "Camera reading",
    "Camera download",
    "Camera error",
]
CAMERA_SENSOR_TYPES = [
    "Monochrome",
    "Colour not requiring Bayer decoding",
    "RGGB Bayer encoding",
    "CMYG Bayer encoding",
    "CMYG2 Bayer encoding",
    "LRGB TRUESENSE Bayer encoding",
]
