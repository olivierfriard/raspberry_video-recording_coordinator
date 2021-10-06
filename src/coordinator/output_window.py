"""
Raspberry Pi coordinator

"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy, QPlainTextEdit, QSpacerItem,
                             QMessageBox, QFileDialog,
                             )


class ResultsWidget(QWidget):
    """
    widget for visualizing text output
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("")

        hbox = QVBoxLayout()

        self.lb = QLabel("")
        hbox.addWidget(self.lb)

        self.ptText = QPlainTextEdit()
        hbox.addWidget(self.ptText)

        hbox2 = QHBoxLayout()
        hbox2.addItem(QSpacerItem(241, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.pbSave = QPushButton("Save results", clicked=self.save_results)
        hbox2.addWidget(self.pbSave)

        self.pbOK = QPushButton("OK", clicked=self.close)
        hbox2.addWidget(self.pbOK)

        hbox.addLayout(hbox2)

        self.setLayout(hbox)

        self.resize(540, 640)

    def save_results(self):
        """
        save content of self.ptText
        """

        fn = QFileDialog().getSaveFileName(self, "Save results", "", "Text files (*.txt *.tsv);;All files (*)")
        file_name = fn[0] if type(fn) is tuple else fn

        if file_name:
            try:
                with open(file_name, "w") as f:
                    f.write(self.ptText.toPlainText())
            except Exception:
                QMessageBox.critical(self, "", f"The file {file_name} can not be saved")
