# -*- coding: utf-8 -*-

"""
This file contains the Qudi Interface file for control wavemeter hardware.

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

from abc import abstractmethod
from enum import IntEnum
from qudi.core.module import Base


class OperationState(IntEnum):
    STOPPED = 0
    ADJUSTMENT = 1
    MEASUREMENT = 2


class WavemeterErrorStatus(IntEnum):
    UNKNOWN_ERROR = -1
    NO_ERRORS = 0
    NO_VALUE = 1
    NO_SIGNAL = 2
    BAD_SIGNAL = 3
    LOW_SIGNAL = 4
    BIG_SIGNAL = 5


class WavemeterInterface(Base):
    """ Define the controls for a wavemeter hardware.

    Note: This interface is very similar in feature with slow counter
    """

    @abstractmethod
    def start_acquisition(self) -> None:
        """
        Method to start the wavemeter acquisition
        """
        pass

    @abstractmethod
    def stop_acquisition(self) -> None:
        """
        Stops the Wavemeter from measuring and kills the thread that queries the data.
        """
        pass

    @abstractmethod
    def get_current_wavelength(self) -> float:
        """
        This method returns the current wavelength.

        @return: the wavelength in m
        """
        pass

    @abstractmethod
    def get_current_frequency(self) -> float:
        """
        This method returns the current frequency.

        @return: the frequency in Hz
        """
        pass

    @abstractmethod
    def get_timing(self):
        """ Get the timing of the internal measurement thread.

        @return: clock length in second
        """
        pass

    @abstractmethod
    def set_timing(self, timing: int) -> None:
        """
        Get the timing of the internal measurement thread.

        @param timing: The timing in milliseconds
        """
        pass

    @abstractmethod
    def get_operation_state(self) -> OperationState:
        """
        Gets the current measurement state of the wavemeter.

        @return: Current measurment state.
        """
        pass

    @abstractmethod
    def get_error_status(self) -> WavemeterErrorStatus:
        """
        Gets the current error status of the wavemeter

        @return: Wavemeter error status
        """
        pass
