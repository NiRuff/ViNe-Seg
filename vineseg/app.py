# -*- coding: utf-8 -*-

import functools
import numpy as np
import math
import os
import os.path as osp
import re
import json
import webbrowser
from PIL import Image, ImageEnhance
import imageio
import pandas as pd

import imgviz
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QSlider, QLabel
from qtpy import QtCore
from qtpy.QtCore import Qt
from qtpy import QtGui
from qtpy import QtWidgets

from . import __appname__
from . import PY2
from . import utils
from .config import get_config
from .label_file import LabelFile
from .label_file import LabelFileError
from .logger import logger
from .shape import Shape
from .widgets import BrightnessContrastDialog
from .widgets import Canvas
from .widgets import FileDialogPreview
from .widgets import LabelDialog
from .widgets import LabelListWidget
from .widgets import LabelListWidgetItem
from .widgets import ToolBar
from .widgets import UniqueLabelQListWidget
from .widgets import ZoomWidget
from shapely.geometry import Polygon
from .utils import shape_to_mask
from .traces.tracemanager import tracesForImage
from .traces.dff import dff_calc
from .spike_detection import run_CASCADE
from . import modelmanager
from . import modelmanagerX
from .cascade2p import checks

import sys
from .ai_pipeline.vine_seg.utils import predict, get_vineseg_list

from multiprocessing import Pool
from itertools import repeat

# FIXME
# - [medium] Set max zoom value to something big enough for FitWidth/Window

# TODO(unknown):
# - Zoom is too "steppy".


LABEL_COLORMAP = imgviz.label_colormap()
currDirPath = ""


class MainWindow(QtWidgets.QMainWindow):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = 0, 1, 2

    def __init__(
            self,
            config=None,
            filename=None,
            output=None,
            output_file=None,
            output_dir=None,
    ):
        if output is not None:
            logger.warning(
                "argument output is deprecated, use output_file instead"
            )
            if output_file is None:
                output_file = output

        # see vineseg/config/default_config.yaml for valid configuration
        if config is None:
            config = get_config()
            print(config)
        self._config = config
        self.currentModel = None
        self.currentModelTraceX = None
        self.micModeOn = False
        self.originalImageFile = None

        # set default shape colors
        Shape.line_color = QtGui.QColor(*self._config["shape"]["line_color"])
        Shape.fill_color = QtGui.QColor(*self._config["shape"]["fill_color"])
        Shape.select_line_color = QtGui.QColor(
            *self._config["shape"]["select_line_color"]
        )
        Shape.select_fill_color = QtGui.QColor(
            *self._config["shape"]["select_fill_color"]
        )
        Shape.vertex_fill_color = QtGui.QColor(
            *self._config["shape"]["vertex_fill_color"]
        )
        Shape.hvertex_fill_color = QtGui.QColor(
            *self._config["shape"]["hvertex_fill_color"]
        )

        # Set point size from config file
        Shape.point_size = self._config["shape"]["point_size"]

        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)

        # Whether we need to save or not.
        self.dirty = False

        self._noSelectionSlot = False

        self._copied_shapes = None

        # Main widgets and related state.
        self.labelDialog = LabelDialog(
            parent=self,
            labels=self._config["labels"],
            sort_labels=self._config["sort_labels"],
            show_text_field=self._config["show_label_text_field"],
            completion=self._config["label_completion"],
            fit_to_content=self._config["fit_to_content"],
            flags=self._config["label_flags"],
        )

        self.labelList = LabelListWidget()
        self.lastOpenDir = None
        try:
            from tensorflow.version import VERSION
            self.cascade_enabled = True
        except ImportError:
            print("Setup for CASCADE not given\nVisit our github documentary for "
                  "specifications about how to install ViNe-Seg with CASCADE.")
            self.cascade_enabled = False

        self.flag_dock = self.flag_widget = None
        self.flag_dock = QtWidgets.QDockWidget(self.tr("Flags"), self)
        self.flag_dock.setObjectName("Flags")
        self.flag_widget = QtWidgets.QListWidget()
        if config["flags"]:
            self.loadFlags({k: False for k in config["flags"]})
        self.flag_dock.setWidget(self.flag_widget)
        self.flag_widget.itemChanged.connect(self.setDirty)

        self.labelList.itemSelectionChanged.connect(self.labelSelectionChanged)
        self.labelList.itemDoubleClicked.connect(self.editLabel)
        self.labelList.itemChanged.connect(self.labelItemChanged)
        self.labelList.itemDropped.connect(self.labelOrderChanged)
        self.shape_dock = QtWidgets.QDockWidget(
            self.tr("Polygon Labels"), self
        )
        self.shape_dock.setObjectName("Labels")
        self.shape_dock.setWidget(self.labelList)

        self.uniqLabelList = UniqueLabelQListWidget()
        self.uniqLabelList.setToolTip(
            self.tr(
                "Select label to start annotating for it. "
                "Press 'Esc' to deselect."
            )
        )
        if self._config["labels"]:
            for label in self._config["labels"]:
                item = self.uniqLabelList.createItemFromLabel(label)
                self.uniqLabelList.addItem(item)
                rgb = self._get_rgb_by_label(label)
                self.uniqLabelList.setItemLabel(item, label, rgb)
        self.label_dock = QtWidgets.QDockWidget(self.tr(u"Label List"), self)
        self.label_dock.setObjectName(u"Label List")
        self.label_dock.setWidget(self.uniqLabelList)

        self.fileSearch = QtWidgets.QLineEdit()
        self.fileSearch.setPlaceholderText(self.tr("Search Filename"))
        self.fileSearch.textChanged.connect(self.fileSearchChanged)
        self.fileListWidget = QtWidgets.QListWidget()
        self.fileListWidget.itemSelectionChanged.connect(
            self.fileSelectionChanged
        )
        fileListLayout = QtWidgets.QVBoxLayout()
        fileListLayout.setContentsMargins(0, 0, 0, 0)
        fileListLayout.setSpacing(0)
        fileListLayout.addWidget(self.fileSearch)
        fileListLayout.addWidget(self.fileListWidget)
        self.file_dock = QtWidgets.QDockWidget(self.tr(u"File List"), self)
        self.file_dock.setObjectName(u"Files")
        fileListWidget = QtWidgets.QWidget()
        fileListWidget.setLayout(fileListLayout)
        self.file_dock.setWidget(fileListWidget)

        self.zoomWidget = ZoomWidget()
        self.setAcceptDrops(True)

        self.l1 = QLabel("Adjust here before\n manually editing shapes.\nConfidence-Requirement(%): 50")
        self.l1.setAlignment(Qt.AlignCenter)
        fileListLayout.addWidget(self.l1)

        self.sl = QSlider(Qt.Horizontal)
        self.sl.setMinimum(0)
        self.sl.setMaximum(100)
        self.sl.setValue(50)
        self.sl.setTickPosition(QSlider.TicksBelow)
        self.sl.setTickInterval(1)
        self.sl.setEnabled(False)

        fileListLayout.addWidget(self.sl)
        self.sl.valueChanged.connect(self.valuechange)
        self.sl.sliderReleased.connect(self.valueapply)
        # self.setLayout(fileListLayout)
        self.setWindowTitle("ViNe-Seg")

        self.canvas = self.labelList.canvas = Canvas(
            epsilon=self._config["epsilon"],
            double_click=self._config["canvas"]["double_click"],
            num_backups=self._config["canvas"]["num_backups"],
        )
        self.canvas.zoomRequest.connect(self.zoomRequest)

        scrollArea = QtWidgets.QScrollArea()
        scrollArea.setWidget(self.canvas)
        scrollArea.setWidgetResizable(True)
        self.scrollBars = {
            Qt.Vertical: scrollArea.verticalScrollBar(),
            Qt.Horizontal: scrollArea.horizontalScrollBar(),
        }
        self.canvas.scrollRequest.connect(self.scrollRequest)

        self.canvas.newShape.connect(self.newShape)
        self.canvas.shapeMoved.connect(self.movedShape)
        # self.canvas.shapeMoved.connect(self.setDirty)
        self.canvas.selectionChanged.connect(self.shapeSelectionChanged)
        self.canvas.drawingPolygon.connect(self.toggleDrawingSensitive)

        self.setCentralWidget(scrollArea)

        features = QtWidgets.QDockWidget.DockWidgetFeatures()
        for dock in ["flag_dock", "label_dock", "shape_dock", "file_dock"]:
            if self._config[dock]["closable"]:
                features = features | QtWidgets.QDockWidget.DockWidgetClosable
            if self._config[dock]["floatable"]:
                features = features | QtWidgets.QDockWidget.DockWidgetFloatable
            if self._config[dock]["movable"]:
                features = features | QtWidgets.QDockWidget.DockWidgetMovable
            getattr(self, dock).setFeatures(features)
            if self._config[dock]["show"] is False:
                getattr(self, dock).setVisible(False)

        self.addDockWidget(Qt.RightDockWidgetArea, self.flag_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.label_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.shape_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.file_dock)

        from .utils import newIcon
        self.setWindowIcon(newIcon("icon"))

        # Actions
        action = functools.partial(utils.newAction, self)
        shortcuts = self._config["shortcuts"]
        quit = action(
            self.tr("&Quit"),
            self.close,
            shortcuts["quit"],
            "quit",
            self.tr("Quit application"),
        )
        open_ = action(
            self.tr("&Open"),
            self.openFile,
            shortcuts["open"],
            "open",
            self.tr("Open image or label file"),
        )
        opendir = action(
            self.tr("&Open Dir"),
            self.openDirDialog,
            shortcuts["open_dir"],
            "open",
            self.tr(u"Open Dir"),
        )
        openNextImg = action(
            self.tr("&Next Image"),
            self.openNextImg,
            shortcuts["open_next"],
            "next",
            self.tr(u"Open next (hold Ctl+Shift to copy labels)"),
            enabled=False,
        )
        openPrevImg = action(
            self.tr("&Prev Image"),
            self.openPrevImg,
            shortcuts["open_prev"],
            "prev",
            self.tr(u"Open prev (hold Ctl+Shift to copy labels)"),
            enabled=False,
        )
        save = action(
            self.tr("&Save"),
            self.saveFile,
            shortcuts["save"],
            "save",
            self.tr("Save labels to file"),
            enabled=False,
        )
        refresh = action(
            self.tr("&Refresh"),
            self.refresh,
            None,
            "refresh",
            self.tr("Refresh Directory and calculate Mean Image"),
            enabled=False,
        )
        saveAs = action(
            self.tr("&Save As"),
            self.saveFileAs,
            shortcuts["save_as"],
            "save-as",
            self.tr("Save labels to a different file"),
            enabled=False,
        )

        deleteFile = action(
            self.tr("&Delete File"),
            self.deleteFile,
            shortcuts["delete_file"],
            "delete",
            self.tr("Delete current label file"),
            enabled=False,
        )

        loadPolygons = action(
            self.tr("&Load Polygons"),
            self.loadPolygons,
            shortcuts["load_polygons"],
            "loadPolygons",
            self.tr("Load Polygons for current file"),
            enabled=False,
        )

        changeOutputDir = action(
            self.tr("&Change Output Dir"),
            slot=self.changeOutputDirDialog,
            shortcut=shortcuts["save_to"],
            icon="open",
            tip=self.tr(u"Change where annotations are loaded/saved"),
        )

        saveAuto = action(
            text=self.tr("Save &Automatically"),
            slot=lambda x: self.actions.saveAuto.setChecked(x),
            icon="save",
            tip=self.tr("Save automatically"),
            checkable=True,
            enabled=True,
        )
        saveAuto.setChecked(self._config["auto_save"])

        saveWithImageData = action(
            text="Save With Image Data",
            slot=self.enableSaveImageWithData,
            tip="Save image data in label file",
            checkable=True,
            checked=self._config["store_data"],
        )

        close = action(
            "&Close",
            self.closeFile,
            shortcuts["close"],
            "close",
            "Close current file",
        )

        toggle_keep_prev_mode = action(
            self.tr("Keep Previous Annotation"),
            self.toggleKeepPrevMode,
            shortcuts["toggle_keep_prev_mode"],
            None,
            self.tr('Toggle "keep pevious annotation" mode'),
            checkable=True,
        )
        toggle_keep_prev_mode.setChecked(self._config["keep_prev"])

        createMode = action(
            self.tr("Create Polygons"),
            lambda: self.toggleDrawMode(False, createMode="polygon"),
            shortcuts["create_polygon"],
            "objects",
            self.tr("Start drawing polygons"),
            enabled=False,
        )
        createRectangleMode = action(
            self.tr("Create Rectangle"),
            lambda: self.toggleDrawMode(False, createMode="rectangle"),
            shortcuts["create_rectangle"],
            "objects",
            self.tr("Start drawing rectangles"),
            enabled=False,
        )
        createCircleMode = action(
            self.tr("Create Circle"),
            lambda: self.toggleDrawMode(False, createMode="circle"),
            shortcuts["create_circle"],
            "objects",
            self.tr("Start drawing circles"),
            enabled=False,
        )
        createLineMode = action(
            self.tr("Create Line"),
            lambda: self.toggleDrawMode(False, createMode="line"),
            shortcuts["create_line"],
            "objects",
            self.tr("Start drawing lines"),
            enabled=False,
        )
        createPointMode = action(
            self.tr("Create Point"),
            lambda: self.toggleDrawMode(False, createMode="point"),
            shortcuts["create_point"],
            "objects",
            self.tr("Start drawing points"),
            enabled=False,
        )
        createLineStripMode = action(
            self.tr("Create LineStrip"),
            lambda: self.toggleDrawMode(False, createMode="linestrip"),
            shortcuts["create_linestrip"],
            "objects",
            self.tr("Start drawing linestrip. Ctrl+LeftClick ends creation."),
            enabled=False,
        )
        editMode = action(
            self.tr("Edit Polygons"),
            self.setEditMode,
            shortcuts["edit_polygon"],
            "edit",
            self.tr("Move and edit the selected polygons"),
            enabled=False,
        )

        delete = action(
            self.tr("Delete Polygons"),
            self.deleteSelectedShape,
            shortcuts["delete_polygon"],
            "cancel",
            self.tr("Delete the selected polygons"),
            enabled=False,
        )
        duplicate = action(
            self.tr("Duplicate Polygons"),
            self.duplicateSelectedShape,
            shortcuts["duplicate_polygon"],
            "copy",
            self.tr("Create a duplicate of the selected polygons"),
            enabled=False,
        )
        copy = action(
            self.tr("Copy Polygons"),
            self.copySelectedShape,
            shortcuts["copy_polygon"],
            "copy_clipboard",
            self.tr("Copy selected polygons to clipboard"),
            enabled=False,
        )
        paste = action(
            self.tr("Paste Polygons"),
            self.pasteSelectedShape,
            shortcuts["paste_polygon"],
            "paste",
            self.tr("Paste copied polygons"),
            enabled=False,
        )
        undoLastPoint = action(
            self.tr("Undo last point"),
            self.canvas.undoLastPoint,
            shortcuts["undo_last_point"],
            "undo",
            self.tr("Undo last drawn point"),
            enabled=False,
        )
        removePoint = action(
            text="Remove Selected Point",
            slot=self.removeSelectedPoint,
            shortcut=shortcuts["remove_selected_point"],
            icon="edit",
            tip="Remove selected point from polygon",
            enabled=False,
        )

        undo = action(
            self.tr("Undo"),
            self.undoShapeEdit,
            shortcuts["undo"],
            "undo",
            self.tr("Undo last add and edit of shape"),
            enabled=False,
        )

        hideAll = action(
            self.tr("&Hide\nPolygons"),
            functools.partial(self.togglePolygons, False),
            icon="eye",
            tip=self.tr("Hide all polygons"),
            enabled=False,
        )
        showAll = action(
            self.tr("&Show\nPolygons"),
            functools.partial(self.togglePolygons, True),
            icon="eye",
            tip=self.tr("Show all polygons"),
            enabled=False,
        )

        help = action(
            self.tr("&Tutorial"),
            self.tutorial,
            icon="help",
            tip=self.tr("Show tutorial page"),
        )

        autoseg = action(
            self.tr("&ViNe-Seg"),
            self.autosegmentation,
            icon="ViNeSeg",
            tip=self.tr("Run ViNe-Seg Segmentation Pipeline"),
        )

        micMode = action(
            self.tr("&Microscope Mode"),
            self.microscope,
            icon="microscope",
            tip=self.tr("Run ViNe-Seg while waiting for microscope output"),
        )

        showmodelmanager = action(
            self.tr("ViNe-Seg Model Manager"),
            self.popup_model_manager,
            # icon="ViNeSeg",
            tip=self.tr("Open Model Manager"),
        )

        addLocalModel = action(
            self.tr("Add Local ViNe-Seg Model"),
            self.popup_local_model_prompt,
            # icon="ViNeSeg",
            tip=self.tr("Add locally trained model"),
        )

        showmodelmanagerX = action(
            self.tr("CASCADE Model Manager"),
            self.popup_model_managerX,
            # icon="ViNeSeg",
            tip=self.tr("Open Model Manager"),
        )

        startTraceExtraction = action(
            self.tr("Extract Traces"),
            self.start_trace_extraction,
            icon="curve",
            tip=self.tr("Extract fluorescence traces"),
        )

        startCASCADE = action(
            self.tr("CASCADE Spike Inference"),
            self.start_CASCADE,
            icon="curveBin",
            tip=self.tr("Start CASCADE Spike Inference"),
        )

        zoom = QtWidgets.QWidgetAction(self)
        zoom.setDefaultWidget(self.zoomWidget)
        self.zoomWidget.setWhatsThis(
            str(
                self.tr(
                    "Zoom in or out of the image. Also accessible with "
                    "{} and {} from the canvas."
                )
            ).format(
                utils.fmtShortcut(
                    "{},{}".format(shortcuts["zoom_in"], shortcuts["zoom_out"])
                ),
                utils.fmtShortcut(self.tr("Ctrl+Wheel")),
            )
        )
        self.zoomWidget.setEnabled(False)

        zoomIn = action(
            self.tr("Zoom &In"),
            functools.partial(self.addZoom, 1.1),
            shortcuts["zoom_in"],
            "zoom-in",
            self.tr("Increase zoom level"),
            enabled=False,
        )
        zoomOut = action(
            self.tr("&Zoom Out"),
            functools.partial(self.addZoom, 0.9),
            shortcuts["zoom_out"],
            "zoom-out",
            self.tr("Decrease zoom level"),
            enabled=False,
        )
        zoomOrg = action(
            self.tr("&Original size"),
            functools.partial(self.setZoom, 100),
            shortcuts["zoom_to_original"],
            "zoom",
            self.tr("Zoom to original size"),
            enabled=False,
        )
        keepPrevScale = action(
            self.tr("&Keep Previous Scale"),
            self.enableKeepPrevScale,
            tip=self.tr("Keep previous zoom scale"),
            checkable=True,
            checked=self._config["keep_prev_scale"],
            enabled=True,
        )
        fitWindow = action(
            self.tr("&Fit Window"),
            self.setFitWindow,
            shortcuts["fit_window"],
            "fit-window",
            self.tr("Zoom follows window size"),
            checkable=True,
            enabled=False,
        )
        fitWidth = action(
            self.tr("Fit &Width"),
            self.setFitWidth,
            shortcuts["fit_width"],
            "fit-width",
            self.tr("Zoom follows window width"),
            checkable=True,
            enabled=False,
        )
        brightnessContrast = action(
            "&Brightness Contrast",
            self.brightnessContrast,
            None,
            "color",
            "Adjust brightness and contrast",
            enabled=False,
        )
        adjustMinNeuronSize = action(
            "&Adjust Min. Neuron Size",
            self.adjustMinNeuronSize,
            None,
            "min_area",
            "Adjust minimum area for neuron labeling",
            enabled=True,
        )
        adjustMaxNeuronSize = action(
            "&Adjust Max. Neuron Size",
            self.adjustMaxNeuronSize,
            None,
            "max_area",
            "Adjust maximum area for neuron labeling",
            enabled=True,
        )
        removeAberrantNeurons = action(
            "&Remove aberrant Neurons",
            self.removeAberrantNeurons,
            None,
            "remove_aberrant",
            "Remove segmented neurons deviating from defined max/min area",
            enabled=True,
        )
        changeNeuronLabels = action(
            "&Switch Labeling of neurons",
            self.switchLabelingMode,
            None,
            "switch",
            "Change between numbers and size-derived labeling",
            enabled=True,
        )
        # Group zoom controls into a list for easier toggling.
        zoomActions = (
            self.zoomWidget,
            zoomIn,
            zoomOut,
            zoomOrg,
            fitWindow,
            fitWidth,
        )
        self.zoomMode = self.FIT_WINDOW
        fitWindow.setChecked(Qt.Checked)
        self.scalers = {
            self.FIT_WINDOW: self.scaleFitWindow,
            self.FIT_WIDTH: self.scaleFitWidth,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }

        edit = action(
            self.tr("&Edit Label"),
            self.editLabel,
            shortcuts["edit_label"],
            "edit",
            self.tr("Modify the label of the selected polygon"),
            enabled=False,
        )

        fill_drawing = action(
            self.tr("Fill Drawing Polygon"),
            self.canvas.setFillDrawing,
            None,
            "color",
            self.tr("Fill polygon while drawing"),
            checkable=True,
            enabled=True,
        )
        fill_drawing.trigger()

        # Label list context menu.
        labelMenu = QtWidgets.QMenu()
        utils.addActions(labelMenu, (edit, delete))
        self.labelList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.labelList.customContextMenuRequested.connect(
            self.popLabelListMenu
        )

        # Store actions for further handling.
        self.actions = utils.struct(
            saveAuto=saveAuto,
            saveWithImageData=saveWithImageData,
            changeOutputDir=changeOutputDir,
            save=save,
            saveAs=saveAs,
            refresh=refresh,
            open=open_,
            close=close,
            deleteFile=deleteFile,
            loadPolygons=loadPolygons,
            toggleKeepPrevMode=toggle_keep_prev_mode,
            delete=delete,
            edit=edit,
            duplicate=duplicate,
            copy=copy,
            paste=paste,
            undoLastPoint=undoLastPoint,
            undo=undo,
            removePoint=removePoint,
            createMode=createMode,
            editMode=editMode,
            createRectangleMode=createRectangleMode,
            createCircleMode=createCircleMode,
            createLineMode=createLineMode,
            createPointMode=createPointMode,
            createLineStripMode=createLineStripMode,
            zoom=zoom,
            zoomIn=zoomIn,
            zoomOut=zoomOut,
            zoomOrg=zoomOrg,
            keepPrevScale=keepPrevScale,
            fitWindow=fitWindow,
            fitWidth=fitWidth,
            brightnessContrast=brightnessContrast,
            adjustMinNeuronSize=adjustMinNeuronSize,
            adjustMaxNeuronSize=adjustMaxNeuronSize,
            removeAberrantNeurons=removeAberrantNeurons,
            changeNeuronLabels=changeNeuronLabels,
            zoomActions=zoomActions,
            openNextImg=openNextImg,
            openPrevImg=openPrevImg,
            fileMenuActions=(open_, opendir, save, saveAs, close, quit),
            tool=(),
            # XXX: need to add some actions here to activate the shortcut
            editMenu=(
                edit,
                duplicate,
                copy,
                paste,
                delete,
                None,
                undo,
                undoLastPoint,
                None,
                removePoint,
                None,
                toggle_keep_prev_mode,
            ),
            # menu shown at right click
            menu=(
                createMode,
                createRectangleMode,
                createCircleMode,
                createLineMode,
                createPointMode,
                createLineStripMode,
                editMode,
                edit,
                duplicate,
                copy,
                paste,
                delete,
                undo,
                undoLastPoint,
                removePoint,
            ),
            onLoadActive=(
                close,
                createMode,
                createRectangleMode,
                createCircleMode,
                createLineMode,
                createPointMode,
                createLineStripMode,
                editMode,
                brightnessContrast,
                adjustMinNeuronSize,
                adjustMaxNeuronSize,
                removeAberrantNeurons,
            ),
            onShapesPresent=(saveAs, hideAll, showAll),
        )

        self.canvas.vertexSelected.connect(self.actions.removePoint.setEnabled)

        self.menus = utils.struct(
            file=self.menu(self.tr("&File")),
            edit=self.menu(self.tr("&Edit")),
            view=self.menu(self.tr("&View")),
            help=self.menu(self.tr("&Help")),
            autoseg=self.menu(self.tr("&Auto-Segmentation")),
            traceX=self.menu(self.tr("&Trace Extraction")),
            micMode=self.menu(self.tr("&Microscope Mode")),
            traceXModels=QtWidgets.QMenu(self.tr("Select &CASCADE Model")),
            recentFiles=QtWidgets.QMenu(self.tr("Open &Recent")),
            allModels=QtWidgets.QMenu(self.tr("Select &ViNe-Seg Model")),
            availableModels=QtWidgets.QMenu(self.tr("Download Other &Models")),
            availabletraceXModels=QtWidgets.QMenu(self.tr("Download Other &Models")),
            labelList=labelMenu,
        )

        utils.addActions(
            self.menus.file,
            (
                open_,
                openNextImg,
                openPrevImg,
                opendir,
                self.menus.recentFiles,
                save,
                saveAs,
                saveAuto,
                refresh,
                changeOutputDir,
                saveWithImageData,
                close,
                deleteFile,
                loadPolygons,
                None,
                quit,
            ),
        )
        utils.addActions(self.menus.help, (help,))
        utils.addActions(
            self.menus.autoseg,
            (
                autoseg,
                None,
                self.menus.allModels,
                showmodelmanager,
                addLocalModel
            )
        )

        if self.cascade_enabled:
            utils.addActions(
                self.menus.traceX,
                (
                    startTraceExtraction,
                    None,
                    startCASCADE,
                    None,
                    self.menus.traceXModels,
                    showmodelmanagerX
                )
            )
        else:
            utils.addActions(
                self.menus.traceX,
                (
                    startTraceExtraction,
                )
            )
        utils.addActions(
            self.menus.micMode,
            (
                micMode,
            )
        )
        utils.addActions(
            self.menus.view,
            (
                self.flag_dock.toggleViewAction(),
                self.label_dock.toggleViewAction(),
                self.shape_dock.toggleViewAction(),
                self.file_dock.toggleViewAction(),
                None,
                fill_drawing,
                None,
                hideAll,
                showAll,
                None,
                zoomIn,
                zoomOut,
                zoomOrg,
                keepPrevScale,
                None,
                fitWindow,
                fitWidth,
                None,
                brightnessContrast,
                adjustMinNeuronSize,
                adjustMaxNeuronSize,
                removeAberrantNeurons,
                changeNeuronLabels,

            ),
        )

        self.menus.file.aboutToShow.connect(self.updateFileMenu)
        self.menus.autoseg.aboutToShow.connect(self.updateAutosegmentationMenu)
        self.menus.traceX.aboutToShow.connect(self.updateTraceXMenu)

        # Custom context menu for the canvas widget:
        utils.addActions(self.canvas.menus[0], self.actions.menu)
        utils.addActions(
            self.canvas.menus[1],
            (
                action("&Copy here", self.copyShape),
                action("&Move here", self.moveShape),
            ),
        )

        self.tools = self.toolbar("Tools")
        # Menu buttons on Left
        self.actions.tool = (
            open_,
            # opendir,
            # openNextImg,
            # openPrevImg,
            save,
            refresh,
            loadPolygons,
            None,
            createMode,
            editMode,
            duplicate,
            # removed to have more space in menu
            # copy,
            # paste,
            delete,
            undo,
            brightnessContrast,
            adjustMinNeuronSize,
            adjustMaxNeuronSize,
            removeAberrantNeurons,
            changeNeuronLabels,
            None,
            zoom,
            fitWidth,
            deleteFile,
        )

        self.statusBar().showMessage(str(self.tr("%s started.")) % __appname__)
        self.statusBar().show()

        if output_file is not None and self._config["auto_save"]:
            logger.warn(
                "If `auto_save` argument is True, `output_file` argument "
                "is ignored and output filename is automatically "
                "set as IMAGE_BASENAME.json."
            )
        self.output_file = output_file
        self.output_dir = output_dir

        # Application state.
        self.image = QtGui.QImage()
        self.imagePath = None
        self.recentFiles = []
        self.allModels = []
        self.traceXModels = []
        self.availableModels = set()
        self.availabletraceXModels = set()
        self.maxRecent = 7
        self.maxModels = 10
        self.otherData = None
        self.zoom_level = 100
        self.fit_window = False
        self.zoom_values = {}  # key=filename, value=(zoom_mode, zoom_value)
        self.brightnessContrast_values = {}
        self.minMaxNeuronValues = [100, 1000]
        # self.frameRate = 30.8
        self.labelingMode = "Enumerate"  # Enumerate or Area
        self.scroll_values = {
            Qt.Horizontal: {},
            Qt.Vertical: {},
        }  # key=filename, value=scroll_value

        if filename is not None and osp.isdir(filename):
            self.importDirImages(filename, load=False)
        else:
            self.filename = filename

        if config["file_search"]:
            self.fileSearch.setText(config["file_search"])
            self.fileSearchChanged()

        # XXX: Could be completely declarative.
        # Restore application settings.
        self.micModeOn = False
        self.settings = QtCore.QSettings("ViNe-Seg", "ViNe-Seg")
        self.recentFiles = self.settings.value("recentFiles", []) or []
        self.currentModel = self.settings.value("currentModel", None) or None
        self.currentModelTraceX = self.settings.value("currentModelTraceX", None) or None
        self.labelingMode = self.settings.value("labelingMode", str) or None
        size = self.settings.value("window/size", QtCore.QSize(600, 500))
        position = self.settings.value("window/position", QtCore.QPoint(0, 0))
        state = self.settings.value("window/state", QtCore.QByteArray())
        # PyQt4 cannot handle QVariant
        if isinstance(self.recentFiles, QtCore.QVariant):
            self.recentFiles = self.recentFiles.toList()
        if isinstance(self.allModels, QtCore.QVariant):
            self.allModels = self.allModels.toList()
        if isinstance(self.traceXModels, QtCore.QVariant):
            self.traceXModels = self.traceXModels.toList()
        if isinstance(self.availableModels, QtCore.QVariant):
            self.availableModels = self.availableModels.toSet()
        if isinstance(self.availabletraceXModels, QtCore.QVariant):
            self.availabletraceXModels = self.availabletraceXModels.toList()
        if isinstance(size, QtCore.QVariant):
            size = size.toSize()
        if isinstance(position, QtCore.QVariant):
            position = position.toPoint()
        if isinstance(state, QtCore.QVariant):
            state = state.toByteArray()
        self.resize(size)
        self.move(position)
        # or simply:
        # self.restoreGeometry(settings['window/geometry']
        self.restoreState(state)

        # Populate the File menu dynamically.
        self.updateFileMenu()
        # Since loading the file may take some time,
        # make sure it runs in the background.
        if self.filename is not None:
            self.queueEvent(functools.partial(self.loadFile, self.filename))

        # Callbacks:
        self.zoomWidget.valueChanged.connect(self.paintCanvas)
        self.populateModeActions()
        self.updateAutosegmentationMenu()
        self.updateTraceXMenu()

        # self.firstStart = True
        # if self.firstStart:
        #    QWhatsThis.enterWhatsThisMode()

    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            utils.addActions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):
        toolbar = ToolBar(title)
        toolbar.setObjectName("%sToolBar" % title)
        # toolbar.setOrientation(Qt.Vertical)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            utils.addActions(toolbar, actions)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)
        return toolbar

    # Support Functions

    def noShapes(self):
        return not len(self.labelList)

    def populateModeActions(self):
        tool, menu = self.actions.tool, self.actions.menu
        self.tools.clear()
        utils.addActions(self.tools, tool)
        self.canvas.menus[0].clear()
        utils.addActions(self.canvas.menus[0], menu)
        self.menus.edit.clear()
        actions = (
            self.actions.createMode,
            self.actions.createRectangleMode,
            self.actions.createCircleMode,
            self.actions.createLineMode,
            self.actions.createPointMode,
            self.actions.createLineStripMode,
            self.actions.editMode,
        )
        utils.addActions(self.menus.edit, actions + self.actions.editMenu)

    def valuechange(self):
        conf = self.getConfidence()
        self.l1.setText("Adjust here before\n manually editing shapes.\nConfidence-Requirement (%): " + str(conf))

    def getConfidence(self):
        return self.sl.value()

    # reload polygons here
    def valueapply(self):
        conf = self.sl.value()
        self.loadPolygons()
        # now apply to drawing ROIs

    def setDirty(self):
        # Even if we autosave the file, we keep the ability to undo
        self.actions.undo.setEnabled(self.canvas.isShapeRestorable)

        if self._config["auto_save"] or self.actions.saveAuto.isChecked():
            label_file = osp.splitext(self.imagePath)[0] + ".json"
            if self.output_dir:
                label_file_without_path = osp.basename(label_file)
                label_file = osp.join(self.output_dir, label_file_without_path)
            self.saveLabels(label_file)
            return
        self.dirty = True
        self.actions.save.setEnabled(True)
        title = __appname__
        if self.filename is not None:
            title = "{} - {}*".format(title, self.filename)
        self.setWindowTitle(title)

    def setClean(self):
        self.dirty = False
        self.actions.save.setEnabled(False)
        self.actions.createMode.setEnabled(True)
        self.actions.createRectangleMode.setEnabled(True)
        self.actions.createCircleMode.setEnabled(True)
        self.actions.createLineMode.setEnabled(True)
        self.actions.createPointMode.setEnabled(True)
        self.actions.createLineStripMode.setEnabled(True)
        title = __appname__
        if self.filename is not None:
            title = "{} - {}".format(title, self.filename)
        self.setWindowTitle(title)

        if self.hasLabelFile():
            self.actions.deleteFile.setEnabled(True)
        else:
            self.actions.deleteFile.setEnabled(False)

        if self.hasJSONFile():
            self.actions.loadPolygons.setEnabled(True)
        else:
            self.actions.loadPolygons.setEnabled(False)

    def toggleActions(self, value=True):
        """Enable/Disable widgets which depend on an opened image."""
        for z in self.actions.zoomActions:
            z.setEnabled(value)
        for action in self.actions.onLoadActive:
            action.setEnabled(value)

    def queueEvent(self, function):
        QtCore.QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def resetState(self):
        self.labelList.clear()
        self.uniqLabelList.clear()
        self.filename = None
        # self.currentModel = None
        self.imagePath = None
        self.imageData = None
        self.labelFile = None
        self.otherData = None
        self.canvas.resetState()

    def currentItem(self):
        items = self.labelList.selectedItems()
        if items:
            return items[0]
        return None

    def addRecentFile(self, filename):
        if filename in self.recentFiles:
            self.recentFiles.remove(filename)
        elif len(self.recentFiles) >= self.maxRecent:
            self.recentFiles.pop()
        self.recentFiles.insert(0, filename)

    def loadInstalledModels(self, menu="vineseg"):
        if menu == "vineseg":
            self.allModels = []
        else:
            self.traceXModels = []
        # check model manifest
        script_dir = os.path.dirname(__file__)
        if menu == "vineseg":
            model_path = os.path.join(script_dir, "experiments/")
        else:
            model_path = os.path.join(script_dir, "CASCADE_models/")
        manifest_path = os.path.join(model_path, "MANIFEST.json")

        with open(manifest_path, 'r') as f:
            local_manifest = json.load(f)

        for model in local_manifest["installed"]:
            self.addModel(model["location"], menu=menu)
            self.addModel(model["location"], menu=menu)

    def addModel(self, model_name, menu):
        if menu == "vineseg":
            if model_name in self.allModels:
                self.allModels.remove(model_name)
            elif len(self.allModels) >= self.maxModels:
                self.allModels.pop()
            self.allModels.insert(0, model_name)
        else:
            if model_name in self.traceXModels:
                self.traceXModels.remove(model_name)
            elif len(self.traceXModels) >= self.maxModels:
                self.traceXModels.pop()
            self.traceXModels.insert(0, model_name)

    def addAvailableModel(self, name, url):
        self.availableModels.add((name, url))

    def addAvailableTraceXModel(self, name, url):
        self.availabletraceXModels.add((name, url))

    # Callbacks

    def undoShapeEdit(self):
        self.canvas.restoreShape()
        self.labelList.clear()
        self.loadShapes(self.canvas.shapes)
        self.actions.undo.setEnabled(self.canvas.isShapeRestorable)

    def tutorial(self):
        url = "https://github.com/wkentaro/labelme/tree/main/examples/tutorial"  # NOQA
        webbrowser.open(url)

    def microscope(self):
        self.micModeOn = True

        mbFormat = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Warning, "Microscope Output Directory",
                                         "Choose directory in which you will load your microscope's TIF images",
                                         QtWidgets.QMessageBox.Ok)
        mbFormat.exec()

        self.openDirDialog(pattern="_mean.png")
        mbFormat = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Warning, "Microscope Mode",
                                         "You are in Microscope now. Use the Refresh button after you started creating your images.",
                                         QtWidgets.QMessageBox.Ok)
        mbFormat.exec()
        self.actions.refresh.setEnabled(True)

    def autosegmentation(self):

        if not self.mayContinue():
            return

        sys.path.insert(0, './ai_pipeline')
        # from .ai_pipeline.prediction import pred_main
        # from .ai_pipeline.model import test

        self.traceProgress = QtWidgets.QProgressDialog("Autosegmentation...", "cancel", 0, 100,
                                                       self)
        self.traceProgress.setWindowModality(Qt.WindowModal)
        self.traceProgress.forceShow()
        self.traceProgress.setValue(1)

        if self.imagePath != None:

            if not self.imagePath.endswith((".png", ".tiff", "tif")):
                mbFormat = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Warning, "Unsupported file format",
                                                 "Please choose PNG, TIF or TIFF image file.",
                                                 QtWidgets.QMessageBox.Ok)
                mbFormat.exec()

            elif self.brightnessContrast_values[self.filename] != (None, None):
                img = Image.open(self.imagePath)
                if self.imagePath.endswith(".tiff"):
                    img.save(self.imagePath.replace(".tiff", ".png"))
                    img = Image.open(self.imagePath.replace(".tiff", ".png"))
                elif self.imagePath.endswith(".tif"):
                    img.save(self.imagePath.replace(".tif", ".png"))
                    img = Image.open(self.imagePath.replace(".tif", ".png"))

                im_curr = ImageEnhance.Brightness(img).enhance(self.brightnessContrast_values[self.filename][0] / 50)
                im_output = ImageEnhance.Contrast(im_curr).enhance(
                    self.brightnessContrast_values[self.filename][1] / 50)
                # tiff tif or PNG
                if self.imagePath.endswith(".png"):
                    im_output.save(osp.splitext(self.imagePath)[0] + "_b_{brightness}_c{contrast}.png".format(
                        brightness=self.brightnessContrast_values[self.filename][0],
                        contrast=self.brightnessContrast_values[self.filename][1]))
                    self.imagePath = osp.splitext(self.imagePath)[0] + "_b_{brightness}_c{contrast}.png".format(
                        brightness=self.brightnessContrast_values[self.filename][0],
                        contrast=self.brightnessContrast_values[self.filename][1])
                    self.loadFile(self.imagePath)
                elif self.imagePath.endswith(".tiff"):
                    im_output.save(osp.splitext(self.imagePath)[0] + "_b_{brightness}_c{contrast}.tiff".format(
                        brightness=self.brightnessContrast_values[self.filename][0],
                        contrast=self.brightnessContrast_values[self.filename][1]), quality=100)
                    self.imagePath = osp.splitext(self.imagePath)[0] + + "_b_{brightness}_c{contrast}.tiff".format(
                        brightness=self.brightnessContrast_values[self.filename][0],
                        contrast=self.brightnessContrast_values[self.filename][1])
                    self.loadFile(self.imagePath)
                elif self.imagePath.endswith(".tif"):
                    im_output.save(osp.splitext(self.imagePath)[0] + + "_b_{brightness}_c{contrast}.tif".format(
                        brightness=self.brightnessContrast_values[self.filename][0],
                        contrast=self.brightnessContrast_values[self.filename][1]), quality=100)
                    self.imagePath = osp.splitext(self.imagePath)[0] + + "_b_{brightness}_c{contrast}.tif".format(
                        brightness=self.brightnessContrast_values[self.filename][0],
                        contrast=self.brightnessContrast_values[self.filename][1])
                    self.loadFile(self.imagePath)

        elif self.imagePath == None:
            self.openFile()

        if self.imagePath != None:
            if not self.imagePath.endswith((".png", ".tiff", ".tif")):
                mbFormat = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Warning, "Unsupported file format",
                                                 "Please choose PNG, TIF or TIFF image file.",
                                                 QtWidgets.QMessageBox.Ok)
                mbFormat.exec()

            if self.imagePath.endswith((".png", ".tiff", "tif")):
                im_path = self.imagePath.replace("\\", "/")
                self.traceProgress.setValue(15)

                image_path = self.imagePath
                model_path = os.path.dirname(__file__).replace("\\", "/") + "/experiments/" + self.currentModel

                print(image_path, model_path)

                prediction_result = predict(image_path, model_path, plot_first=True)
                if prediction_result[0].masks == None:
                    vineseg_list = [{'shape_type': 'polygon', 'points': [], 'score': 0, 'label': 'Neuron'}]

                    mbFormat = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Warning, "No shapes detected by this model.",
                                                     "Please try another model or adapt min/max size of neuronal bodies.",
                                                     QtWidgets.QMessageBox.Ok)
                    mbFormat.exec()

                else:
                    vineseg_list = get_vineseg_list(prediction_result, min_size=int(self.minMaxNeuronValues[0] // 2),
                                                    max_size=int(self.minMaxNeuronValues[1] * 2))
                import base64

                def image_to_base64(image_path):
                    with open(image_path, "rb") as image_file:
                        # Read the file
                        data = image_file.read()

                        # Encode as base64
                        encoded = base64.b64encode(data)
                        return encoded.decode('utf-8')

                imageData = image_to_base64(image_path)
                # print("imageData", imageData)

                json_out = {"version": "4.5.13", "flags": {}, "shapes": vineseg_list, "imagePath": image_path,
                            "imageData": imageData, "imageHeight": utils.img_b64_to_arr(imageData).shape[0],
                            "imageWidth": utils.img_b64_to_arr(imageData).shape[1]}
                # print(json_out)

                import shutil
                # Step 1: Get the current module's directory
                vineseg_dir = os.path.dirname(__file__)

                # Step 2: Create 'data' directory
                data_dir = os.path.join(vineseg_dir, 'data')
                os.makedirs(data_dir, exist_ok=True)

                # Step 3: Copy the current image to the 'data' directory
                new_image_path = os.path.join(data_dir, os.path.basename(self.imagePath))

                if self.imagePath.replace("\\", "/") != new_image_path.replace("\\", "/"):
                    shutil.copy(self.imagePath, new_image_path)

                # Step 4: Modify `self.imagePath` to point to the new location
                self.imagePath = new_image_path

                import stat
                file_path = self.getJSONFile()
                self.originalImageFile = self.filename
                self.filename = file_path
                self.labelFile = file_path
                print(file_path)
                dir_path = os.path.dirname(file_path)

                # Ensure directory exists with the right permissions
                os.makedirs(dir_path, exist_ok=True)
                os.chmod(dir_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

                # If the file exists, set its permissions
                if os.path.exists(file_path):
                    os.chmod(file_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

                import tempfile

                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".json", encoding='utf-8') as tmpfile:
                    json.dump(json_out, tmpfile)
                    temp_name = tmpfile.name

                # If you want to move the temporary file to the desired location
                shutil.move(temp_name, file_path)

                self.labelingMode = "Area"
                self.traceProgress.setValue(self.traceProgress.maximum())
                self.traceProgress.close()

                # self.loadPolygons()
                self.setClean()

                if self.filename:
                    if self.filename.endswith(".json"):
                        self.updateJSON()
                        self.loadFile(self.filename, justJSON=True)

            else:
                self.traceProgress.close()

        else:
            self.traceProgress.close()
        # load again here as it sometimes doesn't execute earlier (??)
        self.loadPolygons()

    def toggleDrawingSensitive(self, drawing=True):
        """Toggle drawing sensitive.

        In the middle of drawing, toggling between modes should be disabled.
        """
        self.actions.editMode.setEnabled(not drawing)
        self.actions.undoLastPoint.setEnabled(drawing)
        self.actions.undo.setEnabled(not drawing)
        self.actions.delete.setEnabled(not drawing)

    def toggleDrawMode(self, edit=True, createMode="polygon"):
        self.canvas.setEditing(edit)
        self.canvas.createMode = createMode
        if edit:
            self.actions.createMode.setEnabled(True)
            self.actions.createRectangleMode.setEnabled(True)
            self.actions.createCircleMode.setEnabled(True)
            self.actions.createLineMode.setEnabled(True)
            self.actions.createPointMode.setEnabled(True)
            self.actions.createLineStripMode.setEnabled(True)
        else:
            if createMode == "polygon":
                self.actions.createMode.setEnabled(False)
                self.actions.createRectangleMode.setEnabled(True)
                self.actions.createCircleMode.setEnabled(True)
                self.actions.createLineMode.setEnabled(True)
                self.actions.createPointMode.setEnabled(True)
                self.actions.createLineStripMode.setEnabled(True)
            elif createMode == "rectangle":
                self.actions.createMode.setEnabled(True)
                self.actions.createRectangleMode.setEnabled(False)
                self.actions.createCircleMode.setEnabled(True)
                self.actions.createLineMode.setEnabled(True)
                self.actions.createPointMode.setEnabled(True)
                self.actions.createLineStripMode.setEnabled(True)
            elif createMode == "line":
                self.actions.createMode.setEnabled(True)
                self.actions.createRectangleMode.setEnabled(True)
                self.actions.createCircleMode.setEnabled(True)
                self.actions.createLineMode.setEnabled(False)
                self.actions.createPointMode.setEnabled(True)
                self.actions.createLineStripMode.setEnabled(True)
            elif createMode == "point":
                self.actions.createMode.setEnabled(True)
                self.actions.createRectangleMode.setEnabled(True)
                self.actions.createCircleMode.setEnabled(True)
                self.actions.createLineMode.setEnabled(True)
                self.actions.createPointMode.setEnabled(False)
                self.actions.createLineStripMode.setEnabled(True)
            elif createMode == "circle":
                self.actions.createMode.setEnabled(True)
                self.actions.createRectangleMode.setEnabled(True)
                self.actions.createCircleMode.setEnabled(False)
                self.actions.createLineMode.setEnabled(True)
                self.actions.createPointMode.setEnabled(True)
                self.actions.createLineStripMode.setEnabled(True)
            elif createMode == "linestrip":
                self.actions.createMode.setEnabled(True)
                self.actions.createRectangleMode.setEnabled(True)
                self.actions.createCircleMode.setEnabled(True)
                self.actions.createLineMode.setEnabled(True)
                self.actions.createPointMode.setEnabled(True)
                self.actions.createLineStripMode.setEnabled(False)
            else:
                raise ValueError("Unsupported createMode: %s" % createMode)
        self.actions.editMode.setEnabled(not edit)

    def setEditMode(self):
        self.toggleDrawMode(True)

    def updateFileMenu(self):
        current = self.filename

        def exists(filename):
            return osp.exists(str(filename))

        menu = self.menus.recentFiles
        menu.clear()
        files = [f for f in self.recentFiles if f != current and exists(f)]
        for i, f in enumerate(files):
            icon = utils.newIcon("labels")
            action = QtWidgets.QAction(
                icon, "&%d %s" % (i + 1, QtCore.QFileInfo(f).fileName()), self
            )
            action.triggered.connect(functools.partial(self.loadRecent, f))
            menu.addAction(action)

    def updateAutosegmentationMenu(self):

        def exists(filename):
            return osp.exists(str(filename))

        self.loadInstalledModels(menu="vineseg")
        menu = self.menus.allModels
        menu.clear()
        models = [m for m in self.allModels]

        # print(self.currentModel)

        if self.currentModel == None:
            self.setModel(models[0])
        if not os.path.exists(os.path.join(os.path.sep, os.path.dirname(__file__), "experiments", self.currentModel)):
            # print(os.path.join(os.path.sep, os.path.dirname(__file__), "experiments", self.currentModel))
            self.setModel(models[0])
        for i, m in enumerate(models):
            if m != self.currentModel:
                icon = utils.newIcon("None")
            else:
                icon = utils.newIcon("done")
            action = QtWidgets.QAction(
                icon, "&%d %s" % (i + 1, QtCore.QFileInfo(m).fileName()), self
            )
            action.triggered.connect(functools.partial(self.setModel, m))
            menu.addAction(action)

        menuAvailable = self.menus.availableModels
        menuAvailable.clear()
        modelsAvailable = [m for m in self.availableModels]

        local_models, online_models = [], []

        for m in modelsAvailable:
            if m[0] not in self.allModels:
                online_models.append(m)
            else:
                local_models.append(m)

        for i, m in enumerate(online_models):
            icon = utils.newIcon("download")
            action = QtWidgets.QAction(
                icon, "&%d %s" % (i + 1, QtCore.QFileInfo(m[0]).fileName()), self
            )
            action.triggered.connect(functools.partial(self.loadModel, m))
            menuAvailable.addAction(action)

    def updateTraceXMenu(self):

        def exists(filename):
            return osp.exists(str(filename))

        if self.cascade_enabled:
            self.loadInstalledModels(menu="CASCADE")
            menu = self.menus.traceXModels
            menu.clear()
            models = [m for m in self.traceXModels]
            if self.currentModelTraceX == None:
                self.setModelTraceX(models[0])
            if not os.path.exists(
                    os.path.join(os.path.sep, os.path.dirname(__file__), "CASCADE_models", self.currentModelTraceX)):
                self.setModelTraceX(models[0])
            for i, m in enumerate(models):
                if m != self.currentModelTraceX:
                    icon = utils.newIcon("None")
                else:
                    icon = utils.newIcon("done")
                action = QtWidgets.QAction(
                    icon, "&%d %s" % (i + 1, QtCore.QFileInfo(m).fileName()), self
                )
                action.triggered.connect(functools.partial(self.setModelTraceX, m))
                menu.addAction(action)

            menuAvailable = self.menus.availabletraceXModels
            menuAvailable.clear()
            modelsAvailable = [m for m in self.availabletraceXModels]

            local_models, online_models = [], []

            for m in modelsAvailable:
                if m[0] not in self.traceXModels:
                    online_models.append(m)
                else:
                    local_models.append(m)

            for i, m in enumerate(online_models):
                icon = utils.newIcon("download")
                action = QtWidgets.QAction(
                    icon, "&%d %s" % (i + 1, QtCore.QFileInfo(m[0]).fileName()), self
                )
                action.triggered.connect(functools.partial(self.loadModel, m))
                menuAvailable.addAction(action)

    def popLabelListMenu(self, point):
        self.menus.labelList.exec_(self.labelList.mapToGlobal(point))

    def validateLabel(self, label):
        # no validation
        if self._config["validate_label"] is None:
            return True

        for i in range(self.uniqLabelList.count()):
            label_i = self.uniqLabelList.item(i).data(Qt.UserRole)
            if self._config["validate_label"] in ["exact"]:
                if label_i == label:
                    return True
        return False

    def editLabel(self, item=None):
        if item and not isinstance(item, LabelListWidgetItem):
            raise TypeError("item must be LabelListWidgetItem type")

        if not self.canvas.editing():
            return
        if not item:
            item = self.currentItem()
        if item is None:
            return
        shape = item.shape()
        if shape is None:
            return
        # print(shape.label)
        text, flags, group_id = self.labelDialog.popUp(
            text=shape.label,
            flags=shape.flags,
            group_id=shape.group_id,
        )
        if text is None:
            return
        if not self.validateLabel(text):
            self.errorMessage(
                self.tr("Invalid label"),
                self.tr("Invalid label '{}' with validation type '{}'").format(
                    text, self._config["validate_label"]
                ),
            )
            return
        shape.label = text
        shape.flags = flags
        shape.group_id = group_id

        self._update_shape_color(shape)
        if shape.group_id is None:
            item.setText(
                '{} <font color="#{:02x}{:02x}{:02x}">●</font>'.format(
                    shape.label, *shape.fill_color.getRgb()[:3]
                )
            )
        else:
            item.setText("{} ({})".format(shape.label, shape.group_id))
        self.setDirty()
        if not self.uniqLabelList.findItemsByLabel(shape.label):
            item = QtWidgets.QListWidgetItem()
            item.setData(Qt.UserRole, shape.label)
            self.uniqLabelList.addItem(item)

    def fileSearchChanged(self):
        self.importDirImages(
            self.lastOpenDir,
            pattern=self.fileSearch.text(),
            load=False,
        )

    def fileSelectionChanged(self):
        items = self.fileListWidget.selectedItems()
        if not items:
            return
        item = items[0]

        if not self.mayContinue():
            return

        currIndex = self.imageList.index(str(item.text()))
        if currIndex < len(self.imageList):
            filename = self.imageList[currIndex]
            if filename:
                self.loadFile(filename)

    # React to canvas signals.
    def shapeSelectionChanged(self, selected_shapes):
        self._noSelectionSlot = True
        for shape in self.canvas.selectedShapes:
            shape.selected = False
        self.labelList.clearSelection()
        self.canvas.selectedShapes = selected_shapes
        for shape in self.canvas.selectedShapes:
            shape.selected = True
            item = self.labelList.findItemByShape(shape)
            self.labelList.selectItem(item)
            self.labelList.scrollToItem(item)
        self._noSelectionSlot = False
        n_selected = len(selected_shapes)
        self.actions.delete.setEnabled(n_selected)
        self.actions.duplicate.setEnabled(n_selected)
        self.actions.copy.setEnabled(n_selected)
        self.actions.edit.setEnabled(n_selected == 1)

    def addLabel(self, shape, copy=False, new=False, moved=False):
        if moved:
            # delete shape then add shape
            self.remLabels([shape])
            self.canvas.loadShapes([shape], replace=False)
        if copy and not new:
            shape.label = "Neuron manual"
            text = shape.label
        elif copy and new:
            text = shape.label
        elif shape.group_id is None:
            text = shape.label
        else:
            text = "{} ({})".format(shape.label, shape.group_id)
        label_list_item = LabelListWidgetItem(text, shape)
        self.labelList.addItem(label_list_item)
        if not self.uniqLabelList.findItemsByLabel(shape.label):
            item = self.uniqLabelList.createItemFromLabel(shape.label)
            self.uniqLabelList.addItem(item)
            rgb = self._get_rgb_by_label(shape.label)
            self.uniqLabelList.setItemLabel(item, shape.label, rgb)
        self.labelDialog.addLabelHistory(shape.label)
        for action in self.actions.onShapesPresent:
            action.setEnabled(True)

        self._update_shape_color(shape)
        label_list_item.setText(
            '{} <font color="#{:02x}{:02x}{:02x}">●</font>'.format(
                text, *shape.fill_color.getRgb()[:3]
            )
        )

    def _update_shape_color(self, shape):
        r, g, b = self._get_rgb_by_label(shape.label)
        shape.line_color = QtGui.QColor(r, g, b)
        shape.vertex_fill_color = QtGui.QColor(r, g, b)
        shape.hvertex_fill_color = QtGui.QColor(255, 255, 255)
        shape.fill_color = QtGui.QColor(r, g, b, 128)
        shape.select_line_color = QtGui.QColor(255, 255, 255)
        shape.select_fill_color = QtGui.QColor(r, g, b, 155)

    def _get_rgb_by_label(self, label):
        if self._config["shape_color"] == "auto" or self.labelingMode == "Enumerate":
            item = self.uniqLabelList.findItemsByLabel(label)[0]
            label_id = self.uniqLabelList.indexFromItem(item).row() + 1
            label_id += self._config["shift_auto_shape_color"]
            return LABEL_COLORMAP[label_id % len(LABEL_COLORMAP)]
        elif (
                self._config["shape_color"] == "manual"
                and self._config["label_colors"]
                and label in self._config["label_colors"]
        ):
            return self._config["label_colors"][label]
        elif self._config["default_shape_color"]:
            return self._config["default_shape_color"]

        return (0, 255, 0)

    def remLabels(self, shapes):
        for shape in shapes:
            item = self.labelList.findItemByShape(shape)
            self.labelList.removeItem(item)

    def loadShapes(self, shapes, replace=True, copy=False):
        self._noSelectionSlot = True
        for shape in shapes:
            self.addLabel(shape, copy=copy)
        self.labelList.clearSelection()
        self._noSelectionSlot = False
        self.canvas.loadShapes(shapes, replace=replace)

    def loadLabels(self, shapes, confidence):
        s = []
        warningDisplayed = False
        for shape in shapes:
            label = shape["label"]
            points = shape["points"]
            shape_type = shape["shape_type"]
            flags = shape["flags"]
            group_id = shape["group_id"]
            other_data = shape["other_data"]
            try:
                score = other_data["score"]
                if score * 100 < confidence:
                    continue
            except KeyError:
                if not warningDisplayed:
                    print("No confidence score given as 'score'. Displaying all polygons")
                warningDisplayed = True

            if not points:
                # skip point-empty shape
                continue

            shape = Shape(
                label=label,
                shape_type=shape_type,
                group_id=group_id,
            )
            for x, y in points:
                shape.addPoint(QtCore.QPointF(x, y))
            shape.close()

            default_flags = {}
            if self._config["label_flags"]:
                for pattern, keys in self._config["label_flags"].items():
                    if re.match(pattern, label):
                        for key in keys:
                            default_flags[key] = False
            shape.flags = default_flags
            shape.flags.update(flags)
            shape.other_data = other_data

            s.append(shape)
        self.loadShapes(s)

    def loadFlags(self, flags):
        self.flag_widget.clear()
        for key, flag in flags.items():
            item = QtWidgets.QListWidgetItem(key)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if flag else Qt.Unchecked)
            self.flag_widget.addItem(item)

    def saveLabels(self, filename):
        lf = LabelFile()

        def format_shape(s):
            # PyQt4 cannot handle QVariant
            if isinstance(s, QtCore.QVariant):
                s = s.toPyObject()

            data = s.other_data.copy()
            data.update(
                dict(
                    label=s.label.encode("utf-8") if PY2 else s.label,
                    points=[(p.x(), p.y()) for p in s.points],
                    group_id=s.group_id,
                    shape_type=s.shape_type,
                    flags=s.flags,
                )
            )
            return data

        shapes = [format_shape(item.shape()) for item in self.labelList]
        flags = {}
        for i in range(self.flag_widget.count()):
            item = self.flag_widget.item(i)
            key = item.text()
            flag = item.checkState() == Qt.Checked
            flags[key] = flag
        try:
            imagePath = osp.relpath(self.imagePath, osp.dirname(filename))
            imageData = self.imageData if self._config["store_data"] else None
            if osp.dirname(filename) and not osp.exists(osp.dirname(filename)):
                os.makedirs(osp.dirname(filename))
            lf.save(
                filename=filename,
                shapes=shapes,
                imagePath=imagePath,
                imageData=imageData,
                imageHeight=self.image.height(),
                imageWidth=self.image.width(),
                otherData=self.otherData,
                flags=flags,
            )
            self.labelFile = lf
            items = self.fileListWidget.findItems(
                self.imagePath, Qt.MatchExactly
            )
            if len(items) > 0:
                if len(items) != 1:
                    raise RuntimeError("There are duplicate files.")
                items[0].setCheckState(Qt.Checked)
            # disable allows next and previous image to proceed
            # self.filename = filename
            return True
        except LabelFileError as e:
            self.errorMessage(
                self.tr("Error saving label data"), self.tr("<b>%s</b>") % e
            )
            return False

    def duplicateSelectedShape(self):
        added_shapes = self.canvas.duplicateSelectedShapes()
        self.labelList.clearSelection()
        for shape in added_shapes:
            self.addLabel(shape, copy=True)
        self.setDirty()

    def pasteSelectedShape(self):
        self.loadShapes(self._copied_shapes, replace=False, copy=True)
        self.setDirty()

    def copySelectedShape(self):
        self._copied_shapes = [s.copy() for s in self.canvas.selectedShapes]
        self.actions.paste.setEnabled(len(self._copied_shapes) > 0)

    def labelSelectionChanged(self):
        if self._noSelectionSlot:
            return
        if self.canvas.editing():
            selected_shapes = []
            for item in self.labelList.selectedItems():
                selected_shapes.append(item.shape())
            if selected_shapes:
                self.canvas.selectShapes(selected_shapes)
            else:
                self.canvas.deSelectShape()

    def labelItemChanged(self, item):
        shape = item.shape()
        self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)

    def labelOrderChanged(self):
        self.setDirty()
        self.canvas.loadShapes([item.shape() for item in self.labelList])

    # Callback functions:

    def movedShape(self, text="Neuron manual", flags={}, group_id=None):
        for shape in self.canvas.selectedShapes:
            self.addLabel(shape, moved=True)
        self.labelList.clearSelection()
        self.actions.editMode.setEnabled(True)
        self.actions.undoLastPoint.setEnabled(False)
        self.actions.undo.setEnabled(True)
        self.setDirty()

    def newShape(self):
        """Pop-up and give focus to the label editor.
        position MUST be in global coordinates.
        """
        items = self.uniqLabelList.selectedItems()
        text = None
        if items:
            text = items[0].data(Qt.UserRole)
        flags = {}
        group_id = None
        if self._config["display_label_popup"] or not text:
            previous_text = self.labelDialog.edit.text()
            text, flags, group_id = "Neuron manual", {}, None  # self.labelDialog.popUp(text)
            # text, flags, group_id = self.labelDialog.popUp(text)
            # print(text, flags, group_id)
            # if not text:
            #    self.labelDialog.edit.setText(previous_text)

        # if text and not self.validateLabel(text):
        #     self.errorMessage(
        #         self.tr("Invalid label"),
        #         self.tr("Invalid label '{}' with validation type '{}'").format(
        #             text, self._config["validate_label"]
        #         ),
        #     )
        #     text = ""
        if text:
            self.labelList.clearSelection()
            shape = self.canvas.setLastLabel(text, flags)
            # shape = self.canvas.setLastLabel("Neuron manual", flags) # for naming them neuron manual regardless of users choice
            shape.group_id = group_id
            self.addLabel(shape, copy=True, new=True)
            self.actions.editMode.setEnabled(True)
            self.actions.undoLastPoint.setEnabled(False)
            self.actions.undo.setEnabled(True)
            self.setDirty()
        else:
            self.canvas.undoLastLine()
            self.canvas.shapesBackups.pop()

    def scrollRequest(self, delta, orientation):
        units = -delta * 0.1  # natural scroll
        bar = self.scrollBars[orientation]
        value = bar.value() + bar.singleStep() * units
        self.setScroll(orientation, value)

    def setScroll(self, orientation, value):
        self.scrollBars[orientation].setValue(value)
        self.scroll_values[orientation][self.filename] = value

    def setZoom(self, value):
        self.actions.fitWidth.setChecked(False)
        self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.MANUAL_ZOOM
        self.zoomWidget.setValue(value)
        self.zoom_values[self.filename] = (self.zoomMode, value)

    def addZoom(self, increment=1.1):
        zoom_value = self.zoomWidget.value() * increment
        if increment > 1:
            zoom_value = math.ceil(zoom_value)
        else:
            zoom_value = math.floor(zoom_value)
        self.setZoom(zoom_value)

    def zoomRequest(self, delta, pos):
        canvas_width_old = self.canvas.width()
        units = 1.1
        if delta < 0:
            units = 0.9
        self.addZoom(units)

        canvas_width_new = self.canvas.width()
        if canvas_width_old != canvas_width_new:
            canvas_scale_factor = canvas_width_new / canvas_width_old

            x_shift = round(pos.x() * canvas_scale_factor) - pos.x()
            y_shift = round(pos.y() * canvas_scale_factor) - pos.y()

            self.setScroll(
                Qt.Horizontal,
                self.scrollBars[Qt.Horizontal].value() + x_shift,
            )
            self.setScroll(
                Qt.Vertical,
                self.scrollBars[Qt.Vertical].value() + y_shift,
            )

    def setFitWindow(self, value=True):
        if value:
            self.actions.fitWidth.setChecked(False)
        self.zoomMode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjustScale()

    def setFitWidth(self, value=True):
        if value:
            self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjustScale()

    def enableKeepPrevScale(self, enabled):
        self._config["keep_prev_scale"] = enabled
        self.actions.keepPrevScale.setChecked(enabled)

    def onNewBrightnessContrast(self, qimage):
        self.canvas.loadPixmap(
            QtGui.QPixmap.fromImage(qimage), clear_shapes=False
        )

    def brightnessContrast(self, value):
        dialog = BrightnessContrastDialog(
            utils.img_data_to_pil(self.imageData),
            self.onNewBrightnessContrast,
            parent=self,
        )
        brightness, contrast = self.brightnessContrast_values.get(
            self.filename, (None, None)
        )
        if brightness is not None:
            dialog.slider_brightness.setValue(brightness)
        if contrast is not None:
            dialog.slider_contrast.setValue(contrast)
        dialog.exec_()

        brightness = dialog.slider_brightness.value()
        contrast = dialog.slider_contrast.value()
        self.brightnessContrast_values[self.filename] = (brightness, contrast)

    def switchLabelingMode(self):
        self.setDirty()
        if self.mayContinue():
            if self.labelingMode == "Enumerate":
                self.labelingMode = "Area"
                self.labelList.clear()
                self.uniqLabelList.clear()
            else:
                self.labelingMode = "Enumerate"
                self.labelList.clear()
                self.uniqLabelList.clear()

            if self.filename:
                if self.filename.endswith(".json"):
                    self.updateJSON()
                    self.loadFile(self.filename, justJSON=True)

    def updateJSON(self):
        class NpEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, np.integer):
                    return int(obj)
                if isinstance(obj, np.floating):
                    return float(obj)
                if isinstance(obj, np.ndarray):
                    return obj.tolist()

        if self.filename:
            if self.filename.endswith(".json"):
                with open(self.filename) as f:
                    data = json.load(f)

                json_dict = {"version": "4.5.13"
                    , "flags": {}
                    , "shapes": []
                    , "score": []
                    , "imagePath": data["imagePath"]
                    , "imageData": data["imageData"]
                    , "imageHeight": data["imageHeight"]
                    , "imageWidth": data["imageWidth"]
                             }

                ROI_polygon = []
                ROI_label = []
                ROI_score = []
                for shape in data["shapes"]:
                    ROI_polygon.append(shape["points"])
                    ROI_label.append(shape["label"])
                    ROI_score.append(shape["score"])

                for index, polygon in enumerate(ROI_polygon):
                    enumerateLabel = "Neuron" + str(index)
                    dict_neuron = {}
                    # dict_neuron["label"] = "Neuron" #Neuron_name
                    dict_neuron["shape_type"] = "polygon"
                    area_neuron = Polygon(polygon).area
                    # rename only if Neuron not manual
                    if ROI_label[index].lower() == "neuron manual":
                        areaLabel = "Neuron manual"
                        ROI_score[index] = .99
                    else:
                        if area_neuron > self.minMaxNeuronValues[1]:
                            areaLabel = "Neuron too big"
                        elif area_neuron < self.minMaxNeuronValues[0]:
                            areaLabel = "Neuron too small"
                        else:
                            areaLabel = "Neuron"
                    dict_neuron["points"] = polygon
                    dict_neuron["score"] = ROI_score[index]

                    if self.labelingMode == "Enumerate":
                        dict_neuron["label"] = enumerateLabel
                    elif self.labelingMode == "Area":
                        dict_neuron["label"] = areaLabel
                    json_dict["shapes"].append(dict_neuron)

                with open(self.filename, 'w') as f:
                    json.dump(json_dict, f, cls=NpEncoder)

            else:
                print("No .json file loaded")

    def removeAberrantJSON(self):
        class NpEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, np.integer):
                    return int(obj)
                if isinstance(obj, np.floating):
                    return float(obj)
                if isinstance(obj, np.ndarray):
                    return obj.tolist()

        if self.filename:
            if self.filename.endswith(".json"):
                with open(self.filename) as f:
                    data = json.load(f)

                json_dict = {"version": "4.5.13"
                    , "flags": {}
                    , "shapes": []
                    , "score": []
                    , "imagePath": data["imagePath"]
                    , "imageData": data["imageData"]
                    , "imageHeight": data["imageHeight"]
                    , "imageWidth": data["imageWidth"]
                             }

                ROI_polygon = []
                ROI_label = []
                ROI_score = []
                for shape in data["shapes"]:
                    ROI_polygon.append(shape["points"])
                    ROI_label.append(shape["label"])
                    ROI_score.append(shape["score"])

                for index, polygon in enumerate(ROI_polygon):
                    dict_neuron = {}
                    # dict_neuron["label"] = "Neuron" #Neuron_name
                    dict_neuron["shape_type"] = "polygon"
                    area_neuron = Polygon(polygon).area
                    # skip if name not manual and size doesn't fit
                    if ROI_label[index].lower() == "neuron manual":
                        areaLabel = "Neuron manual"
                        ROI_score[index] = .99
                    elif ROI_label[index].lower() in ["neuron too small", "neuron too big"]:
                        if area_neuron > self.minMaxNeuronValues[1]:
                            continue
                        elif area_neuron < self.minMaxNeuronValues[0]:
                            continue
                    else:
                        areaLabel = "Neuron"
                    dict_neuron["points"] = polygon
                    dict_neuron["score"] = ROI_score[index]

                    dict_neuron["label"] = areaLabel
                    json_dict["shapes"].append(dict_neuron)

                with open(self.filename, 'w') as f:
                    json.dump(json_dict, f, cls=NpEncoder)

            else:
                print("No .json file loaded")

    def adjustMinNeuronSize(self, value):
        if not self.mayContinue():
            return
        minArea, ok = QtWidgets.QInputDialog().getInt(self,
                                                      "Choose minimum Neuron Area for Neuron Labeling (default: 100)",
                                                      "Minimum Area (px)",
                                                      self.minMaxNeuronValues[0])
        if ok and minArea:
            self.minMaxNeuronValues[0] = minArea
            self.labelingMode = "Area"

        if self.filename:
            if self.filename.endswith(".json"):
                self.updateJSON()
                self.loadFile(self.filename, justJSON=True)

    def adjustMaxNeuronSize(self, value):
        if not self.mayContinue():
            return
        maxArea, ok = QtWidgets.QInputDialog().getInt(self,
                                                      "Choose maximum Neuron Area for Neuron Labeling (default: 1000)",
                                                      "Maximum Area (px)",
                                                      self.minMaxNeuronValues[1])
        if ok and maxArea:
            self.minMaxNeuronValues[1] = maxArea
            self.labelingMode = "Area"

        if self.filename:
            if self.filename.endswith(".json"):
                self.updateJSON()
                self.loadFile(self.filename, justJSON=True)

    def removeAberrantNeurons(self):
        if not self.mayContinue():
            return
        mb = QtWidgets.QMessageBox
        msg = self.tr(
            "All segmentation results outside your defined min/max area will be removed. Continue?")
        c = mb.warning(self, self.tr("Confirm"), msg, mb.Yes | mb.No)

        if c == mb.Yes:
            pass
        else:
            return

        self.labelingMode = "Area"

        if self.filename:
            if self.filename.endswith(".json"):
                self.removeAberrantJSON()
                self.loadFile(self.filename, justJSON=True, confidence=self.sl.value())

    def togglePolygons(self, value):
        for item in self.labelList:
            item.setCheckState(Qt.Checked if value else Qt.Unchecked)

    def loadFile(self, filename=None, justJSON=False, confidence=50):

        if filename is not None:
            # tif file conversion to 8 bit png if tif was 16 bit
            if filename.endswith("tif"):
                image = imageio.imread(filename)
                # downscaling to 8bit and upscaling for low max brightness
                image = (image / (image.max() / 255)).astype('uint8')
                filename = filename.replace(".tif", ".png")
                imageio.imwrite(filename, image)

            elif filename.endswith("tiff"):
                image = imageio.imread(filename)
                # downscaling to 8bit and upscaling for low max brightness
                image = (image / (image.max() / 255)).astype('uint8')
                filename = filename.replace(".tiff", ".png")
                imageio.imwrite(filename, image)

        """Load the specified file, or the last opened file if None."""
        # changing fileListWidget loads file

        if filename in self.imageList and (
                self.fileListWidget.currentRow() != self.imageList.index(filename)
        ):
            self.fileListWidget.setCurrentRow(self.imageList.index(filename))
            self.fileListWidget.repaint()
            return

        if not justJSON:
            self.resetState()
            self.sl.setEnabled(False)
        else:
            # soft resetState
            self.labelList.clear()
            self.uniqLabelList.clear()
            # self.filename = None
            # self.currentModel = None
            # self.imagePath = None
            # self.imageData = None
            self.labelFile = None
            self.otherData = None
            self.canvas.resetState()
        # self image path set to None
        self.canvas.setEnabled(False)
        if filename is None:
            filename = self.settings.value("filename", "")
        filename = str(filename)
        if not QtCore.QFile.exists(filename):
            self.errorMessage(
                self.tr("Error opening file"),
                self.tr("No such file: <b>%s</b>") % filename,
            )
            return False

        # assumes same name, but json extension
        self.status(
            str(self.tr("Loading %s...")) % osp.basename(str(filename))
        )
        label_file = osp.splitext(filename)[0] + ".json"

        if self.output_dir:
            label_file_without_path = osp.basename(label_file)
            label_file = osp.join(self.output_dir, label_file_without_path)
        if QtCore.QFile.exists(label_file) and LabelFile.is_label_file(
                label_file
        ):
            try:
                self.labelFile = LabelFile(label_file)

            except LabelFileError as e:
                self.errorMessage(
                    self.tr("Error opening file"),
                    self.tr(
                        "<p><b>%s</b></p>"
                        "<p>Make sure <i>%s</i> is a valid label file."
                    )
                    % (e, label_file),
                )
                self.status(self.tr("Error reading %s") % label_file)
                return False

            if not justJSON:
                self.imageData = LabelFile.load_image_file(filename)
                if self.imageData:
                    self.imagePath = filename

                # self.imageData = self.labelFile.imageData
                # print(self.imagePath, filename)
                #
                # self.imagePath = osp.join(
                #     osp.dirname(label_file),
                #     self.labelFile.imagePath,
                # )
                # print(self.imagePath, filename)

                self.otherData = self.labelFile.otherData
        else:
            if not justJSON:
                self.imageData = LabelFile.load_image_file(filename)
                if self.imageData:
                    self.imagePath = filename
            self.labelFile = None
        image = QtGui.QImage.fromData(self.imageData)
        if image.isNull():
            formats = [
                "*.{}".format(fmt.data().decode())
                for fmt in QtGui.QImageReader.supportedImageFormats()
            ]
            self.errorMessage(
                self.tr("Error opening file"),
                self.tr(
                    "<p>Make sure <i>{0}</i> is a valid image file.<br/>"
                    "Supported image formats: {1}</p>"
                ).format(filename, ",".join(formats)),
            )
            self.status(self.tr("Error reading %s") % filename)
            return False
        self.image = image
        self.filename = filename
        if self._config["keep_prev"]:
            prev_shapes = self.canvas.shapes
        self.canvas.loadPixmap(QtGui.QPixmap.fromImage(image))
        flags = {k: False for k in self._config["flags"] or []}
        if self.labelFile:
            self.loadLabels(self.labelFile.shapes, confidence=confidence)
            if self.labelFile.flags is not None:
                flags.update(self.labelFile.flags)
        self.loadFlags(flags)
        if self._config["keep_prev"] and self.noShapes():
            self.loadShapes(prev_shapes, replace=False)
            self.setDirty()
        else:
            self.setClean()
        self.canvas.setEnabled(True)
        # set zoom values
        is_initial_load = not self.zoom_values
        if self.filename in self.zoom_values:
            self.zoomMode = self.zoom_values[self.filename][0]
            self.setZoom(self.zoom_values[self.filename][1])
        elif is_initial_load or not self._config["keep_prev_scale"]:
            self.adjustScale(initial=True)
        # set scroll values
        for orientation in self.scroll_values:
            if self.filename in self.scroll_values[orientation]:
                self.setScroll(
                    orientation, self.scroll_values[orientation][self.filename]
                )
        # set brightness contrast values
        dialog = BrightnessContrastDialog(
            utils.img_data_to_pil(self.imageData),
            self.onNewBrightnessContrast,
            parent=self,
        )
        brightness, contrast = self.brightnessContrast_values.get(
            self.filename, (None, None)
        )
        if self._config["keep_prev_brightness"] and self.recentFiles:
            brightness, _ = self.brightnessContrast_values.get(
                self.recentFiles[0], (None, None)
            )
        if self._config["keep_prev_contrast"] and self.recentFiles:
            _, contrast = self.brightnessContrast_values.get(
                self.recentFiles[0], (None, None)
            )
        if brightness is not None:
            dialog.slider_brightness.setValue(brightness)
        if contrast is not None:
            dialog.slider_contrast.setValue(contrast)
        self.brightnessContrast_values[self.filename] = (brightness, contrast)
        if brightness is not None or contrast is not None:
            dialog.onNewValue(None)
        self.paintCanvas()
        self.addRecentFile(self.filename)
        self.toggleActions(True)
        self.canvas.setFocus()
        self.status(str(self.tr("Loaded %s")) % osp.basename(str(filename)))

        return True

    def resizeEvent(self, event):
        if (
                self.canvas
                and not self.image.isNull()
                and self.zoomMode != self.MANUAL_ZOOM
        ):
            self.adjustScale()
        super(MainWindow, self).resizeEvent(event)

    def paintCanvas(self):
        assert not self.image.isNull(), "cannot paint null image"
        self.canvas.scale = 0.01 * self.zoomWidget.value()
        self.canvas.adjustSize()
        self.canvas.update()

    def adjustScale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoomMode]()
        value = int(100 * value)
        self.zoomWidget.setValue(value)
        self.zoom_values[self.filename] = (self.zoomMode, value)

    def scaleFitWindow(self):
        """Figure out the size of the pixmap to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scaleFitWidth(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.pixmap.width()

    def enableSaveImageWithData(self, enabled):
        self._config["store_data"] = enabled
        self.actions.saveWithImageData.setChecked(enabled)

    def closeEvent(self, event):
        if not self.mayContinue():
            event.ignore()
        self.settings.setValue(
            "filename", self.filename if self.filename else ""
        )
        self.settings.setValue("window/size", self.size())
        self.settings.setValue("window/position", self.pos())
        self.settings.setValue("window/state", self.saveState())
        self.settings.setValue("recentFiles", self.recentFiles)
        self.settings.setValue("currentModel", self.currentModel)
        self.settings.setValue("currentModelTraceX", self.currentModelTraceX)
        self.settings.setValue("labelingMode", self.labelingMode)
        # ask the use for where to save the labels
        # self.settings.setValue('window/geometry', self.saveGeometry())

    def dragEnterEvent(self, event):
        extensions = [
            ".%s" % fmt.data().decode().lower()
            for fmt in QtGui.QImageReader.supportedImageFormats()
        ]
        if event.mimeData().hasUrls():
            items = [i.toLocalFile() for i in event.mimeData().urls()]
            if any([i.lower().endswith(tuple(extensions)) for i in items]):
                event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not self.mayContinue():
            event.ignore()
            return
        items = [i.toLocalFile() for i in event.mimeData().urls()]
        self.importDroppedImageFiles(items)

    # User Dialogs #

    def loadRecent(self, filename):
        if self.mayContinue():
            self.loadFile(filename)

    def setModel(self, modelname):
        self.currentModel = modelname

    def setModelTraceX(self, modelname):
        self.currentModelTraceX = modelname

    def popup_model_manager(self):
        self.w = modelmanager.ModelWindow()
        self.w.show()

    def popup_model_managerX(self):
        self.w = modelmanagerX.ModelWindow()
        self.w.show()

    def popup_local_model_prompt(self):

        # prompt for open file
        path = osp.dirname(str(self.filename)) if self.filename else "."
        formats = ["*.pt"]
        filters = self.tr("Local Model file (*.pt)")
        fileDialog = FileDialogPreview(self)
        fileDialog.setFileMode(FileDialogPreview.ExistingFile)
        fileDialog.setNameFilter(filters)
        fileDialog.setWindowTitle(
            self.tr("%s - Choose Local Model file") % __appname__,
        )
        fileDialog.setWindowFilePath(path)
        fileDialog.setViewMode(FileDialogPreview.Detail)
        if fileDialog.exec_():
            fileName = fileDialog.selectedFiles()[0]
            if fileName:
                self.w = modelmanager.ModelWindow()
                # add notification for copying and adjusting manifest

                self.statusBar().showMessage(
                    self.tr("%s . Local model will be copied and integrated in active MANIFEST file %s")
                    % ("Local Model Integration", self.output_dir)
                )
                self.statusBar().show()

                # copy .pt file in vinseg/experiments
                model_dir = os.path.dirname(self.w.local_manifest_path)
                from shutil import copyfile

                if not os.path.exists(model_dir + "/" + os.path.basename(fileName)):
                    try:
                        copyfile(fileName, model_dir + "/" + os.path.basename(fileName))
                    except IOError as e:
                        print(f"Error occurred copying file: {e}")
                else:
                    print("Destination file already exists. Skipping copy.")

                # adjust manifest file
                self.w.add_local_model(fileName)

        pass # - todo


    def get_file_path(self):
        if not self.mayContinue():
            return
        path = osp.dirname(str(self.filename)) if self.filename else "."
        formats = ["*.tsv", ".txt"]
        filters = self.tr("df/f files (%s)") % " ".join(
            formats)
        fileDialog = FileDialogPreview(self)
        fileDialog.setFileMode(FileDialogPreview.ExistingFile)
        fileDialog.setNameFilter(filters)
        fileDialog.setWindowTitle(
            self.tr("%s - Choose df/f .tsv file") % __appname__,
        )
        fileDialog.setWindowFilePath(path)
        fileDialog.setViewMode(FileDialogPreview.Detail)
        if fileDialog.exec_():
            return fileDialog.selectedFiles()[0]
        else:
            return False

    def start_CASCADE(self):
        if not self.mayContinue():
            return
        if self.filename:
            if os.path.exists(self.filename.replace(".json", "_traces_df_f.tsv")):
                df_f_path = self.filename.replace(".json", "_traces_df_f.tsv")
                # ask if this path is correct
                mb = QtWidgets.QMessageBox
                msg = self.tr(
                    "df/f values for this file found in " + self.filename.replace(".json", "_traces_df_f.tsv")
                    + "\nUse this file as source for df/f values?")
                c = mb.warning(self, self.tr("Confirm file"), msg, mb.Yes | mb.No)
                if c == mb.Yes:
                    pass
                if c == mb.No:
                    df_f_path = self.get_file_path()
            else:
                mb = QtWidgets.QMessageBox
                msg = self.tr(
                    "Please choose dF/F file for the current experiment in the following window.")
                mb.warning(self, self.tr("Attention"), msg, mb.Ok)
                df_f_path = self.get_file_path()
        else:
            df_f_path = self.get_file_path()

        # run cascade code
        if df_f_path:
            self.traceProgress = QtWidgets.QProgressDialog("Running CASCADE Spike Inference...", "Cancel", 0, 10, self)
            self.traceProgress.setWindowModality(Qt.WindowModal)
            self.traceProgress.forceShow()

            run_CASCADE(dff_path=df_f_path, model_name=os.path.join(os.path.sep, os.path.dirname(__file__),
                                                                    "CASCADE_models", self.currentModelTraceX),
                        pb=self.traceProgress)

            mb = QtWidgets.QMessageBox
            msg = self.tr(
                "Spike probabilities and discrete locations written to {}.".format(df_f_path + "/predictions"))
            mb.warning(self, self.tr("Attention"), msg, mb.Ok)

    def saveTracesDialog(self):

        if self.originalImageFile:
            defaultOpenDirPath = (
                osp.dirname(self.originalImageFile) if self.originalImageFile else "."
            )
        else:
            defaultOpenDirPath = self.currentPath()

        filters = self.tr("Trace files (*%s)") % "tsv"
        dlg = QtWidgets.QFileDialog(
            self, "Choose where to store traces", defaultOpenDirPath, filters
        )
        dlg.setDefaultSuffix(LabelFile.suffix[1:])
        dlg.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        dlg.setOption(QtWidgets.QFileDialog.DontConfirmOverwrite, False)
        dlg.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, False)
        basename = osp.basename(osp.splitext(self.filename)[0])
        default_tracesfile_name = osp.join(
            defaultOpenDirPath, basename + "_traces.tsv"
        )
        filename = dlg.getSaveFileName(
            self,
            self.tr("Choose where to store traces"),
            default_tracesfile_name,
            self.tr("Traces files (*%s)") % "tsv",
        )
        if isinstance(filename, tuple):
            filename, _ = filename
        return filename

    def start_trace_extraction(self):
        if not self.mayContinue():
            return

        # check if there is any rois
        if self.uniqLabelList.count() < 1:
            # show warning that there are no rois
            mb = QtWidgets.QMessageBox
            msg = self.tr("No ROIs detected! Please run the Auto-Segmentation first")
            mb.warning(self, self.tr("Attention"), msg, mb.Ok)
            return

        # get dir
        if self.lastOpenDir and osp.exists(self.lastOpenDir):
            defaultOpenDirPath = self.lastOpenDir
        elif self.originalImageFile:
            defaultOpenDirPath = (
                osp.dirname(self.originalImageFile) if self.originalImageFile else "."
            )
        else:
            defaultOpenDirPath = (
                osp.dirname(self.filename) if self.filename else "."
            )
        images_dir = str(
            QtWidgets.QFileDialog.getExistingDirectory(
                self,
                self.tr("%s - Open Images Directory") % __appname__,
                defaultOpenDirPath,
                QtWidgets.QFileDialog.ShowDirsOnly
                | QtWidgets.QFileDialog.DontResolveSymlinks,
            )
        )
        if not images_dir:
            return
        # load image file names into an array
        images_type = "tif"
        imagesArray = [os.path.join(images_dir, f) for f in sorted(os.listdir(images_dir)) if
                       os.path.isfile(os.path.join(images_dir, f)) and f.endswith("." + images_type)]

        # if no tif files, try tiff files
        if len(imagesArray) < 1:
            images_type = "tiff"
            imagesArray = [os.path.join(images_dir, f) for f in sorted(os.listdir(images_dir)) if
                           os.path.isfile(os.path.join(images_dir, f)) and f.endswith("." + images_type)]

        # if still no images found, option for choosing other directory
        if len(imagesArray) < 1:
            mb = QtWidgets.QMessageBox
            msg = self.tr(
                "No .tif or .tiff files found in given directory. Choose another directory?")
            c = mb.warning(self, self.tr("Attention"), msg, mb.Yes | mb.No)
            if c == mb.Yes:
                self.start_trace_extraction()
            if c == mb.No:
                return
        # sorting worked

        self.imagesArray = imagesArray
        mb = QtWidgets.QMessageBox
        msg = self.tr(
            "Found {} images in this folder, is this the correct length of your recording?".format(
                str(len(imagesArray))))
        c = mb.warning(self, self.tr("Attention"), msg, mb.Yes | mb.No)
        if c == mb.No:
            return

        self.extractTraces(imagesArray)

    def extractTraces(self, imagesArray):  # , frequency):

        self.setDirty()

        if not self.mayContinue():
            return

        if self.filename:
            if self.filename.endswith(".json"):
                with open(self.filename) as f:
                    data = json.load(f)
            else:
                print("No JSON file provided. abort")
                return
        else:
            print("No JSON file provided. abort")
            return

        self.traceProgress = QtWidgets.QProgressDialog("Calculating Traces...", "cancel", 0, len(imagesArray), self)
        self.traceProgress.setWindowModality(Qt.WindowModal)
        self.traceProgress.forceShow()

        self.traceProgress.setValue(1)

        masks = []

        for i in range(0, len(data['shapes'])):
            # compute only for shapes with min confidence
            if data['shapes'][i]['score'] * 100 >= self.getConfidence():
                roimask = shape_to_mask((data['imageHeight'], data['imageWidth']), data['shapes'][i]['points'],
                                        shape_type=None,
                                        line_width=1, point_size=1)
                masks.append(roimask)

        self.traceProgress.setValue(10)

        with Pool() as pool:
            traces = pool.starmap(tracesForImage, zip(imagesArray, repeat(masks, len(imagesArray))))

        self.traceProgress.setValue(self.traceProgress.maximum() - 10)

        traceFileName = self.saveTracesDialog()
        # write traces to file
        pd.DataFrame(data=np.array(traces)).to_csv(traceFileName, sep="\t", header=False, index=False)
        # copy json file to trace location
        # Step 1: Read the JSON file
        with open(self.getJSONFile(), 'r') as file:
            data = json.load(file)

        # Step 2: Write the JSON data to another file
        output_file_path = os.path.dirname(traceFileName) + "/" + os.path.basename(self.getJSONFile())

        print(output_file_path)

        with open(output_file_path, 'w') as file:
            json.dump(data, file, indent=4)

        self.traceProgress.setValue(self.traceProgress.maximum())
        self.traceProgress.close()

        # get long filter length
        lfl, ok = QtWidgets.QInputDialog().getInt(self,
                                                  "Dynamic Baseline Estimation (long filter length)",
                                                  "Please provide the wished long filter length [frames] for the dynamic baseline calculation (default: 5401 frames)",
                                                  5401, 0, 1000000)

        if ok and lfl:
            self.traceProgress = QtWidgets.QProgressDialog("Calculating dF/F...", "cancel", 0, len(imagesArray), self)
            self.traceProgress.setWindowModality(Qt.WindowModal)
            self.traceProgress.forceShow()
            self.traceProgress.setValue(1)

            dff_calc(traceFileName, lfl)

            self.traceProgress.setValue(self.traceProgress.maximum())
            self.traceProgress.close()
            mbFormat = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Warning, "Files Written",
                                             "Raw Traces and dF/F files written to {}.".format(
                                                 os.path.dirname(traceFileName)),
                                             QtWidgets.QMessageBox.Ok)
            mbFormat.exec()

        else:
            mbFormat = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Warning, "No RWS was given",
                                             "No rolling window size was given. Only raw traces were written to {}.".format(
                                                 os.path.dirname(traceFileName)),
                                             QtWidgets.QMessageBox.Ok)
            mbFormat.exec()

        return

    def openPrevImg(self, _value=False):
        self.fileSelectionChanged()
        keep_prev = self._config["keep_prev"]
        if QtWidgets.QApplication.keyboardModifiers() == (
                Qt.ControlModifier | Qt.ShiftModifier
        ):
            self._config["keep_prev"] = True

        if not self.mayContinue():
            return

        if len(self.imageList) <= 0:
            return

        if self.filename is None:
            return

        currIndex = self.imageList.index(self.filename)
        if currIndex - 1 >= 0:
            filename = self.imageList[currIndex - 1]
            if filename:
                self.loadFile(filename)

        self._config["keep_prev"] = keep_prev

    def openNextImg(self, _value=False, load=True):
        self.fileSelectionChanged()
        keep_prev = self._config["keep_prev"]
        if QtWidgets.QApplication.keyboardModifiers() == (
                Qt.ControlModifier | Qt.ShiftModifier
        ):
            self._config["keep_prev"] = True

        if not self.mayContinue():
            return

        if len(self.imageList) <= 0:
            return

        filename = None
        if self.filename is None:
            filename = self.imageList[0]
        else:
            currIndex = self.imageList.index(self.filename)
            if currIndex + 1 < len(self.imageList):
                filename = self.imageList[currIndex + 1]
            else:
                filename = self.imageList[-1]
        self.filename = filename

        if self.filename and load:
            self.loadFile(self.filename)

        self._config["keep_prev"] = keep_prev

    def openFile(self, _value=False):
        if not self.mayContinue():
            return
        path = osp.dirname(str(self.filename)) if self.filename else "."
        formats = [
            "*.{}".format(fmt.data().decode())
            for fmt in QtGui.QImageReader.supportedImageFormats()
        ]
        filters = self.tr("Image & Label files (%s)") % " ".join(
            formats + ["*%s" % LabelFile.suffix]
        )
        fileDialog = FileDialogPreview(self)
        fileDialog.setFileMode(FileDialogPreview.ExistingFile)
        fileDialog.setNameFilter(filters)
        fileDialog.setWindowTitle(
            self.tr("%s - Choose Image or Label file") % __appname__,
        )
        fileDialog.setWindowFilePath(path)
        fileDialog.setViewMode(FileDialogPreview.Detail)
        if fileDialog.exec_():
            fileName = fileDialog.selectedFiles()[0]
            if fileName:
                self.loadFile(fileName)

    def changeOutputDirDialog(self, _value=False):
        default_output_dir = self.output_dir
        if default_output_dir is None and self.filename:
            default_output_dir = osp.dirname(self.filename)
        if default_output_dir is None:
            default_output_dir = self.currentPath()

        output_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("%s - Save/Load Annotations in Directory") % __appname__,
            default_output_dir,
            QtWidgets.QFileDialog.ShowDirsOnly
            | QtWidgets.QFileDialog.DontResolveSymlinks,
        )
        output_dir = str(output_dir)

        if not output_dir:
            return

        self.output_dir = output_dir

        self.statusBar().showMessage(
            self.tr("%s . Annotations will be saved/loaded in %s")
            % ("Change Annotations Dir", self.output_dir)
        )
        self.statusBar().show()

        current_filename = self.filename
        self.importDirImages(self.lastOpenDir, load=False)

        if current_filename in self.imageList:
            # retain currently selected file
            self.fileListWidget.setCurrentRow(
                self.imageList.index(current_filename)
            )
            self.fileListWidget.repaint()

    def saveFile(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        if self.labelFile:
            # DL20180323 - overwrite when in directory
            self._saveFile(self.labelFile.filename)

            if self.filename:
                if self.filename.endswith(".json"):
                    with open(self.filename) as f:
                        data = json.load(f)
                else:
                    print("ERROR")
                    return
            else:
                return

            masks = []

            for i in range(0, len(data['shapes'])):
                roimask = shape_to_mask((data['imageHeight'], data['imageWidth']), data['shapes'][i]['points'],
                                        shape_type=None,
                                        line_width=1, point_size=1)
                masks.append(roimask)
            masks = np.array(masks)
            image = Image.fromarray(masks.max(axis=0))
            image.save(self.filename.replace(".json", ".png"))

        elif self.output_file:
            self._saveFile(self.output_file)
            self.close()
        else:
            self._saveFile(self.saveFileDialog())

    def saveFileAs(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        self._saveFile(self.saveFileDialog())

    def saveFileDialog(self):
        caption = self.tr("%s - Choose File") % __appname__
        filters = self.tr("Label files (*%s)") % LabelFile.suffix
        if self.output_dir:
            dlg = QtWidgets.QFileDialog(
                self, caption, self.output_dir, filters
            )
        else:
            dlg = QtWidgets.QFileDialog(
                self, caption, self.currentPath(), filters
            )
        dlg.setDefaultSuffix(LabelFile.suffix[1:])
        dlg.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        dlg.setOption(QtWidgets.QFileDialog.DontConfirmOverwrite, False)
        dlg.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, False)
        basename = osp.basename(osp.splitext(self.filename)[0])
        if self.output_dir:
            default_labelfile_name = osp.join(
                self.output_dir, basename + LabelFile.suffix
            )
        else:
            default_labelfile_name = osp.join(
                self.currentPath(), basename + LabelFile.suffix
            )
        filename = dlg.getSaveFileName(
            self,
            self.tr("Choose File"),
            default_labelfile_name,
            self.tr("Label files (*%s)") % LabelFile.suffix,
        )
        if isinstance(filename, tuple):
            filename, _ = filename
        return filename

    def _saveFile(self, filename):
        if filename and self.saveLabels(filename):
            self.addRecentFile(filename)
            self.setClean()

    def closeFile(self, _value=False):
        if not self.mayContinue():
            return
        self.resetState()
        self.setClean()
        self.toggleActions(False)
        self.canvas.setEnabled(False)
        self.actions.saveAs.setEnabled(False)

    # to check
    def getJSONFile(self):
        # cope with problems of mixed / and \\
        label_file = self.imagePath.replace("\\", "/")
        dir_name = os.path.dirname(label_file)
        filename = os.path.basename(label_file)
        if filename.endswith(".png"):
            label_file = dir_name + "/predictions/" + filename.replace(".png", ".json")
        elif filename.endswith(".tiff"):
            label_file = dir_name + "/predictions/" + filename.replace(".tiff", ".json")
        elif filename.endswith(".tif"):
            label_file = dir_name + "/predictions/" + filename.replace(".tif", ".json")

        return label_file

    def getLabelFile(self):
        if self.filename.lower().endswith(".json"):
            label_file = self.filename
        else:
            label_file = osp.splitext(self.filename)[0] + ".json"

        return label_file

    def deleteFile(self):
        mb = QtWidgets.QMessageBox
        msg = self.tr(
            "You are about to permanently delete this label file, "
            "proceed anyway?"
        )
        answer = mb.warning(self, self.tr("Attention"), msg, mb.Yes | mb.No)
        if answer != mb.Yes:
            return

        label_file = self.getLabelFile()
        if osp.exists(label_file):
            os.remove(label_file)
            logger.info("Label file is removed: {}".format(label_file))

            item = self.fileListWidget.currentItem()
            item.setCheckState(Qt.Unchecked)

            self.resetState()

    def loadPolygons(self):
        if not self.mayContinue():
            return

        label_file = self.getJSONFile()
        if osp.exists(label_file):
            self.loadFile(label_file, justJSON=True, confidence=self.getConfidence())
        # enable slider
        self.sl.setEnabled(True)

    # Message Dialogs. #
    def hasLabels(self):
        if self.noShapes():
            self.errorMessage(
                "No objects labeled",
                "You must label at least one object to save the file.",
            )
            return False
        return True

    def hasLabelFile(self):
        if self.filename is None:
            return False

        label_file = self.getLabelFile()
        return osp.exists(label_file)

    def hasJSONFile(self):
        if self.filename is None:
            return False

        JSON_file = self.getJSONFile()
        return osp.exists(JSON_file)

    def mayContinue(self):
        if not self.dirty:
            return True
        mb = QtWidgets.QMessageBox
        msg = self.tr(
            'Save annotations to "{}" before closing?\n!! Polygons with confidence values lower than current selection will be lost.').format(
            self.filename
        )
        answer = mb.question(
            self,
            self.tr("Save annotations?"),
            msg,
            mb.Save | mb.Discard | mb.Cancel,
            mb.Save,
        )
        if answer == mb.Discard:
            return True
        elif answer == mb.Save:
            self.saveFile()
            return True
        else:  # answer == mb.Cancel
            return False

    def errorMessage(self, title, message):
        return QtWidgets.QMessageBox.critical(
            self, title, "<p><b>%s</b></p>%s" % (title, message)
        )

    def currentPath(self):
        return osp.dirname(str(self.filename)) if self.filename else "."

    def toggleKeepPrevMode(self):
        self._config["keep_prev"] = not self._config["keep_prev"]

    def removeSelectedPoint(self):
        self.canvas.removeSelectedPoint()
        self.canvas.update()
        if not self.canvas.hShape.points:
            self.canvas.deleteShape(self.canvas.hShape)
            self.remLabels([self.canvas.hShape])
            self.setDirty()
            if self.noShapes():
                for action in self.actions.onShapesPresent:
                    action.setEnabled(False)

    def deleteSelectedShape(self, ask=True):
        if ask:
            yes, no = QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No
            msg = self.tr(
                "You are about to permanently delete {} polygons, "
                "proceed anyway?"
            ).format(len(self.canvas.selectedShapes))
        else:
            yes = True

        # if yes == QtWidgets.QMessageBox.warning(
        #         self, self.tr("Attention"), msg, yes | no, yes
        # ):
        if yes:
            self.remLabels(self.canvas.deleteSelected())
            self.setDirty()
            if self.noShapes():
                for action in self.actions.onShapesPresent:
                    action.setEnabled(False)

    def copyShape(self):
        self.canvas.endMove(copy=True)
        for shape in self.canvas.selectedShapes:
            self.addLabel(shape)
        self.labelList.clearSelection()
        self.setDirty()

    def moveShape(self):
        self.canvas.endMove(copy=False)
        self.setDirty()

    def openDirDialog(self, _value=False, dirpath=None, pattern=None):
        if not self.mayContinue():
            return

        defaultOpenDirPath = dirpath if dirpath else "."
        if self.lastOpenDir and osp.exists(self.lastOpenDir):
            defaultOpenDirPath = self.lastOpenDir
        else:
            defaultOpenDirPath = (
                osp.dirname(self.filename) if self.filename else "."
            )

        targetDirPath = str(
            QtWidgets.QFileDialog.getExistingDirectory(
                self,
                self.tr("%s - Open Directory") % __appname__,
                defaultOpenDirPath,
                QtWidgets.QFileDialog.ShowDirsOnly
                | QtWidgets.QFileDialog.DontResolveSymlinks,
            )
        )
        self.importDirImages(targetDirPath, pattern=pattern)

    @property
    def imageList(self):
        lst = []
        for i in range(self.fileListWidget.count()):
            item = self.fileListWidget.item(i)
            lst.append(item.text())
        return lst

    def importDroppedImageFiles(self, imageFiles):
        extensions = [
            ".%s" % fmt.data().decode().lower()
            for fmt in QtGui.QImageReader.supportedImageFormats()
        ]

        self.filename = None
        for file in imageFiles:
            if file in self.imageList or not file.lower().endswith(
                    tuple(extensions)
            ):
                continue
            label_file = osp.splitext(file)[0] + ".json"
            if self.output_dir:
                label_file_without_path = osp.basename(label_file)
                label_file = osp.join(self.output_dir, label_file_without_path)
            item = QtWidgets.QListWidgetItem(file)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if QtCore.QFile.exists(label_file) and LabelFile.is_label_file(
                    label_file
            ):
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            self.fileListWidget.addItem(item)

        if len(self.imageList) > 1:
            self.actions.openNextImg.setEnabled(True)
            self.actions.openPrevImg.setEnabled(True)

        self.openNextImg()

    def refresh(self):

        # Access all PNG files in directory
        allfiles = os.listdir(self.lastOpenDir)
        imlist = sorted([filename for filename in allfiles if filename[-4:] in [".tif", "tiff"]])

        N = len(imlist) - 1

        if N >= 500:
            imlist = imlist[-500:]

        images = np.array([np.array(Image.open(self.lastOpenDir + "/" + fname)) for fname in imlist])
        arr = np.array(np.mean(images, axis=(0)), dtype=np.uint16)

        arr = (arr / (arr.max() / 255)).astype('uint8')
        out = Image.fromarray(arr)

        out.save(self.lastOpenDir + "/" + str(max(0, N - 500)) + "-" + str(N) + "_mean.png")

        if self.micModeOn:
            self.importDirImages(self.lastOpenDir, pattern="_mean.png")

        self.fileSelectionChanged()

        self.imagePath = self.lastOpenDir + "/" + str(max(0, N - 500)) + "-" + str(N) + "_mean.png"

        self.loadFile(self.imagePath)

    def importDirImages(self, dirpath, pattern=None, load=True):
        self.actions.openNextImg.setEnabled(True)
        self.actions.openPrevImg.setEnabled(True)

        if not self.mayContinue() or not dirpath:
            return

        self.lastOpenDir = dirpath
        self.filename = None
        self.fileListWidget.clear()
        for filename in self.scanAllImages(dirpath):
            if pattern and pattern not in filename:
                continue
            label_file = osp.splitext(filename)[0] + ".json"
            if self.output_dir:
                label_file_without_path = osp.basename(label_file)
                label_file = osp.join(self.output_dir, label_file_without_path)
            item = QtWidgets.QListWidgetItem(filename)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if QtCore.QFile.exists(label_file) and LabelFile.is_label_file(
                    label_file
            ):
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            self.fileListWidget.addItem(item)
        self.openNextImg(load=load)

    def scanAllImages(self, folderPath):
        extensions = [
            ".%s" % fmt.data().decode().lower()
            for fmt in QtGui.QImageReader.supportedImageFormats()
        ]

        images = []
        for root, dirs, files in os.walk(folderPath):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    relativePath = osp.join(root, file)
                    images.append(relativePath)
        images.sort(key=lambda x: x.lower())
        return images
