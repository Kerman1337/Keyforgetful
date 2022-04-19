import os
import string
import rsa
from sys import platform

from PyQt5 import QtCore, QtGui, QtWidgets

import py.res_rc    # required for loading resource files. Do not delete
import py.ui.database_creation_ui as database_creation_ui
from py.spinner_widget import QtWaitingSpinner
from py.show_msg import show_msg

if platform == "linux" or platform == "linux2":
    from pysqlcipher3 import dbapi2 as sqlite3
elif platform == "win32":
    import sqlite3
# elif platform == "darwin":
    # OS X


class ThreadCreateKeys(QtCore.QThread):

    def __init__(self, name_db, new_rsa_bit, parent=None):
        QtCore.QThread.__init__(self, parent)
        self.name_db = name_db
        self.new_rsa_bit = new_rsa_bit

    def run(self):
        (pubkey, privkey) = rsa.newkeys(self.new_rsa_bit)
        pubkey_pem = pubkey.save_pkcs1('PEM')
        privkey_pem = privkey.save_pkcs1('PEM')
        with open('data/{0}_pubkey.pem'.format(self.name_db), mode='w+')\
                as pubfile:
            pubfile.write(pubkey_pem.decode())
            pubfile.close()
        with open('data/{0}_privkey.pem'.format(self.name_db), mode='w+')\
                as privfile:
            privfile.write(privkey_pem.decode())
            privfile.close()


class CreateDB(QtWidgets.QDialog, database_creation_ui.Ui_Dialog):

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.label_6.hide()
        self.validate_password = None

        self.spinner = QtWaitingSpinner(self, centerOnParent=False,
                                        disableParentWhenSpinning=True)
        self.spinner.setGeometry(QtCore.QRect(180, 230, 121, 16))
        self.spinner.setRoundness(70.0)
        self.spinner.setMinimumTrailOpacity(15.0)
        self.spinner.setTrailFadePercentage(70.0)
        self.spinner.setNumberOfLines(12)
        self.spinner.setLineLength(10)
        self.spinner.setLineWidth(5)
        self.spinner.setInnerRadius(10)
        self.spinner.setRevolutionsPerSecond(1)
        self.spinner.setColor(QtGui.QColor(0, 0, 0))

        self.setWindowIcon(QtGui.QIcon(':/resource/image/key.ico'))

        self.pushButton.clicked.connect(self.create_database)
        self.lineEdit.textChanged.connect(self.valid_name_db)
        self.lineEdit_2.textChanged.connect(self.valid_password)
        self.lineEdit_3.textChanged.connect(self.confirm_password)

        self.create_keys = None

        rsa_keys = [1024, 2048, 3072, 4096]
        for rsa_key in rsa_keys:
            self.comboBox.addItem(str(rsa_key), rsa_key)
        self.comboBox.setCurrentIndex(3)

        self._new_rsa_bit = self.comboBox.currentData()

    @QtCore.pyqtSlot()
    def valid_name_db(self):
        data_files = os.listdir(path="data")
        name_db = self.lineEdit.text()
        new_name_db = []
        for name_db_ in data_files:
            type_file = name_db_[name_db_.find("."):]
            if type_file == '.db':
                new_name_db.append(name_db_[:-3])
        if len(new_name_db) == 0:
            self.lineEdit.setStyleSheet("border: 1px solid green")
        else:
            for item_db in new_name_db:
                if name_db == item_db:
                    self.lineEdit.setStyleSheet("border: 1px solid red")
                    break
                else:
                    self.lineEdit.setStyleSheet("border: 1px solid green")
        if name_db == '':
            self.lineEdit.setStyleSheet("border: 1px solid red")

    @QtCore.pyqtSlot()
    def valid_password(self):
        password = self.lineEdit_2.text()
        confirm_pass = self.lineEdit_3.text()
        if self._isvalid_password(password):
            self.lineEdit_2.setStyleSheet("border: 1px solid green")
            self.validate_password = True
        else:
            self.lineEdit_2.setStyleSheet("border: 1px solid red")
            self.validate_password = False
        if confirm_pass == '':
            pass
        elif confirm_pass == password:
            self.lineEdit_3.setStyleSheet("border: 1px solid green")
        else:
            self.lineEdit_3.setStyleSheet("border: 1px solid red")

    @QtCore.pyqtSlot()
    def confirm_password(self):
        password = self.lineEdit_2.text()
        confirm_pass = self.lineEdit_3.text()
        if confirm_pass == password:
            self.lineEdit_3.setStyleSheet("border: 1px solid green")
        else:
            self.lineEdit_3.setStyleSheet("border: 1px solid red")

    @QtCore.pyqtSlot()
    def create_database(self):
        data_files = os.listdir(path="data")
        name_db = self.lineEdit.text()
        pwd = self.lineEdit_2.text()
        pwd_re = self.lineEdit_3.text()
        if name_db == '':
            show_msg(title='Ошибка',
                     top_text='Введите название БД',
                     window_type='critical',
                     buttons='ok')
            self.lineEdit.setStyleSheet("border: 1px solid red")
        else:
            result = False
            new_name_db = []
            for name_db_ in data_files:
                type_file = name_db_[name_db_.find("."):]
                if type_file == '.db':
                    new_name_db.append(name_db_[:-3])
            for item_db in new_name_db:
                if name_db == item_db:
                    result = True
                    break
            if result:
                show_msg(title='Ошибка',
                         top_text='Такая база данных уже существует',
                         window_type='critical',
                         buttons='ok')
                self.lineEdit.setStyleSheet("border: 1px solid red")
            elif pwd == '' and pwd_re == '':
                show_msg(title='Ошибка',
                         top_text='Заполните поля ввода паролей',
                         window_type='critical',
                         buttons='ok')
                self.lineEdit_2.setStyleSheet("border: 1px solid red")
                self.lineEdit_3.setStyleSheet("border: 1px solid red")
            elif pwd == '':
                show_msg(title='Ошибка',
                         top_text='Поле введите пароль пустое',
                         window_type='critical',
                         buttons='ok')
                self.lineEdit_2.setStyleSheet("border: 1px solid red")
            elif self.validate_password is None or not self.validate_password:
                show_msg(title='Ошибка',
                         top_text='Неправильный пароль',
                         bottom_text='- 8 символов или больше\n'
                                     '- Верхний и нижний регистр\n'
                                     '- Минимум 1 цифра\n'
                                     '- Не может быть русскими буквами',
                         window_type='critical',
                         buttons='ok')
                self.lineEdit_2.setStyleSheet("border: 1px solid red")
                self.lineEdit_3.setStyleSheet("border: 1px solid red")
            elif pwd_re == '':
                show_msg(title='Ошибка',
                         top_text='Поле подтвердите пароль пустое',
                         window_type='critical',
                         buttons='ok')
                self.lineEdit_3.setStyleSheet("border: 1px solid red")
            elif pwd != pwd_re:
                show_msg(title='Ошибка',
                         top_text='Пароли не совпадают',
                         window_type='critical',
                         buttons='ok')
                self.lineEdit_3.setStyleSheet("border: 1px solid red")
            elif pwd == pwd_re:
                self._new_rsa_bit = self.comboBox.currentData()
                conn_db_creation = sqlite3.connect(r'data/' + name_db + '.db')
                cur_db_creation = conn_db_creation.cursor()
                cur_db_creation.execute("PRAGMA key = '{}'".format(pwd))
                cur_db_creation.execute("PRAGMA foreign_keys = ON")
                cur_db_creation.execute("""
                CREATE TABLE IF NOT EXISTS account_information(
                    "id" INTEGER NOT NULL UNIQUE PRIMARY KEY AUTOINCREMENT,
                    "section" TEXT NOT NULL,
                    "name" TEXT NOT NULL,
                    "login" TEXT NOT NULL,
                    "pass" TEXT NOT NULL,
                    "email" TEXT DEFAULT 'NULL',
                    "secret_word" TEXT DEFAULT 'NULL',
                    "url" TEXT DEFAULT 'NULL')""")
                cur_db_creation.execute("""
                CREATE TABLE IF NOT EXISTS db_information(
                    "name" TEXT NOT NULL,
                    "value" INTEGER NOT NULL)""")
                cur_db_creation.execute("""
                CREATE TABLE IF NOT EXISTS data_change_time(
                    "id" INTEGER NOT NULL UNIQUE 
                        REFERENCES account_information (id) ON DELETE CASCADE 
                                                            ON UPDATE CASCADE,
                    "create_account" TEXT NOT NULL,
                    "update_account" TEXT DEFAULT 'NULL',
                    "change_section" TEXT DEFAULT 'NULL',
                    "change_login" TEXT DEFAULT 'NULL',
                    "change_pass" TEXT DEFAULT 'NULL',
                    "change_email" TEXT DEFAULT 'NULL',
                    "change_secret_word" TEXT DEFAULT 'NULL',
                    "change_url" TEXT DEFAULT 'NULL')""")
                cur_db_creation.execute("""
                INSERT INTO db_information (name, value) 
                VALUES ('rsa_bit', {})""".format(self._new_rsa_bit))
                conn_db_creation.commit()
                cur_db_creation.close()
                conn_db_creation.close()
                self.create_keys = ThreadCreateKeys(name_db=self.lineEdit.text(),
                                                    new_rsa_bit=self._new_rsa_bit)
                self.create_keys.started.connect(self.spinner_started)
                self.create_keys.finished.connect(self.spinner_finished)
                self.create_keys.start()
            else:
                show_msg(title='Ошибка',
                         top_text='Неизвестная ошибка',
                         bottom_text='Обратитесь к разработчику',
                         window_type='critical',
                         buttons='ok')
                self.lineEdit_3.setStyleSheet("border: 1px solid red")

    @QtCore.pyqtSlot()
    def spinner_started(self):
        self.spinner.start()
        self.label_6.show()

    @QtCore.pyqtSlot()
    def spinner_finished(self):
        self.spinner.stop()
        self.label_6.hide()
        show_msg(title='Успех',
                 top_text='База данных успешно создана' + (' ' * 500),
                 bottom_text='Более подробно по нажатию '
                             'кнопки "Show Details..."',
                 detailed_text='- База данных: \n' + os.getcwd() + '\\data\\'
                               + self.lineEdit.text() + '.db' + '\n\n'
                                       
                               '- Открытый ключ: \n' + os.getcwd() + '\\data\\'
                               + self.lineEdit.text() + '_pubkey.pem' + '\n\n'
                                               
                               '- Закрытый ключ: \n' + os.getcwd() + '\\data\\'
                               + self.lineEdit.text() + '_privkey.pem',
                 window_type='information',
                 buttons='ok')
        self.lineEdit.clear()
        self.lineEdit_2.clear()
        self.lineEdit_3.clear()
        self.lineEdit.setStyleSheet("border: 1px solid gray")
        self.lineEdit_2.setStyleSheet("border: 1px solid gray")
        self.lineEdit_3.setStyleSheet("border: 1px solid gray")
        self.close()

    @staticmethod
    def _isvalid_password(password: str) -> bool:
        """
        Checking the password for correctness.

        :param password: Set password.
        :return: Result of checking.
        """
        has_no = set(password).isdisjoint
        return not (len(password) < 8 or
                    has_no(string.digits) or
                    has_no(string.ascii_lowercase) or
                    has_no(string.ascii_uppercase))

    def get_new_rsa_bit(self):
        return self._new_rsa_bit
