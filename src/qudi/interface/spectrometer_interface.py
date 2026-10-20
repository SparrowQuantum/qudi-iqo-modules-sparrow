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
    def open_connection(self):
        """Establish communication with the spectrometer.

        Activation must not reach the device, so that a spectrometer that is
        switched off, moved or still booting cannot stop the module, its logic
        and its GUI from loading.

        Calling this when the connection is already open does nothing, so a
        caller may use it before every exchange without keeping track. Each
        module also calls it itself before talking to the device, so a caller
        that forgets still gets a clear communication error rather than a
        half-prepared instrument.

        :raises IOError: If the device cannot be reached.
        """
        pass

    @abstractmethod
    def close_connection(self):
        """Release communication with the spectrometer.

        A module has to be able to shut down even when the device cannot be
        reached, so anything that goes wrong here is written to the log and
        nothing is raised. The module is left ready to be opened again later.
        """
        pass

    @abstractmethod
    def record_spectrum(self):
        """Launch an acquisition and wait for a response.

        :return: (2, N) float array holding the wavelengths in metres in the
            first row and the measured values in the second.
        """
        pass

    @property
    @abstractmethod
    def exposure_time(self):
        """Get the acquisition exposure time.

        :return: Exposure time in seconds.
        """
        pass

    @exposure_time.setter
    @abstractmethod
    def exposure_time(self, value):
        """Set the acquisition exposure time.

        :param value: Exposure time to set, in seconds.
        """
        pass

    @property
    @abstractmethod
    def shutter_open(self) -> bool:
        """Get the acquisition shutter state.

        :return: True when the shutter is open.
        """
        pass

    @shutter_open.setter
    @abstractmethod
    def shutter_open(self, value):
        """Set the acquisition shutter state.

        :param value: True to open the shutter.
        """
        pass

    @property
    @abstractmethod
    def background_correction(self) -> bool:
        """Report whether this hardware subtracts its own dark frame.

        Hardware holding a background (a server-side dark frame, say) corrects
        at the source. Hardware holding none must return False and ignore
        writes, so a caller may hand the setting over unconditionally and read
        back whether it took effect, correcting itself only when it did not.

        :return: True when spectra are returned background-corrected.
        """
        pass

    @background_correction.setter
    @abstractmethod
    def background_correction(self, value: bool):
        """Request background correction, ignored when unsupported.

        :param value: True to have the hardware subtract its own dark frame.
        """
        pass

    @abstractmethod
    def stop_acquisition(self):
        """Ask an acquisition in progress to stop.

        Returns once the request has been placed, which may be before the
        acquisition itself ends. Does nothing when none is running.
        """
        pass

    @abstractmethod
    def get_wavelength(self) -> float:
        """Get the centre wavelength of the spectrometer.

        :return: Centre wavelength in metres.
        :raises NotImplementedError: If the dispersion is fixed.
        """
        pass

    @abstractmethod
    def set_wavelength(self, value: float):
        """Set the centre wavelength of the spectrometer.

        Returns once the grating has reached the position.

        :param value: Centre wavelength in metres.
        :raises NotImplementedError: If the dispersion is fixed.
        """
        pass

    @abstractmethod
    def acquire_background(self) -> bool:
        """Record a dark frame held and subtracted by the hardware.

        Pairs with background_correction: hardware that can record its own
        background (closing its shutter, say) does so here and applies it to
        later spectra. Hardware that cannot must return False without
        acquiring, leaving the caller to record and subtract a background.

        :return: True when the hardware now holds a background.
        """
        pass
