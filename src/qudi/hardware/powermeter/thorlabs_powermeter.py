# -*- coding: utf-8 -*-

"""
Hardware module for using a Thorlabs power meter as a process value device.
Uses PyVISA with SCPI commands — works on Windows, macOS, and Linux without
any platform-specific Thorlabs libraries.

Compatible devices (PM100 series and others with SCPI support):
- PM100A, PM100D, PM100USB
- PM101 Series, PM102 Series, PM103 Series
- PM16 Series, PM160, PM160T, PM160T-HP
- PM200, PM400

Copyright (c) 2022, the qudi developers. See the AUTHORS.md file at the top-level directory of this
distribution and on <https://github.com/Ulm-IQO/qudi-iqo-modules/>

This file is part of qudi.

Qudi is free software: you can redistribute it and/or modify it under the terms of
the GNU Lesser General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

Qudi is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License along with qudi.
If not, see <https://www.gnu.org/licenses/>.
"""

import pyvisa

from qudi.core.configoption import ConfigOption
from qudi.interface.powermeter_interface import (
    PowerMeterInterface,
    PowerMeterConstraints,
    PowerLimitMode,
)
from qudi.interface.process_control_interface import (
    ProcessValueInterface,
    ProcessControlConstraints,
)

# Thorlabs USB vendor ID used to auto-detect power meters
_THORLABS_VENDOR_ID = '0x1313'


class ThorlabsPowermeter(ProcessValueInterface, PowerMeterInterface):
    """Hardware module for Thorlabs powermeter using PyVISA (cross-platform).

    Example config:

    powermeter:
        module.Class: 'powermeter.thorlabs_powermeter.ThorlabsPowermeter'
        options:
            # Device address of the powermeter.
            # If omitted, the module will connect to the first Thorlabs powermeter found.
            # The module logs an info message with the addresses of all available powermeters upon activation.
            address: 'USB0::0x1313::0x8078::P0012345::INSTR'
            wavelength: 940.0
    """

    _address: str = ConfigOption("address", default=None, missing="nothing")
    _wavelength: float = ConfigOption("wavelength", default=None, missing="warn")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._channel_name = "Power"
        self._constraints = None
        self._pm_constrains = None
        self._is_active = False

        self._rm = None
        self._device = None
        self._device_address = None

    def on_activate(self):
        """Startup the module"""
        self._rm = pyvisa.ResourceManager()

        # find available Thorlabs power meters
        all_resources = self._rm.list_resources()
        available_power_meters = [
            r for r in all_resources if _THORLABS_VENDOR_ID.lower() in r.lower()
        ]
        self.log.info(f"Available power meters: {available_power_meters}")

        if self._address is None:
            try:
                first = available_power_meters[0]
            except IndexError:
                self.log.exception("No powermeter available on system.")
                raise ValueError
            else:
                self.log.info(f"Using first available powermeter with address {first}.")
                self._device_address = first
        else:
            if self._address in available_power_meters:
                self.log.info(f"Using powermeter with address {self._address}.")
                self._device_address = self._address
            else:
                self.log.exception(f"No powermeter with address {self._address} found.")
                raise ValueError

        # connect and query constraints
        try:
            self._init_powermeter(reset=True)
        except Exception as e:
            self.log.exception(
                "Connection to powermeter was unsuccessful. Try using the Power Meter Driver "
                "Switcher application to switch your powermeter to the TLPM driver."
            )
            raise e

        self._is_active = True

        min_power = float(self._device.query('SENS:POW:RANG? MIN'))
        max_power = float(self._device.query('SENS:POW:RANG? MAX'))

        self._constraints = ProcessControlConstraints(
            process_channels=(self._channel_name,),
            units={self._channel_name: "W"},
            limits={self._channel_name: (min_power, max_power)},
            dtypes={self._channel_name: float},
        )

        self._pm_constrains = PowerMeterConstraints(
            wavelength={"default": 930, "bounds": (self._get_wavelength_range())},
            power_range={
                "default": (min_power + max_power) / 2,
                "bounds": (min_power, max_power),
            },
            power_limit_modes=(PowerLimitMode.AUTO, PowerLimitMode.MANUAL),
            power_range_mode_default=PowerLimitMode.AUTO,
        )

        if self._wavelength is not None:
            self.set_wavelength(self._wavelength)

        self._close_powermeter()
        self._is_active = False

    def on_deactivate(self):
        """Stops the module"""
        self.set_activity_state(self._channel_name, False)
        if self._rm is not None:
            self._rm.close()
            self._rm = None

    @property
    def process_values(self):
        """Read-Only property returning a snapshot of current process values for all channels."""
        return {self._channel_name: self.get_process_value(self._channel_name)}

    @property
    def constraints(self):
        """Read-Only property holding the constraints for this hardware module."""
        return self._constraints

    def set_activity_state(self, channel, active):
        """Set activity state."""
        if channel != self._channel_name:
            raise AssertionError(
                f"Invalid channel name. Only valid channel is: {self._channel_name}"
            )
        if active != self._is_active:
            self._is_active = active
            if active:
                self._init_powermeter()
            else:
                self._close_powermeter()

    def get_activity_state(self, channel):
        """Get activity state for given channel."""
        if channel != self._channel_name:
            raise AssertionError(
                f"Invalid channel name. Only valid channel is: {self._channel_name}"
            )
        return self._is_active

    @property
    def activity_states(self):
        """Current activity state for each channel."""
        return {self._channel_name: self._is_active}

    @activity_states.setter
    def activity_states(self, values):
        """Set activity state for multiple channels."""
        for ch, enabled in values.items():
            if ch != self._channel_name:
                raise AssertionError(
                    f"Invalid channel name. Only valid channel is: {self._channel_name}"
                )
            self.set_activity_state(ch, enabled)

    def get_process_value(self, channel):
        """Return a measured value"""
        if channel != self._channel_name:
            raise AssertionError(
                f"Invalid channel name. Only valid channel is: {self._channel_name}"
            )
        if not self.get_activity_state(self._channel_name):
            raise AssertionError(
                "Channel is not active. Activate first before getting process value."
            )
        return self._get_power()

    def get_power(self):
        """Get the measured power from the powermeter in Watts."""
        self._check_enabled()
        return self._get_power()

    def get_wavelength(self) -> float:
        """Get the currently set wavelength of the powermeter in nm."""
        self._check_enabled()
        return float(self._device.query('SENS:CORR:WAV?'))

    def set_wavelength(self, wavelength: float):
        """Set the wavelength of the powermeter in nm."""
        self._check_enabled()
        try:
            self.pm_constraints.wavelength.check_value_range(wavelength)
        except ValueError as e:
            self.log.exception("Wavelength out of bounds.")
            raise e
        self._device.write(f'SENS:CORR:WAV {wavelength}')

    def get_power_range(self) -> float:
        """Gets the current power range of the power meter in Watts."""
        self._check_enabled()
        return float(self._device.query('SENS:POW:RANG?'))

    def set_power_range(self, limit: float):
        """Sets the power range of the power meter in Watts."""
        self._check_enabled()
        try:
            self.pm_constraints.power_range.check_value_range(limit)
        except ValueError as e:
            self.log.exception("Power limit out of bounds.")
            raise e
        self._device.write(f'SENS:POW:RANG {limit}')

    def get_auto_power_range(self) -> bool:
        """Returns True if auto power range is enabled."""
        self._check_enabled()
        return self._device.query('SENS:POW:RANG:AUTO?').strip() in ('1', 'ON')

    def set_auto_power_range(self, enabled):
        """Enable or disable auto power range."""
        self._check_enabled()
        mode = PowerLimitMode(enabled)
        self._device.write(f'SENS:POW:RANG:AUTO {"ON" if mode.value else "OFF"}')

    def get_enabled(self) -> bool:
        """Returns True if the power meter is active."""
        return self.get_activity_state(self._channel_name)

    def set_enabled(self, enable: bool):
        """Enable or disable the power meter."""
        self.set_activity_state(self._channel_name, enable)

    @property
    def pm_constraints(self) -> PowerMeterConstraints:
        """Read-only property containing the constraints of the powermeter."""
        return self._pm_constrains.copy()

    def set_bandwidth(self, bandwidth: str) -> None:
        """Set the photodiode input filter state ('high' or 'low' bandwidth).

        Note: Only available on PM100D, PM100A, PM100USB, PM200, PM400.
        """
        self._check_enabled()
        bandwidth = bandwidth.lower()
        if bandwidth not in ('high', 'low'):
            raise ValueError("'bandwidth' should be 'high' or 'low'.")
        state = 'OFF' if bandwidth == 'high' else 'ON'
        self._device.write(f'INP:FILT:LPAS:STAT {state}')

    def get_bandwidth(self) -> str:
        """Get the photodiode input filter state.

        Note: Only available on PM100D, PM100A, PM100USB, PM200, PM400.
        Returns 'high' or 'low'.
        """
        self._check_enabled()
        state = self._device.query('INP:FILT:LPAS:STAT?').strip()
        return 'low' if state in ('1', 'ON') else 'high'

    def _init_powermeter(self, reset=False):
        """Open a VISA connection to the power meter."""
        self._device = self._rm.open_resource(self._device_address)
        self._device.timeout = 5000
        if reset:
            self._device.write('*RST')
            self._device.write('*CLS')

    def _close_powermeter(self):
        """Close VISA connection to the power meter."""
        if self._device is not None:
            self._device.close()
            self._device = None

    def _get_power(self):
        """Return the power reading from the power meter in Watts."""
        return float(self._device.query('MEAS:POW?'))

    def _get_wavelength_range(self):
        """Return the measurement wavelength range in nm as (min, max)."""
        wl_min = float(self._device.query('SENS:CORR:WAV? MIN'))
        wl_max = float(self._device.query('SENS:CORR:WAV? MAX'))
        return wl_min, wl_max

    def _check_enabled(self):
        if not self.get_enabled():
            raise AssertionError(
                "Power meter is not active. Activate by calling 'set_enabled(True)'"
            )
