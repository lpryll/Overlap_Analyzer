# -*- coding: utf-8 -*-
import re
from qgis.core import (
    QgsProject,
    QgsApplication,
    QgsVectorLayer,
    QgsWkbTypes,
    QgsGeometry,
    QgsMapLayerProxyModel,
    QgsCoordinateTransform
)
from qgis.gui import (
    QgsMapLayerComboBox,
    QgsFieldComboBox
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QProgressBar, QCheckBox, QDoubleSpinBox, QGroupBox,
    QTabWidget, QWidget, QHeaderView, QAbstractItemView,
    QFileDialog, QMessageBox, QComboBox, QLineEdit, QApplication
)

from .compat import enum_value, log_message, polygon_geometry_type
from .i18n import tr
from .overlap_engine import OverlapAnalysisTask
from .output_builder import create_overlap_memory_layer, export_results_to_csv
from .report_generator import OverlapReportGenerator

SELECT_ROWS = enum_value(QAbstractItemView, "SelectionBehavior", "SelectRows")
SINGLE_SELECTION = enum_value(QAbstractItemView, "SelectionMode", "SingleSelection")
NO_EDIT_TRIGGERS = enum_value(QAbstractItemView, "EditTrigger", "NoEditTriggers")
RESIZE_STRETCH = enum_value(QHeaderView, "ResizeMode", "Stretch")
RESIZE_CONTENT = enum_value(QHeaderView, "ResizeMode", "ResizeToContents")
USER_CHECKABLE = enum_value(Qt, "ItemFlag", "ItemIsUserCheckable")
CHECKED = enum_value(Qt, "CheckState", "Checked")
UNCHECKED = enum_value(Qt, "CheckState", "Unchecked")
ALIGN_RIGHT = enum_value(Qt, "AlignmentFlag", "AlignRight") | enum_value(Qt, "AlignmentFlag", "AlignVCenter")
USER_ROLE = enum_value(Qt, "ItemDataRole", "UserRole")
WAIT_CURSOR = enum_value(Qt, "CursorShape", "WaitCursor")


class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        try:
            return float(self.text()) < float(other.text())
        except ValueError:
            return super().__lt__(other)


class OverlapAnalyzerDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self.canvas = iface.mapCanvas()

        self.current_task = None
        self.detail_results = []
        self.net_results = []
        self.last_base_layer_id = None
        self.last_base_field = ""
        self._sel_connected = set()
        self._syncing = False

        self.setWindowTitle(tr("window_title"))
        self.resize(1020, 700)
        self.setup_ui()
        self.populate_overlay_layers()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # 1. HEDEF KATMAN GRUBU
        base_group = QGroupBox(tr("grp_base"))
        base_layout = QGridLayout(base_group)

        base_layout.addWidget(QLabel(tr("lbl_base_layer")), 0, 0)
        self.cmb_base_layer = QgsMapLayerComboBox()
        poly_filter = enum_value(QgsMapLayerProxyModel, "Filter", "PolygonLayer")
        self.cmb_base_layer.setFilters(poly_filter)
        base_layout.addWidget(self.cmb_base_layer, 0, 1)

        base_layout.addWidget(QLabel(tr("lbl_base_field")), 0, 2)
        self.cmb_base_field = QgsFieldComboBox()
        base_layout.addWidget(self.cmb_base_field, 0, 3)

        self.chk_only_selected = QCheckBox(tr("chk_only_selected"))
        base_layout.addWidget(self.chk_only_selected, 1, 0, 1, 2)

        base_layout.addWidget(QLabel(tr("lbl_sliver")), 1, 2)
        self.spn_sliver = QDoubleSpinBox()
        self.spn_sliver.setRange(0.0, 10000.0)
        self.spn_sliver.setDecimals(3)
        self.spn_sliver.setValue(0.100)
        base_layout.addWidget(self.spn_sliver, 1, 3)

        main_layout.addWidget(base_group)

        # 2. ÇAKIŞTIRILACAK KATMANLAR GRUBU
        ov_group = QGroupBox(tr("grp_overlays"))
        ov_layout = QVBoxLayout(ov_group)

        btn_bar = QHBoxLayout()
        btn_sel_all = QPushButton(tr("btn_sel_all"))
        btn_desel_all = QPushButton(tr("btn_desel_all"))
        btn_refresh = QPushButton(tr("btn_refresh"))
        btn_sel_all.clicked.connect(lambda: self.toggle_all_overlays(True))
        btn_desel_all.clicked.connect(lambda: self.toggle_all_overlays(False))
        btn_refresh.clicked.connect(self.populate_overlay_layers)
        btn_bar.addWidget(btn_sel_all)
        btn_bar.addWidget(btn_desel_all)
        btn_bar.addWidget(btn_refresh)
        btn_bar.addStretch()
        ov_layout.addLayout(btn_bar)

        self.tbl_overlays = QTableWidget(0, 3)
        self.tbl_overlays.setHorizontalHeaderLabels([tr("ov_col_include"), tr("ov_col_layer"), tr("ov_col_field")])
        self.tbl_overlays.horizontalHeader().setSectionResizeMode(0, RESIZE_CONTENT)
        self.tbl_overlays.horizontalHeader().setSectionResizeMode(1, RESIZE_STRETCH)
        self.tbl_overlays.horizontalHeader().setSectionResizeMode(2, RESIZE_STRETCH)
        self.tbl_overlays.setMaximumHeight(170)
        ov_layout.addWidget(self.tbl_overlays)

        main_layout.addWidget(ov_group)

        # 3. ÇALIŞTIRMA VE İLERLEME ÇUBUĞU
        run_layout = QHBoxLayout()
        self.btn_run = QPushButton(tr("btn_run"))
        self.btn_run.setMinimumHeight(36)
        font = self.btn_run.font()
        font.setBold(True)
        self.btn_run.setFont(font)
        self.btn_run.clicked.connect(self.start_analysis)

        self.btn_cancel = QPushButton(tr("btn_cancel"))
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_analysis)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)

        run_layout.addWidget(self.btn_run, 2)
        run_layout.addWidget(self.btn_cancel, 0)
        run_layout.addWidget(self.progress_bar, 3)
        main_layout.addLayout(run_layout)

        # 4. SONUÇ SEKMELERİ
        self.tabs = QTabWidget()

        tab_detail = QWidget()
        lyt_detail = QVBoxLayout(tab_detail)
        lyt_detail.addWidget(QLabel(tr("hint_detail")))

        self.tbl_results = QTableWidget(0, 7)
        self.tbl_results.setHorizontalHeaderLabels([
            tr("col_base_id"), tr("col_ov_layer"), tr("col_ov_id"),
            tr("col_base_ha"), tr("col_ov_m2"), tr("col_ov_ha"), tr("col_ov_pct")
        ])
        self.tbl_results.setSelectionBehavior(SELECT_ROWS)
        self.tbl_results.setSelectionMode(SINGLE_SELECTION)
        self.tbl_results.setEditTriggers(NO_EDIT_TRIGGERS)
        self.tbl_results.setSortingEnabled(True)
        self.tbl_results.horizontalHeader().setSectionResizeMode(RESIZE_STRETCH)
        self.tbl_results.cellClicked.connect(self.on_detail_row_clicked)
        lyt_detail.addWidget(self.tbl_results)
        self.tabs.addTab(tab_detail, tr("tab_detail"))

        tab_net = QWidget()
        lyt_net = QVBoxLayout(tab_net)
        lyt_net.addWidget(QLabel(tr("hint_net")))

        self.tbl_net = QTableWidget(0, 6)
        self.tbl_net.setHorizontalHeaderLabels([
            tr("col_base_id"), tr("col_tot_base_ha"), tr("col_union_ha"),
            tr("col_union_pct"), tr("col_net_ha"), tr("col_net_m2")
        ])
        self.tbl_net.setSelectionBehavior(SELECT_ROWS)
        self.tbl_net.setSelectionMode(SINGLE_SELECTION)
        self.tbl_net.setEditTriggers(NO_EDIT_TRIGGERS)
        self.tbl_net.setSortingEnabled(True)
        self.tbl_net.horizontalHeader().setSectionResizeMode(RESIZE_STRETCH)
        self.tbl_net.cellClicked.connect(self.on_net_row_clicked)
        lyt_net.addWidget(self.tbl_net)
        self.tabs.addTab(tab_net, tr("tab_net"))

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel(tr("lbl_filter_id")))
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText(tr("ph_filter_id"))
        self.txt_filter.setClearButtonEnabled(True)
        self.txt_filter.textChanged.connect(self.apply_target_filter)
        filter_layout.addWidget(self.txt_filter, 1)
        filter_layout.addWidget(QLabel(tr("lbl_filter_ov")))
        self.txt_filter_ov = QLineEdit()
        self.txt_filter_ov.setPlaceholderText(tr("ph_filter_ov"))
        self.txt_filter_ov.setClearButtonEnabled(True)
        self.txt_filter_ov.textChanged.connect(self.apply_target_filter)
        filter_layout.addWidget(self.txt_filter_ov, 1)
        self.lbl_filter_count = QLabel("")
        filter_layout.addWidget(self.lbl_filter_count)
        main_layout.addLayout(filter_layout)

        tick_layout = QHBoxLayout()
        self.btn_check_visible = QPushButton(tr("btn_check_visible"))
        self.btn_uncheck_all = QPushButton(tr("btn_uncheck_all"))
        self.btn_check_visible.clicked.connect(self.check_visible_targets)
        self.btn_uncheck_all.clicked.connect(self.uncheck_all_targets)
        tick_layout.addWidget(self.btn_check_visible)
        tick_layout.addWidget(self.btn_uncheck_all)
        tick_layout.addStretch()
        main_layout.addLayout(tick_layout)

        main_layout.addWidget(self.tabs)

        # 5. ÇIKTI BUTONLARI
        out_layout = QHBoxLayout()
        self.btn_add_layer = QPushButton(tr("btn_add_layer"))
        self.btn_add_layer.setEnabled(False)
        self.btn_add_layer.clicked.connect(self.add_memory_layer_to_map)

        self.btn_export_csv = QPushButton(tr("btn_export_csv"))
        self.btn_export_csv.setEnabled(False)
        self.btn_export_csv.clicked.connect(self.export_to_csv)

        self.btn_export_pdf = QPushButton(tr("btn_export_pdf"))
        self.btn_export_pdf.setEnabled(False)
        self.btn_export_pdf.clicked.connect(self.export_to_pdf)

        out_layout.addWidget(self.btn_add_layer)
        out_layout.addWidget(self.btn_export_csv)
        out_layout.addWidget(self.btn_export_pdf)
        main_layout.addLayout(out_layout)

        self.lbl_pdf_scope = QLabel(tr("lbl_pdf_scope_all"))
        main_layout.addWidget(self.lbl_pdf_scope)
        self.tbl_results.itemChanged.connect(self.on_check_changed)
        self.tbl_net.itemChanged.connect(self.on_check_changed)
        self.tbl_results.itemSelectionChanged.connect(self.update_pdf_scope_label)
        self.tbl_net.itemSelectionChanged.connect(self.update_pdf_scope_label)

        self.cmb_base_layer.layerChanged.connect(self.on_base_layer_changed)
        self.on_base_layer_changed(self.cmb_base_layer.currentLayer())

    def on_base_layer_changed(self, layer):
        self.cmb_base_field.setLayer(layer)
        self.populate_overlay_layers()

    def populate_overlay_layers(self):
        self.tbl_overlays.setRowCount(0)
        base_layer = self.cmb_base_layer.currentLayer()
        user_role = USER_ROLE

        for layer in QgsProject.instance().mapLayers().values():
            if not isinstance(layer, QgsVectorLayer):
                continue
            if layer.geometryType() != polygon_geometry_type():
                continue
            if base_layer and layer.id() == base_layer.id():
                continue

            row = self.tbl_overlays.rowCount()
            self.tbl_overlays.insertRow(row)

            chk_item = QTableWidgetItem()
            chk_item.setFlags(chk_item.flags() | USER_CHECKABLE)
            chk_item.setCheckState(CHECKED)
            chk_item.setData(user_role, layer.id())
            self.tbl_overlays.setItem(row, 0, chk_item)

            self.tbl_overlays.setItem(row, 1, QTableWidgetItem(layer.name()))

            field_combo = QComboBox()
            field_combo.addItem(tr("use_feat_id"), "")
            for field in layer.fields():
                field_combo.addItem(field.name(), field.name())
            self.tbl_overlays.setCellWidget(row, 2, field_combo)

    def toggle_all_overlays(self, select: bool):
        state = CHECKED if select else UNCHECKED
        for row in range(self.tbl_overlays.rowCount()):
            item = self.tbl_overlays.item(row, 0)
            if item:
                item.setCheckState(state)

    def start_analysis(self):
        base_layer = self.cmb_base_layer.currentLayer()
        if not base_layer:
            QMessageBox.warning(self, tr("warn_title"), tr("warn_no_base"))
            return

        selected_overlays = []
        user_role = USER_ROLE

        for row in range(self.tbl_overlays.rowCount()):
            chk_item = self.tbl_overlays.item(row, 0)
            if chk_item and chk_item.checkState() == CHECKED:
                layer_id = chk_item.data(user_role)
                ov_layer = QgsProject.instance().mapLayer(layer_id)
                combo = self.tbl_overlays.cellWidget(row, 2)
                field_name = combo.currentData() if combo else ""
                if ov_layer:
                    selected_overlays.append((ov_layer, field_name))

        if not selected_overlays:
            QMessageBox.warning(self, tr("warn_title"), tr("warn_no_ov"))
            return

        self.last_base_layer_id = base_layer.id()
        self.last_base_field = self.cmb_base_field.currentField()
        if base_layer.id() not in self._sel_connected:
            try:
                base_layer.selectionChanged.connect(self.update_pdf_scope_label)
                self._sel_connected.add(base_layer.id())
            except (TypeError, RuntimeError) as exc:
                log_message(f"selectionChanged could not be connected: {exc}", "Warning")

        self.btn_run.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_add_layer.setEnabled(False)
        self.btn_export_csv.setEnabled(False)
        self.btn_export_pdf.setEnabled(False)
        self.progress_bar.setValue(0)
        self.tbl_results.setRowCount(0)
        self.tbl_net.setRowCount(0)

        self.current_task = OverlapAnalysisTask(
            base_layer=base_layer,
            overlay_layers=selected_overlays,
            base_id_field=self.cmb_base_field.currentField(),
            min_sliver_area=self.spn_sliver.value(),
            only_selected=self.chk_only_selected.isChecked()
        )
        self.current_task.progressChanged.connect(lambda p: self.progress_bar.setValue(int(p)))
        self.current_task.analysisFinished.connect(self.on_analysis_finished)
        self.current_task.taskTerminated.connect(self.on_analysis_terminated)

        QgsApplication.taskManager().addTask(self.current_task)

    def cancel_analysis(self):
        if self.current_task:
            self.current_task.cancel()

    def on_analysis_terminated(self):
        self.btn_run.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setValue(0)

    def on_analysis_finished(self, detail_results: list, net_results: list, summary: dict):
        self.btn_run.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setValue(100)

        self.detail_results = detail_results
        self.net_results = net_results

        self.populate_detail_table(detail_results)
        self.populate_net_table(net_results)

        has_detail = len(detail_results) > 0
        has_any = has_detail or len(net_results) > 0
        self.btn_add_layer.setEnabled(has_detail)
        self.btn_export_csv.setEnabled(has_any)
        self.btn_export_pdf.setEnabled(has_any)

    def populate_detail_table(self, results: list):
        self._syncing = True
        self.tbl_results.setSortingEnabled(False)
        self.tbl_results.setRowCount(len(results))
        user_role = USER_ROLE

        for row_idx, r in enumerate(results):
            id_item = QTableWidgetItem(str(r["base_id"]))
            id_item.setData(user_role, r["geometry_wkt"])
            id_item.setData(int(user_role) + 1, r.get("base_fid"))
            id_item.setFlags(id_item.flags() | USER_CHECKABLE)
            id_item.setCheckState(UNCHECKED)

            ov_layer_item = QTableWidgetItem(str(r["overlay_layer"]))
            ov_id_item = QTableWidgetItem(str(r["overlay_id"]))

            base_ha_item = NumericTableWidgetItem(f"{r['base_area_ha']:.4f}")
            ov_m2_item = NumericTableWidgetItem(f"{r['overlap_area_m2']:.2f}")
            ov_ha_item = NumericTableWidgetItem(f"{r['overlap_area_ha']:.4f}")
            pct_item = NumericTableWidgetItem(f"{r['overlap_pct']:.2f}")

            for item in (base_ha_item, ov_m2_item, ov_ha_item, pct_item):
                item.setTextAlignment(ALIGN_RIGHT)

            if r["overlap_pct"] >= 50.0:
                pct_item.setBackground(QColor(255, 204, 204))
            elif r["overlap_pct"] >= 15.0:
                pct_item.setBackground(QColor(255, 235, 190))

            self.tbl_results.setItem(row_idx, 0, id_item)
            self.tbl_results.setItem(row_idx, 1, ov_layer_item)
            self.tbl_results.setItem(row_idx, 2, ov_id_item)
            self.tbl_results.setItem(row_idx, 3, base_ha_item)
            self.tbl_results.setItem(row_idx, 4, ov_m2_item)
            self.tbl_results.setItem(row_idx, 5, ov_ha_item)
            self.tbl_results.setItem(row_idx, 6, pct_item)

        self.tbl_results.setSortingEnabled(True)
        self._syncing = False
        self.apply_target_filter()

    def populate_net_table(self, net_results: list):
        self._syncing = True
        self.tbl_net.setSortingEnabled(False)
        self.tbl_net.setRowCount(len(net_results))
        user_role = USER_ROLE

        for row_idx, r in enumerate(net_results):
            id_item = QTableWidgetItem(str(r["base_id"]))
            id_item.setData(user_role, r["usable_geometry_wkt"])
            id_item.setData(int(user_role) + 1, r.get("base_fid"))
            id_item.setFlags(id_item.flags() | USER_CHECKABLE)
            id_item.setCheckState(UNCHECKED)

            b_ha = NumericTableWidgetItem(f"{r['base_area_ha']:.4f}")
            u_ha = NumericTableWidgetItem(f"{r['union_overlap_ha']:.4f}")
            u_pct = NumericTableWidgetItem(f"{r['union_overlap_pct']:.2f}")
            net_ha = NumericTableWidgetItem(f"{r['net_usable_ha']:.4f}")
            net_m2 = NumericTableWidgetItem(f"{r['net_usable_m2']:.2f}")

            for item in (b_ha, u_ha, u_pct, net_ha, net_m2):
                item.setTextAlignment(ALIGN_RIGHT)

            net_ha.setBackground(QColor(210, 245, 210))

            self.tbl_net.setItem(row_idx, 0, id_item)
            self.tbl_net.setItem(row_idx, 1, b_ha)
            self.tbl_net.setItem(row_idx, 2, u_ha)
            self.tbl_net.setItem(row_idx, 3, u_pct)
            self.tbl_net.setItem(row_idx, 4, net_ha)
            self.tbl_net.setItem(row_idx, 5, net_m2)

        self.tbl_net.setSortingEnabled(True)
        self._syncing = False
        self.apply_target_filter()

    def zoom_and_flash_wkt(self, wkt_str: str):
        if not wkt_str:
            return
        geom = QgsGeometry.fromWkt(wkt_str)
        if not geom or geom.isEmpty():
            return

        base_layer = self.cmb_base_layer.currentLayer()
        if not base_layer:
            return

        layer_crs = base_layer.crs()
        canvas_crs = self.canvas.mapSettings().destinationCrs()

        geom_for_canvas = QgsGeometry(geom)
        if layer_crs != canvas_crs:
            transform = QgsCoordinateTransform(layer_crs, canvas_crs, QgsProject.instance())
            geom_for_canvas.transform(transform)

        bbox = geom_for_canvas.boundingBox()
        bbox.scale(1.4)
        self.canvas.setExtent(bbox)
        self.canvas.refresh()

        self.canvas.flashGeometries(
            [geom],
            crs=layer_crs,
            startColor=QColor(255, 0, 0, 200),
            endColor=QColor(255, 255, 0, 40),
            flashes=4,
            duration=450
        )

    def on_detail_row_clicked(self, row: int, col: int):
        user_role = USER_ROLE
        item = self.tbl_results.item(row, 0)
        if item:
            self.zoom_and_flash_wkt(item.data(user_role))

    def on_net_row_clicked(self, row: int, col: int):
        user_role = USER_ROLE
        item = self.tbl_net.item(row, 0)
        if item:
            self.zoom_and_flash_wkt(item.data(user_role))

    # ------------------------------------------------------------------
    # Hedef ID filtresi
    # ------------------------------------------------------------------
    @staticmethod
    def _split_tokens(text):
        return [t.strip().lower() for t in text.replace(";", ",").split(",") if t.strip()]

    def _filter_tokens(self):
        return self._split_tokens(self.txt_filter.text())

    def _overlay_filter_tokens(self):
        return self._split_tokens(self.txt_filter_ov.text())

    def _any_filter_active(self):
        return bool(self._filter_tokens() or self._overlay_filter_tokens())

    def apply_target_filter(self, *_):
        tgt = self._filter_tokens()
        ovl = self._overlay_filter_tokens()
        fid_role = self._fid_role

        # Detay tablosu: Hedef ID (sütun 0) ve Çakışan ID (sütun 2) filtresi
        fids_with_match = set()
        for row in range(self.tbl_results.rowCount()):
            item = self.tbl_results.item(row, 0)
            ov_item = self.tbl_results.item(row, 2)
            t_text = item.text().lower() if item else ""
            o_text = ov_item.text().lower() if ov_item else ""
            t_ok = (not tgt) or any(t in t_text for t in tgt)
            o_ok = (not ovl) or any(t in o_text for t in ovl)
            self.tbl_results.setRowHidden(row, not (t_ok and o_ok))
            if t_ok and o_ok and item is not None:
                fid = item.data(fid_role)
                if fid is not None:
                    fids_with_match.add(int(fid))

        # Net özet tablosu: Hedef ID filtresi; çakışan ID filtresi varsa sadece
        # o çakışan ID ile kesişen hedefler kalır
        for row in range(self.tbl_net.rowCount()):
            item = self.tbl_net.item(row, 0)
            t_text = item.text().lower() if item else ""
            t_ok = (not tgt) or any(t in t_text for t in tgt)
            if ovl:
                fid = item.data(fid_role) if item else None
                t_ok = t_ok and fid is not None and int(fid) in fids_with_match
            self.tbl_net.setRowHidden(row, not t_ok)

        total = self.tbl_net.rowCount()
        shown = sum(1 for r in range(total) if not self.tbl_net.isRowHidden(r))
        self.lbl_filter_count.setText(tr("lbl_filter_count", v=shown, t=total) if total else "")
        self.update_pdf_scope_label()

    # ---- Tick box (çoklu nesne işaretleme) ----
    def _set_target_checked(self, fid, checked: bool):
        """Aynı hedef nesnenin tüm satırlarındaki (iki tabloda) kutuyu eşitler."""
        state = CHECKED if checked else UNCHECKED
        fid_role = self._fid_role
        self._syncing = True
        try:
            for tbl in (self.tbl_results, self.tbl_net):
                for row in range(tbl.rowCount()):
                    item = tbl.item(row, 0)
                    if item is not None and item.data(fid_role) == fid and item.checkState() != state:
                        item.setCheckState(state)
        finally:
            self._syncing = False

    def on_check_changed(self, item):
        if self._syncing or item is None or item.column() != 0:
            return
        fid = item.data(self._fid_role)
        if fid is None:
            return
        self._set_target_checked(fid, item.checkState() == CHECKED)
        self.update_pdf_scope_label()

    def _checked_target_fids(self):
        fids = set()
        fid_role = self._fid_role
        for row in range(self.tbl_net.rowCount()):
            item = self.tbl_net.item(row, 0)
            if item is not None and item.checkState() == CHECKED:
                fid = item.data(fid_role)
                if fid is not None:
                    fids.add(int(fid))
        return fids

    def check_visible_targets(self):
        for fid in self._visible_target_fids():
            self._set_target_checked(fid, True)
        self.update_pdf_scope_label()

    def uncheck_all_targets(self):
        for fid in self._known_target_fids():
            self._set_target_checked(fid, False)
        self.update_pdf_scope_label()

    @property
    def _fid_role(self):
        user_role = USER_ROLE
        return int(user_role) + 1

    def _selected_target_fids(self):
        """Listede (aktif sekmede, yoksa diğerinde) seçili satırın hedef nesnesinin feature id'si."""
        tables = [self.tbl_net, self.tbl_results] if self.tabs.currentIndex() == 1 \
            else [self.tbl_results, self.tbl_net]
        for tbl in tables:
            sel = tbl.selectedItems()
            if sel:
                row = sel[0].row()
                item = tbl.item(row, 0)
                if item is not None and not tbl.isRowHidden(row):
                    fid = item.data(self._fid_role)
                    if fid is not None:
                        return {int(fid)}
        return None

    def _visible_target_fids(self):
        fids = set()
        for r in range(self.tbl_net.rowCount()):
            item = self.tbl_net.item(r, 0)
            if item is not None and not self.tbl_net.isRowHidden(r):
                fid = item.data(self._fid_role)
                if fid is not None:
                    fids.add(int(fid))
        return fids

    def _known_target_fids(self):
        return {int(r["base_fid"]) for r in self.net_results if r.get("base_fid") is not None}

    def _resolve_pdf_target_fids(self, base_layer=None):
        """PDF kapsamı: 1) listede seçili satır, 2) haritada seçili nesne(ler),
        3) filtrede görünen hedefler, 4) None = tüm liste."""
        checked = self._checked_target_fids()
        if checked:
            return checked

        fids = self._selected_target_fids()
        if fids is not None:
            return fids

        src_layer = QgsProject.instance().mapLayer(self.last_base_layer_id) or base_layer
        if src_layer is not None:
            try:
                map_fids = {int(f.id()) for f in src_layer.selectedFeatures()} & self._known_target_fids()
            except (RuntimeError, TypeError, ValueError):
                map_fids = set()
            if map_fids:
                return map_fids

        if self._any_filter_active():
            return self._visible_target_fids()
        return None

    def _scope_label_text(self, fids):
        ids = sorted({str(r["base_id"]) for r in self.net_results if r.get("base_fid") in fids})
        text = ", ".join(ids[:5])
        if len(ids) > 5:
            text += f" … (+{len(ids) - 5})"
        return text

    def update_pdf_scope_label(self, *_):
        if not hasattr(self, "lbl_pdf_scope"):
            return
        fids = self._resolve_pdf_target_fids()
        checked = self._checked_target_fids()
        if fids is None:
            self.lbl_pdf_scope.setText(tr("lbl_pdf_scope_all"))
        elif checked and fids == checked:
            self.lbl_pdf_scope.setText(
                tr("lbl_pdf_scope_checked", n=len(fids), ids=self._scope_label_text(fids) or "-"))
        else:
            self.lbl_pdf_scope.setText(tr("lbl_pdf_scope_sel", ids=self._scope_label_text(fids) or "-"))
        if fids is not None and len(fids) > 1:
            self.lbl_pdf_scope.setText(self.lbl_pdf_scope.text() + tr("lbl_pdf_separate"))

    def _target_focus_wkt(self, layer, fids):
        """Hedef nesne(ler)in geometrisini harita (canvas) CRS'inde WKT olarak döner."""
        geoms = []
        for fid in fids:
            feat = layer.getFeature(fid)
            g = feat.geometry() if feat is not None else None
            if g and not g.isEmpty():
                geoms.append(g)
        if not geoms:
            return None
        geom = QgsGeometry.collectGeometry(geoms)
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        if layer.crs() != canvas_crs:
            geom.transform(QgsCoordinateTransform(layer.crs(), canvas_crs, QgsProject.instance()))
        return geom.asWkt()

    def add_memory_layer_to_map(self):
        base_layer = self.cmb_base_layer.currentLayer()
        if base_layer and self.detail_results:
            create_overlap_memory_layer(self.detail_results, base_layer.crs().authid())
            self.iface.messageBar().pushSuccess(
                "Overlap Analyzer", tr("msg_layer_added")
            )

    def export_to_csv(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, tr("dlg_save_csv"), tr("dlg_csv_default"), tr("filter_csv")
        )
        if filepath:
            export_results_to_csv(self.detail_results, self.net_results, filepath)
            QMessageBox.information(self, tr("msg_success"), f'{tr("msg_csv_saved")}\n{filepath}')

    @staticmethod
    def _safe_name(text):
        name = re.sub(r'[\\/:*?"<>|\s]+', "_", str(text)).strip("._")
        return name[:60] or "nesne"

    def _write_pdf(self, filepath, base_layer, src_layer, fids):
        """PDF üretir.
        fids=None      -> tüm liste için tek kapsam
        1 nesne        -> o nesne için tek sayfa grubu
        >1 nesne       -> TEK PDF, her nesne ayrı harita + ayrı bilgi kartıyla ayrı sayfada
        """
        crs_authid = base_layer.crs().authid()

        if fids is None:
            OverlapReportGenerator.export_pdf_report(
                filepath=filepath, canvas=self.canvas,
                base_layer_name=base_layer.name(), crs_authid=crs_authid,
                detail_results=self.detail_results, net_results=self.net_results,
                focus_wkt=None, scope_label=None
            )
            return 1

        ordered = sorted(fids, key=lambda f: (self._scope_label_text({f}).lower(), f))
        sections = []
        for fid in ordered:
            one = {fid}
            sections.append({
                "detail_results": [r for r in self.detail_results if r.get("base_fid") in one],
                "net_results": [r for r in self.net_results if r.get("base_fid") in one],
                "focus_wkt": self._target_focus_wkt(src_layer, one),
                "scope_label": self._scope_label_text(one),
            })

        if len(sections) == 1:
            sec = sections[0]
            OverlapReportGenerator.export_pdf_report(
                filepath=filepath, canvas=self.canvas,
                base_layer_name=base_layer.name(), crs_authid=crs_authid, **sec
            )
        else:
            OverlapReportGenerator.export_multi_pdf_report(
                filepath=filepath, canvas=self.canvas,
                base_layer_name=base_layer.name(), crs_authid=crs_authid, sections=sections
            )
        return len(sections)

    def export_to_pdf(self):
        base_layer = self.cmb_base_layer.currentLayer()
        if not base_layer or not self.net_results:
            return

        target_fids = self._resolve_pdf_target_fids(base_layer)
        if target_fids is not None and not target_fids:
            QMessageBox.warning(self, tr("warn_title"), tr("warn_no_filter_match"))
            return

        prefix = tr("dlg_pdf_prefix")
        if target_fids is None:
            default_name = tr("dlg_pdf_default")
        elif len(target_fids) == 1:
            fid = next(iter(target_fids))
            default_name = f"{prefix}_{self._safe_name(self._scope_label_text({fid}))}.pdf"
        else:
            default_name = f"{prefix}_{len(target_fids)}.pdf"

        filepath, _ = QFileDialog.getSaveFileName(
            self, tr("dlg_save_pdf"), default_name, tr("filter_pdf")
        )
        if not filepath:
            return

        src_layer = QgsProject.instance().mapLayer(self.last_base_layer_id) or base_layer
        QApplication.setOverrideCursor(WAIT_CURSOR)
        try:
            page_groups = self._write_pdf(filepath, base_layer, src_layer, target_fids)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, tr("msg_pdf_err_title"), f'{tr("msg_pdf_err")}\n{str(e)}')
            return
        QApplication.restoreOverrideCursor()

        if page_groups > 1:
            msg = tr("msg_pdf_multi_saved", n=page_groups)
        else:
            msg = tr("msg_pdf_saved")
        self.iface.messageBar().pushSuccess("Overlap Analyzer", f"{msg} {filepath}")
