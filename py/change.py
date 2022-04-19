import string
import random

from PyQt5 import QtWidgets

import py.ui.change_ui as change_ui


class Change(QtWidgets.QDialog, change_ui.Ui_Dialog):
    def __init__(self, title: str, label_text: str, pushbutton: bool):
        """
        Initialize an instance.

        :param title: set window title
        :param label_text: set label text
        :param pushbutton: On / Off generate password button
        """
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle(title)
        self.label.setText(label_text)
        if not pushbutton:
            self.pushButton.hide()
        if title == 'Изменение секретного слова' or title == 'Изменение пароля':
            self.lineEdit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.pushButton.clicked.connect(self.generate_password)

    def generate_password(self):
        chars = string.ascii_letters + string.digits + '_' + '!' + '?' + '@'
        size = random.randint(8, 12)
        result = ''.join(random.choice(chars) for _ in range(size))
        self.lineEdit.setText(result)
