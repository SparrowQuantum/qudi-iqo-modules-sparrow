# -*- coding: utf-8 -*-

"""
Interface file for powermeters. Originally made for Thorlabs PM100D

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Qudi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Qudi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

from abc import abstractmethod
from typing import Union, Mapping
from enum import Enum

import numpy as np

from qudi.core.module import Base
from qudi.util.constraints import ScalarConstraint


__all__ = ['PowerLimitMode', 'PowerMeterConstraints', 'PowerMeterInterface']


class PowerLimitMode(Enum):
    AUTO = True
    MANUAL = False


_SD = Union[ScalarConstraint, Mapping]


class PowerMeterConstraints:
    def __init__(self, wavelength: _SD = None, power_range: _SD = None,
                 power_limit_modes: tuple[PowerLimitMode, ...] = None,
                 power_range_mode_default: PowerLimitMode = None):
        if isinstance(wavelength, ScalarConstraint):
            self.wavelength = wavelength
        elif isinstance(wavelength, Mapping):
            self.wavelength = ScalarConstraint(**wavelength)
        else:
            self.wavelength = ScalarConstraint(default=632, bounds=(0, np.inf))

        if isinstance(power_range, ScalarConstraint):
            self.power_range = power_range
        elif isinstance(power_range, Mapping):
            self.power_range = ScalarConstraint(**power_range)
        else:
            self.power_range = ScalarConstraint(default=1, bounds=(0, np.inf))

        if power_limit_modes is not None:
            self.power_limit_modes = power_limit_modes
        else:
            self.power_limit_modes = (PowerLimitMode.AUTO, PowerLimitMode.MANUAL)

        if power_range_mode_default is not None:
            assert power_range_mode_default in self.power_limit_modes, "Default powerlimit mode not allowed."
            self.power_range_mode_default = power_range_mode_default
        else:
            self.power_range_mode_default = self.power_limit_modes[0]

    def copy(self):
        return PowerMeterConstraints(**vars(self))


class PowerMeterInterface(Base):
    """
    An interface to control and read data from an optical powermeter. Originally designed for the Thorlabs PM100D
    """

    @abstractmethod
    def get_power(self):
        """
        Get the measured power from the powermeter

        @return float: Measured power in Watts
        """
        pass

    @abstractmethod
    def get_wavelength(self) -> float:
        """
        Get the currently set wavelength of the powermeter

        @return float: The set wavelength
        """
        return 0

    def set_wavelength(self, wavelength: float):
        """
        Set the wavelength of the powermeter

        @param float wavelength: The wavelength to set in nanometers
        """
        pass

    @abstractmethod
    def get_power_range(self) -> float:
        """
        Gets the max power measurable by the power meter

        @return float: max power in watts
        """
        return 0.

    @abstractmethod
    def set_power_range(self, limit: float):
        """
        Sets the max power measurable by the power meter in watts

        @param float limit: max power in watts
        """

    @abstractmethod
    def get_auto_power_range(self) -> bool:
        """
        Returns true if the power meter automatically controls the power limit.

        @return bool: True if auto limit is on, False otherwise.
        """
        return False

    @abstractmethod
    def set_auto_power_range(self, enabled: Union[PowerLimitMode, bool]):
        """
        Enable or disable auto power limit.

        @param bool enabled: True to enable auto powerlimit. False otherwise
        """
        pass

    @abstractmethod
    def get_enabled(self) -> bool:
        """
        Returns true if the power meter is active. False otherwise.

        @return bool
        """

    @abstractmethod
    def set_enabled(self, enable: bool):
        """
        Enables or disables the power meter.

        @param bool enable: Enable or disable the powermeter.
        """

    @property
    @abstractmethod
    def pm_constraints(self) -> PowerMeterConstraints:
        """
        Read-only property containing the constraints of the powermeter.

        @return PowerMeterConstraints
        """
        pass
