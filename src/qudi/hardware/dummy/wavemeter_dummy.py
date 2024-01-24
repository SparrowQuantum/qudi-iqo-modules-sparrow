# -*- coding: utf-8 -*-

"""
This module provides a dummy wavemeter hardware module that is useful for
troubleshooting logic and gui modules.

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

import random
from PySide2 import QtCore

from qudi.core.configoption import ConfigOption
from qudi.interface.wavemeter_interface import WavemeterInterface, OperationState, WavemeterErrorStatus
from qudi.util.mutex import Mutex


class HardwarePull(QtCore.QObject):
    """ Helper class for running the hardware communication in a separate
    thread.
    """

    def __init__(self, parentclass):
        super().__init__()

        # remember the reference to the parent class to access functions ad settings
        self._parentclass = parentclass

    def handle_timer(self, state_change):
        """ Threaded method that can be called by a signal from outside to start
            the timer.

        @param bool state_change: (True) starts timer, (False) stops it.
        """

        if state_change:
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self._measure_thread)
            self.timer.start(self._parentclass._measurement_timing)
        else:
            if hasattr(self, 'timer'):
                self.timer.stop()

    def _measure_thread(self):
        """ The threaded method querying the data from the wavemeter. """

        range_step = 0.1

        # update as long as the status is busy
        if self._parentclass.module_state() == 'locked':
            # get the current wavelength from the wavemeter
            self._parentclass._current_wavelength += random.uniform(-range_step, range_step)


class WavemeterDummy(WavemeterInterface):
    """ Dummy hardware class to simulate the controls for a wavemeter.

    Example config for copy-paste:

    wavemeter_dummy:
        module.Class: 'dummy.wavemeter_dummy.WavemeterDummy'
        options:
            measurement_timing: 10.0 # in milliseconds

    """
    # config opts
    _measurement_timing = ConfigOption('measurement_timing', 10.)

    sig_handle_timer = QtCore.Signal(bool)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # locking for thread safety
        self.threadlock = Mutex()

        # the current wavelength read by the wavemeter in nm (vac)
        self._current_wavelength = 940.0

        # Current error status. For debug only
        self._error_status = WavemeterErrorStatus.NO_ERRORS

    def on_activate(self):
        """ Activate module.
        """
        # create an indepentent thread for the hardware communication
        self.hardware_thread = QtCore.QThread()

        # create an object for the hardware communication and let it live on the new thread
        self._hardware_pull = HardwarePull(self)
        self._hardware_pull.moveToThread(self.hardware_thread)

        # connect the signals in and out of the threaded object
        self.sig_handle_timer.connect(self._hardware_pull.handle_timer, QtCore.Qt.QueuedConnection)

        # start the event loop for the hardware
        self.hardware_thread.start()

    def on_deactivate(self):
        """ Deactivate module.
        """

        if self.module_state == 'locked':
            self.stop_acquisition()
        self.hardware_thread.quit()
        self.sig_handle_timer.disconnect()

    def start_acquisition(self):
        """
        Method to start the wavemeter software.
        Also the actual threaded method for getting the current wavemeter reading is started.
        """

        # first check its status
        if self.module_state() == 'locked':
            self.log.error('Wavemeter busy')
            return

        self.module_state.lock()
        # actually start the wavemeter
        self.log.info('starting Wavemeter')

        # start the measuring thread
        self.sig_handle_timer.emit(True)

    def stop_acquisition(self):
        """
        Stops the Wavemeter from measuring and kills the thread that queries the data.
        """
        # check status just for a sanity check
        if self.module_state() == 'idle' or self.module_state() == 'deactivated':
            self.log.warning('Wavemeter was already stopped, stopping it '
                    'anyway!')
        else:
            # stop the measurement thread
            self.sig_handle_timer.emit(False)
            # set status to idle again
            self.module_state.unlock()

        # Stop the actual wavemeter measurement
        self.log.info('stopping Wavemeter')

    def get_current_wavelength(self):
        return float(self._current_wavelength) * 1e-9

    def get_current_frequency(self) -> float:
        return 299792458.0 / self.get_current_wavelength()

    def get_timing(self):
        """ Get the timing of the internal measurement thread.

        @return: clock length in second
        """
        return self._measurement_timing

    def set_timing(self, timing):
        """ Set the timing of the internal measurement thread.

        @param float timing: clock length in second
        """
        self._measurement_timing = float(timing)

    def get_operation_state(self) -> OperationState:
        if self.module_state() == 'locked':
            return OperationState.MEASUREMENT
        return OperationState.STOPPED

    def get_error_status(self) -> WavemeterErrorStatus:
        """
        Gets the current error status of the wavemeter

        @return: Wavemeter error status
        """
        return self._error_status
