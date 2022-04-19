from PyQt5 import QtWidgets

import py.ui.about_ui as about


class About(QtWidgets.QDialog, about.Ui_Dialog):
    def __init__(self, version):
        super().__init__()
        self.setupUi(self)
        self.label_3.setText(f"""
        <html>
            <head/>
                <body style="line-height:20%">
                    <p>Версия {version}</p>
                    <p>Password Saver - программа для хранения аккаунтов.</p>
                </body>
        </html>
        """)
        self.pushButton.clicked.connect(self.close)
