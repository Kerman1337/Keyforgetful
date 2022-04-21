import datetime
import os
from sys import platform

from PyQt5 import QtCore, QtGui, QtWidgets

import py.database as database
import py.main_menu as main_menu
import py.ui.start_window_ui as start_window_ui
import py.database_creation as database_creation
from py.show_msg import show_msg

if platform == "linux" or platform == "linux2":
    from pysqlcipher3 import dbapi2 as sqlite3
elif platform == "win32":
    import sqlite3
# elif platform == "darwin":
    # OS X


def check_database(connect: sqlite3.Connection, pwd: str, new_rsa_bit: int) \
        -> tuple:
    """
    Validates the database and returns a tuple.

    :param connect: sqlite3.Connection object
    :param pwd: pragma key password
    :param new_rsa_bit: rsa key length when creating a new base
    :return: tuple(sqlite3.Connection, bool)
    """
    cur_check_db = connect.cursor()
    cur_check_db.execute(f"PRAGMA key = '{pwd}'")
    try:
        account_information = cur_check_db.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND
        name='account_information'""").fetchall()
        data_change_time = cur_check_db.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND
        name='data_change_time'""").fetchall()
        db_information = cur_check_db.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND
        name='db_information'""").fetchall()
        if len(data_change_time) == 0:
            cur_check_db.execute("""
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
            if len(account_information) == 1:
                id_account_information = cur_check_db.execute("""
                SELECT id FROM account_information""").fetchall()
                now_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for id_ in id_account_information:
                    cur_check_db.execute("""
                    INSERT INTO data_change_time (id, create_account) 
                    VALUES (?,?)""", (id_[0], now_time))
        if len(account_information) == 0:
            cur_check_db.execute("""
            CREATE TABLE IF NOT EXISTS account_information(
                "id" INTEGER NOT NULL UNIQUE PRIMARY KEY AUTOINCREMENT,
                "section" TEXT NOT NULL,
                "name" TEXT NOT NULL,
                "login" TEXT NOT NULL,
                "pass" TEXT NOT NULL,
                "email" TEXT DEFAULT 'NULL',
                "secret_word" TEXT DEFAULT 'NULL',
                "url" TEXT DEFAULT 'NULL')""")
        if len(db_information) == 0:
            cur_check_db.execute("""
            CREATE TABLE IF NOT EXISTS db_information(
                "name" TEXT NOT NULL,
                "value" INTEGER NOT NULL)""")
            cur_check_db.execute("""
            INSERT INTO db_information (name, value) 
            VALUES (?, ?)""", ('rsa_bit', new_rsa_bit))
    except sqlite3.DatabaseError as error:
        show_msg(title='Ошибка',
                 top_text='Ошибка проверки базы данных',
                 bottom_text=str(error),
                 window_type='critical',
                 buttons='ok')
        cur_check_db.close()
        return connect, False
    cur_check_db.close()
    connect.commit()
    return connect, True


class StartWindow(QtWidgets.QDialog, start_window_ui.Ui_Dialog):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.main_window = None
        self.create_db = None
        self.names_db = []
        self.version = 'v 1.2.1'
        self.updates_list_db()
        self.setWindowIcon(QtGui.QIcon(':/resource/image/key.ico'))
        self.label_4.setText(self.version)
        self.new_rsa_bit = None

        self.toolButton.clicked.connect(self.push_tool_button)
        self.pushButton_3.clicked.connect(self.show_main_window)
        self.pushButton_2.clicked.connect(self.show_create_db)

    def updates_list_db(self):
        self.names_db.clear()
        self.comboBox_2.clear()

        path_dir = os.getcwd()
        data_files_name = os.listdir(path="data")
        for file_name in data_files_name:
            type_file = file_name[file_name.find("."):]
            if type_file == '.db':
                self.names_db.append(file_name)
        for name_db in self.names_db:
            db_data = [path_dir + '\\data\\' + name_db, name_db]
            self.comboBox_2.addItem(name_db, db_data)

    @QtCore.pyqtSlot()
    def push_tool_button(self):
        directory_name = QtWidgets.QFileDialog.getOpenFileName(
            None, 'Открытие базы данных', os.getcwd(), 'database files(*.db)')
        if directory_name[0] != '':
            self.comboBox_2.clear()
            filename = ''
            for letter in reversed(directory_name[0]):
                if letter == '/':
                    break
                filename += letter
            file_info = [filename[::-1], directory_name]
            db_data = [file_info[1][0], file_info[0]]
            self.comboBox_2.addItem(file_info[0], db_data)

    @QtCore.pyqtSlot()
    def show_main_window(self):
        if self.comboBox_2.currentIndex() == -1:
            show_msg(title='Ошибка',
                     top_text='Не выбрана база данных',
                     window_type='critical',
                     buttons='ok')
        else:
            pwd = self.lineEdit_2.text()
            wrong_db_info = self.comboBox_2.currentData()

            wrong_db_info_new = ''
            for _item_db_info in range(len(wrong_db_info[0])):
                if wrong_db_info[0][_item_db_info] == '\\':
                    wrong_db_info_new += '/'
                else:
                    wrong_db_info_new += wrong_db_info[0][_item_db_info]

            db_info = [wrong_db_info_new, wrong_db_info[1]]

            conn_start_window = sqlite3.connect(db_info[0])
            cur_start_window = conn_start_window.cursor()
            cur_start_window.execute("PRAGMA key = '{}'".format(pwd))
            try:
                cur_start_window.execute(
                    "SELECT count(*) FROM account_information")
                result = True
                cur_start_window.close()
            except sqlite3.DatabaseError:
                result = False
                cur_start_window.close()
                conn_start_window.close()
            if result:
                self._update_new_rsa_bit()
                conn_start_window, check_result = check_database(
                    conn_start_window, pwd, self.new_rsa_bit)
                conn_start_window.close()
                if check_result:
                    conn, cur, rsa_length = database.connect_sql(db_info[0], pwd)
                    self.main_window = main_menu.MainMenu(version=self.version,
                                                          db_dir=db_info[0],
                                                          db_name=db_info[1],
                                                          pwd=pwd,
                                                          connect=conn,
                                                          cursor=cur,
                                                          rsa_length=rsa_length)
                    del pwd
                    self.main_window.show()
                    self.close()
            else:
                show_msg(title='Ошибка',
                         top_text='Неправильный пароль',
                         window_type='critical',
                         buttons='ok')
                self.lineEdit_2.clear()

    @QtCore.pyqtSlot()
    def show_create_db(self):
        self.create_db = database_creation.CreateDB()
        self.create_db.exec_()
        self.updates_list_db()

    def _update_new_rsa_bit(self):
        self.create_db = database_creation.CreateDB()
        self.new_rsa_bit = self.create_db.get_new_rsa_bit()
