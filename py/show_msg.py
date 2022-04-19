from PyQt5.QtWidgets import QMessageBox
from PyQt5 import QtGui


def show_msg(title: str = None,
             window_icon: str = ':/resource/image/key.ico',
             top_text: str = None,
             bottom_text: str = None,
             detailed_text: str = None,
             window_type: str = None,
             buttons: str = None) -> int:
    """
    Creates a window with parameters and returns the result of the work.

    :param title: window title
    :param window_icon: path to the displayed window icon
    :param top_text: text at the top of the window
    :param bottom_text: text at the bottom of the window
    :param detailed_text: expandable text
    :param window_type: type of the displayed window
    (information, warning, critical)
    :param buttons: type of displayed buttons (yes_no, yes, ok)
    :return: status after closing the window
    """
    msg = QMessageBox()

    if title is not None:
        msg.setWindowTitle(title)

    msg_icon = QtGui.QIcon()
    msg_icon.addPixmap(QtGui.QPixmap(window_icon))
    msg.setWindowIcon(msg_icon)

    if top_text is not None:
        msg.setText(top_text)

    if bottom_text is not None:
        msg.setInformativeText(bottom_text)

    if detailed_text is not None:
        msg.setDetailedText(detailed_text)

    if window_type is not None:
        if window_type == 'information':
            msg.setIcon(QMessageBox.Information)
        elif window_type == 'warning':
            msg.setIcon(QMessageBox.Warning)
        elif window_type == 'critical':
            msg.setIcon(QMessageBox.Critical)
        else:
            raise Exception("show_msg() => Error 'windows_type' value.")

    if buttons is not None:
        if buttons == 'yes_no':
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        elif buttons == 'yes':
            msg.setStandardButtons(QMessageBox.Yes)
        elif buttons == 'ok':
            msg.setStandardButtons(QMessageBox.Ok)
        else:
            raise Exception("show_msg() => Error 'buttons' value.")

    result = msg.exec_()

    return result
