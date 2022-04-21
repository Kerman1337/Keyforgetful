import os.path
import base64
import random
import string
import datetime
import rsa
from sys import platform

from PyQt5 import QtCore, QtGui, QtWidgets, QtPrintSupport

import py.res_rc    # required for loading resource files. Do not delete
import py.about as about
import py.settings as settings
import py.database_creation as database_creation
import py.adding_data as adding_data
import py.loading_db as loading_db
import py.sync_db as sync_db
import py.print_list as print_list
import py.change as change
import py.ui.main_menu_ui as main_menu_ui
from py.show_msg import show_msg
from py.spinner_widget import QtWaitingSpinner

if platform == "linux" or platform == "linux2":
    from pysqlcipher3 import dbapi2 as sqlite3
elif platform == "win32":
    import sqlite3
# elif platform == "darwin":
    # OS X


def record_change_time(cursor: sqlite3.Cursor,
                       row: tuple,
                       change_type: str
                       ) -> bool:
    """
    Records the time of data change in the database.

    :param cursor: current cursor
    :param row: a tuple of values from the selected row
    :param change_type: what changing
    :return: execution result
    """
    try:
        acc_id = cursor.execute("""SELECT id
                                   FROM account_information
                                   WHERE name = ? AND
                                           login = ? AND
                                           email = ? AND
                                           url = ? """, (row[0][0],
                                                         row[0][1],
                                                         row[0][3],
                                                         row[0][5])
                                ).fetchall()[0][0]
        cursor.execute(f"""UPDATE data_change_time
                           SET update_account = ?,
                               {change_type} = ?
                           WHERE id={acc_id}""",
                       (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        return True
    except sqlite3.Error as sqlite_error:
        show_msg(title='Ошибка',
                 top_text='Ошибка выполнения record_change_time()',
                 bottom_text=str(sqlite_error),
                 window_type='critical',
                 buttons='ok')
        return False


class PrintThread(QtCore.QThread):
    def __init__(self, tool_button, tree_widget, pl, db_dir, pwd, parent=None):
        QtCore.QThread.__init__(self, parent)
        self.toolButton = tool_button
        self.treeWidget = tree_widget
        self.pl = pl
        self.db_dir = db_dir
        self.pwd = pwd

    def run(self):
        conn_print_thread = sqlite3.connect(self.db_dir)
        cur_print_thread = conn_print_thread.cursor()
        cur_print_thread.execute("PRAGMA key = '{}'".format(self.pwd))

        with open('{}_privkey.pem'.format(self.toolButton.text()[:-12]), 'rb') \
                as privfile:
            keydata_priv = privfile.read()
            privfile.close()
        privkey = rsa.PrivateKey.load_pkcs1(keydata_priv, 'PEM')

        data = []
        tree_widget_item_count = 0
        iterator = QtWidgets.QTreeWidgetItemIterator(self.treeWidget)
        while iterator.value():
            item = iterator.value()
            if item.text(0) == '':
                data.append([item.text(1)])
                for index in range(2, 7):
                    if item.text(index) == 'None':
                        data[-1].append('')
                    elif index == 3 and item.text(index) == '**********':
                        data3_item = cur_print_thread.execute("""
                        SELECT pass
                        FROM account_information
                        WHERE name='{}' AND
                              login='{}' AND
                              email='{}' AND
                              url='{}'""".format(item.text(1),
                                                 item.text(2),
                                                 item.text(4),
                                                 item.text(6))).fetchall()
                        password_bin = (data3_item[0][0]).encode()
                        password_dec = base64.b64decode(password_bin)
                        decrypto = rsa.decrypt(password_dec, privkey)
                        password = decrypto.decode()
                        data[-1].append(password)
                    elif index == 5 and item.text(index) == '**********':
                        data5_item = cur_print_thread.execute("""
                        SELECT secret_word
                        FROM account_information
                        WHERE name='{}' AND
                              login='{}' AND
                              email='{}' AND
                              url='{}'""".format(item.text(1),
                                                 item.text(2),
                                                 item.text(4),
                                                 item.text(6))).fetchall()
                        secret_bin = (data5_item[0][0]).encode()
                        secret_dec = base64.b64decode(secret_bin)
                        decrypto = rsa.decrypt(secret_dec, privkey)
                        secret = decrypto.decode()
                        if secret == 'None':
                            data[-1].append('')
                        else:
                            data[-1].append(secret)
                    else:
                        data[-1].append(item.text(index))
            if item.parent():
                if item.parent():
                    tree_widget_item_count += 1
            else:
                tree_widget_item_count += 1
            iterator += 1
        self.pl.data = data

        column_widths = []
        for _ in range(1, self.treeWidget.headerItem().columnCount()):
            column_widths.append(180)
        self.pl.columnWidths = column_widths

        headers = []
        for index in range(1, self.treeWidget.headerItem().columnCount()):
            item = self.treeWidget.headerItem().text(index)
            headers.append(item)
        self.pl.headers = headers

        cur_print_thread.close()
        conn_print_thread.close()


class ShowPassThread(QtCore.QThread):
    response = QtCore.pyqtSignal(dict)

    def __init__(self, acc_secret_info, privkey):
        super().__init__()
        self.acc_secret_info = acc_secret_info
        self.privkey = privkey

    def run(self):
        acc_secret_info_result = dict()
        for _key, _value in self.acc_secret_info.items():
            password_bin = (_value[0]).encode()
            password_dec = base64.b64decode(password_bin)
            try:
                decrypto = rsa.decrypt(password_dec, self.privkey)
                password = decrypto.decode()
            except rsa.pkcs1.DecryptionError:
                password = '##ERRORPUBKEY##'

            secret_word_bin = (_value[1]).encode()

            secret_word_dec = base64.b64decode(secret_word_bin)
            try:
                decrypto_secret = rsa.decrypt(secret_word_dec, self.privkey)
                secret_word = decrypto_secret.decode()
            except rsa.pkcs1.DecryptionError:
                secret_word = '##ERRORPUBKEY##'
            acc_secret_info_result[_key] = password, secret_word
        self.response.emit(acc_secret_info_result)


class MainMenu(QtWidgets.QMainWindow, main_menu_ui.Ui_MainWindow):
    def __init__(self,
                 version, db_dir, db_name, pwd, connect, cursor, rsa_length):
        super().__init__()
        self.setupUi(self)

        self.version = version

        self.db_dir = db_dir
        self.db_name = db_name
        self.pwd = pwd

        self.conn = connect
        self.cur = cursor
        self.rsa_length = rsa_length

        self.create_db = None
        self.loading_db = None
        self.adding_data = None
        self.sync_db = None
        self.settings = None
        self.about = None
        self.timer_sec = None
        self.step = None
        self.show_pass_thread = None
        self.print_thread = None
        self.acc_info_list = list()
        self.acc_secret_info_result = dict()
        self.menu_context_alb = None
        self.change = None
        self.pubkey_file = os.path.isfile(f"{db_dir[:-3]}_pubkey.pem")
        self.privkey_file = os.path.isfile(f"{db_dir[:-3]}_privkey.pem")
        self.lines = None
        self.amount_item_0 = 0
        self.srt_section = list()
        self.result_check_privkey = None
        self.result_check_pubkey = None
        self.privkey_dir = None
        self.pubkey_dir = None
        self.choice_pubkey = None
        self.choice_privkey = None
        self.result_check_choice_pubkey = None
        self.result_check_choice_privkey = None
        self.buffer_del_time = 0
        self.buffer = None
        self.hide_password = True
        self.acc_count = None
        self.last_change_db = None

        self.buffer_del_sec = 10

        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        for header_item_index in range(0, 7):
            self.treeWidget.headerItem().setFont(header_item_index, font)
        self.add_tree_widget_item()

        self.progressBar.hide()
        self.statusbar.addPermanentWidget(self.progressBar)
        self.statusbar.addPermanentWidget(self.label_version)

        self.spinner = QtWaitingSpinner(self, centerOnParent=True,
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

        self.check_privkey()
        self.check_pubkey()

        if self.hide_password:
            self.pushButton_showPass.setText('Показать пароли')
        else:
            self.pushButton_showPass.setText('Скрыть пароли')

        self.button_state()

        if (not self.toolButton_pubkey.isEnabled() and
                not self.toolButton_privkey.isEnabled()):
            self.action_syncDb.setEnabled(True)
        else:
            self.action_syncDb.setEnabled(False)

        self.retranslate_ui_main()

        self.set_db_info()

        self.action_saveDb.triggered.connect(self.save_db)
        self.action_createDb.triggered.connect(self.show_create_db)
        self.action_loadDb.triggered.connect(self.show_load_db)
        self.action_syncDb.triggered.connect(self.show_sync_db)
        self.action_print.triggered.connect(self.print_db)
        self.action_exit.triggered.connect(self.close)
        self.action_settings.triggered.connect(self.show_settings)
        self.action_about.triggered.connect(self.show_about)
        self.pushButton_delete.clicked.connect(self.delete_data)
        self.pushButton_addingData.clicked.connect(self.show_adding_data)
        self.pushButton_showHideSections.clicked.connect(
            self.show_hide_all_sections)
        self.pushButton_showPass.clicked.connect(self.password_hide_show)
        self.toolButton_pubkey.clicked.connect(self.check_choice_pubkey)
        self.toolButton_privkey.clicked.connect(self.check_choice_privkey)
        self.treeWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.treeWidget.customContextMenuRequested.connect(
            self.menu_context_album)

    def retranslate_ui_main(self):
        self.setWindowTitle(f"Keyforgetful - Главная | {self.db_name}")
        __sortingEnabled = self.treeWidget.isSortingEnabled()
        self.treeWidget.setSortingEnabled(False)
        self.add_tree_widget_item_text()
        self.treeWidget.setSortingEnabled(__sortingEnabled)
        self.label_version.setText(self.version)

        if self.pubkey_file and self.result_check_pubkey == 'ok':
            self.toolButton_pubkey.setText(self.pubkey_dir)
        elif self.pubkey_file and self.result_check_pubkey == '!ok':
            self.toolButton_pubkey.setText(
                'Ключ не подходит. Укажите pubkey.pem')
        elif self.pubkey_file and self.result_check_pubkey is None:
            self.toolButton_pubkey.setText(self.pubkey_dir)
        elif self.pubkey_file and self.result_check_pubkey == 'not privkey':
            self.toolButton_pubkey.setText('Укажите privkey.pem')
        else:
            self.toolButton_pubkey.setText("Укажите pubkey.pem")

        if self.privkey_file and self.result_check_privkey == 'ok':
            self.privkey_dir = os.path.abspath("data/{}_privkey.pem".format(
                self.db_name[:-3]))
            self.toolButton_privkey.setText(self.privkey_dir)
        elif self.privkey_file and self.result_check_privkey == '!ok':
            self.toolButton_privkey.setText(
                "Ключ не подходит. Укажите privkey.pem")
        elif self.privkey_file and \
                self.result_check_privkey == 'privkey != pubkey':
            self.toolButton_privkey.setText(
                "Ключи разные. Укажите правильный privkey.pem")
            self.toolButton_pubkey.setText(
                "Ключи разные. Укажите правильный pubkey.pem")
        elif self.privkey_file and self.result_check_privkey == 'not pubkey':
            self.toolButton_privkey.setText("Сперва нужно указать pubkey.pem")
        else:
            self.toolButton_privkey.setText("Укажите privkey.pem")

        self.progressBar.setFormat("")

    @QtCore.pyqtSlot()
    def print_db(self):
        if not self.toolButton_privkey.isEnabled():
            pl = print_list.PrintList()
            layout = QtGui.QPageLayout(QtGui.QPageSize(QtGui.QPageSize.A4),
                                       QtGui.QPageLayout.Landscape,
                                       QtCore.QMarginsF(5, 5, 5, 5),
                                       units=QtGui.QPageLayout.Millimeter)
            pl.printer.setPageLayout(layout)
            pd = QtPrintSupport.QPrintDialog(pl.printer, parent=None)
            result = pd.exec_()

            if result == 1:
                self.print_thread = PrintThread(
                    tool_button=self.toolButton_privkey,
                    tree_widget=self.treeWidget,
                    pl=pl,
                    db_dir=self.db_dir,
                    pwd=self.pwd)
                self.print_thread.started.connect(self.print_spinner_started)
                self.print_thread.finished.connect(
                    lambda: self.print_spinner_finished(self.print_thread.pl))
                self.print_thread.start()
        else:
            show_msg(title='Ошибка',
                     top_text='Не указан privkey.pem',
                     window_type='critical',
                     buttons='ok')

    @QtCore.pyqtSlot()
    def print_spinner_started(self):
        self.spinner.start()
        self.statusbar.showMessage("Готовлюсь к печати...")

    @QtCore.pyqtSlot()
    def print_spinner_finished(self, pl):
        pl.print_data()
        self.spinner.stop()
        show_msg(title='Успех',
                 top_text='Печать завершена',
                 window_type='information',
                 buttons='ok')
        self.statusbar.showMessage("Печать завершена.")

    @QtCore.pyqtSlot()
    def show_pass_spinner_started(self):
        self.spinner.start()
        self.statusbar.showMessage("Расшифровываю пароли...")

    @QtCore.pyqtSlot()
    def show_pass_spinner_finished(self):
        section_iter = 0
        for _data_section in self.acc_info_list:
            item_iter = 0
            for _data_item in _data_section:
                if _data_item[1] in self.acc_secret_info_result:
                    self.treeWidget.topLevelItem(section_iter).child(
                        item_iter).setText(
                        3, self.acc_secret_info_result[_data_item[1]][0])
                item_iter += 1
            section_iter += 1

        self.pushButton_showPass.setText('Скрыть пароли')
        self.acc_info_list.clear()
        self.spinner.stop()
        self.statusbar.showMessage("Пароли расшифрованы.", msecs=10000)

    def show_pass_response(self, acc_secret_info_result):
        self.acc_secret_info_result = acc_secret_info_result

    @QtCore.pyqtSlot()
    def save_db(self):
        result = show_msg(title='Сохранение изменений',
                          top_text='Вы действительно хотите сохранить '
                                   'изменения в базе данных?',
                          window_type='information',
                          buttons='yes_no')
        if result == QtWidgets.QMessageBox.Yes:
            self.conn.commit()
            show_msg(title='Успех',
                     top_text='База данных сохранена',
                     buttons='ok')

    @QtCore.pyqtSlot()
    def show_create_db(self):
        self.create_db = database_creation.CreateDB()
        self.create_db.exec_()

    @QtCore.pyqtSlot()
    def show_load_db(self):
        self.loading_db = loading_db.LoadingDB()
        exit_status = self.loading_db.exec()
        if exit_status:
            self.cur.close()
            self.conn.close()

            data_loading_db = self.loading_db.get_data_loading_db()
            self.db_dir = data_loading_db['db_dir']
            self.db_name = data_loading_db['db_name']
            self.pwd = data_loading_db['pwd']

            data_sql_connection = self.loading_db.get_sql_connection()
            self.conn = data_sql_connection['conn']
            self.cur = data_sql_connection['cur']
            self.rsa_length = data_sql_connection['rsa_length']

            self.pubkey_file = os.path.isfile(f"{self.db_dir[:-3]}_pubkey.pem")
            self.privkey_file = os.path.isfile(f"{self.db_dir[:-3]}_privkey.pem")
            self.refresh_tree_widget(load=True)
            self.check_privkey()
            self.check_pubkey()
            self.result_check_choice_pubkey = None
            self.result_check_choice_privkey = None
            self.button_state()
            self.retranslate_ui_main()
            if self.result_check_pubkey:
                self.pushButton_addingData.setEnabled(True)
            [lines], = self.cur.execute(
                "SELECT Count(*) FROM account_information")
            if lines == 0:
                self.pushButton_showHideSections.setEnabled(False)
                self.pushButton_showHideSections.setText(
                    "Развернуть все разделы")
            else:
                self.pushButton_showHideSections.setText("Свернуть все разделы")

    @QtCore.pyqtSlot()
    def show_sync_db(self):
        if ((self.result_check_pubkey == 'ok' or
             self.result_check_choice_pubkey == 'ok') and
                (self.result_check_privkey == 'ok' or
                 self.result_check_choice_privkey == 'ok')):
            self.sync_db = sync_db.SyncDB(self.toolButton_privkey.text(),
                                          self.toolButton_pubkey.text(),
                                          self.choice_privkey,
                                          self.result_check_choice_privkey,
                                          self.db_dir)
            finished_sync_db = self.sync_db.exec()
            if finished_sync_db:
                self.refresh_tree_widget()
        else:
            show_msg(title='Ошибка',
                     top_text='Укажите ключи',
                     window_type='critical',
                     buttons='ok')

    @QtCore.pyqtSlot()
    def show_adding_data(self):
        if not self.hide_password:
            self.password_hide()
        self.adding_data = adding_data.AddingData(self.srt_section,
                                                  self.choice_pubkey,
                                                  self.db_dir,
                                                  self.conn,
                                                  self.cur,
                                                  self.buffer,
                                                  self.buffer_del_sec)
        checkbox_status = self.adding_data.exec_()
        self.buffer = self.adding_data.get_buffer()
        self.refresh_tree_widget()

        if self.lines != 0 and self.privkey_file and \
                self.result_check_privkey == 'ok' \
                or self.lines != 0 and self.result_check_choice_privkey == 'ok':
            self.pushButton_delete.setEnabled(True)
            self.pushButton_showPass.setEnabled(True)
        elif self.lines != 0 and self.privkey_file and \
                self.result_check_privkey == '!ok'\
                or self.lines != 0 and self.result_check_choice_privkey == '!ok':
            self.pushButton_delete.setEnabled(True)
            self.pushButton_showPass.setEnabled(False)
        elif self.lines == 0:
            self.pushButton_delete.setEnabled(False)
        else:
            self.pushButton_delete.setEnabled(True)

        if checkbox_status:
            self.delete_buffer()

    @QtCore.pyqtSlot()
    def show_settings(self):
        self.settings = settings.Settings(self.buffer_del_sec)
        exit_status = self.settings.exec_()
        if exit_status:
            self.buffer_del_sec = self.settings.get_buffer_del_sec()

    @QtCore.pyqtSlot()
    def show_about(self):
        self.about = about.About(self.version)
        self.about.exec_()

    @QtCore.pyqtSlot()
    def show_hide_all_sections(self):
        _text = self.pushButton_showHideSections.text()
        if _text == 'Развернуть все разделы':
            self.treeWidget.expandAll()
            self.pushButton_showHideSections.setText('Свернуть все разделы')
        else:
            self.treeWidget.collapseAll()
            self.pushButton_showHideSections.setText('Развернуть все разделы')

    def copy_pass_buffer(self):
        row = self.current_row()
        if row[1] == 'item_1':
            self.buffer = QtWidgets.QApplication.clipboard()
            if self.buffer is not None:
                data_one_section = self.cur.execute("""
                SELECT pass
                FROM account_information
                WHERE name='{}' AND
                      login='{}' AND
                      email='{}' AND
                      url='{}'""".format(row[0][0], row[0][1],
                                         row[0][3], row[0][5])).fetchall()
                if self.choice_privkey is not None:
                    privkey = self.choice_privkey
                else:
                    with open('{}_privkey.pem'.format(self.db_dir[:-3]), 'rb') \
                            as privfile:
                        keydata_priv = privfile.read()
                        privfile.close()
                    privkey = rsa.PrivateKey.load_pkcs1(keydata_priv, 'PEM')
                password_bin = data_one_section[0][0].encode()
                password_dec = base64.b64decode(password_bin)
                decrypto = rsa.decrypt(password_dec, privkey)
                password = decrypto.decode()
                self.buffer.setText(password)

    def copy_secret_buffer(self):
        row = self.current_row()
        self.buffer = QtWidgets.QApplication.clipboard()
        if self.buffer is not None:
            data_one_section = self.cur.execute("""
            SELECT secret_word 
            FROM account_information 
            WHERE name='{}' AND 
                  login='{}' AND 
                  email='{}' AND 
                  url='{}'""".format(row[0][0], row[0][1],
                                     row[0][3], row[0][5])
                                           ).fetchall()
            if self.choice_privkey is not None:
                privkey = self.choice_privkey
            else:
                with open('{}_privkey.pem'.format(self.db_dir[:-3]), 'rb') \
                        as privfile:
                    keydata_priv = privfile.read()
                    privfile.close()
                privkey = rsa.PrivateKey.load_pkcs1(keydata_priv,
                                                    'PEM')
            secret_bin = data_one_section[0][0].encode()
            secret_dec = base64.b64decode(secret_bin)
            decrypto = rsa.decrypt(secret_dec, privkey)
            secret = decrypto.decode()
            return secret

        return None

    @QtCore.pyqtSlot()
    def delete_data(self):
        row = self.current_row()
        if row[1] == 'item_0 first' or row[1] == 'item_0':
            show_msg(title='Ошибка',
                     top_text='Нельзя удалить раздел.',
                     bottom_text='Если хотите удалить раздел, '
                                 'то удалите все аккаунты в нём.',
                     window_type='critical',
                     buttons='ok')
        elif row[1] == 'item_1':
            result = show_msg(title='Удаление аккаунта',
                              top_text=f'Данные аккаунта <b>{row[0][0]}</b> '
                                       f'с логином <b>{row[0][1]}</b> '
                                       f'будут удалены',
                              window_type='information',
                              bottom_text='Вы уверенны?',
                              buttons='yes_no')
            if result == QtWidgets.QMessageBox.Yes:
                acc_id = self.cur.execute("""
                SELECT id
                FROM account_information
                WHERE name = ? AND
                    login = ? AND
                    email = ? AND
                    url = ? """, (row[0][0], row[0][1], row[0][3],
                                  row[0][5])).fetchall()[0][0]
                self.cur.execute("DELETE FROM data_change_time WHERE id = ?",
                                 (str(acc_id),))
                self.cur.execute("""
                DELETE FROM account_information
                WHERE name = ? AND
                      login = ? AND
                      email = ? AND
                      url = ? """, (row[0][0], row[0][1], row[0][3],
                                    row[0][5]))
                self.refresh_tree_widget()

        if self.lines == 0:
            self.pushButton_delete.setEnabled(False)
            self.pushButton_showPass.setEnabled(False)

    @QtCore.pyqtSlot()
    def password_hide_show(self):
        if self.lines != 0:
            if self.pushButton_showPass.text() == 'Показать пароли':
                self.hide_password = False
                if self.choice_privkey is not None:
                    privkey = self.choice_privkey
                else:
                    with open('{}_privkey.pem'.format(self.db_dir[:-3]), 'rb') \
                            as privfile:
                        keydata_priv = privfile.read()
                        privfile.close()
                    privkey = rsa.PrivateKey.load_pkcs1(keydata_priv, 'PEM')

                for _data_section in range(self.amount_item_0):
                    data_one_section = self.cur.execute("""
                    SELECT *
                    FROM account_information
                    WHERE section='{}'""".format(
                        self.srt_section[_data_section])).fetchall()
                    acc_info = []
                    for item in data_one_section:
                        acc_info.append(list(item[2:]))

                    self.acc_info_list.append(acc_info)

                __acc_secret_info = dict()
                for _data_section in self.acc_info_list:
                    for _data_item in _data_section:
                        __acc_secret_info[_data_item[1]] = _data_item[2],\
                                                           _data_item[4]

                self.show_pass_thread = ShowPassThread(__acc_secret_info,
                                                       privkey)
                self.show_pass_thread.started.connect(
                    self.show_pass_spinner_started)
                self.show_pass_thread.response.connect(self.show_pass_response)
                self.show_pass_thread.finished.connect(
                    self.show_pass_spinner_finished)
                self.show_pass_thread.start()
            elif self.pushButton_showPass.text() == 'Скрыть пароли':
                self.hide_password = True
                top_level_item_iter = -1
                for data_section in range(self.amount_item_0):
                    data_one_section = self.cur.execute("""
                    SELECT *
                    FROM account_information
                    WHERE section='{}'""".format(
                        self.srt_section[data_section])).fetchall()
                    acc_info = []
                    for item in data_one_section:
                        acc_info.append(item[2:])
                    self.treeWidget.topLevelItem(data_section).setText(
                        0, str(self.srt_section[data_section]))
                    top_level_item_iter += 1
                    child_iter = -1
                    for index in range(len(acc_info)):
                        child_iter += 1
                        text_iter = 0
                        for _ in acc_info[index]:
                            text_iter += 1
                            if text_iter == 3:
                                self.treeWidget.topLevelItem(top_level_item_iter)\
                                    .child(child_iter) \
                                    .setText(text_iter, '**********')
                self.pushButton_showPass.setText('Показать пароли')

    @QtCore.pyqtSlot()
    def check_choice_pubkey(self):
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/resource/image/checkmark.ico"),
                       QtGui.QIcon.Disabled, QtGui.QIcon.Off)
        directory_name = QtWidgets.QFileDialog.getOpenFileName(
            None, 'Укажите публичный ключ-файл (.pem)', os.getcwd(),
            f'pubkey ({self.db_name[:-3]}_pubkey.pem);;pubkey (*_pubkey.pem)')
        if directory_name[0] != '' and directory_name[1] != '':
            with open(directory_name[0], 'rb') as pubfile:
                keydata_pub = pubfile.read()
                pubfile.close()
            self.choice_pubkey = rsa.PublicKey.load_pkcs1(keydata_pub, 'PEM')
            self.toolButton_pubkey.setEnabled(False)
            self.toolButton_pubkey.setText(directory_name[0])
            self.pushButton_addingData.setEnabled(True)

            if not self.toolButton_privkey.isEnabled():
                if (self.privkey_file and
                        self.result_check_privkey == 'not pubkey'):
                    patch_dir_privkey = f"{self.db_dir[:-3]}_privkey.pem"
                else:
                    patch_dir_privkey = self.toolButton_privkey.text()
                try:
                    with open(patch_dir_privkey, 'rb') as privfile:
                        keydata_priv = privfile.read()
                        privfile.close()
                    self_test_privfile = rsa.PrivateKey.load_pkcs1(keydata_priv,
                                                                   'PEM')
                    chars = string.ascii_letters + string.digits
                    rnd_text = ''.join(random.choice(chars) for _ in range(20))
                    rnd_text = rnd_text.encode()
                    crypto_text = rsa.encrypt(rnd_text, self.choice_pubkey)
                    self_test_decrypto = rsa.decrypt(crypto_text,
                                                     self_test_privfile)
                    self.result_check_choice_pubkey = 'ok'
                    self.action_syncDb.setEnabled(True)
                    if self.toolButton_privkey.text() == 'Сперва нужно указать pubkey.pem':
                        self.toolButton_privkey.setText(patch_dir_privkey)
                        self.toolButton_privkey.setIcon(icon)
                except rsa.pkcs1.DecryptionError as rsa_dec_error:
                    self.toolButton_pubkey.setEnabled(True)
                    self.toolButton_pubkey.setText('Ключ неправильный. '
                                                   'Укажите pubkey.pem')
                    self.pushButton_addingData.setEnabled(False)
                    self.statusbar.showMessage(f'Ошибка: {rsa_dec_error}',
                                               30000)
                    self.result_check_choice_pubkey = '!ok'

    @QtCore.pyqtSlot()
    def check_choice_privkey(self):
        directory_name = QtWidgets.QFileDialog.getOpenFileName(
            None, 'Укажите приватный ключ-файл (.pem)', os.getcwd(),
            f'privkey ({self.db_name[:-3]}_privkey.pem);;privkey (*_privkey.pem)')
        if directory_name[0] != '' and directory_name[1] != '':
            with open(directory_name[0], 'rb') as privfile:
                keydata_priv = privfile.read()
                privfile.close()
            self.choice_privkey = rsa.PrivateKey.load_pkcs1(keydata_priv, 'PEM')
            if self.lines == 0:
                self.toolButton_privkey.setEnabled(False)
                self.toolButton_privkey.setText(directory_name[0])
                self.result_check_choice_privkey = 'ok'
                if not self.toolButton_pubkey.isEnabled():
                    self.action_syncDb.setEnabled(True)
            elif self.lines != 0:
                try:
                    first_pass = self.cur.execute("""
                    SELECT pass
                    FROM account_information
                    ORDER BY ID ASC LIMIT 1""").fetchall()
                    password_bin = (first_pass[0][0]).encode()
                    password_dec = base64.b64decode(password_bin)
                    decrypto = rsa.decrypt(password_dec, self.choice_privkey)
                    password = decrypto.decode()
                    self.result_check_choice_privkey = 'ok'
                except rsa.pkcs1.DecryptionError as rsa_dec_error:
                    self.result_check_choice_privkey = '!ok'
                    self.toolButton_privkey.setText(
                        'Ключ не подходит. '
                        'Выберете правильный privkey')
                    self.statusbar.showMessage(f'Ошибка: {rsa_dec_error}',
                                               30000)
                if self.result_check_choice_privkey == 'ok':
                    self.toolButton_privkey.setEnabled(False)
                    self.toolButton_privkey.setText(directory_name[0])
                    self.pushButton_showPass.setEnabled(True)
                    if not self.toolButton_pubkey.isEnabled():
                        try:
                            with open(self.toolButton_pubkey.text(), 'rb')\
                                    as pubfile:
                                keydata_pub = pubfile.read()
                                pubfile.close()
                            self_test_pubfile = rsa.PublicKey.load_pkcs1(
                                keydata_pub, 'PEM')
                            chars = string.ascii_letters + string.digits
                            rnd_text = ''.join(random.choice(chars)
                                               for _ in range(20))
                            rnd_text = rnd_text.encode()
                            crypto_text = rsa.encrypt(rnd_text,
                                                      self_test_pubfile)
                            self_test_decrypto = rsa.decrypt(crypto_text,
                                                             self.choice_privkey)
                            self.result_check_choice_pubkey = 'ok'
                            self.action_syncDb.setEnabled(True)
                        except rsa.pkcs1.DecryptionError as rsa_dec_error:
                            self.toolButton_pubkey.setEnabled(True)
                            self.toolButton_pubkey.setText('Ключ неправильный. '
                                                           'Укажите pubkey.pem')
                            self.pushButton_addingData.setEnabled(False)
                            self.statusbar.showMessage(
                                f'Ошибка: {rsa_dec_error}', 30000)
                            self.result_check_choice_pubkey = '!ok'

    def check_privkey(self):
        if self.lines != 0 and self.privkey_file:
            try:
                with open('{}_privkey.pem'.format(self.db_dir[:-3]), 'rb')\
                        as privfile:
                    keydata_priv = privfile.read()
                    privfile.close()
                privkey = rsa.PrivateKey.load_pkcs1(keydata_priv, 'PEM')
                first_pass = self.cur.execute("""
                SELECT pass
                FROM account_information
                ORDER BY ID ASC LIMIT 1""").fetchall()
                password_bin = (first_pass[0][0]).encode()
                password_dec = base64.b64decode(password_bin)
                decrypto = rsa.decrypt(password_dec, privkey)
                password = decrypto.decode()
                self.result_check_privkey = 'ok'
            except rsa.pkcs1.DecryptionError:
                self.result_check_privkey = '!ok'
        elif self.lines == 0 and self.privkey_file and self.pubkey_file:
            try:
                with open('{}_privkey.pem'.format(self.db_dir[:-3]), 'rb')\
                        as privfile:
                    keydata_priv = privfile.read()
                    privfile.close()
                privkey = rsa.PrivateKey.load_pkcs1(keydata_priv, 'PEM')
                with open('{}_pubkey.pem'.format(self.db_dir[:-3]), 'rb') as \
                        pubfile:
                    keydata_pub = pubfile.read()
                    pubfile.close()
                pubkey = rsa.PublicKey.load_pkcs1(keydata_pub, 'PEM')
                chars = string.ascii_letters + string.digits
                rnd_pass = ''.join(random.choice(chars) for _ in range(20))
                rnd_pass = rnd_pass.encode()
                crypto_pass = rsa.encrypt(rnd_pass, pubkey)
                decrypto = rsa.decrypt(crypto_pass, privkey)
                self.result_check_privkey = 'ok'
            except rsa.pkcs1.DecryptionError:
                self.result_check_privkey = 'privkey != pubkey'
        elif self.lines == 0 and self.privkey_file and not self.pubkey_file:
            self.result_check_privkey = 'not pubkey'
        else:
            self.result_check_privkey = None

    def check_pubkey(self):
        if self.pubkey_file and self.privkey_file\
                and self.result_check_privkey == 'ok':
            try:
                with open('{}_privkey.pem'.format(self.db_dir[:-3]), 'rb')\
                        as privfile:
                    keydata_priv = privfile.read()
                    privfile.close()
                privkey = rsa.PrivateKey.load_pkcs1(keydata_priv, 'PEM')
                with open('{}_pubkey.pem'.format(self.db_dir[:-3]), 'rb') \
                        as pubfile:
                    keydata_pub = pubfile.read()
                    pubfile.close()
                pubkey = rsa.PublicKey.load_pkcs1(keydata_pub, 'PEM')
                chars = string.ascii_letters + string.digits
                rnd_pass = ''.join(random.choice(chars) for _ in range(20))
                rnd_pass = rnd_pass.encode()
                crypto_pass = rsa.encrypt(rnd_pass, pubkey)
                decrypto = rsa.decrypt(crypto_pass, privkey)
                self.result_check_pubkey = 'ok'
            except rsa.pkcs1.DecryptionError:
                self.result_check_pubkey = '!ok'
        else:
            self.result_check_pubkey = None

    def button_state(self):
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/resource/image/cross.ico"),
                       QtGui.QIcon.Disabled, QtGui.QIcon.Off)
        if self.pubkey_file and self.result_check_pubkey == 'ok':
            self.pubkey_dir = os.path.abspath("data/{}_pubkey.pem".format(
                self.db_name[:-3]))
            self.toolButton_pubkey.setEnabled(False)
        elif self.pubkey_file and self.result_check_pubkey == '!ok':
            self.toolButton_pubkey.setEnabled(True)
            self.pushButton_addingData.setEnabled(False)
        elif self.pubkey_file and self.result_check_pubkey is None:
            self.pubkey_dir = os.path.abspath("data/{}_pubkey.pem".format(
                self.db_name[:-3]))
            self.toolButton_pubkey.setEnabled(False)
        elif self.pubkey_file and self.result_check_pubkey == 'not privkey':
            self.toolButton_pubkey.setEnabled(False)
            self.toolButton_pubkey.setIcon(icon)
        else:
            self.toolButton_pubkey.setEnabled(True)
            self.pushButton_addingData.setEnabled(False)

        if self.privkey_file and self.result_check_privkey == 'ok':
            self.toolButton_privkey.setEnabled(False)
            self.pushButton_showPass.setEnabled(True)
        elif self.privkey_file and self.result_check_privkey == '!ok':
            self.toolButton_privkey.setEnabled(True)
            self.pushButton_addingData.setEnabled(False)
            self.pushButton_showPass.setEnabled(False)
        elif self.privkey_file and \
                self.result_check_privkey == 'privkey != pubkey':
            self.toolButton_privkey.setEnabled(True)
            self.toolButton_pubkey.setEnabled(True)
            self.pushButton_addingData.setEnabled(False)
        elif self.privkey_file and self.result_check_privkey == 'not pubkey':
            self.toolButton_privkey.setEnabled(False)
            self.toolButton_privkey.setIcon(icon)
        else:
            self.toolButton_privkey.setEnabled(True)
            self.pushButton_showPass.setEnabled(False)

        if self.lines == 0:
            self.pushButton_delete.setEnabled(False)
            self.pushButton_showPass.setEnabled(False)

    def delete_buffer(self):
        buffer_del_sec_loc = self.buffer_del_sec
        self.buffer_del_time = buffer_del_sec_loc
        if buffer_del_sec_loc != 0:
            self.timer_sec = QtCore.QTimer()
            self.timer_sec.timeout.connect(
                lambda: self.__update_buffer(buffer_del_sec_loc))
            self.step = 100
            self.statusbar.showMessage("Данные будут удалены с буфера обмена "
                                       f"через {buffer_del_sec_loc} секунд")
            self.progressBar.show()
            self.progressBar.setValue(self.step)
            timer_del = 1000
            self.timer_sec.start(timer_del)
        else:
            self.statusbar.showMessage("Скопирован")

    def __update_buffer(self, buffer_del_sec_loc):
        self.step -= 100 / buffer_del_sec_loc
        self.buffer_del_time -= 1
        self.progressBar.setValue(self.step)
        self.statusbar.showMessage(
            "Данные будут удалены с буфера обмена через "
            f"{self.buffer_del_time} секунд")

        if self.step <= 0:
            self.buffer.clear()
            if platform == "linux" or platform == "linux2":
                self.buffer.setText("")
            self.statusbar.showMessage("Данные удалены с буфера обмена")
            self.timer_sec.stop()
            self.step = 100

    def menu_context_album(self, event):
        row = self.current_row()
        if row[1] == 'item_1':
            self.menu_context_alb = QtWidgets.QMenu(self.treeWidget)

            rsub_menu_copy_log = self.menu_context_alb.addMenu("Копировать")
            rsub_menu_change_log = self.menu_context_alb.addMenu("Изменить")
            rsub_menu_transfer_acc = self.menu_context_alb.addMenu(
                "Переместить в")
            rsub_menu_delete_acc = self.menu_context_alb.addAction("Удалить")

            rmenu_copy_log = rsub_menu_copy_log.addAction("Копировать логин")
            rmenu_copy_pass = rsub_menu_copy_log.addAction("Копировать пароль")
            rmenu_copy_email = rsub_menu_copy_log.addAction("Копировать почту")
            rmenu_copy_secret = rsub_menu_copy_log.addAction(
                "Копировать секретное слово")
            rmenu_copy_url = rsub_menu_copy_log.addAction("Копировать url")

            if self.result_check_privkey == 'ok'\
                    or self.result_check_choice_privkey == 'ok':
                rmenu_copy_pass.setEnabled(True)
                rmenu_copy_secret.setEnabled(True)
            else:
                rmenu_copy_pass.setEnabled(False)
                rmenu_copy_secret.setEnabled(False)

            rmenu_change_log = rsub_menu_change_log.addAction("Изменить логин")
            rmenu_change_pass = rsub_menu_change_log.addAction("Изменить пароль")
            rmenu_change_email = rsub_menu_change_log.addAction("Изменить почту")
            rmenu_change_secret = rsub_menu_change_log.addAction(
                "Изменить секретное слово")
            rmenu_change_url = rsub_menu_change_log.addAction("Изменить url")

            sect_list = []
            section = self.cur.execute("""
            SELECT section 
            FROM account_information 
            GROUP BY section 
            ORDER BY id""").fetchall()
            for section_item in section:
                sect_list.append(rsub_menu_transfer_acc.addAction(
                    section_item[0]))

            if not self.toolButton_pubkey.isEnabled():
                rmenu_change_log.setEnabled(True)
                rmenu_change_pass.setEnabled(True)
                rmenu_change_email.setEnabled(True)
                rmenu_change_secret.setEnabled(True)
                rmenu_change_url.setEnabled(True)
            else:
                rmenu_change_log.setEnabled(False)
                rmenu_change_pass.setEnabled(False)
                rmenu_change_email.setEnabled(False)
                rmenu_change_secret.setEnabled(False)
                rmenu_change_url.setEnabled(False)

            action2 = self.menu_context_alb.exec_(
                self.treeWidget.mapToGlobal(event))
            if action2 is not None:
                if action2 == rmenu_copy_log:
                    self.buffer = QtWidgets.QApplication.clipboard()
                    if self.buffer is not None:
                        self.buffer.setText(row[0][1])
                        self.delete_buffer()
                elif action2 == rmenu_copy_email:
                    self.buffer = QtWidgets.QApplication.clipboard()
                    if self.buffer is not None:
                        if row[0][3] == 'None':
                            show_msg(title='Ошибка',
                                     top_text='На этом аккаунте нет почты',
                                     window_type='critical',
                                     buttons='ok')
                        else:
                            self.buffer.setText(row[0][3])
                            self.delete_buffer()
                elif action2 == rmenu_copy_url:
                    self.buffer = QtWidgets.QApplication.clipboard()
                    if self.buffer is not None:
                        if row[0][5] == 'None':
                            show_msg(title='Ошибка',
                                     top_text='На этом аккаунте не указан url',
                                     window_type='critical',
                                     buttons='ok')
                        else:
                            self.buffer.setText(row[0][5])
                            self.delete_buffer()
                elif action2 == rmenu_copy_pass:
                    self.copy_pass_buffer()
                    self.delete_buffer()
                elif action2 == rmenu_copy_secret:
                    copy_secret_buffer = self.copy_secret_buffer()
                    if copy_secret_buffer is not None:
                        if copy_secret_buffer == 'None':
                            show_msg(title='Ошибка',
                                     top_text='На этом аккаунте не указанно '
                                              'секретное слово',
                                     window_type='critical',
                                     buttons='ok')
                        else:
                            self.buffer.setText(copy_secret_buffer)
                            self.delete_buffer()
                elif action2 == rmenu_change_log:
                    self.change = change.Change('Изменение логина',
                                                'Введите новый логин', False)
                    result_close_window = self.change.exec_()
                    if result_close_window:
                        login = self.change.lineEdit.text()
                        if login != '':
                            record_change_time(self.cur, row, 'change_login')
                            self.cur.execute("""
                            UPDATE account_information
                            SET login = ?
                            WHERE name = ? AND
                                  login = ? AND
                                  email = ? AND
                                  url = ? """, (login, row[0][0], row[0][1],
                                                row[0][3], row[0][5]))
                            self.refresh_tree_widget()
                        else:
                            show_msg(title='Ошибка',
                                     top_text='Нельзя изменить на пустой логин',
                                     window_type='critical',
                                     buttons='ok')
                elif action2 == rmenu_change_pass:
                    self.change = change.Change('Изменение пароля',
                                                'Введите новый пароль', True)
                    result_close_window = self.change.exec_()
                    if result_close_window:
                        if self.change.lineEdit.text() == '':
                            show_msg(title='Ошибка',
                                     top_text='Нельзя изменить на пустой пароль',
                                     window_type='critical',
                                     buttons='ok')
                        else:
                            if not self.toolButton_pubkey.isEnabled():
                                path_to_pubkey = self.toolButton_pubkey.text()
                            else:
                                path_to_pubkey = f"{self.db_dir[:-3]}_pubkey.pem"
                            with open(path_to_pubkey, 'rb') as pubfile:
                                keydata_pub = pubfile.read()
                                pubfile.close()
                            pubkey = rsa.PublicKey.load_pkcs1(keydata_pub, 'PEM')
                            pass_bin = self.change.lineEdit.text().encode()
                            crypto_pass = rsa.encrypt(pass_bin, pubkey)
                            password = base64.b64encode(crypto_pass).decode()
                            record_change_time(self.cur, row, 'change_pass')
                            self.cur.execute("""
                            UPDATE account_information
                            SET pass = ?
                            WHERE name = ? AND
                                  login = ? AND
                                  email = ? AND
                                  url= ? """, (password, row[0][0], row[0][1],
                                               row[0][3], row[0][5]))
                            self.refresh_tree_widget()
                elif action2 == rmenu_change_email:
                    self.change = change.Change('Изменение почты',
                                                'Введите новую почту', False)
                    result_close_window = self.change.exec_()
                    if result_close_window:
                        email = self.change.lineEdit.text()
                        if email == '':
                            email = None
                        record_change_time(self.cur, row, 'change_email')
                        self.cur.execute("""
                        UPDATE account_information
                        SET email = ?
                        WHERE name = ? AND
                              login = ? AND
                              email = ? AND
                              url = ? """, (email, row[0][0], row[0][1],
                                            row[0][3], row[0][5]))
                        self.refresh_tree_widget()
                elif action2 == rmenu_change_secret:
                    self.change = change.Change('Изменение секретного слова',
                                                'Введите новое секретное слово',
                                                False)
                    result_close_window = self.change.exec_()
                    if result_close_window:
                        secret_text = self.change.lineEdit.text()
                        if secret_text == '':
                            secret_text = 'None'
                        if not self.toolButton_pubkey.isEnabled():
                            path_to_pubkey = self.toolButton_pubkey.text()
                        else:
                            path_to_pubkey = f"{self.db_dir[:-3]}_pubkey.pem"
                        with open(path_to_pubkey, 'rb') as pubfile:
                            keydata_pub = pubfile.read()
                            pubfile.close()
                        pubkey = rsa.PublicKey.load_pkcs1(keydata_pub, 'PEM')
                        secret_bin = secret_text.encode()
                        crypto_secret = rsa.encrypt(secret_bin, pubkey)
                        secret = base64.b64encode(crypto_secret).decode()
                        record_change_time(self.cur, row, 'change_secret_word')
                        self.cur.execute("""
                        UPDATE account_information
                        SET secret_word = ?
                        WHERE name = ? AND
                              login = ? AND
                              email = ? AND
                              url = ? """, (secret, row[0][0], row[0][1],
                                            row[0][3], row[0][5]))
                        self.refresh_tree_widget()
                elif action2 == rmenu_change_url:
                    self.change = change.Change('Изменение url',
                                                'Введите новый url', False)
                    result_close_window = self.change.exec_()
                    if result_close_window:
                        url = self.change.lineEdit.text()
                        if url == '':
                            url = None
                        record_change_time(self.cur, row, 'change_url')
                        self.cur.execute("""
                        UPDATE account_information
                        SET url = ?
                        WHERE name = ? AND
                              login = ? AND
                              email = ? AND
                              url = ? """, (url, row[0][0], row[0][1],
                                            row[0][3], row[0][5]))
                        self.refresh_tree_widget()
                elif action2 == rsub_menu_delete_acc:
                    self.delete_data()

                for item_type in sect_list:
                    if action2 is not None and action2 == item_type:
                        record_change_time(self.cur, row, 'change_section')
                        self.cur.execute("""
                        UPDATE account_information
                        SET section = ?
                        WHERE name = ? AND
                              login = ? AND
                              email = ? AND
                              url = ? """, (item_type.text(), row[0][0],
                                            row[0][1], row[0][3], row[0][5]))
                        self.refresh_tree_widget()

    def add_tree_widget_item(self):
        [self.lines], = self.cur.execute(
            "SELECT Count(*) FROM account_information")
        section = []
        if self.lines != 0:
            self.pushButton_showHideSections.setEnabled(True)
            for _line in range(1, self.lines + 1):
                [_current_id], = self.cur.execute("""
                SELECT ID 
                FROM account_information 
                LIMIT 1 OFFSET {}""".format(_line - 1))

                [_current_section], = self.cur.execute("""
                SELECT section 
                FROM account_information 
                WHERE ID='{}'""".format(_current_id))

                section.append(_current_section)
            self.srt_section = list(dict.fromkeys(section))
            self.amount_item_0 = len(list(set(section)))
            for _data_section in range(self.amount_item_0):
                if _data_section == 0:
                    item_0 = QtWidgets.QTreeWidgetItem(self.treeWidget)
                    brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
                    brush.setStyle(QtCore.Qt.NoBrush)
                    for index in range(0, 7):
                        item_0.setBackground(index, brush)
                    data_one_section = self.cur.execute("""
                    SELECT * 
                    FROM account_information 
                    WHERE section='{}'""".format(
                        self.srt_section[_data_section])).fetchall()
                else:
                    data_one_section = self.cur.execute("""
                    SELECT * 
                    FROM account_information 
                    WHERE section='{}'""".format(
                        self.srt_section[_data_section])).fetchall()
                    item_0 = QtWidgets.QTreeWidgetItem(self.treeWidget)
                for _ in range(len(data_one_section)):
                    item_1 = QtWidgets.QTreeWidgetItem(item_0)
        else:
            self.pushButton_showHideSections.setEnabled(False)

    def delete_tree_widget_item(self):
        self.treeWidget.clear()

    def add_tree_widget_item_text(self):
        if self.lines != 0:
            privkey = None
            top_level_item_iter = -1

            if self.privkey_file:
                with open('{}_privkey.pem'.format(self.db_dir[:-3]), 'rb')\
                        as privfile:
                    keydata_priv = privfile.read()
                    privfile.close()
                privkey = rsa.PrivateKey.load_pkcs1(keydata_priv, 'PEM')
            elif self.choice_privkey:
                privkey = self.choice_privkey

            for _data_section in range(self.amount_item_0):
                data_one_section = self.cur.execute("""
                SELECT * 
                FROM account_information 
                WHERE section='{}'""".format(
                    self.srt_section[_data_section])).fetchall()
                acc_info = []
                for item in data_one_section:
                    acc_info.append(item[2:])
                self.treeWidget.topLevelItem(_data_section)\
                    .setText(0, str(self.srt_section[_data_section]))
                top_level_item_iter += 1
                child_iter = -1
                for _index in range(len(acc_info)):
                    child_iter += 1
                    text_iter = 0
                    for _value in acc_info[_index]:
                        text_iter += 1
                        if (text_iter == 3 and self.hide_password)\
                                or (text_iter == 5 and self.hide_password):
                            self.treeWidget.topLevelItem(top_level_item_iter)\
                                .child(child_iter)\
                                .setText(text_iter, str('**********'))
                        elif _value is None:
                            value = None
                            self.treeWidget.topLevelItem(top_level_item_iter)\
                                .child(child_iter)\
                                .setText(text_iter, str(value))
                        elif len(_value) == self.rsa_length:
                            value_bin = _value.encode()
                            value_dec = base64.b64decode(value_bin)
                            try:
                                decrypto_value = rsa.decrypt(value_dec, privkey)
                                value = decrypto_value.decode()
                                self.treeWidget\
                                    .topLevelItem(top_level_item_iter)\
                                    .child(child_iter)\
                                    .setText(text_iter, str(value))
                            except rsa.pkcs1.DecryptionError:
                                value = '##ERRORPUBKEY##'
                                self.treeWidget\
                                    .topLevelItem(top_level_item_iter)\
                                    .child(child_iter)\
                                    .setText(text_iter, str(value))
                        elif (text_iter == 3 and self.rsa_length == -1)\
                                or (text_iter == 5 and self.rsa_length == -1):
                            value = '##ERRORKEYLENGTH##'
                            self.treeWidget\
                                .topLevelItem(top_level_item_iter)\
                                .child(child_iter)\
                                .setText(text_iter, str(value))
                        else:
                            self.treeWidget\
                                .topLevelItem(top_level_item_iter)\
                                .child(child_iter)\
                                .setText(text_iter, str(_value))

    def create_tree_widget_top_items(self):
        """
        Creates a list with QTreeWidget => topLevelItem.

        :return: list[QTreeWidgetItem]
        """
        top_tree_widget_items = []
        for index_top_item in range(self.treeWidget.topLevelItemCount()):
            top_item = self.treeWidget.topLevelItem(index_top_item)
            top_tree_widget_items.append(top_item)
        return top_tree_widget_items
    
    def check_head_item_expand(self):
        """
        Checks top-level treeWidget items for expanded state and returns
        a dictionary with section name and expanded state.
            example: {'name_section': 'True/False'}

        :return: dict[str, bool]
        """

        top_tree_widget_items = self.create_tree_widget_top_items()

        name_and_expanded = {}
        for top_item in top_tree_widget_items:
            name_section = top_item.text(0)
            is_expanded = top_item.isExpanded()
            name_and_expanded[name_section] = is_expanded

        return name_and_expanded

    def refresh_tree_widget(self, load=False):
        """ Update QTreeWidgetItems with save expanded state. """
        name_expanded_top_item = self.check_head_item_expand()
        self.delete_tree_widget_item()
        self.add_tree_widget_item()
        self.add_tree_widget_item_text()
        self.set_db_info()

        tree_widget_items = self.create_tree_widget_top_items()

        for top_item in tree_widget_items:
            section_name = top_item.text(0)
            if section_name in name_expanded_top_item:
                if name_expanded_top_item[section_name]:
                    self.treeWidget.expandItem(top_item)
            elif not load:
                self.treeWidget.expandItem(top_item)

    def current_row(self):
        index = self.treeWidget.selectedIndexes()
        row_data = []
        iter_number = 0
        item_type = None
        for _index_item in index:
            values_dict = _index_item.model().itemData(_index_item)
            if iter_number == 0:
                if len(values_dict) == 0:
                    item_type = 'item_1'
                elif len(values_dict) == 1:
                    item_type = 'item_0'
                elif len(values_dict) == 2:
                    item_type = 'item_0 first'
            for key, value in values_dict.items():
                if value is None:
                    continue
                row_data.append(value)
            iter_number += 1
        return row_data, item_type

    def set_db_info(self):
        self.acc_count = self.calc_acc_count()
        self.last_change_db = self.get_last_change_db()
        self.label_db_info.setText(f"Аккаунтов: {self.acc_count} | "
                                   f"Последнее изменение: {self.last_change_db}")

    def get_last_change_db(self) -> str:
        """
        Returns the date and time of the last change in the database.

        :return: str(date and time)
        """
        create_acc = self.cur.execute(
            "SELECT create_account FROM data_change_time").fetchall()
        update_acc = self.cur.execute(
            "SELECT update_account FROM data_change_time").fetchall()
        time_list = list()
        time_list.extend(create_acc)
        time_list.extend(update_acc)
        time_list = list(set(time_list))
        new_update_acc = list()
        for item in time_list:
            if item[0] != 'NULL':
                new_update_acc.append(item[0])

        time_list.clear()
        for item in new_update_acc:
            time_list.append(
                datetime.datetime.strptime(item, "%Y-%m-%d %H:%M:%S"))

        if len(time_list) == 0:
            last_change_db = '-'
        else:
            last_change_db = max(time_list)
            last_change_db = last_change_db.strftime('%d-%m-%Y %H:%M:%S')

        return last_change_db

    def calc_acc_count(self) -> int:
        """
        Counts the number of accounts.

        :return: Return number of accounts
        """
        acc_count = self.cur.execute(
            "SELECT count(*) FROM account_information").fetchall()[0][0]
        return acc_count

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        close = show_msg(title='Предупреждение',
                         top_text='Все несохраненные изменения будут потеряны',
                         bottom_text='Все равно выйти?',
                         window_type='warning',
                         buttons='yes_no')
        if close == QtWidgets.QMessageBox.Yes:
            if self.buffer is not None:
                self.buffer.clear()
            self.cur.close()
            self.conn.close()
            a0.accept()
        else:
            a0.ignore()
