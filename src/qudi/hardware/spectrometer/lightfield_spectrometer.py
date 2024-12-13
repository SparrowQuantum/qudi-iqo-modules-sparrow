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

    def on_activate(self):
        """Activate module.

        This method needs to set ip the CLR to Python binding and start Lightfield.
        """

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
        self.au = Automation(True, lst)
        self.app = self.au.LightFieldApplication
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

    def on_deactivate(self):
        """Deactivate module."""
        self.app.UserInteractionManager.SuppressUserInteraction = False
        # disconnect event handlers
        self.exp.ExperimentCompleted -= EventHandler(self._set_acquisition_complete)
        self.exp.ImageDataSetReceived -= EventHandler(self._frame_callback)
        self.exp.SettingChanged -= EventHandler(self._setting_changed_callback)

        self.au.Dispose()

        if hasattr(self, "au"):
            del self.au

    def _set_value(self, setting, value):
        if self.exp.Exists(setting):
            self.exp.SetValue(setting, value)

    def _get_value(self, setting):
        if self.exp.Exists(setting):
            return self.exp.GetValue(setting)

    def get_minimum_and_maximum_exposure_time(self) -> dict:
        """Get the minimum and maximum exposure time in seconds"""
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
        return [savedexperiment for savedexperiment in self.exp.GetSavedExperiments()]

    def save_experiment(self, experiment_name: str):
        """Saves experiments configured in Lightfield"""
        self.exp.SaveAs(experiment_name)

    def load_experiment(self, experiment_name: str):
        """Open experiments configured in Lightfield"""
        if self.exp.Exists(experiment_name):
            self.exp.Load(experiment_name)
        else:
            raise ValueError(f"Experiment {experiment_name} not found")

    def _start_acquire(self):
        """Acquire a frame/spectrum"""
        if self.is_running:
            self.stop_aquisition()
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
        if not Path(folder_path).is_dir():
            raise ValueError(f"Folder path {folder_path} is not a directory")
        self._set_value(self.exp_setting.FileNameGenerationDirectory, folder_path)

    def get_file_director(self) -> str:
        """Get the file path and name for storing recorded frame/spectrum"""
        return self._get_value(self.exp_setting.FileNameGenerationDirectory)

    @property
    def number_of_frames(self):
        """Get the number of frames to store"""
        return self._get_value(self.exp_setting.AcquisitionFramesToStore)

    @number_of_frames.setter
    def number_of_frames(self, value: int):
        self._set_value(self.exp_setting.AcquisitionFramesToStore, str(value))

    @property
    def shutter(self) -> str:
        """Get the shutter mode:
        Normal, AlwaysClosed, AlwaysOpen
        """
        shutter_mode = self._get_value(self.cam_setting.ShutterTimingMode).ToString()
        return shutter_mode

    @shutter.setter
    def shutter(self, shutter_mode: str):
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
    def pixels_in_spectrum(self):
        """Length is the number of pixels in the spectrum."""
        return self.exp.SystemColumnCalibration.Length

    @property
    def exposure_time(self) -> float:
        """Get the exposure time in seconds"""

        value_in_milliseconds = self._get_value(
            self.cam_setting.ShutterTimingExposureTime
        )

        return float(value_in_milliseconds / 1e3)

    @exposure_time.setter
    def exposure_time(self, value: float):
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

    def record_spectrum(self) -> np.ndarray:
        """Record a single spectrum and return it as a numpy array (2,N) where N is the number of pixels"""
        self._start_acquire()

        data = np.zeros((2, self.pixels_in_spectrum))
        data[0, :] = self.get_wavelength_array()
        if self.exp.ExperimentCompleted:
            data[1, :] = np.asarray(self.lastframe)

        return data

    def get_wavelength_array(self) -> np.ndarray:
        """Get the wavelength array in meters"""
        wl_list = [
            float(self.exp.SystemColumnCalibration.Get(i)) * 1e-9
            for i in range(0, self.pixels_in_spectrum)
        ]
        return np.asarray(wl_list)

    @property
    def is_running(self):
        return self.exp.IsRunning

    def stop_aquisition(self):
        if self.is_running:
            self.exp.Stop()

        if self.module_state() == "locked":
            self.module_state.unlock()

        return
