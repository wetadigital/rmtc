# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
GUIs for Data Augmentation Options
"""

from Qt import QtWidgets

import rmtc.core.ops.process.image.transform as augment_processors
from rmtc.ops import process, assets


class ImageAugmentation(QtWidgets.QWidget):
    """
    UI that manages image data augmentation for training.
    """

    def __init__(self, parent=None):
        super(ImageAugmentation, self).__init__(parent=parent)

        layout = QtWidgets.QFormLayout()
        self._augment_translate = QtWidgets.QCheckBox(parent=self)
        layout.addRow("Translate:", self._augment_translate)
        self._augment_rotate = QtWidgets.QCheckBox(parent=self)
        layout.addRow("Rotate:", self._augment_rotate)
        self._augment_scale = QtWidgets.QCheckBox(parent=self)
        layout.addRow("Scale:", self._augment_scale)
        self._augment_flip = QtWidgets.QCheckBox(parent=self)
        layout.addRow("Flip:", self._augment_flip)
        self._random_seed = QtWidgets.QSpinBox(parent=self)
        max_signed_int_32 = (1 << 31) - 1  # Max seed value
        self._random_seed.setRange(0, max_signed_int_32)
        self._random_seed.setValue(123456)
        layout.addRow("Random Seed:", self._random_seed)

        self.setLayout(layout)

    def get_process(self):
        """
        Get the image augmentation process, or None if no options are selected.
        """
        process_stack = []
        if self._augment_flip.isChecked():
            process_stack.append(
                augment_processors.Flip(
                    probability=(0.1, 0.1),
                ),
            )
        if self._augment_rotate.isChecked():
            process_stack.append(
                augment_processors.Rotate(
                    max_angle=10.0,
                    angle=None,
                ),
            )
        if self._augment_scale.isChecked():
            process_stack.append(
                augment_processors.Scale(
                    scale_min=(0.8, 0.8),
                    scale_max=(1.2, 1.2),
                ),
            )
        if self._augment_translate.isChecked():
            process_stack.append(
                augment_processors.Translate(
                    max_x=0.1,
                    max_y=0.1,
                ),
            )

        return process.ProcessStack(stack=process_stack) if process_stack else None

    def get_random_seed(self):
        """
        Get the seed for deterministic randomization.
        """
        return self._random_seed.value()


# Widget classes for image augmentation according to data type
AUGMENTATION_WIDGETS = {
    assets.Image: ImageAugmentation,
}
