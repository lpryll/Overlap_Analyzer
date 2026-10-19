# -*- coding: utf-8 -*-
import os
from qgis.PyQt.QtGui import QIcon

try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction

from .i18n import tr
from .overlap_dialog import OverlapAnalyzerDialog

class OverlapAnalyzerPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = "&Overlap Analyzer"
        self.toolbar = self.iface.addToolBar("Overlap Analyzer")
        self.toolbar.setObjectName("OverlapAnalyzerToolbar")
        self.dlg = None

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, "icon.svg")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        self.action = QAction(icon, "Overlap Analyzer Pro", self.iface.mainWindow())
        self.action.setObjectName("OverlapAnalyzerAction")
        self.action.setStatusTip(tr("status_tip"))
        self.action.triggered.connect(self.run)
        self.iface.addPluginToVectorMenu(self.menu, self.action)
        self.toolbar.addAction(self.action)
        self.actions.append(self.action)

    def unload(self):
        for action in self.actions:
            self.iface.removePluginVectorMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        if self.toolbar:
            del self.toolbar
        if self.dlg:
            self.dlg.close()
            self.dlg = None

    def run(self):
        if self.dlg is None:
            self.dlg = OverlapAnalyzerDialog(self.iface)
        else:
            self.dlg.populate_overlay_layers()
        self.dlg.show()
        self.dlg.raise_()
        self.dlg.activateWindow()