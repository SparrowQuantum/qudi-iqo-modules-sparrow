# -*- coding: utf-8 -*-

"""
Hardware module for using a Thorlabs power meter as a process value device.
It uses the TLPM driver, which supersedes the now legacy PM100D driver. It is installed
together with the Optical Power Monitor software.

Compatible devices according to Thorlabs:
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

import platform
from ctypes import (
    byref,
    c_bool,
    c_char_p,
    cdll,
    c_double,
    c_int,
    c_int16,
    c_long,
    create_string_buffer,
    c_uint32,
)

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

# constants
SET_VALUE = c_int16(0)
MIN_VALUE = c_int16(1)
MAX_VALUE = c_int16(2)


class ThorlabsPowermeter(ProcessValueInterface, PowerMeterInterface):
    """Hardware module for Thorlabs powermeter using the TLPM library.

    Example config:

    powermeter:
        module.Class: 'powermeter.thorlabs_powermeter.ThorlabsPowermeter'
        options:
            # Device address of the powermeter.
            # If omitted, the module will connect to the first powermeter found on the system.
            # The module logs an info message with the addresses of all available powermeters upon activation.
            address: 'USB0::0x1313::0x8078::P0012345::INSTR'
            wavelength: 940.0
    """

    _address: str = ConfigOption("address", missing="warn")
    _wavelength: float = ConfigOption("wavelength", default=None, missing="warn")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._channel_name = "Power"
        self._constraints = None
        self._pm_constrains = None
        self._is_active = False

        self._dll = None
        self._devSession = c_long()
        self._devSession.value = 0
        self._device_address = None

    def _test_for_error(self, status):
        if status < 0:
            msg = create_string_buffer(1024)
            self._dll.TLPM_errorMessage(self._devSession, c_int(status), msg)
            self.log.exception(c_char_p(msg.raw).value)
            raise ValueError

    def on_activate(self):
        """Startup the module"""
        # load the dll
        try:
            if platform.architecture()[0] == "32bit":
                self._dll = cdll.LoadLibrary(
                    "C:/Program Files (x86)/IVI Foundation/VISA/WinNT/Bin/TLPM_32.dll"
                )
            else:
                self._dll = cdll.LoadLibrary(
                    "C:/Program Files/IVI Foundation/VISA/Win64/Bin/TLPM_64.dll"
                )
        except FileNotFoundError as e:
            self.log.error(
                "TLPM _dll not found. Is the Thorlabs Optical Power Monitor software installed?"
            )
            raise e

        # get list of available power meters
        device_count = c_uint32()
        result = self._dll.TLPM_findRsrc(self._devSession, byref(device_count))
        self._test_for_error(result)

        available_power_meters = []
        resource_name = create_string_buffer(1024)

        for i in range(0, device_count.value):
            result = self._dll.TLPM_getRsrcName(
                self._devSession, c_int(i), resource_name
            )
            self._test_for_error(result)
            available_power_meters.append(c_char_p(resource_name.raw).value.decode())

        self.log.info(f"Available power meters: {available_power_meters}")

        # figure out address of powermeter
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

        # try connecting to the powermeter
        try:
            self._init_powermeter(reset=True)
        except ValueError as e:
            self.log.exception(
                "Connection to powermeter was unsuccessful. Try using the Power Meter Driver "
                + "Switcher application to switch your powermeter to the TLPM driver."
            )
            raise e

        self._is_active = True

        # get power range
        min_power, max_power = c_double(), c_double()
        result = self._dll.TLPM_getPowerRange(
            self._devSession, MIN_VALUE, byref(min_power)
        )
        self._test_for_error(result)
        result = self._dll.TLPM_getPowerRange(
            self._devSession, MAX_VALUE, byref(max_power)
        )
        self._test_for_error(result)

        # set constraints
        self._constraints = ProcessControlConstraints(
            process_channels=(self._channel_name,),
            units={self._channel_name: "W"},
            limits={self._channel_name: (min_power.value, max_power.value)},
            dtypes={self._channel_name: float},
        )

        self._pm_constrains = PowerMeterConstraints(
            wavelength={"default": 930, "bounds": (self._get_wavelength_range())},
            power_range={
                "default": (min_power.value + max_power.value) / 2,
                "bounds": (min_power.value, max_power.value),
            },
            power_limit_modes=(PowerLimitMode.AUTO, PowerLimitMode.MANUAL),
            power_range_mode_default=PowerLimitMode.AUTO,
        )

        # set wavelength if defined in config
        if self._wavelength is not None:
            self.set_wavelength(self._wavelength)

        # close connection since default state is not active
        self._close_powermeter()
        self._is_active = False

    def on_deactivate(self):
        """Stops the module"""
        self.set_activity_state(self._channel_name, False)

    @property
    def process_values(self):
        """Read-Only property returning a snapshot of current process values for all channels.

        @return dict: Snapshot of the current process values (values) for all channels (keys)
        """
        value = self.get_process_value(self._channel_name)
        return {self._channel_name: value}

    @property
    def constraints(self):
        """Read-Only property holding the constraints for this hardware module.
        See class ProcessControlConstraints for more details.

        @return ProcessControlConstraints: Hardware constraints
        """
        return self._constraints

    def set_activity_state(self, channel, active):
        """Set activity state. State is bool type and refers to active (True) and inactive (False)."""
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
        """Get activity state for given channel.
        State is bool type and refers to active (True) and inactive (False).
        """
        if channel != self._channel_name:
            raise AssertionError(
                f"Invalid channel name. Only valid channel is: {self._channel_name}"
            )
        return self._is_active

    @property
    def activity_states(self):
        """Current activity state (values) for each channel (keys).
        State is bool type and refers to active (True) and inactive (False).
        """
        return {self._channel_name: self._is_active}

    @activity_states.setter
    def activity_states(self, values):
        """Set activity state (values) for multiple channels (keys).
        State is bool type and refers to active (True) and inactive (False).
        """
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
        """
        Get the measured power from the powermeter

        @return float: Measured power in Watts
        """
        self._check_enabled()
        return self._get_power()

    def get_wavelength(self) -> float:
        """
        Get the currently set wavelength of the powermeter

        @return float: The set wavelength
        """
        self._check_enabled()
        wavelength = c_double()
        result = self._dll.TLPM_getWavelength(
            self._devSession, SET_VALUE, byref(wavelength)
        )
        self._test_for_error(result)
        return wavelength.value

    def set_wavelength(self, wavelength: float):
        """
        Set the wavelength of the powermeter

        @param float wavelength: The wavelength to set in nanometers
        """
        """ Set the new measurement wavelength in nanometers """
        self._check_enabled()
        try:
            self.pm_constraints.wavelength.check_value_range(wavelength)
        except ValueError as e:
            self.log.exception("Wavelength out of bounds.")
            raise e

        result = self._dll.TLPM_setWavelength(self._devSession, c_double(wavelength))
        self._test_for_error(result)

    def get_power_range(self) -> float:
        """
        Gets the max power measurable by the power meter

        @return float: max power in watts
        """
        self._check_enabled()
        power = c_double()
        result = self._dll.TLPM_getPowerRange(self._devSession, SET_VALUE, byref(power))
        self._test_for_error(result)
        return power.value

    def set_power_range(self, limit: float):
        """
        Sets the max power measurable by the power meter in watts

        @param float limit: max power in watts
        """
        self._check_enabled()
        try:
            self.pm_constraints.power_range.check_value_range(limit)
        except ValueError as e:
            self.log.exception("Power limit out of bounds.")
            raise e
        result = self._dll.TLPM_setPowerRange(self._devSession, c_double(limit))
        self._test_for_error(result)

    def get_auto_power_range(self) -> bool:
        """
        Returns true if the power meter automatically controls the power limit.

        @return bool: True if auto limit is on, False otherwise.
        """
        self._check_enabled()
        autorange = c_int16()
        result = self._dll.TLPM_getPowerAutorange(self._devSession, byref(autorange))
        self._test_for_error(result)
        return autorange.value == 1

    def set_auto_power_range(self, enabled):
        """
        Enable or disable auto power limit.

        @param enabled: True to enable auto powerlimit. False otherwise
        """
        self._check_enabled()
        mode = PowerLimitMode(enabled)
        mode = c_int16(1) if mode.value else c_int16(0)
        result = self._dll.TLPM_setPowerAutoRange(self._devSession, mode)
        self._test_for_error(result)

    def get_enabled(self) -> bool:
        """
        Returns true if the power meter is active. False otherwise.

        @return bool
        """
        return self.get_activity_state(self._channel_name)

    def set_enabled(self, enable: bool):
        """
        Enables or disables the power meter.

        @param bool enable: Enable or disable the powermeter.
        """
        self.set_activity_state(self._channel_name, enable)

    @property
    def pm_constraints(self) -> PowerMeterConstraints:
        """
        Read-only property containing the constraints of the powermeter.

        @return PowerMeterConstraints
        """
        return self._pm_constrains.copy()

    def _init_powermeter(self, reset=False):
        """
        Initialize powermeter and open a connection to it.
        :param reset: whether to reset the powermeter upon connection
        """
        id_query, reset_device = c_bool(True), c_bool(reset)
        address = create_string_buffer(self._device_address.encode("utf-8"))
        result = self._dll.TLPM_init(
            address, id_query, reset_device, byref(self._devSession)
        )
        try:
            self._test_for_error(result)
        except ValueError as e:
            self.log.exception("Connection to powermeter was unsuccessful.")
            raise e

    def _close_powermeter(self):
        """Close connection to powermeter."""
        result = self._dll.TLPM_close(self._devSession)
        self._test_for_error(result)

    def _get_power(self):
        """Return the power reading from the power meter"""
        power = c_double()
        result = self._dll.TLPM_measPower(self._devSession, byref(power))
        try:
            self._test_for_error(result)
        except ValueError as e:
            self.log.exception("Getting power from powermeter was unsuccessful.")
            raise e
        return power.value

    def _get_wavelength_range(self):
        """Return the measurement wavelength range of the power meter in nanometers"""
        wavelength_min = c_double()
        wavelength_max = c_double()
        result = self._dll.TLPM_getWavelength(
            self._devSession, MIN_VALUE, byref(wavelength_min)
        )
        self._test_for_error(result)
        result = self._dll.TLPM_getWavelength(
            self._devSession, MAX_VALUE, byref(wavelength_max)
        )
        self._test_for_error(result)

        return wavelength_min.value, wavelength_max.value

    def _check_enabled(self):
        if not self.get_enabled():
            raise AssertionError(
                "Power meter is not active. Activate by calling 'set_enabled(True)'"
            )

    def set_bandwidth(self, bandwidth: str) -> None:
        """
        This function sets the instrument's photodiode input filter state.
        Notes:
        (1) The function is only available on PM100D, PM100A, PM100USB, PM200, PM400.
            :param bandwidth: "high", or "low" bandwidth
        """

        self._check_enabled()

        bandwidth = bandwidth.lower()

        value_dict = {"high": 0, "low": 1}
        if bandwidth not in value_dict.keys():
            raise ValueError("'bandwidth' should be set to 'high', or 'low'.")

        input_filter_state = value_dict[bandwidth]

        try:
            result = self._dll.TLPM_setInputFilterState(
                self._devSession, c_int16(input_filter_state)
            )
        except Exception as e:
            self.log.exception("Setting bandwidth mode was unsuccessful.")
            raise e
        else:
            self._test_for_error(result)

    def get_bandwidth(self) -> str:
        """
        This function returns the instrument's photodiode input filter state.
        Notes:
        (1) The function is only available on PM100D, PM100A, PM100USB, PM200, PM400.
        :return str: 'high' or 'low' bandwidth
        """

        self._check_enabled()
        input_filter_state = c_int16()
        result = self._dll.TLPM_getInputFilterState(
            self._devSession, byref(input_filter_state)
        )
        self._test_for_error(result)

        bandwidth_modes = ["high", "low"]
        bandwidth = bandwidth_modes[int(input_filter_state.value)]
        return bandwidth
