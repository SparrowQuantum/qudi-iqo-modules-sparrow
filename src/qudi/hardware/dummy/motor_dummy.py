# -*- coding: utf-8 -*-

"""
This file contains the dummy for a motorized stage interface.

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
from dataclasses import dataclass

from qudi.core import ConfigOption

from qudi.interface.motor_interface import MotorInterface


@dataclass
class MotorDummyAxis:
    """Generic dummy motor representing one axis."""

    label: str
    pos: float = 0.0
    vel: float = 0.0
    status: int = 0


class MotorDummy(MotorInterface):
    """This is the dummy class to simulate a motorized stage.

    Example config for copy-paste:

    motor_dummy:
        module.Class: 'dummy.motor_dummy.MotorDummy'
        options:
            # Time to wait after each movement in seconds.
            wait_after_movement: 0.1

    """

    wait_after_movement: float = ConfigOption(default=0.1)

    def on_activate(self):
        self._x_axis = MotorDummyAxis("x")
        self._y_axis = MotorDummyAxis("y")
        self._z_axis = MotorDummyAxis("z")
        self._phi_axis = MotorDummyAxis("phi")

    def on_deactivate(self):
        pass

    def get_constraints(self) -> dict[str, dict[str, float | str | list[str] | None]]:
        axis0 = {
            "label": self._x_axis.label,
            "unit": "m",
            "ramp": ["Sinus", "Linear"],
            "pos_min": 0,
            "pos_max": 100,
            "pos_step": 0.001,
            "vel_min": 0,
            "vel_max": 100,
            "vel_step": 0.01,
            "acc_min": 0.1,
            "acc_max": 0.0,
            "acc_step": 0.0,
        }

        axis1 = {
            "label": self._y_axis.label,
            "unit": "m",
            "ramp": ["Sinus", "Linear"],
            "pos_min": 0,
            "pos_max": 100,
            "pos_step": 0.001,
            "vel_min": 0,
            "vel_max": 100,
            "vel_step": 0.01,
            "acc_min": 0.1,
            "acc_max": 0.0,
            "acc_step": 0.0,
        }

        axis2 = {
            "label": self._z_axis.label,
            "unit": "m",
            "ramp": ["Sinus", "Linear"],
            "pos_min": 0,
            "pos_max": 100,
            "pos_step": 0.001,
            "vel_min": 0,
            "vel_max": 100,
            "vel_step": 0.01,
            "acc_min": 0.1,
            "acc_max": 0.0,
            "acc_step": 0.0,
        }

        axis3 = {
            "label": self._phi_axis.label,
            "unit": "°",
            "ramp": ["Sinus", "Trapez"],
            "pos_min": 0,
            "pos_max": 360,
            "pos_step": 0.1,
            "vel_min": 1,
            "vel_max": 20,
            "vel_step": 0.1,
            "acc_min": None,
            "acc_max": None,
            "acc_step": None,
        }

        return {
            axis0["label"]: axis0,
            axis1["label"]: axis1,
            axis2["label"]: axis2,
            axis3["label"]: axis3,
        }

    def move_rel(self, param_dict: dict[str, float]) -> None:
        curr_pos_dict = self.get_pos()
        constraints = self.get_constraints()

        if param_dict.get(self._x_axis.label) is not None:
            move_x = param_dict[self._x_axis.label]
            curr_pos_x = curr_pos_dict[self._x_axis.label]

            if (curr_pos_x + move_x > constraints[self._x_axis.label]["pos_max"]) or (
                curr_pos_x + move_x < constraints[self._x_axis.label]["pos_min"]
            ):
                self.log.warning(
                    "Cannot make further movement of the axis "
                    '"{0}" with the step {1}, since the border [{2},{3}] '
                    "was reached! Ignore command!".format(
                        self._x_axis.label,
                        move_x,
                        constraints[self._x_axis.label]["pos_min"],
                        constraints[self._x_axis.label]["pos_max"],
                    )
                )
            else:
                self._make_wait_after_movement()
                self._x_axis.pos = self._x_axis.pos + move_x

        if param_dict.get(self._y_axis.label) is not None:
            move_y = param_dict[self._y_axis.label]
            curr_pos_y = curr_pos_dict[self._y_axis.label]

            if (curr_pos_y + move_y > constraints[self._y_axis.label]["pos_max"]) or (
                curr_pos_y + move_y < constraints[self._y_axis.label]["pos_min"]
            ):
                self.log.warning(
                    "Cannot make further movement of the axis "
                    '"{0}" with the step {1}, since the border [{2},{3}] '
                    "was reached! Ignore command!".format(
                        self._y_axis.label,
                        move_y,
                        constraints[self._y_axis.label]["pos_min"],
                        constraints[self._y_axis.label]["pos_max"],
                    )
                )
            else:
                self._make_wait_after_movement()
                self._y_axis.pos = self._y_axis.pos + move_y

        if param_dict.get(self._z_axis.label) is not None:
            move_z = param_dict[self._z_axis.label]
            curr_pos_z = curr_pos_dict[self._z_axis.label]

            if (curr_pos_z + move_z > constraints[self._z_axis.label]["pos_max"]) or (
                curr_pos_z + move_z < constraints[self._z_axis.label]["pos_min"]
            ):
                self.log.warning(
                    "Cannot make further movement of the axis "
                    '"{0}" with the step {1}, since the border [{2},{3}] '
                    "was reached! Ignore command!".format(
                        self._z_axis.label,
                        move_z,
                        constraints[self._z_axis.label]["pos_min"],
                        constraints[self._z_axis.label]["pos_max"],
                    )
                )
            else:
                self._make_wait_after_movement()
                self._z_axis.pos = self._z_axis.pos + move_z

        if param_dict.get(self._phi_axis.label) is not None:
            move_phi = param_dict[self._phi_axis.label]
            curr_pos_phi = curr_pos_dict[self._phi_axis.label]

            if (
                curr_pos_phi + move_phi > constraints[self._phi_axis.label]["pos_max"]
            ) or (
                curr_pos_phi + move_phi < constraints[self._phi_axis.label]["pos_min"]
            ):
                self.log.warning(
                    "Cannot make further movement of the axis "
                    '"{0}" with the step {1}, since the border [{2},{3}] '
                    "was reached! Ignore command!".format(
                        self._phi_axis.label,
                        move_phi,
                        constraints[self._phi_axis.label]["pos_min"],
                        constraints[self._phi_axis.label]["pos_max"],
                    )
                )
            else:
                self._make_wait_after_movement()
                self._phi_axis.pos = self._phi_axis.pos + move_phi

    def move_abs(self, param_dict: dict[str, float]) -> None:
        constraints = self.get_constraints()

        if param_dict.get(self._x_axis.label) is not None:
            desired_pos = param_dict[self._x_axis.label]
            constr = constraints[self._x_axis.label]

            if not (constr["pos_min"] <= desired_pos <= constr["pos_max"]):
                self.log.warning(
                    "Cannot make absolute movement of the axis "
                    '"{0}" to possition {1}, since it exceeds the limits '
                    "[{2},{3}] ! Command is ignored!".format(
                        self._x_axis.label,
                        desired_pos,
                        constr["pos_min"],
                        constr["pos_max"],
                    )
                )
            else:
                self._make_wait_after_movement()
                self._x_axis.pos = desired_pos

        if param_dict.get(self._y_axis.label) is not None:
            desired_pos = param_dict[self._y_axis.label]
            constr = constraints[self._y_axis.label]

            if not (constr["pos_min"] <= desired_pos <= constr["pos_max"]):
                self.log.warning(
                    "Cannot make absolute movement of the axis "
                    '"{0}" to possition {1}, since it exceeds the limits '
                    "[{2},{3}] ! Command is ignored!".format(
                        self._y_axis.label,
                        desired_pos,
                        constr["pos_min"],
                        constr["pos_max"],
                    )
                )
            else:
                self._make_wait_after_movement()
                self._y_axis.pos = desired_pos

        if param_dict.get(self._z_axis.label) is not None:
            desired_pos = param_dict[self._z_axis.label]
            constr = constraints[self._z_axis.label]

            if not (constr["pos_min"] <= desired_pos <= constr["pos_max"]):
                self.log.warning(
                    "Cannot make absolute movement of the axis "
                    '"{0}" to possition {1}, since it exceeds the limits '
                    "[{2},{3}] ! Command is ignored!".format(
                        self._z_axis.label,
                        desired_pos,
                        constr["pos_min"],
                        constr["pos_max"],
                    )
                )
            else:
                self._make_wait_after_movement()
                self._z_axis.pos = desired_pos

        if param_dict.get(self._phi_axis.label) is not None:
            desired_pos = param_dict[self._phi_axis.label]
            constr = constraints[self._phi_axis.label]

            if not (constr["pos_min"] <= desired_pos <= constr["pos_max"]):
                self.log.warning(
                    "Cannot make absolute movement of the axis "
                    '"{0}" to possition {1}, since it exceeds the limits '
                    "[{2},{3}] ! Command is ignored!".format(
                        self._phi_axis.label,
                        desired_pos,
                        constr["pos_min"],
                        constr["pos_max"],
                    )
                )
            else:
                self._make_wait_after_movement()
                self._phi_axis.pos = desired_pos

    def abort(self) -> None:
        self.log.info("MotorDummy: Movement stopped!")

    def get_pos(self, param_list: list[str] | None = None) -> dict[str, float]:
        pos = {}
        if param_list is not None:
            if self._x_axis.label in param_list:
                pos[self._x_axis.label] = self._x_axis.pos

            if self._y_axis.label in param_list:
                pos[self._y_axis.label] = self._y_axis.pos

            if self._z_axis.label in param_list:
                pos[self._z_axis.label] = self._z_axis.pos

            if self._phi_axis.label in param_list:
                pos[self._phi_axis.label] = self._phi_axis.pos

        else:
            pos[self._x_axis.label] = self._x_axis.pos
            pos[self._y_axis.label] = self._y_axis.pos
            pos[self._z_axis.label] = self._z_axis.pos
            pos[self._phi_axis.label] = self._phi_axis.pos

        return pos

    def get_status(self, param_list: list[str] | None = None) -> dict[str, int]:
        status = {}
        if param_list is not None:
            if self._x_axis.label in param_list:
                status[self._x_axis.label] = self._x_axis.status

            if self._y_axis.label in param_list:
                status[self._y_axis.label] = self._y_axis.status

            if self._z_axis.label in param_list:
                status[self._z_axis.label] = self._z_axis.status

            if self._phi_axis.label in param_list:
                status[self._phi_axis.label] = self._phi_axis.status

        else:
            status[self._x_axis.label] = self._x_axis.status
            status[self._y_axis.label] = self._y_axis.status
            status[self._z_axis.label] = self._z_axis.status
            status[self._phi_axis.label] = self._phi_axis.status

        return status

    def calibrate(self, param_list: list[str] | None = None) -> None:
        if param_list is not None:
            if self._x_axis.label in param_list:
                self._x_axis.pos = 0.0

            if self._y_axis.label in param_list:
                self._y_axis.pos = 0.0

            if self._z_axis.label in param_list:
                self._z_axis.pos = 0.0

            if self._phi_axis.label in param_list:
                self._phi_axis.pos = 0.0

        else:
            self._x_axis.pos = 0.0
            self._y_axis.pos = 0.0
            self._z_axis.pos = 0.0
            self._phi_axis.pos = 0.0

    def get_velocity(self, param_list: list[str] | None = None) -> dict[str, float]:
        vel = {}
        if param_list is not None:
            if self._x_axis.label in param_list:
                vel[self._x_axis.label] = self._x_axis.vel
            if self._y_axis.label in param_list:
                vel[self._y_axis.label] = self._y_axis.vel
            if self._z_axis.label in param_list:
                vel[self._z_axis.label] = self._z_axis.vel
            if self._phi_axis.label in param_list:
                vel[self._phi_axis.label] = self._phi_axis.vel

        else:
            vel[self._x_axis.label] = self._x_axis.vel
            vel[self._y_axis.label] = self._y_axis.vel
            vel[self._z_axis.label] = self._z_axis.vel
            vel[self._phi_axis.label] = self._phi_axis.vel

        return vel

    def set_velocity(self, param_dict: dict[str, float]) -> None:
        constraints = self.get_constraints()

        if param_dict.get(self._x_axis.label) is not None:
            desired_vel = param_dict[self._x_axis.label]
            constr = constraints[self._x_axis.label]

            if not (constr["vel_min"] <= desired_vel <= constr["vel_max"]):
                self.log.warning(
                    "Cannot set velocity of the axis "
                    '"{0}" to possition {1}, since it exceeds the limits '
                    "[{2},{3}] ! Command is ignored!".format(
                        self._x_axis.label,
                        desired_vel,
                        constr["vel_min"],
                        constr["vel_max"],
                    )
                )
            else:
                self._x_axis.vel = desired_vel

        if param_dict.get(self._y_axis.label) is not None:
            desired_vel = param_dict[self._y_axis.label]
            constr = constraints[self._y_axis.label]

            if not (constr["vel_min"] <= desired_vel <= constr["vel_max"]):
                self.log.warning(
                    "Cannot set velocity of the axis "
                    '"{0}" to possition {1}, since it exceeds the limits '
                    "[{2},{3}] ! Command is ignored!".format(
                        self._y_axis.label,
                        desired_vel,
                        constr["vel_min"],
                        constr["vel_max"],
                    )
                )
            else:
                self._y_axis.vel = desired_vel

        if param_dict.get(self._z_axis.label) is not None:
            desired_vel = param_dict[self._z_axis.label]
            constr = constraints[self._z_axis.label]

            if not (constr["vel_min"] <= desired_vel <= constr["vel_max"]):
                self.log.warning(
                    "Cannot set velocity of the axis "
                    '"{0}" to possition {1}, since it exceeds the limits '
                    "[{2},{3}] ! Command is ignored!".format(
                        self._z_axis.label,
                        desired_vel,
                        constr["vel_min"],
                        constr["vel_max"],
                    )
                )
            else:
                self._z_axis.vel = desired_vel

        if param_dict.get(self._phi_axis.label) is not None:
            desired_vel = param_dict[self._phi_axis.label]
            constr = constraints[self._phi_axis.label]

            if not (constr["vel_min"] <= desired_vel <= constr["vel_max"]):
                self.log.warning(
                    "Cannot set velocity of the axis "
                    '"{0}" to possition {1}, since it exceeds the limits '
                    "[{2},{3}] ! Command is ignored!".format(
                        self._phi_axis.label,
                        desired_vel,
                        constr["pos_min"],
                        constr["pos_max"],
                    )
                )
            else:
                self._phi_axis.vel = desired_vel

    def _make_wait_after_movement(self):
        """Define a time which the dummy should wait after each movement."""
        time.sleep(self.wait_after_movement)
