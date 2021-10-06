



def connect(self):

    self.picture_resolution_cb.currentIndexChanged.connect(lambda: picture_resolution_changed(self))



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


def picture_resolution_changed(self):
    """
    update picture resolution in raspberry info
    """
    if self.current_raspberry_id:
        self.raspberry_info[
            self.current_raspberry_id]["picture resolution"] = self.picture_resolution_cb.currentText()


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