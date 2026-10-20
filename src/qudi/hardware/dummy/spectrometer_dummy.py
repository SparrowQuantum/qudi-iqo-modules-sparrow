# -*- coding: utf-8 -*-
"""
This module contains fake spectrometer.

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

from qudi.interface.spectrometer_interface import SpectrometerInterface

from time import strftime, localtime

import time
import numpy as np


class SpectrometerDummy(SpectrometerInterface):
    """Dummy spectrometer module.

    Shows a silicon vacancy spectrum at liquid helium temperatures.

    Example config for copy-paste:

    spectrometer_dummy:
        module.Class: 'spectrometer.spectrometer_dummy.SpectrometerInterfaceDummy'

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._exposure = 0.5
        self._shutter_open = True
        self._centre_wavelength = 740e-9
        self._stop_requested = False
        self._connected = False

    def on_activate(self):
        """Activate module."""
        pass

    def on_deactivate(self):
        """Deactivate module."""
        self.close_connection()

    def open_connection(self):
        """Open the simulated device, which always succeeds."""
        self._connected = True

    def close_connection(self):
        """Close the simulated device."""
        self._connected = False

    def record_spectrum(self):
        """Record a dummy spectrum.

        :return: (2, 1024) array holding the simulated wavelengths in metres
            and their intensities.
        """
        self.open_connection()
        length = 1024

        # The window follows the centre wavelength, keeping the emitter line
        # at the same offset from it as in the original fixed 730-750 nm span
        centre = self._centre_wavelength * 1e9
        data = np.empty((2, length), dtype=np.double)
        data[0] = np.arange(centre - 10, centre + 10, 20 / length)
        data[1] = np.random.uniform(0, 1000, length)

        if self._shutter_open:
            data[1] = data[1] + 1500 * np.exp(
                -((data[0] - (centre - 3.5)) ** 2) / 0.225**2
            )

        # lorentz, params = self._fitLogic.make_multiplelorentzian_model(no_of_functions=4)
        # sigma = 0.05
        # params.add('l0_amplitude', value=2000)
        # params.add('l0_center', value=736.46)
        # params.add('l0_sigma', value=1.5 * sigma)
        # params.add('l1_amplitude', value=5800)
        # params.add('l1_center', value=736.545)
        # params.add('l1_sigma', value=sigma)
        # params.add('l2_amplitude', value=7500)
        # params.add('l2_center', value=736.923)
        # params.add('l2_sigma', value=sigma)
        # params.add('l3_amplitude', value=1000)
        # params.add('l3_center', value=736.99)
        # params.add('l3_sigma', value=1.5 * sigma)
        # params.add('offset', value=50000.)
        #
        # data[1] += lorentz.eval(x=data[0], params=params)

        data[0] = data[0] * 1e-9  # return to logic in SI units (m)

        # Sleep in slices rather than one block, so stop_acquisition can end
        # the exposure the way it ends one on hardware
        self._stop_requested = False
        remaining = self._exposure
        while remaining > 0 and not self._stop_requested:
            slice_s = min(0.05, remaining)
            time.sleep(slice_s)
            remaining -= slice_s

        return data

    @property
    def exposure_time(self):
        """Get exposure time."""
        return self._exposure

    @exposure_time.setter
    def exposure_time(self, value):
        """Set exposure time."""
        self._exposure = float(value)

    @property
    def shutter_open(self):
        """Get shutter status."""
        return self._shutter_open

    @shutter_open.setter
    def shutter_open(self, value):
        """Set shutter status."""
        self._shutter_open = bool(value)

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
        """End the simulated exposure early."""
        self._stop_requested = True

    def get_wavelength(self):
        """Get the simulated centre wavelength.

        :return: Centre wavelength in metres.
        """
        return self._centre_wavelength

    def set_wavelength(self, value):
        """Set the simulated centre wavelength.

        :param value: Centre wavelength in metres.
        """
        self._centre_wavelength = float(value)
