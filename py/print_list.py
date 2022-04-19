from PyQt5 import QtCore, QtGui, QtPrintSupport


class PrintList:
    def __init__(self):
        self.printer = QtPrintSupport.QPrinter()
        self._painter = QtGui.QPainter()
        self._headerRowHeight = int()
        self._footerRowHeight = int()
        self._currentPageHeight = int()
        self.headerFont = QtGui.QFont("Arial", pointSize=10,
                                      weight=QtGui.QFont.Bold)
        self.bodyFont = QtGui.QFont("Arial", pointSize=10)
        self.footerFont = QtGui.QFont("Arial", pointSize=9, italic=True)
        self.headerFlags = QtCore.Qt.AlignHCenter | QtCore.Qt.TextWordWrap
        self.bodyFlags = QtCore.Qt.TextWordWrap
        self.footerFlags = QtCore.Qt.AlignHCenter | QtCore.Qt.TextWordWrap
        color = QtGui.QColor(QtCore.Qt.black)
        self.headerPen = QtGui.QPen(color, 2)
        self.bodyPen = QtGui.QPen(color, 1)
        self.margin = 5
        self._reset_data()

    def _reset_data(self):
        self.headers = None
        self.columnWidths = None
        self.data = None
        self._brush = QtCore.Qt.NoBrush
        self._currentRowHeight = 0
        self._currentPageHeight = 0
        self._headerRowHeight = 0
        self._footerRowHeight = 0
        self._currentPageNumber = 1
        self._painter = None

    def print_data(self):
        self._painter = QtGui.QPainter()
        self._painter.begin(self.printer)
        self._painter.setBrush(self._brush)
        if self._headerRowHeight == 0:
            self._painter.setFont(self.headerFont)
            self._headerRowHeight = self._calculate_row_height(self.columnWidths,
                                                               self.headers)
        if self._footerRowHeight == 0:
            self._painter.setFont(self.footerFont)
            self._footerRowHeight = self._calculate_row_height(
                [self.printer.width()], "Страница")
        for i in range(len(self.data)):
            height = self._calculate_row_height(self.columnWidths, self.data[i])
            if self._currentPageHeight + height > self.printer.height() -\
                    self._footerRowHeight - 2 * self.margin:
                self._print_footer_row()
                self._currentPageHeight = 0
                self._currentPageNumber += 1
                self.printer.newPage()
            if self._currentPageHeight == 0:
                self._painter.setPen(self.headerPen)
                self._painter.setFont(self.headerFont)
                self.print_row(self.columnWidths, self.headers,
                               self._headerRowHeight, self.headerFlags)
                self._painter.setPen(self.bodyPen)
                self._painter.setFont(self.bodyFont)
            self.print_row(self.columnWidths, self.data[i],
                           height, self.bodyFlags)
        self._print_footer_row()
        self._painter.end()
        self._reset_data()

    def _calculate_row_height(self, widths, cell_data):
        height = 0
        for i in range(len(widths)):
            r = self._painter.boundingRect(0, 0, widths[i] - 2 * self.margin,
                                           50, QtCore.Qt.TextWordWrap,
                                           str(cell_data[i]))
            h = r.height() + 2 * self.margin
            if height < h:
                height = h
        return height

    def print_row(self, widths, cell_data, height, flags):
        x = 0
        for i in range(len(widths)):
            self._painter.drawText(x + self.margin,
                                   self._currentPageHeight + self.margin,
                                   widths[i] - self.margin,
                                   height - 2 * self.margin,
                                   flags, str(cell_data[i]))
            self._painter.drawRect(x, self._currentPageHeight, widths[i], height)
            x += widths[i]
        self._currentPageHeight += height

    def _print_footer_row(self):
        self._painter.setFont(self.footerFont)
        self._painter.drawText(self.margin,
                               self.printer.height() - self._footerRowHeight
                               - self.margin,
                               self.printer.width() - 2 * self.margin,
                               self._footerRowHeight - 2 * self.margin,
                               self.footerFlags,
                               "Страница" + str(self._currentPageNumber))
