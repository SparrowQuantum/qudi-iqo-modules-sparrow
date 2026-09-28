# -*- coding: utf-8 -*-
"""
Interface for a spectrometer.

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
from qudi.core.module import Base


class SpectrometerInterface(Base):
    """This is the interface class to define the controls for the simple optical spectrometer.

    This is interface is very basic, a more advanced one is in progress.

    Warning: This interface use CamelCase. This is should not be done in future versions. See more info here :
    documentation/programming_style.md

    """

    @abstractmethod
    def record_spectrum(self):
        """Launch an acquisition a wait for a response

        @return (2, N) float array: The acquired array with the wavelength in meter in the first row and measured value
                                    int the second
        """
        pass

    @property
    @abstractmethod
    def exposure_time(self):
        """Get the acquisition exposure time

        @return (float): Exposure time in second
        """
        pass

    @exposure_time.setter
    @abstractmethod
    def exposure_time(self, value):
        """Set the acquisition exposure time

        @param (float) value: Exposure time to set in second
        """
        pass

    @property
    @abstractmethod
    def shutter_open(self) -> bool:
        """Get the acquisition shutter state

        @return (bool): Shutter state
        """
        pass

    @shutter_open.setter
    @abstractmethod
    def shutter_open(self, value):
        """Set the acquisition shutter state"""
        pass

    @property
    def background_correction(self) -> bool:
        """Whether this hardware subtracts its own dark frame

        Hardware holding a background (a server-side dark frame, say) corrects
        at the source. Hardware holding none stays False and ignores writes, so
        a caller may hand the setting over unconditionally and read back
        whether it took effect, correcting itself only when it did not.

        @return (bool): True when spectra are returned background-corrected
        """
        return False

    @background_correction.setter
    def background_correction(self, value: bool):
        """Request background correction; ignored when unsupported"""
        pass
