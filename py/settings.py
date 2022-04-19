from PyQt5 import QtWidgets, QtCore

import py.ui.settings_ui as settings_ui


class Settings(QtWidgets.QDialog, settings_ui.Ui_Dialog):
    def __init__(self, buffer_del_sec):
        super().__init__()
        self.setupUi(self)

        self.spinBox.setValue(buffer_del_sec)

        self._buffer_del_sec = self.spinBox.value()
        self.buttonBox.clicked.connect(self.set_buffer_del_sec)

    @QtCore.pyqtSlot()
    def set_buffer_del_sec(self):
        self._buffer_del_sec = self.spinBox.value()

    def get_buffer_del_sec(self) -> int:
        """ Returns the number of seconds before flushing the buffer. """
        return self._buffer_del_sec
