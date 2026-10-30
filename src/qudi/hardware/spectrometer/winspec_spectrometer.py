# -*- coding: utf-8 -*-

"""
Acquire a spectrum using Winspec through the COM interface.
This program gets the data from WinSpec, saves them and
gets the data for plotting.

Copyright (c) 2021, the qudi developers. See the AUTHORS.md file at the top-level directory of this
distribution and on <https://github.com/Ulm-IQO/qudi-iqo-modules/>

This file is part of qudi-iqo-modules.

Qudi is free software: you can redistribute it and/or modify it under the terms of
the GNU Lesser General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

Qudi is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License along with qudi.
If not, see <https://www.gnu.org/licenses/>.
"""

from qudi.core.statusvariable import StatusVar
from qudi.interface.spectrometer_interface import (
    SpectrometerAcquisitionError,
    SpectrometerCommunicationError,
    SpectrometerConstraints,
    SpectrometerInterface,
    SpectrometerUnsupportedFeatureError,
    Spectrum,
)
import math
import numpy as np
import comtypes.client as ctc
import win32com.client as w32c
from ctypes import c_float
import time

import datetime

ctc.GetModule(('{1A762221-D8BA-11CF-AFC2-508201C10000}', 3, 11))
import comtypes.gen.WINX32Lib as WinSpecLib


class WinSpec32(SpectrometerInterface):
    """Hardware module for reading spectra from the WinSpec32 spectrometer software.

    Example config for copy-paste:

    spectrometer_dummy:
        module.Class: 'spectrometer.winspec_spectrometer.WinSpec32'

    """

    time_units = {
        1: {'name': 'us', 'factor': 1e-6},
        2: {'name': 'ms', 'factor': 1e-3},
        3: {'name': 's', 'factor': 1.},
        4: {'name': 'min', 'factor': 60}
    }

    _exposure_time = StatusVar(name='exposure_time', default=0.1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._status = 0
        self._connected = False

        self.query_time = 0.01

    def on_activate(self):
        """Activate module. COM is initialised on first use."""
        pass

    def on_deactivate(self):
        """Deactivate module."""
        self.close_connection()

    def open_connection(self):
        """Dispatch WinSpec32 once, so a missing or broken install surfaces here.

        WinSpec32 is an out-of-process COM server, so dispatching it launches
        the application when it is not running; this does not test whether it
        already was. Calling this when WinSpec32 has already answered does
        nothing. Each method sets COM up again on its own thread, as Windows
        requires, so this only records that the module has reached WinSpec32
        at least once.

        :raises SpectrometerCommunicationError: If WinSpec32 cannot be dispatched.
        """
        if self._connected:
            return
        try:
            w32c.pythoncom.CoInitialize()
            w32c.Dispatch("WinX32.ExpSetup")
        except w32c.pythoncom.com_error as exc:
            raise SpectrometerCommunicationError('Failed to reach WinSpec32') from exc
        self._connected = True

    @property
    def constraints(self):
        """Fixed limits; WinSpec32 does not report an exposure range."""
        return SpectrometerConstraints(
            value_unit='counts',
            exposure_time_range=(1e-6, math.inf),
            center_wavelength_range=None,
            has_shutter=False,
            can_stop_acquisition=False,
            has_hardware_background=False,
        )

    def close_connection(self):
        """Forget the COM connection."""
        self._connected = False

    def check_status(self, method='unknown'):
        if self.status:
            raise SpectrometerCommunicationError(f'WinSpec32 returned status during {method}: {self.status}')

    @property
    def experiment_running(self):
        if not self._connected:
            return False
        w32c.pythoncom.CoInitialize()
        experiment_instance = w32c.Dispatch("WinX32.ExpSetup")
        result, self._status = experiment_instance.GetParam(WinSpecLib.EXP_RUNNING)
        self.check_status('experiment_running')
        return result

    @property
    def status(self):
        return self._status

    @property
    def exposure_time(self):
        """Get the exposure time in seconds.

        Before WinSpec32 has answered this returns the last known value, so
        reading it never dispatches WinSpec32.
        """
        if not self._connected:
            return self._exposure_time
        w32c.pythoncom.CoInitialize()
        experiment_instance = w32c.Dispatch("WinX32.ExpSetup")
        exposure_time, self._status = experiment_instance.GetParam(WinSpecLib.EXP_EXPOSURETIME)
        self.check_status('exposure_time')
        units, self._status = experiment_instance.GetParam(WinSpecLib.EXP_EXPOSURETIME_UNITS)
        self.check_status('exposure_time units')
        exposure_time *= self.time_units[units]['factor']
        self._exposure_time = exposure_time
        return exposure_time

    @exposure_time.setter
    def exposure_time(self, value):
        assert isinstance(value, (float, int)), f'exposure_time needs to be float, but was {value}'
        low, high = self.constraints.exposure_time_range
        if not low <= value <= high:
            raise ValueError(f'Exposure time {value} s outside [{low}, {high}] s')
        self.open_connection()
        w32c.pythoncom.CoInitialize()
        experiment_instance = w32c.Dispatch("WinX32.ExpSetup")
        value = abs(float(value))
        if value < 1e-3:
            unit = 1
            value *= 1e6
        elif value < 1:
            unit = 2
            value *= 1e3
        else:
            unit = 3

        self._status = experiment_instance.SetParam(WinSpecLib.EXP_EXPOSURETIME_UNITS, unit)
        self.check_status(f'exposure_time setting unit to {unit} ({self.time_units[unit]["name"]})')

        self._status = experiment_instance.SetParam(WinSpecLib.EXP_EXPOSURETIME, value)
        self.check_status(f'exposure_time setting to {value}')
        self._exposure_time = value * self.time_units[unit]['factor']

    @property
    def shutter_open(self) -> bool:
        """Report the shutter state, which WinSpec32 owns.

        :return: Always True, as this module never closes it.
        """
        return True

    @shutter_open.setter
    def shutter_open(self, value):
        """Refuse the request, as WinSpec32 owns the shutter.

        :raises SpectrometerUnsupportedFeatureError: Always.
        """
        raise SpectrometerUnsupportedFeatureError('WinSpec32 owns the shutter')

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
        """Refuse cancellation, which is driven from WinSpec32.

        :raises SpectrometerUnsupportedFeatureError: Always.
        """
        raise SpectrometerUnsupportedFeatureError('acquisitions are stopped in WinSpec32')

    def get_center_wavelength(self) -> float:
        """Refuse a centre wavelength read, as WinSpec32 owns the grating.

        :raises SpectrometerUnsupportedFeatureError: Always.
        """
        raise SpectrometerUnsupportedFeatureError('WinSpec32 owns the grating position')

    def set_center_wavelength(self, value: float):
        """Refuse a centre wavelength move, as WinSpec32 owns the grating.

        :param value: Ignored.
        :raises SpectrometerUnsupportedFeatureError: Always.
        """
        raise SpectrometerUnsupportedFeatureError('WinSpec32 owns the grating position')

    def record_spectrum(self):
        """Record a spectrum from the WinSpec32 software.

        :return: Wavelengths in metres and their intensities in counts.
        :raises SpectrometerAcquisitionError: If WinSpec32 will not start the
            acquisition or uses an unsupported wavelength calibration.
        """
        self.open_connection()
        w32c.pythoncom.CoInitialize()
        # get some data structures from COM that we need later
        current_spectrum = w32c.Dispatch("WinX32.DocFile")
        spectrum_library_instance = w32c.Dispatch("WinX32.DocFiles")
        experiment_instance = w32c.Dispatch("WinX32.ExpSetup")

        # Close all documents so we do not get any errors or prompts to save the currently opened spectrum in WinSpec32
        spectrum_library_instance.CloseAll()

        if not experiment_instance.Start(current_spectrum)[0]:
            raise SpectrometerAcquisitionError('WinSpec32 could not start the acquisition')

        # Wait for acquisition to finish (and check for errors continually)
        # If we didn't care about errors, we could just run WinspecExpt.WaitForExperiment()
        while self.experiment_running and self.status == 0:
            time.sleep(self.query_time)

        """
            Pass a pointer to Winspec so it can put the spectrum in a place in
            memory where python will be able to find it.
        """

        datapointer = c_float()
        raw_spectrum = current_spectrum.GetFrame(1, datapointer)
        # winspec uses 16 bit unsigned int. Make sure to consider that while converting to numpy arrays
        values = np.array(raw_spectrum, dtype=np.uint16).flatten().astype(np.double)
        calibration = current_spectrum.GetCalibration()

        if calibration.Order != 2:
            raise SpectrometerAcquisitionError('Cannot handle current WinSpec wavelength calibration.')
        """
            WinSpec doesn't actually store the wavelength information as an array but
            instead calculates it every time you plot using the calibration information
            stored with the spectrum.
        """
        p = np.array([
            calibration.PolyCoeffs(2),
            calibration.PolyCoeffs(1),
            calibration.PolyCoeffs(0)
        ])
        wavelength_m = np.polyval(p, range(1, 1 + len(values))) * 1e-9  # Send to logic in SI units (m)
        return Spectrum(wavelength_m, values)

    def save_spectrum(self, path, postfix=''):
        """Save a spectrum from the WinSpec32 software.

        :param path: Path to save the original spectrum to.
        :param postfix: Suffix appended to the file name.
        """
        self.open_connection()
        w32c.pythoncom.CoInitialize()
        current_spectrum = w32c.Dispatch("WinX32.DocFile")

        savetime = datetime.datetime.now()
        timestr = savetime.strftime("%Y%m%d-%H%M-%S-%f_")
        current_spectrum.SetParam(
            WinSpecLib.DM_FILENAME,
            str(path) + timestr + str(postfix) + ".spe"
        )
        file_name, self._status = current_spectrum.GetParam(WinSpecLib.DM_FILENAME)
        self.check_status('save_spectrum set filename')
        self.log.debug(file_name)
        current_spectrum.Save()
