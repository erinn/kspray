import logging
import sys
from time import sleep

from PySide6.QtCore import (
    QCoreApplication,
    QIODevice,
    QObject,
    QSettings,
    QUrl,
    QUrlQuery,
)
from PySide6 import QtNetwork
from PySide6.QtSerialPort import QSerialPort
from ksync import KMessage

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class Console(QObject):
    """ """

    def __init__(self, parent=None):
        """Initializer."""
        super().__init__(parent)
        self.settings = QSettings()
        self.serial_port = None
        self.open_serial_port()

        self.request = QtNetwork.QNetworkRequest()
        self.url = QUrl(
            f"https://caltopo.com/api/v1/position/report/{self.settings.value('api_key')}"
        )
        self.nam = QtNetwork.QNetworkAccessManager()

        self.connect_signals_slots()

    def connect_signals_slots(self) -> None:
        """
        Conenct the signals to the slots.

        Returns:

        """
        self.nam.finished.connect(self.handle_response)
        self.serial_port.readyRead.connect(self.parse_serial_data)

    def handle_response(self, reply: QtNetwork.QNetworkReply) -> None:
        """
        Handle the response to a QTNetworkAccessManager action
        Returns:

        """
        logger.debug("Checking response from %s server.", self.url.toString())
        error = reply.error()

        if error == QtNetwork.QNetworkReply.NetworkError.NoError:

            bytes_string = reply.readAll()
            logger.debug("Reply: %s", str(bytes_string, "utf-8"))

        else:
            logger.info("Error occurred: %s, %s", error, reply.errorString())

    def open_serial_port(self) -> None:
        """
        Open the QSerialport object for use in the program.
        """
        baud_rate = {
            "4800": QSerialPort.BaudRate.Baud4800,
            "9600": QSerialPort.BaudRate.Baud9600,
            "19200": QSerialPort.BaudRate.Baud19200,
        }

        data_bits = {
            "8": QSerialPort.DataBits.Data8,
            "7": QSerialPort.DataBits.Data7,
            "6": QSerialPort.DataBits.Data6,
            "5": QSerialPort.DataBits.Data5,
        }

        flow_control = {
            "None": QSerialPort.FlowControl.NoFlowControl,
            "RTS/CTS": QSerialPort.FlowControl.HardwareControl,
            "XON/XOFF": QSerialPort.FlowControl.SoftwareControl,
        }
        parity = {
            "None": QSerialPort.Parity.NoParity,
            "Even": QSerialPort.Parity.EvenParity,
            "Odd": QSerialPort.Parity.OddParity,
            "Mark": QSerialPort.Parity.MarkParity,
            "Space": QSerialPort.Parity.SpaceParity,
        }

        stop_bits = {
            "1": QSerialPort.StopBits.OneStop,
            "1.5": QSerialPort.StopBits.OneAndHalfStop,
            "2": QSerialPort.StopBits.TwoStop,
        }

        self.serial_port = QSerialPort(self.settings.value("default_port"))
        self.settings.beginGroup(self.settings.value("default_port"))
        self.serial_port.setBaudRate(
            baud_rate[self.settings.value("baud_rate", defaultValue="9600")]
        )
        self.serial_port.setParity(
            parity[self.settings.value("parity", defaultValue="None")]
        )
        self.serial_port.setDataBits(
            data_bits[self.settings.value("data_bits", defaultValue="8")]
        )
        self.serial_port.setStopBits(
            stop_bits[self.settings.value("stop_bits", defaultValue="2")]
        )
        self.serial_port.setFlowControl(
            flow_control[self.settings.value("flow_control", defaultValue="None")]
        )
        self.settings.endGroup()

        if self.serial_port.open(QIODevice.OpenModeFlag.ReadWrite):
            logger.info("Serial Port %s opened.", self.serial_port.portName())
            return None
        else:
            logger.info(
                "Unable to open serial port due to error: %s", self.serial_port.error()
            )

            QCoreApplication.quit()

    def parse_serial_data(self):
        """

        Returns:

        """
        stx = b"\x02"
        etx = b"\x03"

        # Give the serial port time to push data.
        sleep(1)

        # Move from QByteArray to python bytes.
        binary_line = self.serial_port.readAll().data()

        logger.debug("Raw binary line received: %s", binary_line)

        lines = binary_line.strip(stx).strip(etx).splitlines()

        for line in lines:
            logger.debug("Parsing binary line %s", line)
            if line.startswith(b"$PKLSH"):
                k = KMessage(line)
                self.send_to_caltopo(k)

    def send_to_caltopo(self, fleetsync_message: KMessage):
        """
        Format the data and send it to the CalTopo API.

        Args:
            fleetsync_message:

        Returns:

        """
        logger.debug("Sending data to URL: %s", self.url.toString())

        query = QUrlQuery()
        query.addQueryItem(
            "id", f"{fleetsync_message.fleet_id}-{fleetsync_message.device_id}"
        )
        query.addQueryItem("lat", str(fleetsync_message.nmea_message.lat))
        query.addQueryItem("lng", str(fleetsync_message.nmea_message.lon))

        self.url.setQuery(query.query())
        self.request.setUrl(self.url)
        self.nam.get(self.request)


if __name__ == "__main__":
    app = QCoreApplication(sys.argv)
    app.setApplicationName("KSpray")
    app.setOrganizationName("SARStats")
    app.setOrganizationDomain("sarstats.com")
    c = Console()
    sys.exit(app.exec())
