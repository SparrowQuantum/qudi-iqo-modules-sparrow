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
from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
from numpy.typing import NDArray

from qudi.core.module import Base


class SpectrometerCommunicationError(IOError):
    """The spectrometer, or the software driving it, could not be reached."""


class SpectrometerAcquisitionError(RuntimeError):
    """The spectrometer was reached but did not deliver a spectrum."""


class SpectrometerUnsupportedFeatureError(NotImplementedError):
    """The spectrometer lacks an optional feature; see SpectrometerConstraints."""


class Spectrum(NamedTuple):
    """One acquired spectrum.

    Unpacks as ``wavelength_m, values = spectrum``, and ``np.array(spectrum)``
    gives the (2, N) array earlier versions of this interface returned.
    """

    wavelength_m: NDArray[np.float64]
    values: NDArray[np.float64]


@dataclass(frozen=True)
class SpectrometerConstraints:
    """What a spectrometer supports, so callers can check before asking.

    :param value_unit: Unit of Spectrum.values, e.g. 'counts'.
    :param exposure_time_range: Inclusive (min, max) exposure time in seconds.
    :param center_wavelength_range: Inclusive (min, max) centre wavelength in
        metres, or None when the dispersion is fixed.
    :param has_shutter: Whether shutter_open can be set.
    :param can_stop_acquisition: Whether stop_acquisition can end an exposure.
    :param has_hardware_background: Whether acquire_background records a dark
        frame that the hardware subtracts itself.
    """

    value_unit: str
    exposure_time_range: tuple[float, float]
    center_wavelength_range: tuple[float, float] | None
    has_shutter: bool
    can_stop_acquisition: bool
    has_hardware_background: bool


class SpectrometerInterface(Base):
    """Single-track optical spectrometer delivering one spectrum per acquisition.

    Modules normally reach the device lazily: activation does not connect, and
    every method that needs the device opens the connection itself (see
    open_connection for the exception). Optional features are declared in constraints; using one
    the device lacks raises SpectrometerUnsupportedFeatureError. Any method
    that reaches the device may raise SpectrometerCommunicationError.
    """

    @property
    @abstractmethod
    def constraints(self) -> SpectrometerConstraints:
        """Report what this spectrometer supports.

        :raises SpectrometerCommunicationError: If the device has to be queried
            for its limits and cannot be reached.
        """

    @abstractmethod
    def open_connection(self) -> None:
        """Establish communication with the spectrometer.

        Activation should not reach the device, so that a spectrometer that is
        switched off, moved or still booting cannot stop the module, its logic
        and its GUI from loading. A module that remote-controls external
        software, and is of no use without it, may instead start that
        software on activation and fail activation if it cannot.

        Calling this when the connection is already open does nothing, so a
        caller may use it before every exchange without keeping track. Each
        module also calls it itself before talking to the device, so a caller
        that forgets still gets a clear communication error rather than a
        half-prepared instrument.

        :raises SpectrometerCommunicationError: If the device cannot be reached.
        """

    @abstractmethod
    def close_connection(self) -> None:
        """Release communication with the spectrometer.

        A module has to be able to shut down even when the device cannot be
        reached, so anything that goes wrong here is written to the log and
        nothing is raised. The module is left ready to be opened again later.
        """

    @abstractmethod
    def record_spectrum(self) -> Spectrum:
        """Launch an acquisition and wait for it to finish.

        :return: Wavelengths in metres and the measured values, in the unit
            given by constraints.value_unit.
        :raises SpectrometerCommunicationError: If the device cannot be reached.
        :raises SpectrometerAcquisitionError: If the device could not start or
            complete the acquisition.
        """

    @property
    @abstractmethod
    def exposure_time(self) -> float:
        """Get the acquisition exposure time.

        :return: Exposure time in seconds.
        :raises SpectrometerCommunicationError: If the device cannot be reached.
        """

    @exposure_time.setter
    @abstractmethod
    def exposure_time(self, value: float) -> None:
        """Set the acquisition exposure time.

        :param value: Exposure time in seconds.
        :raises ValueError: If value is outside constraints.exposure_time_range.
        :raises SpectrometerCommunicationError: If the device cannot be reached.
        """

    @property
    @abstractmethod
    def shutter_open(self) -> bool:
        """Get the acquisition shutter state.

        :return: True when light reaches the detector, which is always the
            case for a spectrometer without a shutter.
        :raises SpectrometerCommunicationError: If the device cannot be reached.
        """

    @shutter_open.setter
    @abstractmethod
    def shutter_open(self, value: bool) -> None:
        """Set the acquisition shutter state.

        :param value: True to open the shutter.
        :raises SpectrometerUnsupportedFeatureError: If constraints.has_shutter
            is False.
        :raises SpectrometerCommunicationError: If the device cannot be reached.
        """

    @property
    @abstractmethod
    def background_correction(self) -> bool:
        """Report whether this hardware subtracts its own dark frame.

        Hardware holding a background (a server-side dark frame, say) corrects
        at the source. Hardware holding none must return False and ignore
        writes, so a caller may hand the setting over unconditionally and read
        back whether it took effect, correcting itself only when it did not.

        :return: True when spectra are returned background-corrected.
        :raises SpectrometerCommunicationError: If the device cannot be reached.
        """

    @background_correction.setter
    @abstractmethod
    def background_correction(self, value: bool) -> None:
        """Request background correction, ignored when unsupported.

        :param value: True to have the hardware subtract its own dark frame.
        :raises SpectrometerCommunicationError: If the device cannot be reached.
        """

    @abstractmethod
    def acquire_background(self) -> bool:
        """Record a dark frame held and subtracted by the hardware.

        Pairs with background_correction: hardware that can record its own
        background (closing its shutter, say) does so here and applies it to
        later spectra. Hardware that cannot must return False without
        acquiring, leaving the caller to record and subtract a background.

        :return: True when the hardware now holds a background.
        :raises SpectrometerCommunicationError: If the device cannot be reached.
        :raises SpectrometerAcquisitionError: If the dark frame could not be
            recorded.
        """

    @abstractmethod
    def stop_acquisition(self) -> None:
        """Ask an acquisition in progress to stop.

        Returns once the request has been placed, which may be before the
        acquisition itself ends. Does nothing when none is running.

        :raises SpectrometerUnsupportedFeatureError: If
            constraints.can_stop_acquisition is False.
        :raises SpectrometerCommunicationError: If the device cannot be reached.
        """

    @abstractmethod
    def get_center_wavelength(self) -> float:
        """Get the centre wavelength of the spectrometer.

        :return: Centre wavelength in metres.
        :raises SpectrometerUnsupportedFeatureError: If
            constraints.center_wavelength_range is None.
        :raises SpectrometerCommunicationError: If the device cannot be reached.
        """

    @abstractmethod
    def set_center_wavelength(self, value: float) -> None:
        """Set the centre wavelength of the spectrometer.

        Returns once the grating has reached the position.

        :param value: Centre wavelength in metres.
        :raises SpectrometerUnsupportedFeatureError: If
            constraints.center_wavelength_range is None.
        :raises ValueError: If value is outside
            constraints.center_wavelength_range.
        :raises SpectrometerCommunicationError: If the device cannot be reached.
        """
