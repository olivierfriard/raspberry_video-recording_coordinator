"""
Raspberry Pi coordinator

connections
"""



def connect(self):

    self.picture_resolution_cb.currentIndexChanged.connect(lambda: picture_resolution_changed(self))
    self.picture_brightness_sb.valueChanged.connect(lambda: picture_brightness_changed(self))
    self.picture_contrast_sb.valueChanged.connect(lambda: picture_contrast_changed(self))
    self.picture_sharpness_sb.valueChanged.connect(lambda: picture_sharpness_changed(self))
    self.picture_saturation_sb.valueChanged.connect(lambda: picture_saturation_changed(self))
    self.picture_iso_sb.valueChanged.connect(lambda: picture_iso_changed(self))
    self.picture_rotation_sb.valueChanged.connect(lambda: picture_rotation_changed(self))
    self.picture_hflip_cb.clicked.connect(lambda: picture_hflip_changed(self))
    self.picture_vflip_cb.clicked.connect(lambda: picture_vflip_changed(self))
    self.picture_annotation_cb.clicked.connect(lambda: picture_annotation_changed(self))

    self.time_lapse_cb.clicked.connect(lambda: time_lapse_changed(self))
    self.time_lapse_duration_sb.valueChanged.connect(lambda: time_lapse_duration_changed(self))
    self.time_lapse_wait_sb.valueChanged.connect(lambda: time_lapse_wait_changed(self))

    self.video_brightness_sb.valueChanged.connect(lambda: video_brightness_changed(self))
    self.video_contrast_sb.valueChanged.connect(lambda: video_contrast_changed(self))
    self.video_sharpness_sb.valueChanged.connect(lambda: video_sharpness_changed(self))
    self.video_saturation_sb.valueChanged.connect(lambda: video_saturation_changed(self))
    self.video_iso_sb.valueChanged.connect(lambda: video_iso_changed(self))
    self.video_rotation_sb.valueChanged.connect(lambda: video_rotation_changed(self))
    self.video_hflip_cb.clicked.connect(lambda: video_hflip_changed(self))
    self.video_vflip_cb.clicked.connect(lambda: video_vflip_changed(self))
    self.video_quality_sb.valueChanged.connect(lambda: video_quality_changed(self))
    self.video_fps_sb.valueChanged.connect(lambda: video_fps_changed(self))
    self.video_duration_sb.valueChanged.connect(lambda: video_duration_changed(self))
    self.video_mode_cb.currentIndexChanged.connect(lambda: video_mode_changed(self))


def picture_brightness_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["picture brightness"] = self.picture_brightness_sb.value()


def picture_contrast_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["picture contrast"] = self.picture_contrast_sb.value()


def picture_sharpness_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["picture sharpness"] = self.picture_sharpness_sb.value()


def picture_saturation_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["picture saturation"] = self.picture_saturation_sb.value()


def picture_iso_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["picture iso"] = self.picture_iso_sb.value()


def picture_rotation_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["picture rotation"] = self.picture_rotation_sb.value()


def picture_hflip_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["picture hflip"] = self.picture_hflip_cb.isChecked()


def picture_vflip_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["picture vflip"] = self.picture_vflip_cb.isChecked()


def picture_annotation_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["picture annotation"] = self.picture_annotation_cb.isChecked()


def time_lapse_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["time lapse"] = self.time_lapse_cb.isChecked()


def time_lapse_duration_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["time lapse duration"] = self.time_lapse_duration_sb.value()


def time_lapse_wait_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["time lapse wait"] = self.time_lapse_wait_sb.value()


def picture_resolution_changed(self):
    """
    update picture resolution in raspberry info
    """
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["picture resolution"] = self.picture_resolution_cb.currentText()


def video_brightness_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["video brightness"] = self.video_brightness_sb.value()


def video_contrast_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["video contrast"] = self.video_contrast_sb.value()


def video_sharpness_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["video sharpness"] = self.video_sharpness_sb.value()


def video_saturation_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["video saturation"] = self.video_saturation_sb.value()


def video_iso_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["video iso"] = self.video_iso_sb.value()


def video_rotation_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["video rotation"] = self.video_rotation_sb.value()


def video_hflip_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["video hflip"] = self.video_hflip_cb.isChecked()


def video_vflip_changed(self):
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["video vflip"] = self.video_vflip_cb.isChecked()


def video_quality_changed(self):
    """
    update video quality in raspberry info
    """
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["video quality"] = self.video_quality_sb.value()


def video_fps_changed(self):
    """
    update video FPS in raspberry info
    """
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["FPS"] = self.video_fps_sb.value()


def video_duration_changed(self):
    """
    update video duration in raspberry info
    """
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["video duration"] = self.video_duration_sb.value()


def video_mode_changed(self):
    """
    update video mode in raspberry info
    """
    if self.current_raspberry_id:
        self.raspberry_info[self.current_raspberry_id]["video mode"] = self.video_mode_cb.currentText()


def update_rpi_settings(self, raspberry_id):
    # video settings

    self.video_quality_sb.setValue(self.raspberry_info[raspberry_id]["video quality"])
    self.video_fps_sb.setValue(self.raspberry_info[raspberry_id]["FPS"])
    self.video_duration_sb.setValue(self.raspberry_info[raspberry_id]["video duration"])
    self.video_mode_cb.setCurrentText(self.raspberry_info[raspberry_id]["video mode"])

