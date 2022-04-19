import base64
import copy
import datetime
import os
import rsa
from sys import platform

from PyQt5 import QtCore, QtGui, QtWidgets

import py.ui.sync_db_ui as sync_db_ui
from py.spinner_widget import QtWaitingSpinner
from py.show_msg import show_msg

if platform == "linux" or platform == "linux2":
    from pysqlcipher3 import dbapi2 as sqlite3
    from pysqlcipher3.dbapi2 import Error
elif platform == "win32":
    import sqlite3
    from sqlite3.dbapi2 import Error
# elif platform == "darwin":
#     OS X


class SyncDBThread(QtCore.QThread):
    response = QtCore.pyqtSignal(int)

    def __init__(self, path, pwd, path_to_privkey, path_to_pubkey, db_dir):
        super().__init__()
        self.path = path
        self.pwd = pwd
        self.path_to_privkey = path_to_privkey
        self.path_to_pubkey = path_to_pubkey
        self.db_dir = db_dir

    # TODO: Восстанавливает удаленные аккаунты при синхронизации. исправить
    def run(self):
        thread_conn_main = sqlite3.connect(self.db_dir)
        thread_conn_main.row_factory = lambda cursor, row: list(row)
        thread_cur_main = thread_conn_main.cursor()
        thread_cur_main.execute("PRAGMA key = '{}'".format(self.pwd))
        rows_main_db = thread_cur_main.execute(
            "SELECT * FROM account_information").fetchall()

        rows_main_db_decrypt = []
        for row_main in rows_main_db:
            pass_decrypt_row = decrypt(self.path_to_privkey, row_main[4])
            secret_decrypt_row = decrypt(self.path_to_privkey, row_main[6])
            row_decrypt = []
            for row_index_data in range(8):
                if row_index_data == 4:
                    row_decrypt.append(pass_decrypt_row)
                elif row_index_data == 6:
                    row_decrypt.append(secret_decrypt_row)
                else:
                    row_decrypt.append(row_main[row_index_data])
            rows_main_db_decrypt.append(row_decrypt)

        thread_conn_sync = sqlite3.connect(self.path)
        thread_conn_sync.row_factory = lambda cursor, row: list(row)
        thread_cur_sync = thread_conn_sync.cursor()
        thread_cur_sync.execute("PRAGMA key = '{}'".format(self.pwd))
        rows_sync_db = thread_cur_sync.execute(
            "SELECT * FROM account_information").fetchall()

        rows_sync_db_decrypt = []
        for row_sync in rows_sync_db:
            pass_decrypt_row = decrypt(self.path_to_privkey, row_sync[4])
            secret_decrypt_row = decrypt(self.path_to_privkey, row_sync[6])
            row_decrypt = []
            for row_index_data in range(8):
                if row_index_data == 4:
                    row_decrypt.append(pass_decrypt_row)
                elif row_index_data == 6:
                    row_decrypt.append(secret_decrypt_row)
                else:
                    row_decrypt.append(row_sync[row_index_data])
            rows_sync_db_decrypt.append(row_decrypt)

        unique_rows_sync_db = []
        for row in rows_sync_db_decrypt:
            if row not in rows_main_db_decrypt:
                unique_rows_sync_db.append(row)

        sync_list_decrypt = copy.deepcopy(rows_main_db_decrypt)

        indexes_mutable_columns = [1, 3, 4, 5, 6, 7]
        names_mutable_columns = ['change_section', 'change_login',
                                 'change_pass', 'change_email',
                                 'change_secret_word', 'change_url']
        for unique_row in unique_rows_sync_db:
            for index_row_main, row_main in enumerate(rows_main_db_decrypt):
                if unique_row[0] == row_main[0] and unique_row[3] == row_main[3]:
                    for index_column, name_column in zip(indexes_mutable_columns,
                                                         names_mutable_columns):
                        if unique_row[index_column] != row_main[index_column]:
                            data_change_time_sync = thread_cur_sync.execute(f"""
                                SELECT {name_column}
                                FROM data_change_time
                                WHERE id = ?""", (
                                str(row_main[0]),)).fetchall()[0][0]
                            data_change_time_main = thread_cur_main.execute(f"""
                                SELECT {name_column}
                                FROM data_change_time
                                WHERE id = ?""", (
                                str(row_main[0]),)).fetchall()[0][0]
                            if data_change_time_sync != 'NULL' and\
                                    data_change_time_main != 'NULL':
                                if datetime.datetime.strptime(
                                        data_change_time_main,
                                        "%Y-%m-%d %H:%M:%S") < \
                                        datetime.datetime.strptime(
                                            data_change_time_sync,
                                            "%Y-%m-%d %H:%M:%S"):
                                    thread_cur_main.execute(f"""
                                        UPDATE data_change_time
                                        SET {name_column} = ?
                                        WHERE id = ? """, (data_change_time_sync,
                                                           str(row_main[0])))
                                    sync_list_decrypt[index_row_main][index_column]\
                                        = unique_row[index_column]
                            elif data_change_time_main == 'NULL':
                                thread_cur_main.execute(f"""
                                    UPDATE data_change_time
                                    SET {name_column} = ?
                                    WHERE id = ? """, (data_change_time_sync,
                                                       str(row_main[0])))
                                sync_list_decrypt[index_row_main][index_column]\
                                    = unique_row[index_column]
                    break
                elif index_row_main + 1 == len(rows_main_db_decrypt):
                    dct_sync_info = thread_cur_sync.execute(
                        "SELECT * FROM data_change_time WHERE id = ?", (
                            str(unique_row[0]),)).fetchall()
                    last_id_main = sync_list_decrypt[-1][0]
                    unique_row[0] = last_id_main + 1
                    sync_list_decrypt.append(unique_row)
                    thread_cur_main.execute("""
                        INSERT INTO data_change_time
                        (id, create_account, update_account, change_section, 
                        change_login, change_pass, change_email, 
                        change_secret_word, change_url)
                        VALUES (?,?,?,?,?,?,?,?,?)""", (
                            unique_row[0], dct_sync_info[0][1],
                            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            dct_sync_info[0][3], dct_sync_info[0][4],
                            dct_sync_info[0][5], dct_sync_info[0][6],
                            dct_sync_info[0][7], dct_sync_info[0][8]))

        sync_list_decrypt_unique = sync_list_decrypt.copy()
        for list_item in sync_list_decrypt:
            if list_item in rows_main_db_decrypt:
                sync_list_decrypt_unique.remove(list_item)

        id_main_db = [item_list[0] for item_list in rows_main_db_decrypt]

        with open(self.path_to_pubkey, 'rb') as pubfile:
            keydata_pub = pubfile.read()
            pubfile.close()
        pubkey = rsa.PublicKey.load_pkcs1(keydata_pub, 'PEM')

        sync_list = []

        for item_list in sync_list_decrypt_unique:
            crypto_password = rsa.encrypt(item_list[4].encode(), pubkey)
            password_encrypted = (base64.b64encode(crypto_password)).decode()
            item_list[4] = password_encrypted
            crypto_secret = rsa.encrypt(item_list[6].encode(), pubkey)
            secret_encrypted = (base64.b64encode(crypto_secret)).decode()
            item_list[6] = secret_encrypted
            sync_list.append(item_list)

        for list_item in sync_list:
            if list_item[0] in id_main_db:
                thread_cur_main.execute("""
                    UPDATE account_information
                    SET section = ?,
                        name = ?,
                        login = ?,
                        pass = ?,
                        email = ?,
                        secret_word = ?,
                        url = ?
                    WHERE id = ?""", (
                        list_item[1], list_item[2], list_item[3], list_item[4],
                        list_item[5], list_item[6], list_item[7], list_item[0]))
            else:
                thread_cur_main.execute("""
                    INSERT INTO account_information
                    (id, section, name, login, pass, email, secret_word, url)
                    VALUES (?,?,?,?,?,?,?,?)""", (
                        list_item[0], list_item[1], list_item[2], list_item[3],
                        list_item[4], list_item[5], list_item[6], list_item[7]))

        thread_cur_sync.execute("DELETE FROM account_information")
        thread_cur_sync.execute("DELETE FROM data_change_time")
        duplicate_sync_db_ai = thread_cur_main.execute(
            "SELECT * FROM account_information").fetchall()
        duplicate_sync_db_dct = thread_cur_main.execute(
            "SELECT * FROM data_change_time").fetchall()

        for list_item in duplicate_sync_db_ai:
            thread_cur_sync.execute("""
                INSERT INTO account_information
                (id, section, name, login, pass, email, secret_word, url)
                VALUES (?,?,?,?,?,?,?,?)""", list_item)
        for list_item in duplicate_sync_db_dct:
            thread_cur_sync.execute("""
                INSERT INTO data_change_time
                (id, create_account, update_account, change_section, change_login,
                change_pass, change_email, change_secret_word, change_url)
                VALUES (?,?,?,?,?,?,?,?,?)""", list_item)

        added_acc_count = 0
        for list_item in sync_list_decrypt_unique:
            if list_item not in rows_main_db_decrypt or \
                    list_item not in rows_sync_db_decrypt:
                added_acc_count += 1

        # TODO: Считает при добавлении и изменении с sync в main.
        #  Нужно чтобы и с main в sync.
        self.response.emit(added_acc_count)

        thread_conn_main.commit()
        thread_conn_sync.commit()
        thread_cur_main.close()
        thread_cur_sync.close()
        thread_conn_main.close()
        thread_conn_sync.close()


def create_and_check_connection(path: str, pwd: str) \
        -> sqlite3.Connection or None:
    """
    Connects to the database and verifies the password.
    Returns None or a connection object.

    :param path: path to database file
    :param pwd: input password for database
    :return: sqlite3.Connection object / None
    """
    try:
        conn_sync = sqlite3.connect(path)
        cur_sync = conn_sync.cursor()
        cur_sync.execute("PRAGMA key = '{}'".format(pwd))
        cur_sync.execute("SELECT name from account_information WHERE id=1")
        cur_sync.close()
        return conn_sync
    except Error:
        show_msg(title='Ошибка',
                 top_text='Неправильный пароль',
                 window_type='critical',
                 buttons='ok')
        conn_sync = None
        return conn_sync


def execute_read_query(conn_sync: sqlite3.Connection, query: str) -> list:
    """
    Executes the passed sql database query and returns the result.

    :param conn_sync: sqlite3.Connection object
    :param query: sql query string
    :return: list
    """
    result = []
    cur_sync = conn_sync.cursor()
    try:
        cur_sync.execute(query)
        result = cur_sync.fetchall()
        cur_sync.close()
        return result
    except Error as e:
        show_msg(title='Ошибка',
                 top_text=f'Ошибка выполнения запроса: ({e})',
                 window_type='critical',
                 buttons='ok')
        cur_sync.close()
        return result


def decrypt(path_to_privkey: str, crypt_s: str, choice_privkey: str = None,
            result_check_choice_privkey: str = None) -> str:
    """
    Decrypts the string with the private key and returns it.

    :param crypt_s: Input crypto string
    :param path_to_privkey: Path to privkey.pem file
    :param choice_privkey: Privkey.pem file if available
    :param result_check_choice_privkey: Result of checking privkey.pem
    :return: Output decrypt string or 'error'
    """
    if result_check_choice_privkey == 'ok':
        privkey = choice_privkey
    else:
        with open(path_to_privkey, 'rb') as privfile:
            keydata_priv = privfile.read()
            privfile.close()
        privkey = rsa.PrivateKey.load_pkcs1(keydata_priv, 'PEM')
    password_bin = crypt_s.encode()
    password_dec = base64.b64decode(password_bin)
    try:
        decrypto = rsa.decrypt(password_dec, privkey)
        result = decrypto.decode()
        return result
    except rsa.pkcs1.DecryptionError as error:
        show_msg(title='Ошибка',
                 top_text='Ошибка расшифровки закрытого ключа',
                 bottom_text=str(error),
                 window_type='critical',
                 buttons='ok')
        return 'error'


class SyncDB(QtWidgets.QDialog, sync_db_ui.Ui_Dialog):
    def __init__(self, path_to_privkey, path_to_pubkey, choice_privkey,
                 result_check_choice_privkey, db_dir):
        super().__init__()
        self.setupUi(self)

        self.db_dir = db_dir

        self.choice_privkey = choice_privkey
        self.result_check_choice_privkey = result_check_choice_privkey

        self.path_to_privkey = path_to_privkey
        self.path_to_pubkey = path_to_pubkey
        self.acc_count = None
        self.sync_db_thread = None
        self.sync_db_finished = 0

        self.label_11.setHidden(True)

        self.databases_from_dir = []
        self.databases_from_dir.clear()
        data_files_name = os.listdir(path="data")
        for _name_db in data_files_name:
            type_file = _name_db[_name_db.find("."):]
            if type_file == '.db':
                self.databases_from_dir.append(_name_db)

        path_dir = os.getcwd()
        for _addItem in self.databases_from_dir:
            # TODO: need fix \\data\\ => /data/ from linux
            path_to_db = [path_dir + '/data/' + _addItem, _addItem]
            self.comboBox.addItem(_addItem, path_to_db)

        self.spinner = QtWaitingSpinner(self, centerOnParent=False,
                                        disableParentWhenSpinning=True)
        self.spinner.setGeometry(QtCore.QRect(180, 240, 121, 16))
        self.spinner.setRoundness(70.0)
        self.spinner.setMinimumTrailOpacity(15.0)
        self.spinner.setTrailFadePercentage(70.0)
        self.spinner.setNumberOfLines(12)
        self.spinner.setLineLength(10)
        self.spinner.setLineWidth(5)
        self.spinner.setInnerRadius(10)
        self.spinner.setRevolutionsPerSecond(1)
        self.spinner.setColor(QtGui.QColor(0, 0, 0))

        self.toolButton.clicked.connect(self.push_tool_button)
        self.pushButton.clicked.connect(self.start_sync)

    @QtCore.pyqtSlot()
    def push_tool_button(self):
        directory_name = QtWidgets.QFileDialog.getOpenFileName(
            None, 'Открытие базы данных', os.getcwd(), 'database files(*.db)')
        if directory_name[0] != '':
            self.comboBox.clear()
            filename = ''
            for _letter in reversed(directory_name[0]):
                if _letter == '/':
                    break
                filename += _letter
            file_info = [filename[::-1], directory_name]
            db_data = [file_info[1][0], file_info[0]]
            self.comboBox.addItem("", db_data)
            self.comboBox.setItemText(0, file_info[0])

    @QtCore.pyqtSlot()
    def start_sync(self):
        self.label_5.setPixmap(QtGui.QPixmap(":/resource/image/question.ico"))
        self.label_6.setPixmap(QtGui.QPixmap(":/resource/image/question.ico"))
        self.label_7.setPixmap(QtGui.QPixmap(":/resource/image/question.ico"))
        path = self.comboBox.currentData()[0]
        pwd = self.lineEdit.text()
        conn_sync = create_and_check_connection(path, pwd)
        if conn_sync is not None:
            self.label_5.setPixmap(
                QtGui.QPixmap(":/resource/image/checkmark.ico"))
            check_empty = "SELECT * from account_information"
            rows = execute_read_query(conn_sync, check_empty)
            if len(rows) != 0:
                self.label_6.setPixmap(
                    QtGui.QPixmap(":/resource/image/checkmark.ico"))
                decrypt_result = decrypt(self.path_to_privkey, rows[0][4],
                                         self.choice_privkey,
                                         self.result_check_choice_privkey)
                if decrypt_result == 'error':
                    self.label_7.setPixmap(
                        QtGui.QPixmap(":/resource/image/cross.ico"))
                else:
                    self.label_7.setPixmap(
                        QtGui.QPixmap(":/resource/image/checkmark.ico"))
                    path_to_privkey, path_to_pubkey = \
                        self.path_to_privkey, self.path_to_pubkey
                    self.sync_db_thread = SyncDBThread(path, pwd,
                                                       path_to_privkey,
                                                       path_to_pubkey,
                                                       self.db_dir)
                    self.sync_db_thread.started.connect(self.spinner_started)
                    self.sync_db_thread.response.connect(self.response_slot)
                    self.acc_count = 0
                    self.sync_db_thread.finished.connect(
                        lambda: self.spinner_finished(self.acc_count))
                    self.sync_db_thread.start()
            else:
                self.label_6.setPixmap(
                    QtGui.QPixmap(":/resource/image/cross.ico"))
                show_msg(title='Ошибка',
                         top_text='База данных пустая',
                         window_type='critical',
                         buttons='ok')
            conn_sync.close()
        else:
            self.label_5.setPixmap(QtGui.QPixmap(":/resource/image/cross.ico"))
            self.lineEdit.clear()

    def response_slot(self, acc_count):
        self.acc_count = acc_count

    @QtCore.pyqtSlot()
    def spinner_started(self):
        self.spinner.start()
        self.label_11.setText("Синхронизирую...")
        self.label_11.show()

    @QtCore.pyqtSlot()
    def spinner_finished(self, acc_count):
        self.spinner.stop()
        self.label_11.setText(f"Синхронизированно {acc_count} аккаунтов")
        self.label_11.setStyleSheet("font-weight: 900; font-size: 16px")
        self.pushButton.setEnabled(False)
        self.sync_db_finished = 1

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        self.done(self.sync_db_finished)
