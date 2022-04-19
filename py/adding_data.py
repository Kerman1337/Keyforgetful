import string
import random
import base64
import datetime
import rsa

from PyQt5 import QtCore, QtWidgets, QtGui

import py.ui.adding_data_ui as adding_data_ui
from py.show_msg import show_msg


class AddingData(QtWidgets.QDialog, adding_data_ui.Ui_Dialog):

    def __init__(self, srt_section, choice_pubkey, db_dir,
                 conn, cur, buffer, buffer_del_sec):
        super().__init__()
        self.setupUi(self)

        self.choice_pubkey = choice_pubkey
        self.db_dir = db_dir

        self.conn = conn
        self.cur = cur

        self._buffer = buffer

        self.checkbox_copy_buffer = 0

        self.lineEdit_7 = QtWidgets.QLineEdit(self.gridLayoutWidget)
        self.lineEdit_7.setObjectName("lineEdit_7")
        self.gridLayout.addWidget(self.lineEdit_7, 0, 1, 1, 1)
        self.lineEdit_7.hide()
        self.lineEdit_3.setEchoMode(QtWidgets.QLineEdit.Password)
        self.lineEdit_5.setEchoMode(QtWidgets.QLineEdit.Password)
        self.pushButton_5.setEnabled(False)

        [self.lines], = self.cur.execute(
            "SELECT Count(*) FROM account_information")

        if self.lines != 0:
            self.srt_section_main_menu = srt_section
            for _ in self.srt_section_main_menu:
                self.comboBox.addItem("")
        else:
            self.add_section()

        self.checkBox.setText(f"на {buffer_del_sec} секунд")
        if self.lines != 0:
            for index_item, section in enumerate(
                    self.srt_section_main_menu):
                self.comboBox.setItemText(index_item, str(section))

        if buffer_del_sec == 0:
            self.checkBox.setText("")

        self.pushButton.clicked.connect(self.add_section)
        self.pushButton_2.clicked.connect(self.generate_password)
        self.pushButton_3.clicked.connect(self.add_data)
        self.pushButton_4.clicked.connect(self.close)
        self.pushButton_5.clicked.connect(self.copy_password)

        self.lineEdit.textChanged.connect(self.name_check_text)
        self.lineEdit_2.textChanged.connect(self.login_check_text)
        self.lineEdit_3.textChanged.connect(self.password_check_text)
        self.lineEdit_7.textChanged.connect(self.section_check_text)

    @QtCore.pyqtSlot()
    def name_check_text(self):
        if self.lineEdit.text() == '':
            self.lineEdit.setStyleSheet("border: 1px solid red;")
        else:
            self.lineEdit.setStyleSheet("")

    @QtCore.pyqtSlot()
    def login_check_text(self):
        if self.lineEdit_2.text() == '':
            self.lineEdit_2.setStyleSheet("border: 1px solid red;")
        else:
            self.lineEdit_2.setStyleSheet("")

    @QtCore.pyqtSlot()
    def password_check_text(self):
        if self.lineEdit_3.text() == '':
            self.lineEdit_3.setStyleSheet("border: 1px solid red;")
            self.pushButton_5.setEnabled(False)
        else:
            self.lineEdit_3.setStyleSheet("")
            self.pushButton_5.setEnabled(True)

    @QtCore.pyqtSlot()
    def section_check_text(self):
        if self.lineEdit_7.text() == '':
            self.lineEdit_7.setStyleSheet("border: 1px solid red;")
        else:
            self.lineEdit_7.setStyleSheet("")

    @QtCore.pyqtSlot()
    def add_data(self):
        section = None
        if self.lineEdit_7.isVisible():
            section = self.lineEdit_7.text()
        elif self.comboBox.isVisible():
            section = self.comboBox.currentText()
        name = self.lineEdit.text()
        login = self.lineEdit_2.text()
        entered_password = self.lineEdit_3.text()
        password_bin = entered_password.encode()

        if self.choice_pubkey is not None:
            pubkey = self.choice_pubkey
        else:
            with open('{}_pubkey.pem'.format(self.db_dir[:-3]), 'rb') \
                    as pubfile:
                keydata_pub = pubfile.read()
                pubfile.close()
            pubkey = rsa.PublicKey.load_pkcs1(keydata_pub, 'PEM')

        crypto_password = rsa.encrypt(password_bin, pubkey)
        password = (base64.b64encode(crypto_password)).decode()

        email = self.lineEdit_4.text()
        entered_secret_word = self.lineEdit_5.text()
        if entered_secret_word == '':
            entered_secret_word = 'None'

        secret_word_bin = entered_secret_word.encode()
        crypto_secret = rsa.encrypt(secret_word_bin, pubkey)
        secret_word = (base64.b64encode(crypto_secret)).decode()

        url = self.lineEdit_6.text()
        if section == '':
            show_msg(title='Ошибка',
                     top_text='Введите раздел',
                     window_type='critical',
                     buttons='ok')
            self.lineEdit_7.setStyleSheet("border: 1px solid red;")
        elif name == '':
            show_msg(title='Ошибка',
                     top_text='Введите название',
                     window_type='critical',
                     buttons='ok')
            self.lineEdit.setStyleSheet("border: 1px solid red;")
        elif login == '':
            show_msg(title='Ошибка',
                     top_text='Введите логин',
                     window_type='critical',
                     buttons='ok')
            self.lineEdit_2.setStyleSheet("border: 1px solid red;")
        elif entered_password == '':
            show_msg(title='Ошибка',
                     top_text='Введите пароль',
                     window_type='critical',
                     buttons='ok')
            self.lineEdit_3.setStyleSheet("border: 1px solid red;")
        else:
            if email == '':
                email = 'None'
            if entered_secret_word == '':
                secret_word = 'None'
            if url == '':
                url = 'None'
            if self.lines == 0:
                new_id = 1
                self.cur.execute("""
                    INSERT INTO account_information
                    (ID, section, name, login, pass, email, secret_word, url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (
                        new_id, section, name, login, password,
                        email, secret_word, url))
                self.cur.execute("""
                    INSERT INTO data_change_time
                    (id, create_account)
                    VALUES (?, ?)""", (
                        new_id,
                        datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                if self.checkBox.isChecked():
                    self._buffer = QtWidgets.QApplication.clipboard()
                    self._buffer.setText(entered_password)
                    self.checkbox_copy_buffer = 1
                self.close()
            else:
                self.cur.execute("""
                    SELECT ID
                    FROM account_information
                    WHERE name='{}' and login='{}'
                """.format(name, login))
                exist_account = self.cur.fetchone()
                if exist_account is not None:
                    show_msg(title='Ошибка',
                             top_text='Такой аккаунт уже существует',
                             window_type='critical',
                             buttons='ok')
                else:
                    [max_id], = self.cur.execute("""
                        SELECT ID 
                        FROM account_information 
                        ORDER BY ID 
                        DESC LIMIT 1""")
                    new_id = max_id + 1
                    self.cur.execute("""
                        INSERT INTO account_information
                        (id, section, name, login, 
                        pass, email, secret_word, url)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (
                            new_id, section, name, login, password,
                            email, secret_word, url))
                    self.cur.execute("""
                        INSERT INTO data_change_time
                        (id, create_account)
                        VALUES (?, ?)""", (
                            new_id,
                            datetime.datetime.now().strftime(
                                '%Y-%m-%d %H:%M:%S')))

                    if self.checkBox.isChecked():
                        self._buffer = QtWidgets.QApplication.clipboard()
                        self._buffer.setText(entered_password)
                        self.checkbox_copy_buffer = 1
                    self.close()

    @QtCore.pyqtSlot()
    def add_section(self):
        self.comboBox.hide()
        self.pushButton.hide()
        self.lineEdit_7.show()

    @QtCore.pyqtSlot()
    def generate_password(self):
        def gen_pass():
            chars = string.ascii_letters + string.digits + '_' + '!' + '?' + '@'
            size = random.randint(8, 12)
            return ''.join(random.choice(chars) for _ in range(size))
        self.lineEdit_3.setText(gen_pass())

    # TODO: Сделать функцию таймера по времени и перенести в отдельный файл.
    def copy_password(self):
        self._buffer = QtWidgets.QApplication.clipboard()
        self._buffer.setText(self.lineEdit_3.text())

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        self.done(self.checkbox_copy_buffer)

    def get_buffer(self):
        return self._buffer
