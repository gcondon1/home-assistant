"""
Support for Nest Thermostat Binary Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.nest/
"""
from itertools import chain
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.nest import (
    DATA_NEST, DATA_NEST_CONFIG, CONF_BINARY_SENSORS, NestSensorDevice)
from homeassistant.const import CONF_MONITORED_CONDITIONS

DEPENDENCIES = ['nest']

BINARY_TYPES = {'online': 'connectivity'}

CLIMATE_BINARY_TYPES = {
    'fan': None,
    'is_using_emergency_heat': 'heat',
    'is_locked': None,
    'has_leaf': None,
}

CAMERA_BINARY_TYPES = {
    'motion_detected': 'motion',
    'sound_detected': 'sound',
    'person_detected': 'occupancy',
}

STRUCTURE_BINARY_TYPES = {
    'away': None,
}

STRUCTURE_BINARY_STATE_MAP = {
    'away': {'away': True, 'home': False},
}

_BINARY_TYPES_DEPRECATED = [
    'hvac_ac_state',
    'hvac_aux_heater_state',
    'hvac_heater_state',
    'hvac_heat_x2_state',
    'hvac_heat_x3_state',
    'hvac_alt_heat_state',
    'hvac_alt_heat_x2_state',
    'hvac_emer_heat_state',
]

_VALID_BINARY_SENSOR_TYPES = {**BINARY_TYPES, **CLIMATE_BINARY_TYPES,
                              **CAMERA_BINARY_TYPES, **STRUCTURE_BINARY_TYPES}

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Nest binary sensors.

    No longer used.
    """


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up a Nest binary sensor based on a config entry."""
    nest = hass.data[DATA_NEST]

    discovery_info = \
        hass.data.get(DATA_NEST_CONFIG, {}).get(CONF_BINARY_SENSORS, {})

    # Add all available binary sensors if no Nest binary sensor config is set
    if discovery_info == {}:
        conditions = _VALID_BINARY_SENSOR_TYPES
    else:
        conditions = discovery_info.get(CONF_MONITORED_CONDITIONS, {})

    for variable in conditions:
        if variable in _BINARY_TYPES_DEPRECATED:
            wstr = (variable + " is no a longer supported "
                    "monitored_conditions. See "
                    "https://home-assistant.io/components/binary_sensor.nest/ "
                    "for valid options.")
            _LOGGER.error(wstr)

    def get_binary_sensors():
        """Get the Nest binary sensors."""
        sensors = []
        for structure in nest.structures():
            sensors += [NestBinarySensor(structure, None, variable)
                        for variable in conditions
                        if variable in STRUCTURE_BINARY_TYPES]
        device_chain = chain(nest.thermostats(),
                             nest.smoke_co_alarms(),
                             nest.cameras())
        for structure, device in device_chain:
            sensors += [NestBinarySensor(structure, device, variable)
                        for variable in conditions
                        if variable in BINARY_TYPES]
            sensors += [NestBinarySensor(structure, device, variable)
                        for variable in conditions
                        if variable in CLIMATE_BINARY_TYPES
                        and device.is_thermostat]

            if device.is_camera:
                sensors += [NestBinarySensor(structure, device, variable)
                            for variable in conditions
                            if variable in CAMERA_BINARY_TYPES]
                for activity_zone in device.activity_zones:
                    sensors += [NestActivityZoneSensor(structure,
                                                       device,
                                                       activity_zone)]

        return sensors

    async_add_devices(await hass.async_add_job(get_binary_sensors), True)


class NestBinarySensor(NestSensorDevice, BinarySensorDevice):
    """Represents a Nest binary sensor."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the device class of the binary sensor."""
        return _VALID_BINARY_SENSOR_TYPES.get(self.variable)

    def update(self):
        """Retrieve latest state."""
        value = getattr(self._device, self.variable)
        if self.variable in STRUCTURE_BINARY_TYPES:
            self._state = bool(STRUCTURE_BINARY_STATE_MAP
                               [self.variable].get(value))
        else:
            self._state = bool(value)


class NestActivityZoneSensor(NestBinarySensor):
    """Represents a Nest binary sensor for activity in a zone."""

    def __init__(self, structure, device, zone):
        """Initialize the sensor."""
        super(NestActivityZoneSensor, self).__init__(structure, device, "")
        self.zone = zone
        self._name = "{} {} activity".format(self._name, self.zone.name)

    @property
    def device_class(self):
        """Return the device class of the binary sensor."""
        return 'motion'

    def update(self):
        """Retrieve latest state."""
        self._state = self._device.has_ongoing_motion_in_zone(
            self.zone.zone_id)
