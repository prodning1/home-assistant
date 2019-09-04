"""
Support for Denon Network Receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.denon/
"""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    MediaPlayerDevice,
)
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON, STATE_UNKNOWN
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ["pyserial"]

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Music station"

SUPPORT_DENON = (
    SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
)
SUPPORT_MEDIA_MODES = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

NORMAL_INPUTS = {
    "PHONO": "Phono",
    "CD": "CD",
    "TUNER": "Tuner",
    "DVD": "DVD",
    "VDP": "VDP",
    "TV": "TV",
    "Satelite / Cable": "DBS/SAT",
    "VCR 1": "VCR-1",
    "VCR 2": "VCR-2",
    "VCR 3": "VCR-3",
    "Video Aux": "V.AUX",
    "CD-R/Tape 1": "CDR/TAPE1",
    "MD/Tape 2": "MD/TAPE2",
    "USB": "USB",
    "IPOD": "IPOD",
}

MEDIA_MODES = {"Tuner": "TUNER"}

# Sub-modes of 'NET/USB'
# {'USB': 'USB', 'iPod Direct': 'IPD', 'Internet Radio': 'IRP',
#  'Favorites': 'FVP'}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Denon platform."""
    denon = DenonDevice(config.get(CONF_NAME), config.get(CONF_HOST))

    if denon.update():
        add_entities([denon])


class DenonDevice(MediaPlayerDevice):
    """Representation of a Denon device."""

    def __init__(self, name, host):
        """Initialize the Denon device."""
        self._name = name
        self._host = host
        self._pwstate = "PWSTANDBY"
        self._volume = 0
        self._volume_max = 80
        self._source_list = NORMAL_INPUTS.copy()
        self._source_list.update(MEDIA_MODES)
        self._muted = False
        self._mediasource = ""
        self._mediainfo = ""

    @classmethod
    def serial_request(cls, serial, command, all_lines=False):
        """Execute `command` and return the response."""
        _LOGGER.debug("Sending: %s", command)
        serial.write(command.encode("ASCII") + b"\r")
        lines = []
        while True:
            line = serial.read_until(b"\r")
            if not line:
                break
            lines.append(line.decode("ASCII").strip())
            _LOGGER.debug("Received: %s", line)

        if all_lines:
            return lines
        return lines[0] if lines else ""

    def serial_command(self, command):
        import serial

        """Establish a telnet connection and sends `command`."""
        telnet = serial.Serial(self._host, 9600, timeout=0.2)
        _LOGGER.debug("Sending: %s", command)
        telnet.write(command.encode("ASCII") + b"\r")
        telnet.read()  # skip response
        telnet.close()

    def update(self):
        import serial

        """Get the latest details from the device."""
        try:
            telnet = serial.Serial(self._host, 9600, timeout=0.2)
        except OSError:
            return False

        self._pwstate = self.serial_request(telnet, "PW?")
        for line in self.serial_request(telnet, "MV?", all_lines=True):
            if line.startswith("MV"):
                self._volume = int(line[len("MV") :])
        self._muted = self.serial_request(telnet, "MU?") == "MUON"
        self._mediasource = self.serial_request(telnet, "SI?")[len("SI") :]

        if self._mediasource in MEDIA_MODES.values():
            self._mediainfo = ""
            answer_codes = [
                "NSE0",
                "NSE1X",
                "NSE2X",
                "NSE3X",
                "NSE4",
                "NSE5",
                "NSE6",
                "NSE7",
                "NSE8",
            ]
            for line in self.serial_request(telnet, "NSE", all_lines=True):
                self._mediainfo += line[len(answer_codes.pop(0)) :] + "\n"
        else:
            self._mediainfo = self.source

        telnet.close()
        return True

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._pwstate == "PWSTANDBY":
            return STATE_OFF
        if self._pwstate == "PWON":
            return STATE_ON

        return STATE_UNKNOWN

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume / self._volume_max

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        return self._muted

    @property
    def source_list(self):
        """Return the list of available input sources."""
        return sorted(list(self._source_list.keys()))

    @property
    def media_title(self):
        """Return the current media info."""
        return self._mediainfo

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self._mediasource in MEDIA_MODES.values():
            return SUPPORT_DENON | SUPPORT_MEDIA_MODES
        return SUPPORT_DENON

    @property
    def source(self):
        """Return the current input source."""
        for pretty_name, name in self._source_list.items():
            if self._mediasource == name:
                return pretty_name

    def turn_off(self):
        """Turn off media player."""
        self.serial_command("PWSTANDBY")

    def volume_up(self):
        """Volume up media player."""
        self.set_volume_level(self._volume + 3)

    def volume_down(self):
        """Volume down media player."""
        self.set_volume_level(self._volume - 3)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self.serial_command("MV" + str(round(volume * self._volume_max)).zfill(2))

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        self.serial_command("MU" + ("ON" if mute else "OFF"))

    def turn_on(self):
        """Turn the media player on."""
        self.serial_command("PWON")

    def select_source(self, source):
        """Select input source."""
        self.serial_command("SI" + self._source_list.get(source))
