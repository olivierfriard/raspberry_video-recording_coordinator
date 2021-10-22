"""
Raspberry Pi coordinator

connections
"""
from PyQt5.QtWidgets import (QSpinBox, QCheckBox, QComboBox)
import pprint


def get_widgets_list(self):

    return [
            self.video_mode_cb,
            self.video_duration_sb,
            self.video_quality_sb,
            self.video_fps_sb,
            self.video_rotation_sb,
            self.video_hflip_cb,
            self.video_vflip_cb,
            self.video_brightness_sb,
            self.video_contrast_sb,
            self.video_sharpness_sb,
            self.video_saturation_sb,
            self.video_iso_sb,
            self.picture_resolution_cb,
            self.picture_rotation_sb,
            self.picture_hflip_cb,
            self.picture_vflip_cb,
            self.picture_brightness_sb,
            self.picture_contrast_sb,
            self.picture_sharpness_sb,
            self.picture_saturation_sb,
            self.picture_iso_sb,
            self.picture_annotation_cb,
            self.time_lapse_wait_sb,
            self.time_lapse_duration_sb,
            ]



def connect(self):

    for w in get_widgets_list(self):
        if w.accessibleName():
            if isinstance(w, QComboBox):
                w.currentIndexChanged.connect(lambda: widget_value_changed(self))
            elif isinstance(w, QSpinBox):
                w.valueChanged.connect(lambda: widget_value_changed(self))
            elif isinstance(w, QCheckBox):
                w.clicked.connect(lambda: widget_value_changed(self))
            else:
                raise
        else:
            raise        

def widget_value_changed(self):
    """
    update raspberry_info dictionary when widget value changed
    """

    if self.current_raspberry_id:
        if isinstance(self.sender(), QComboBox):
            self.raspberry_info[self.current_raspberry_id][self.sender().accessibleName()] = self.sender().currentText()
        if isinstance(self.sender(), QSpinBox):
            self.raspberry_info[self.current_raspberry_id][self.sender().accessibleName()] = self.sender().value()
        if isinstance(self.sender(), QCheckBox):
            self.raspberry_info[self.current_raspberry_id][self.sender().accessibleName()] = self.sender().isChecked()

        # pprint.pprint(self.raspberry_info[self.current_raspberry_id])



def update_rpi_settings(self, raspberry_id):
    """
    update widget values with raspberry_info values
    """

    for w in get_widgets_list(self):
        if w.accessibleName():
            if isinstance(w, QComboBox):
                w.setCurrentText(self.raspberry_info[raspberry_id][w.accessibleName()])
            elif isinstance(w, QSpinBox):
                w.setValue(self.raspberry_info[raspberry_id][w.accessibleName()])
            elif isinstance(w, QCheckBox):
                w.setChecked(self.raspberry_info[raspberry_id][w.accessibleName()])
            else:
                raise
        else:
            raise
