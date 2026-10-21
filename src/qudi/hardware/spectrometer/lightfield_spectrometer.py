# -*- coding: utf-8 -*-

"""
This is a module for using a spectrometer through the Princeton Instruments
Lightfield software.

This module is still unusable and fucking broken and very probably
just crashes Lightfield.

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
import time

import numpy as np

from qudi.core.statusvariable import StatusVar
from qudi.interface.spectrometer_interface import SpectrometerInterface

import os, glob, string
import sys
from enum import Enum
from pathlib import Path

# .Net imports
import clr
import System
from System import EventHandler, EventArgs
import System.Collections.Generic as col
from System.Threading import AutoResetEvent


class LFImageMode(Enum):
    """Spectrometer imaging mode."""

    LFImageModeNormal = 1
    LFImageModePreview = 2
    LFImageModeBackground = 3


class ShutterTimingMode(Enum):
    Normal = 1
    AlwaysClosed = 2
    AlwaysOpen = 3


class Lightfield(SpectrometerInterface):
    """Control Princeton Instruments Lightfield from Qudi.

    This hardware module needs a brave soul fluent in C# and Python,
    as it can only do one thing right now: crash Lightfield.

    Example config for copy-paste:

    lightfield_spectrometer:
        module.Class: 'spectrometer.lightfield_spectrometer.Lightfield'

    """

    _exposure_time = StatusVar(name="exposure_time", default=0.1)

    def on_activate(self):
        """Activate module. LightField is started on first use."""
        self._lightfield_automation = None

    def on_deactivate(self):
        """Deactivate module."""
        self.close_connection()

    def open_connection(self):
        """Set up the CLR to Python binding and start LightField.

        Calling this when LightField is already running does nothing. Every
        method that talks to it calls this first, so the first request starts
        it. Loading the module deliberately does not, since starting LightField
        is slow and fails outright when LIGHTFIELD_ROOT is unset or the
        application refuses to launch.

        :raises IOError: If LightField cannot be started.
        """
        if self._lightfield_automation is not None:
            return
        try:
            self._launch_lightfield()
        except Exception as exc:
            self.close_connection()
            raise IOError("Failed to start LightField") from exc

    def _launch_lightfield(self):
        lfpath = os.environ["LIGHTFIELD_ROOT"]
        lfaddinpath = os.path.join(os.environ["LIGHTFIELD_ROOT"], "AddInViews")

        sys.path.append(lfpath)
        sys.path.append(lfaddinpath)
        ref1 = clr.AddReference("PrincetonInstruments.LightFieldViewV4")
        ref2 = clr.AddReference("PrincetonInstruments.LightField.AutomationV4")
        ref3 = clr.AddReference("PrincetonInstruments.LightFieldAddInSupportServices")

        try:
            for i in ref2.DefinedTypes:
                print("ASS Defined type:", i)
        except System.Reflection.ReflectionTypeLoadException as e:
            for i in e.LoaderExceptions:
                print("EXC:", i.Message)

        print("ASS Entry point:", ref2.EntryPoint)
        print("ASS is Dynamic:", ref2.IsDynamic)

        from PrincetonInstruments.LightField.Automation import Automation
        from PrincetonInstruments.LightField.AddIns import (
            CameraSettings,
            ExperimentSettings,
            SpectrometerSettings,
        )

        # import PrincetonInstruments.LightField.AddIns as ai

        lst = col.List[System.String]()
        self._lightfield_automation = Automation(True, lst)
        self.app = self._lightfield_automation.LightFieldApplication
        self.exp = self.app.Experiment
        self.cam_setting = CameraSettings
        self.spec_setting = SpectrometerSettings
        self.exp_setting = ExperimentSettings
        self.file_manager = self.app.FileManager
        self.acquireCompleted = AutoResetEvent(False)

        self.exposure_time_limits = self.get_minimum_and_maximum_exposure_time()

        self.exp.ExperimentCompleted += EventHandler(self._set_acquisition_complete)
        self.exp.ImageDataSetReceived += EventHandler(self._frame_callback)
        self.exp.SettingChanged += EventHandler(self._setting_changed_callback)

        self.app.UserInteractionManager.SuppressUserInteraction = True

        self.prevExperimentName = self.exp.Name

        self.lastframe = list()

    def close_connection(self):
        """Shut LightField down, logging anything that goes wrong."""
        if self._lightfield_automation is None:
            return
        try:
            self.app.UserInteractionManager.SuppressUserInteraction = False
            # disconnect event handlers
            self.exp.ExperimentCompleted -= EventHandler(self._set_acquisition_complete)
            self.exp.ImageDataSetReceived -= EventHandler(self._frame_callback)
            self.exp.SettingChanged -= EventHandler(self._setting_changed_callback)
        except Exception:
            self.log.exception("Failed to disconnect LightField event handlers")
        finally:
            try:
                self._lightfield_automation.Dispose()
            except Exception:
                self.log.exception("Failed to shut LightField down")
            finally:
                self._lightfield_automation = None

    def _set_value(self, setting, value):
        self.open_connection()
        if self.exp.Exists(setting):
            self.exp.SetValue(setting, value)

    def _get_value(self, setting):
        self.open_connection()
        if self.exp.Exists(setting):
            return self.exp.GetValue(setting)

    def get_minimum_and_maximum_exposure_time(self) -> dict:
        """Get the minimum and maximum exposure time in seconds"""
        self.open_connection()
        min = self.exp.GetMaximumRange(
            self.cam_setting.ShutterTimingExposureTime
        ).Minimum
        max = self.exp.GetMaximumRange(
            self.cam_setting.ShutterTimingExposureTime
        ).Maximum
        return dict(min=min, max=max)

    # Callbacks
    def _setting_changed_callback(self, sender, args):
        """Lightfieldsettings changed."""
        # TODO: This should can be used to update the GUI
        pass

    def _frame_callback(self, sender, args):
        """A frame/spectrum was recorded."""
        # TODO: This should be cleaned up

        dataSet = args.ImageDataSet
        frame = dataSet.GetFrame(0, 0)
        arr = frame.GetData()
        dims = [frame.Width, frame.Height]

        self.lastframe = list(arr)

    def _set_acquisition_complete(self, sender, args):
        """A frame/spectrum was recorded."""
        self.acquireCompleted.Set()
        self.module_state.unlock()

    def get_experiment_list(self):
        """Get experiments configured in Lightfield"""
        self.open_connection()
        return [savedexperiment for savedexperiment in self.exp.GetSavedExperiments()]

    def save_experiment(self, experiment_name: str):
        """Saves experiments configured in Lightfield"""
        self.open_connection()
        self.exp.SaveAs(experiment_name)

    def load_experiment(self, experiment_name: str):
        """Open experiments configured in Lightfield"""
        self.open_connection()
        if self.exp.Exists(experiment_name):
            self.exp.Load(experiment_name)
        else:
            raise ValueError(f"Experiment {experiment_name} not found")

    def _start_acquire(self):
        """Acquire a frame/spectrum"""
        if self.is_running:
            self.stop_acquisition()
            time.sleep(0.2)

        if self.module_state() == "locked":
            self.log.warning("Unable to start a acquisition. It is already running.")
        else:
            self.calibration = self.exp.SystemColumnCalibration
            self.calerrors = self.exp.SystemColumnCalibrationErrors
            self.intcal = self.exp.SystemIntensityCalibration
            if self.exp.IsReadyToRun:
                self.module_state.lock()
                self.exp.Acquire()
                # Wait for acquisition to complete
                self.acquireCompleted.WaitOne()

    # write a function that save folder path and file name
    def set_file_directory(self, folder_path: str, file_name: str):
        """Set the file path and name for storing recorded frame/spectrum"""
        self.open_connection()
        if not Path(folder_path).is_dir():
            raise ValueError(f"Folder path {folder_path} is not a directory")
        self._set_value(self.exp_setting.FileNameGenerationDirectory, folder_path)

    def get_file_director(self) -> str:
        """Get the file path and name for storing recorded frame/spectrum"""
        self.open_connection()
        return self._get_value(self.exp_setting.FileNameGenerationDirectory)

    @property
    def number_of_frames(self):
        """Get the number of frames to store"""
        self.open_connection()
        return self._get_value(self.exp_setting.AcquisitionFramesToStore)

    @number_of_frames.setter
    def number_of_frames(self, value: int):
        self.open_connection()
        self._set_value(self.exp_setting.AcquisitionFramesToStore, str(value))

    @property
    def shutter(self) -> str:
        """Get the shutter mode:
        Normal, AlwaysClosed, AlwaysOpen
        """
        self.open_connection()
        shutter_mode = self._get_value(self.cam_setting.ShutterTimingMode).ToString()
        return shutter_mode

    @shutter.setter
    def shutter(self, shutter_mode: str):
        self.open_connection()
        if shutter_mode not in ShutterTimingMode.__members__:
            raise ValueError()
        else:
            self._set_value(self.cam_setting.ShutterTimingMode, shutter_mode)

    @property
    def shutter_open(self) -> bool:
        if self.shutter == "AlwaysOpen" or self.shutter == "Normal":
            return True
        else:
            return False

    @shutter_open.setter
    def shutter_open(self, value: bool):
        if value:
            self.shutter = str(ShutterTimingMode.AlwaysOpen.name)
        else:
            self.shutter = str(ShutterTimingMode.AlwaysClosed.name)

    @property
    def background_correction(self) -> bool:
        return False

    @background_correction.setter
    def background_correction(self, value: bool):
        pass

    def acquire_background(self) -> bool:
        return False

    @property
    def pixels_in_spectrum(self):
        """Length is the number of pixels in the spectrum."""
        self.open_connection()
        return self.exp.SystemColumnCalibration.Length

    @property
    def exposure_time(self) -> float:
        """Get the exposure time in seconds.

        Before LightField is started this returns the last known value, so
        reading it never launches LightField.
        """
        if self._lightfield_automation is None:
            return self._exposure_time

        value_in_milliseconds = self._get_value(
            self.cam_setting.ShutterTimingExposureTime
        )

        self._exposure_time = float(value_in_milliseconds / 1e3)
        return self._exposure_time

    @exposure_time.setter
    def exposure_time(self, value: float):
        self.open_connection()
        if (
            value < self.exposure_time_limits["min"]
            or value > self.exposure_time_limits["max"]
        ):
            raise ValueError(
                f"Exposure time {value} not in range [{self.exposure_time_limits['min']}, {self.exposure_time_limits['max']}]"
            )

        value_in_milliseconds = value * 1e3

        self._set_value(
            self.cam_setting.ShutterTimingExposureTime, value_in_milliseconds
        )
        self._exposure_time = float(value)

    def record_spectrum(self) -> np.ndarray:
        """Record a single spectrum and return it as a numpy array (2,N) where N is the number of pixels"""
        self.open_connection()
        self._start_acquire()

        data = np.zeros((2, self.pixels_in_spectrum))
        data[0, :] = self.get_wavelength_array()
        if self.exp.ExperimentCompleted:
            data[1, :] = np.asarray(self.lastframe)

        return data

    def get_wavelength_array(self) -> np.ndarray:
        """Get the wavelength array in meters"""
        self.open_connection()
        wl_list = [
            float(self.exp.SystemColumnCalibration.Get(i)) * 1e-9
            for i in range(0, self.pixels_in_spectrum)
        ]
        return np.asarray(wl_list)

    def get_center_wavelength(self) -> float:
        """Refuse a centre wavelength read, as LightField owns the grating.

        :raises NotImplementedError: Always.
        """
        raise NotImplementedError("LightField owns the grating position")

    def set_center_wavelength(self, value: float):
        """Refuse a centre wavelength move, as LightField owns the grating.

        :param value: Ignored.
        :raises NotImplementedError: Always.
        """
        raise NotImplementedError("LightField owns the grating position")

    @property
    def is_running(self):
        return self._lightfield_automation is not None and self.exp.IsRunning

    def stop_acquisition(self):
        if self._lightfield_automation is None:
            return
        if self.is_running:
            self.exp.Stop()

        if self.module_state() == "locked":
            self.module_state.unlock()

        return
