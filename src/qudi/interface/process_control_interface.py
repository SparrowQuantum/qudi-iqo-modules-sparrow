"""
Qudi interface definitions for a simple multi/single channel setpoint device,
a simple multi/single channel process value reading device
and the combination of both (reading/setting setpoints and reading process value).

Copyright (c) 2021, the qudi developers. See the AUTHORS.md file at the top-level directory of this
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

__all__ = [
    'ProcessControlChannelInactiveError',
    'ProcessControlCommunicationError',
    'ProcessControlConstraintError',
    'ProcessControlConstraints',
    'ProcessControlInterface',
    'ProcessControlInvalidChannelError',
    'ProcessSetpointInterface',
    'ProcessValueInterface',
]

from abc import abstractmethod
from collections.abc import Iterable, Mapping

import numpy as np
from qudi.core.module import Base
from qudi.util.helpers import in_range

_Real = int | float


class ProcessControlCommunicationError(IOError):
    """Exception raised for errors in the communication with the process control device."""


class ProcessControlChannelInactiveError(RuntimeError):
    """Exception raised for errors related to inactive process control channels."""


class ProcessControlInvalidChannelError(ValueError):
    """Exception raised for errors related to invalid process control channels."""


class ProcessControlConstraintError(ValueError):
    """Exception raised for errors in the process control constraints."""


class ProcessControlConstraints:
    """Data object holding the constraints for a set of process/setpoint channels."""

    def __init__(
        self,
        setpoint_channels: Iterable[str] | None = None,
        process_channels: Iterable[str] | None = None,
        units: Mapping[str, str] | None = None,
        limits: Mapping[str, tuple[_Real, _Real]] | None = None,
        dtypes: Mapping[str, type[int] | type[float]] | None = None,
    ) -> None:
        """Initialize the process control constraints."""
        if units is None:
            units = {}
        if limits is None:
            limits = {}
        if dtypes is None:
            dtypes = {}
        if setpoint_channels is None:
            setpoint_channels = ()
        if process_channels is None:
            process_channels = ()

        self._setpoint_channels = () if setpoint_channels is None else tuple(setpoint_channels)
        self._process_channels = () if process_channels is None else tuple(process_channels)

        all_channels = set(self._setpoint_channels)
        all_channels.update(self._process_channels)

        if not set(units).issubset(all_channels):
            msg = "units contain channels not present in setpoint or process channels."
            raise ValueError(msg)
        if not all(isinstance(unit, str) for unit in units.values()):
            msg = "all units must be strings."
            raise TypeError(msg)
        if not set(limits).issubset(all_channels):
            msg = "limits contain channels not present in setpoint or process channels."
            raise ValueError(msg)
        if not all(len(lim) == 2 for lim in limits.values()):
            msg = "all limits must be tuples of length 2."
            raise ValueError(msg)
        if not set(dtypes).issubset(all_channels):
            msg = "dtypes contain channels not present in setpoint or process channels."
            raise ValueError(msg)
        if not all(t in (int, float) for t in dtypes.values()):
            msg = "all dtypes must be int or float."
            raise TypeError(msg)

        self._channel_units = {ch: units.get(ch, '') for ch in all_channels}
        self._channel_limits = {ch: limits.get(ch, (-np.inf, np.inf)) for ch in all_channels}
        self._channel_dtypes = {ch: dtypes.get(ch, float) for ch in all_channels}

    @property
    def all_channels(self) -> tuple[str, ...]:
        return (*self.setpoint_channels, *self.process_channels)

    @property
    def setpoint_channels(self) -> tuple[str, ...]:
        return self._setpoint_channels

    @property
    def process_channels(self) -> tuple[str, ...]:
        return self._process_channels

    @property
    def channel_units(self) -> dict[str, str]:
        return self._channel_units.copy()

    @property
    def channel_limits(self) -> dict[str, tuple[_Real, _Real]]:
        return self._channel_limits.copy()

    @property
    def channel_dtypes(self) -> dict[str, type[int] | type[float]]:
        return self._channel_dtypes.copy()

    def channel_value_in_range(self, channel: str, value: _Real) -> tuple[bool, _Real]:
        return in_range(value, *self._channel_limits[channel])


class _ProcessControlInterfaceBase(Base):
    """Abstract base class for all interfaces in this module"""

    @property
    @abstractmethod
    def constraints(self) -> ProcessControlConstraints:
        """Read-Only property holding the constraints for this hardware module.

        See class ProcessControlConstraints for more details.

        @raises ProcessControlCommunicationError: If the module is unable to retrieve the constraints from the hardware.
        """

    @abstractmethod
    def set_activity_state(self, channel: str, active: bool) -> None:
        """Set activity state for given channel.

        State is bool type and refers to active (True) and inactive (False).

        @param channel: The name of the channel for which to set the activity state.
        @param active: The desired activity state for the channel.
        @raises ProcessControlCommunicationError: If the module is unable to set the activity state for the given channel.
        @raises ProcessControlInvalidChannelError: If the given channel is not valid.
        @raises TypeError: If the given value is not of the expected type (bool).
        """

    @abstractmethod
    def get_activity_state(self, channel: str) -> bool:
        """Get activity state for given channel.

        State is bool type and refers to active (True) and inactive (False).

        @param channel: The name of the channel for which to get the activity state.
        @raises ProcessControlCommunicationError: If the module is unable to get the activity state for the given channel.
        @raises ProcessControlInvalidChannelError: If the given channel is not valid.
        """

    # Non-abstract default implementations below

    @property
    def activity_states(self) -> dict[str, bool]:
        """Current activity state (values) for each channel (keys).

        State is bool type and refers to active (True) and inactive (False).

        @raises ProcessControlCommunicationError: If the module is unable to get the activity state for any of the channels.
        """
        return {ch: self.get_activity_state(ch) for ch in self.constraints.all_channels}

    @activity_states.setter
    def activity_states(self, values: Mapping[str, bool]) -> None:
        """Set activity state (values) for multiple channels (keys).

        State is bool type and refers to active (True) and inactive (False).

        @param values: A mapping of channel names (keys) to the desired activity states (values).
        @raises ProcessControlCommunicationError: If the module is unable to set the activity state for any of the channels.
        @raises ProcessControlInvalidChannelError: If any of the given channels are not valid.
        @raises ProcessControlConstraintError: If any of the given values violate the constraints for the respective channels.
        """
        for ch, enabled in values.items():
            self.set_activity_state(ch, enabled)


class ProcessSetpointInterface(_ProcessControlInterfaceBase):
    """A simple interface to control the setpoint for one or multiple process values.

    This interface is in fact a very general/universal interface that can be used for a lot of
    things. It can be used to interface any hardware where one to control one or multiple control
    values, like a temperature or how much a PhD student get paid.
    """

    @abstractmethod
    def set_setpoint(self, channel: str, value: _Real) -> None:
        """Set new setpoint for a single channel.

        @param channel: The name of the channel for which to set the setpoint.
        @param value: The desired setpoint value for the channel.
        @raises ProcessControlCommunicationError: If the module is unable to set the setpoint for the given channel.
        @raises ProcessControlChannelInactiveError: If the setpoint cannot be set because the channel is inactive.
        @raises ProcessControlInvalidChannelError: If the given channel is not valid.
        @raises ProcessControlConstraintError: If the given value violates the constraints for the channel.
        """

    @abstractmethod
    def get_setpoint(self, channel: str) -> _Real:
        """Get current setpoint for a single channel.

        @param channel: The name of the channel for which to get the setpoint.
        @raises ProcessControlCommunicationError: If the module is unable to get the setpoint for the given channel.
        @raises ProcessControlChannelInactiveError: If the setpoint cannot be retrieved because the channel is inactive.
        @raises ProcessControlInvalidChannelError: If the given channel is not valid.
        """

    # Non-abstract default implementations below

    @property
    def setpoints(self) -> dict[str, _Real]:
        """The current setpoints (values) for all channels (keys).

        @raises ProcessControlCommunicationError: If the module is unable to get the setpoints for any of the channels.
        @raises ProcessControlChannelInactiveError: If any of the setpoints cannot be retrieved because the respective channels are inactive.
        @raises ProcessControlConstraintError: If any of the setpoints violate the constraints for the respective channels.
        """
        return {ch: self.get_setpoint(ch) for ch in self.constraints.setpoint_channels}

    @setpoints.setter
    def setpoints(self, values: Mapping[str, _Real]) -> None:
        """Set the setpoints (values) for all channels (keys) at once.

        @param values: A mapping of channel names (keys) to the desired setpoints (values).
        @raises ProcessControlCommunicationError: If the module is unable to set the setpoints for any of the channels.
        @raises ProcessControlChannelInactiveError: If any of the setpoints cannot be set because the respective channels are inactive.
        @raises ProcessControlInvalidChannelError: If any of the given channels are not valid.
        @raises ProcessControlConstraintError: If any of the given values violate the constraints for the respective channels.
        """
        for ch, setpoint in values.items():
            self.set_setpoint(ch, setpoint)


class ProcessValueInterface(_ProcessControlInterfaceBase):
    """A simple interface to read one or multiple process values.

    This interface is in fact a very general/universal interface that can be used for a lot of
    things. It can be used to interface any hardware where one to control one or multiple control
    values, like a temperature or how much a PhD student get paid.
    """

    @abstractmethod
    def get_process_value(self, channel: str) -> _Real:
        """Get current process value for a single channel.

        @param channel: The name of the channel for which to get the process value.
        @raises ProcessControlCommunicationError: If the module is unable to get the process value for the given channel.
        @raises ProcessControlChannelInactiveError: If the process value cannot be retrieved because the channel is inactive.
        @raises ProcessControlInvalidChannelError: If the given channel is not valid.
        """

    # Non-abstract default implementations below

    @property
    def process_values(self) -> dict[str, _Real]:
        """Read-Only property returning a snapshot of current process values (values) for all
        channels (keys).

        @raises ProcessControlCommunicationError: If the module is unable to get the process value for any of the channels.
        @raises ProcessControlChannelInactiveError: If any of the process values cannot be retrieved because the respective channels are inactive.
        """
        return {ch: self.get_process_value(ch) for ch in self.constraints.process_channels}


class ProcessControlInterface(ProcessSetpointInterface, ProcessValueInterface):
    """A simple interface to control the setpoints for and read one or multiple process values.

    This interface is in fact a very general/universal interface that can be used for a lot of
    things. It can be used to interface any hardware where one to control one or multiple control
    values, like a temperature or how much a PhD student get paid.
    """
