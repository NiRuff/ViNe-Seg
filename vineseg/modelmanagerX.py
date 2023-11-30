import sys
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QLabel, QWidget, QTableWidgetItem, QHeaderView, QVBoxLayout, \
    QTableView, QHBoxLayout, QProgressBar, QAbstractItemView, QPushButton
import os
import json
import urllib.request
import shutil
import zipfile

# import logging as logging
# logging.basicConfig(level=logging.INFO, format='# %(asctime)s %(levelname)s:%(message)s')

default_url = "http://vineseg.isyn-mainz.de/"
script_dir = os.path.dirname(__file__)
manifest_path = os.path.join(script_dir, "CASCADE_models/MANIFEST.json")


class ModelWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Model Manager")

        self.initUI(self.window())
        self.load_manifests()
        self.compare_manifests()
        self.setup_table()

    def initUI(self, MainWindow):
        MainWindow.setObjectName("ModelManagerWindow")
        MainWindow.resize(700, 300)
        MainWindow.setMinimumWidth(700)

        self.horizontalLayout_2 = QHBoxLayout(MainWindow)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.tableWidget = QtWidgets.QTableWidget(MainWindow)
        self.tableWidget.setObjectName(u"tableWidget")
        self.tableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tableWidget.setProperty("showDropIndicator", False)

        self.verticalLayout.addWidget(self.tableWidget)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.label = QLabel(MainWindow)
        self.label.setObjectName(u"label")

        self.verticalLayout_2.addWidget(self.label)

        self.progressBar = QProgressBar(MainWindow)
        self.progressBar.setObjectName(u"progressBar")
        self.progressBar.setValue(0)

        self.verticalLayout_2.addWidget(self.progressBar)
        self.progressBar.hide()

        self.horizontalLayout.addLayout(self.verticalLayout_2)

        self.pushButton = QPushButton(MainWindow)
        self.pushButton.setObjectName(u"pushButton")
        self.pushButton.setMaximumWidth(150)
        self.pushButton.setEnabled(False)
        self.pushButton.setText("Select a Model")

        self.horizontalLayout.addWidget(self.pushButton)

        self.verticalLayout.addLayout(self.horizontalLayout)

        self.horizontalLayout_2.addLayout(self.verticalLayout)

        self.tableWidget.setShowGrid(True)
        self.tableWidget.setWordWrap(True)
        self.tableWidget.setCornerButtonEnabled(True)
        self.tableWidget.setColumnCount(3)
        self.tableWidget.setObjectName("tableWidget")
        self.tableWidget.setRowCount(0)
        self.tableWidget.horizontalHeader().setVisible(True)
        self.tableWidget.setHorizontalHeaderLabels(["Model Name", "Description", "Status"])
        self.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tableWidget.verticalHeader().setVisible(False)
        self.tableWidget.setSelectionBehavior(QtWidgets.QTableView.SelectRows)
        self.tableWidget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tableWidget.itemSelectionChanged.connect(self.selection_changed)

    def load_manifests(self):
        with open(manifest_path, 'r') as f:
            self.local_manifest = json.load(f)
        with urllib.request.urlopen(default_url + "MANIFEST_CASCADE.json") as url:
            self.online_manifest = json.loads(url.read().decode())

    def compare_manifests(self):
        self.model_list = []
        # check if default model is installed
        if next((item for item in self.local_manifest["installed"] if
                 item["name"] == self.online_manifest["default"]["name"]), None):
            self.online_manifest["default"]["status"] = "installed"
            self.model_list.append(self.online_manifest["default"])
        else:
            self.online_manifest["default"]["status"] = "available"
            self.model_list.append(self.online_manifest["default"])

        # check if online models are installed
        for model in self.online_manifest["available"]:
            if next((item for item in self.local_manifest["installed"] if item["name"] == model["name"]), None):
                model["status"] = "installed"
                self.model_list.append(model)
            else:
                model["status"] = "available"
                self.model_list.append(model)

    def setup_table(self):
        self.tableWidget.setRowCount(len(self.model_list))
        i = 0
        for model in self.model_list:
            self.tableWidget.setItem(i, 0, QTableWidgetItem(model['name']))
            self.tableWidget.setItem(i, 1, QTableWidgetItem(model['description']))
            self.tableWidget.setItem(i, 2, QTableWidgetItem(model['status']))

            i += 1
        #self.tableWidget.horizontalHeader().resizeSections(QHeaderView.ResizeToContents)

    def selection_changed(self):
        self.disconnect_button()
        index = self.tableWidget.selectionModel().selectedRows(0)
        if index:
            row = index[0].row()
            model = self.model_list[row]
            if model["status"] == "installed":
                self.pushButton.setText("Remove")
                if len(self.local_manifest["installed"]) == 1:
                    self.pushButton.setEnabled(False)
                else:
                    self.pushButton.setEnabled(True)
                    self.pushButton.clicked.connect(lambda: self.uninstall_model(row))
            else:
                self.pushButton.setText("Install")
                self.pushButton.clicked.connect(lambda: self.install_model(row))
                self.pushButton.setEnabled(True)
        else:
            self.pushButton.setText("Select a Model")
            self.pushButton.setEnabled(False)

    def disconnect_button(self):
        try:
            self.pushButton.clicked.disconnect()
        except Exception:
            pass

    def install_model(self, model_index):
        # avoid duble click
        self.disconnect_button()
        self.pushButton.setEnabled(False)
        self.pushButton.setText("Installing...")

        model = self.model_list[model_index]
        # get the path of the model
        model_path = model["location"]
        model_url = model["url"]

        # check paths for download exists
        if not os.path.exists(
                os.path.join(os.path.sep, script_dir, "CASCADE_models", model_path)):
            os.makedirs(os.path.join(os.path.sep, script_dir, "CASCADE_models", model_path))

        # unhide progress bar
        self.progressBar.setValue(0)
        self.progressBar.show()

        # download model
        self.label.setText("Retrieving file 1 of 1.")
        urllib.request.urlretrieve(model_url,
                                   os.path.join(script_dir, "CASCADE_models", model_path) + ".zip", self.Handle_Progress)
        # unzip file
        my_zip = zipfile.ZipFile(os.path.join(script_dir, "CASCADE_models", model_path) + ".zip")
        storage_path = os.path.join(script_dir, "CASCADE_models", model_path)
        for file in my_zip.namelist():
            my_zip.extract(file, storage_path)
        my_zip.close()
        # remove zip file after extraction
        os.remove(os.path.join(script_dir, "CASCADE_models", model_path) + ".zip")


        # update local manifest file
        self.label.setText("Finishing up...")
        self.local_manifest["installed"].append({
            "name": model["name"],
            "location": model_path
        })


        json_string = json.dumps(self.local_manifest)
        with open(manifest_path, 'w') as outfile:
            outfile.write(json_string)

        # update model list
        self.compare_manifests()
        self.setup_table()

        self.progressBar.hide()
        self.label.setText("")
        self.selection_changed()

    def uninstall_model(self, model_index):
        self.disconnect_button()
        self.pushButton.setEnabled(False)
        self.pushButton.setText("Removing...")

        model = self.model_list[model_index]
        # get the path of the model
        model_path = model["location"]
        model_dir = os.path.join(os.path.sep, script_dir, "CASCADE_models", model_path)
        try:
            shutil.rmtree(model_dir)
        except OSError as e:
            print("Error: %s : %s" % (model_dir, e.strerror))
            self.pushButton.setText("failed")

        # remove model from local manifest
        for i in range(len(self.local_manifest["installed"])):
            if self.local_manifest["installed"][i]['name'] == model["name"]:
                del self.local_manifest["installed"][i]
                break
        json_string = json.dumps(self.local_manifest)
        with open(manifest_path, 'w') as outfile:
            outfile.write(json_string)

        # update model list
        self.compare_manifests()
        self.setup_table()
        self.selection_changed()

    def Handle_Progress(self, blocknum, blocksize, totalsize):
        # calculate the progress
        readed_data = blocknum * blocksize

        if totalsize > 0:
            download_percentage = readed_data * 100 / totalsize
            self.progressBar.setValue(download_percentage)
            QtWidgets.QApplication.processEvents()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    mainWin = ModelWindow()
    mainWin.show()
    sys.exit(app.exec_())
