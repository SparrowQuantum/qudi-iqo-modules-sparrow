# -*- coding: utf-8 -*-

"""
This module controls spectrometers from Ocean Optics Inc.
All spectrometers supported by python-seabreeze should work.
Please visit https://python-seabreeze.readthedocs.io/en/latest/index.html for more information.

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

from qudi.core.configoption import ConfigOption
from qudi.core.statusvariable import StatusVar
from qudi.interface.spectrometer_interface import SpectrometerInterface

import numpy as np
import seabreeze.spectrometers as sb


class OceanOptics(SpectrometerInterface):
    """Hardware module for reading spectra from the Ocean Optics spectrometer software.

    Example config for copy-paste:

    myspectrometer:
        module.Class: 'spectrometer.oceanoptics_spectrometer.OceanOptics'
        options:
            spectrometer_serial: 'QEP01583' #insert here the right serial number.

    """
    _serial = ConfigOption(name='spectrometer_serial', default=None, missing='warn')
    _integration_time = StatusVar(name='integration_time', default=0.1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._spectrometer = None

    def on_activate(self):
        """Activate module. The spectrometer is opened on first use."""
        pass

    def on_deactivate(self):
        """Deactivate module."""
        self.close_connection()

    def open_connection(self):
        """Open the spectrometer and apply the stored integration time.

        Calling this when the spectrometer is already open does nothing. Every
        method that talks to it calls this first, so whichever request comes
        first opens the device.

        :raises IOError: If no spectrometer with the configured serial answers.
        """
        if self._spectrometer is not None:
            return
        # cseabreeze and pyseabreeze raise unrelated types, so catch broadly and normalise
        try:
            self.log.info(f'available spectrometers: {sb.list_devices()}')
            self._spectrometer = sb.Spectrometer.from_serial_number(self._serial)
            self.log.info(''.format(self._spectrometer.model, self._spectrometer.serial_number))
            self.exposure_time = self._integration_time
        except Exception as exc:
            self.close_connection()
            raise IOError(f'Failed to open Ocean Optics spectrometer {self._serial}') from exc
        self.log.info(f'Exposure set to {self._integration_time} seconds')

    def close_connection(self):
        """Close the spectrometer, logging anything that goes wrong."""
        if self._spectrometer is None:
            return
        try:
            self._spectrometer.close()
        except Exception:
            self.log.exception('Failed to close the Ocean Optics spectrometer')
        self._spectrometer = None

    def record_spectrum(self):
        """Record a spectrum from the Ocean Optics spectrometer.

        :return: (2, N) array holding the wavelengths in metres and their
            intensities.
        """
        self.open_connection()
        wavelengths = self._spectrometer.wavelengths()
        specdata = np.empty((2, len(wavelengths)), dtype=np.double)
        specdata[0] = wavelengths / 1e9
        specdata[1] = self._spectrometer.intensities()
        return specdata

    @property
    def exposure_time(self):
        """Get the integration time.

        :return: Exposure time in seconds.
        """
        return self._integration_time

    @exposure_time.setter
    def exposure_time(self, value):
        """Set the integration time.

        :param value: Exposure time in seconds.
        """
        assert isinstance(value, (float, int)), f'exposure_time needs to be a float in seconds, but was {value}'
        self.open_connection()
        self._integration_time = float(value)
        self._spectrometer.integration_time_micros(int(self._integration_time * 1e6))

    @property
    def shutter_open(self) -> bool:
        """Report the shutter state, which this device has no shutter for.

        :return: Always True, as light always reaches the detector.
        """
        return True

    @shutter_open.setter
    def shutter_open(self, value):
        """Ignore the request, as the device has no shutter.

        :param value: Ignored.
        """
        pass

    @property
    def background_correction(self):
        """Hardware background correction. Not supported."""
        return False

    @background_correction.setter
    def background_correction(self, value):
        pass

    def acquire_background(self):
        """Hardware background acquisition. Not supported."""
        return False

    def stop_acquisition(self):
        """Refuse cancellation, which this device cannot honour.

        A read blocks for the integration time and cannot be interrupted.

        :raises NotImplementedError: Always.
        """
        raise NotImplementedError('OceanOptics acquisitions cannot be stopped')

    def get_center_wavelength(self) -> float:
        """Refuse a centre wavelength read, as the dispersion is fixed.

        :raises NotImplementedError: Always.
        """
        raise NotImplementedError('OceanOptics has no movable grating')

    def set_center_wavelength(self, value: float):
        """Refuse a centre wavelength move, as the dispersion is fixed.

        :param value: Ignored.
        :raises NotImplementedError: Always.
        """
        raise NotImplementedError('OceanOptics has no movable grating')
