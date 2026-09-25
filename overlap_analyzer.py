# -*- coding: utf-8 -*-
"""
Overlap Analyzer - QGIS Plugin
Compatible with Qt5 and Qt6.
"""
import os
import csv

from qgis.PyQt import QtCore, QtGui, QtWidgets
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter,
    QGroupBox, QListWidget, QListWidgetItem, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QLabel, QProgressBar, QMessageBox, QCheckBox, QWidget,
    QDoubleSpinBox, QLineEdit
)
from qgis.PyQt.QtGui import QIcon, QColor, QDesktopServices

from qgis.core import (
    QgsProject, QgsVectorLayer,
    QgsWkbTypes, QgsCoordinateTransform
)

from .worker import IntersectionThread

# Qt5/Qt6 enum shims
QT_VERSION = 6 if hasattr(Qt, 'Orientation') else 5

if QT_VERSION == 6:
    Qt_Horizontal = Qt.Orientation.Horizontal
    Qt_Checked = Qt.CheckState.Checked
    Qt_Unchecked = Qt.CheckState.Unchecked
    Qt_UserRole = Qt.ItemDataRole.UserRole
    Qt_EditRole = Qt.ItemDataRole.EditRole
    Qt_ItemIsUserCheckable = Qt.ItemFlag.ItemIsUserCheckable
    Qt_NoEditTriggers = QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
    Qt_ItemIsEditable = Qt.ItemFlag.ItemIsEditable
    QAbstractItemView_MultiSelection = QtWidgets.QAbstractItemView.SelectionMode.MultiSelection
    QAbstractItemView_SelectRows = QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
    QHeaderView_Stretch = QHeaderView.ResizeMode.Stretch
    QHeaderView_ResizeToContents = QHeaderView.ResizeMode.ResizeToContents
    Qt_WindowMinMaxCloseHints = (
        Qt.WindowType.WindowMinimizeButtonHint
        | Qt.WindowType.WindowMaximizeButtonHint
        | Qt.WindowType.WindowCloseButtonHint
    )
else:
    Qt_Horizontal = Qt.Orientation.Horizontal
    Qt_Checked = Qt.CheckState.Checked
    Qt_Unchecked = Qt.CheckState.Unchecked
    Qt_UserRole = Qt.ItemDataRole.UserRole
    Qt_EditRole = Qt.ItemDataRole.EditRole
    Qt_ItemIsUserCheckable = Qt.ItemFlag.ItemIsUserCheckable
    Qt_NoEditTriggers = QtWidgets.QAbstractItemView.NoEditTriggers
    Qt_ItemIsEditable = Qt.ItemFlag.ItemIsEditable
    QAbstractItemView_MultiSelection = QtWidgets.QAbstractItemView.MultiSelection
    QAbstractItemView_SelectRows = QtWidgets.QAbstractItemView.SelectRows
    QHeaderView_Stretch = QHeaderView.ResizeMode.Stretch
    QHeaderView_ResizeToContents = QHeaderView.ResizeMode.ResizeToContents
    Qt_WindowMinMaxCloseHints = (
        Qt.WindowType.WindowMinimizeButtonHint
        | Qt.WindowType.WindowMaximizeButtonHint
        | Qt.WindowType.WindowCloseButtonHint
    )


class OverlapAnalyzer:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        self.dialog = None

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.action = QtWidgets.QAction(
            QIcon(icon_path), u'Overlap Analyzer', self.iface.mainWindow()
        )
        self.action.triggered.connect(self.run)
        self.action.setStatusTip(u'Spatial overlap analysis between layers')
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(u'&Overlap Analyzer', self.action)

    def unload(self):
        if self.action:
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginMenu(u'&Overlap Analyzer', self.action)

    def run(self):
        if self.dialog is None:
            self.dialog = OverlapAnalyzerDialog(self.iface)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()


class OverlapAnalyzerDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self.worker = None
        self.results = []
        # Which "only selected features" options the results currently shown
        # were produced with. When either is on, the map selection is part of
        # the analysis input and must not be touched when a result row is
        # clicked.
        self.results_src_only_selected = False
        self.results_ref_only_selected = False

        self.setWindowTitle(u'Overlap Analyzer')
        # By default a QDialog only gets a close button on Windows; add
        # minimize/maximize so the window can be shrunk or made full screen.
        self.setWindowFlags(self.windowFlags() | Qt_WindowMinMaxCloseHints)
        self.setMinimumSize(700, 700)
        self.resize(900, 750)

        self.setup_ui()
        self.load_layers()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.load_layers()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        main_splitter = QSplitter(Qt_Horizontal)

        # ── Left: Layer Selection ──
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        group1 = QGroupBox(u'Layers to Search')
        g1_layout = QVBoxLayout()
        self.chk_select_all = QCheckBox(u'Select All')
        self.chk_select_all.stateChanged.connect(self.toggle_select_all)
        g1_layout.addWidget(self.chk_select_all)
        self.lst_source_layers = QListWidget()
        self.lst_source_layers.setSelectionMode(QAbstractItemView_MultiSelection)
        g1_layout.addWidget(self.lst_source_layers)

        self.chk_src_only_selected = QCheckBox(u'Only process selected features')
        self.chk_src_only_selected.setToolTip(
            u'If checked, only features selected on the map are included in '
            u'the analysis for the checked layers.\n'
            u'Layers with no selected features are skipped. '
            u'The reference layer is not affected by this option.'
        )
        g1_layout.addWidget(self.chk_src_only_selected)

        btn_refresh1 = QPushButton(u'Refresh')
        btn_refresh1.clicked.connect(self.load_layers)
        g1_layout.addWidget(btn_refresh1)
        group1.setLayout(g1_layout)
        left_layout.addWidget(group1)

        group2 = QGroupBox(u'Layer to Check (Reference)')
        g2_layout = QVBoxLayout()
        self.cmb_reference_layer = QComboBox()
        g2_layout.addWidget(QLabel(u'Reference Layer:'))
        g2_layout.addWidget(self.cmb_reference_layer)

        self.chk_ref_only_selected = QCheckBox(u'Only process selected features')
        self.chk_ref_only_selected.setToolTip(
            u'If checked, only the features selected on the map in the '
            u'reference layer are used for checking.\n'
            u'Independent of the option in the layers-to-search area.'
        )
        g2_layout.addWidget(self.chk_ref_only_selected)

        g2_layout.addWidget(QLabel(u'Buffer Distance (meters):'))
        self.spn_buffer = QDoubleSpinBox()
        self.spn_buffer.setRange(0, 999999.0)
        self.spn_buffer.setSuffix(' m')
        self.spn_buffer.setDecimals(1)
        self.spn_buffer.setValue(0)
        g2_layout.addWidget(self.spn_buffer)

        btn_refresh2 = QPushButton(u'Refresh')
        btn_refresh2.clicked.connect(self.load_layers)
        g2_layout.addWidget(btn_refresh2)
        group2.setLayout(g2_layout)
        left_layout.addWidget(group2)

        self.btn_analyze = QPushButton(u'Analyze')
        self.btn_analyze.setStyleSheet(
            'QPushButton { background-color: #4CAF50; color: white; '
            'font-weight: bold; padding: 8px; border-radius: 4px; }'
            'QPushButton:hover { background-color: #45a049; }'
        )
        self.btn_analyze.clicked.connect(self.run_analysis)
        left_layout.addWidget(self.btn_analyze)

        main_splitter.addWidget(left_widget)

        # ── Right: Results + Attributes ──
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # -- Results: one row per feature, every attribute field as a column --
        results_group = QGroupBox(u'Results List')
        r_layout = QVBoxLayout()

        self.lbl_result_count = QLabel(u'Results found: 0')
        r_layout.addWidget(self.lbl_result_count)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel(u'Filter:'))
        self.cmb_filter_field = QComboBox()
        self.cmb_filter_field.addItem(u'All')
        self.cmb_filter_field.currentIndexChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.cmb_filter_field)
        self.txt_filter_value = QLineEdit()
        self.txt_filter_value.setPlaceholderText(u'Value contains…')
        self.txt_filter_value.textChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.txt_filter_value)
        self.btn_filter_clear = QPushButton(u'Clear Filter')
        self.btn_filter_clear.clicked.connect(self.clear_filter)
        filter_layout.addWidget(self.btn_filter_clear)
        r_layout.addLayout(filter_layout)

        self.table_results = QTableWidget()
        self.table_results.setColumnCount(3)
        self.table_results.setHorizontalHeaderLabels([
            u'Layer Name', u'Feature ID', u'Status'
        ])
        self.table_results.horizontalHeader().setSectionResizeMode(QHeaderView_ResizeToContents)
        self.table_results.setSelectionBehavior(QAbstractItemView_SelectRows)
        self.table_results.setAlternatingRowColors(True)
        self.table_results.setEditTriggers(Qt_NoEditTriggers)
        # Clicking a column header sorts by it: ascending, click again for
        # descending. Qt provides this natively once sorting is enabled.
        self.table_results.setSortingEnabled(True)
        self.table_results.itemSelectionChanged.connect(self.on_result_selected)
        r_layout.addWidget(self.table_results)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        r_layout.addWidget(self.progress)

        self.btn_export = QPushButton(u'Save as CSV')
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_csv)
        r_layout.addWidget(self.btn_export)

        results_group.setLayout(r_layout)
        right_layout.addWidget(results_group)

        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([300, 500])

        main_layout.addWidget(main_splitter)

    def load_layers(self):
        self.lst_source_layers.clear()
        self.cmb_reference_layer.clear()
        self.results = []
        self.table_results.setRowCount(0)
        self.table_results.setColumnCount(3)
        self.table_results.setHorizontalHeaderLabels([
            u'Layer Name', u'Feature ID', u'Status'
        ])
        self._reset_filter_controls([])
        self._base_count_text = u'Results found: 0'
        self._total_result_count = 0
        self.lbl_result_count.setText(self._base_count_text)
        self.btn_export.setEnabled(False)

        layers = QgsProject.instance().mapLayers().values()
        vector_layers = []
        for layer in layers:
            if isinstance(layer, QgsVectorLayer) and layer.isValid():
                geom_type = layer.geometryType()
                if geom_type in (0, 1, 2):
                    vector_layers.append(layer)

        vector_layers.sort(key=lambda lyr: lyr.name().lower())

        if not vector_layers:
            self.iface.messageBar().pushWarning(
                u'Warning', u'No vector layer found in the project.'
            )
            return

        for layer in vector_layers:
            item = QListWidgetItem(layer.name())
            item.setData(Qt_UserRole, layer.id())
            item.setFlags(item.flags() | Qt_ItemIsUserCheckable)
            item.setCheckState(Qt_Unchecked)
            self.lst_source_layers.addItem(item)
            self.cmb_reference_layer.addItem(layer.name(), layer.id())

    def toggle_select_all(self, state=None):
        # isChecked() is used instead of comparing `state` with Qt.Checked:
        # under Qt6 the signal emits a plain int, which does not compare
        # equal to the Qt.CheckState enum.
        check_state = Qt_Checked if self.chk_select_all.isChecked() else Qt_Unchecked
        for i in range(self.lst_source_layers.count()):
            self.lst_source_layers.item(i).setCheckState(check_state)

    def get_selected_source_layers(self):
        selected = []
        for i in range(self.lst_source_layers.count()):
            item = self.lst_source_layers.item(i)
            if item.checkState() == Qt_Checked:
                layer = QgsProject.instance().mapLayer(item.data(Qt_UserRole))
                if layer:
                    selected.append(layer)
        return selected

    def get_reference_layer(self):
        layer_id = self.cmb_reference_layer.currentData()
        if layer_id:
            return QgsProject.instance().mapLayer(layer_id)
        return None

    def run_analysis(self):
        source_layers = self.get_selected_source_layers()
        reference_layer = self.get_reference_layer()

        if not source_layers:
            QMessageBox.warning(self, u'Warning', u'Please select at least one layer to search.')
            return
        if reference_layer is None:
            QMessageBox.warning(self, u'Warning', u'Please select a reference layer.')
            return
        if reference_layer in source_layers:
            QMessageBox.warning(self, u'Warning', u'The reference layer must not be among the layers to search.')
            return

        # Reference layer: optionally restrict to its selected features.
        ref_only_selected = self.chk_ref_only_selected.isChecked()
        reference_fids = None
        if ref_only_selected:
            reference_fids = list(reference_layer.selectedFeatureIds())
            if not reference_fids:
                QMessageBox.warning(
                    self, u'Warning',
                    u'The reference layer has no selected feature.\n'
                    u'Select a feature from the reference layer on the map, '
                    u'or turn off "Only process selected features" in the '
                    u'reference area.'
                )
                return

        # Source layers: optionally restrict to their selected features.
        src_only_selected = self.chk_src_only_selected.isChecked()
        selected_fids = None
        if src_only_selected:
            # Snapshot the selection now (GUI thread) so the worker thread
            # does not depend on selection changes made while it runs.
            selected_fids = {}
            skipped = []
            for lyr in source_layers:
                ids = list(lyr.selectedFeatureIds())
                if ids:
                    selected_fids[lyr.id()] = ids
                else:
                    skipped.append(lyr.name())

            if not selected_fids:
                QMessageBox.warning(
                    self, u'Warning',
                    u'None of the checked layers have a selected feature.\n'
                    u'Select features on the map, or turn off "Only process '
                    u'selected features" in the layers-to-search area.'
                )
                return

            if skipped:
                self.iface.messageBar().pushWarning(
                    u'Warning',
                    u'Layers with no selected features were skipped: '
                    + u', '.join(skipped)
                )
            source_layers = [lyr for lyr in source_layers if lyr.id() in selected_fids]

        if self.worker is not None:
            if self.worker.isRunning():
                self.worker.stop()
                self.worker.wait(5000)
            for sig in ('finished', 'error', 'progress'):
                try:
                    getattr(self.worker, sig).disconnect()
                except TypeError:
                    pass
            self.worker = None

        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setText(u'Analyzing...')
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.results = []
        self.results_src_only_selected = src_only_selected
        self.results_ref_only_selected = ref_only_selected
        self.table_results.setRowCount(0)
        self.btn_export.setEnabled(False)

        buffer_dist = self.spn_buffer.value()

        self.worker = IntersectionThread(
            source_layers, reference_layer, buffer_dist, selected_fids,
            reference_fids
        )
        self.worker.finished.connect(self.on_analysis_finished)
        self.worker.error.connect(self.on_analysis_error)
        self.worker.progress.connect(self.update_progress)
        self.worker.start()

    def on_analysis_finished(self, results):
        self.results = results
        self.populate_results_table(results)
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText(u'Analyze')
        self.progress.setVisible(False)
        self.btn_export.setEnabled(bool(results))

    def on_analysis_error(self, message):
        QMessageBox.critical(self, u'Error', f'An error occurred during analysis:\n{message}')
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText(u'Analyze')
        self.progress.setVisible(False)

    def update_progress(self, value):
        if self.progress.maximum() == 0:
            self.progress.setRange(0, 100)
        self.progress.setValue(value)

    def _collect_result_fields(self, results):
        """Resolve each result's layer once and build the ordered union of
        attribute field names across every layer involved, so features from
        different source layers can share one column set. Returns
        (layer_cache: {layer_id: layer}, field_names: [str, ...])."""
        layer_cache = {}
        field_names = []
        seen_fields = set()

        for result in results:
            layer_id = result['layer_id']
            if layer_id not in layer_cache:
                layer_cache[layer_id] = QgsProject.instance().mapLayer(layer_id)
            layer = layer_cache[layer_id]
            if layer is None:
                continue
            for f in layer.fields():
                if f.name() not in seen_fields:
                    seen_fields.add(f.name())
                    field_names.append(f.name())

        return layer_cache, field_names

    def populate_results_table(self, results):
        # Sorting must be off while rows are inserted, or QTableWidget
        # resorts after every setItem call and rows/data mismatch.
        self.table_results.setSortingEnabled(False)
        self.table_results.setRowCount(0)

        if not results:
            self.table_results.setColumnCount(3)
            self.table_results.setHorizontalHeaderLabels([
                u'Layer Name', u'Feature ID', u'Status'
            ])
            self._reset_filter_controls([])
            self._base_count_text = u'No matching area found.'
            self._total_result_count = 0
            self.lbl_result_count.setText(self._base_count_text)
            self.table_results.setSortingEnabled(True)
            return

        layer_cache, field_names = self._collect_result_fields(results)

        base_headers = [u'Layer Name', u'Feature ID', u'Status']
        self.table_results.setColumnCount(len(base_headers) + len(field_names))
        self.table_results.setHorizontalHeaderLabels(base_headers + field_names)
        self._reset_filter_controls(base_headers + field_names)

        self.table_results.setRowCount(len(results))
        for row, result in enumerate(results):
            layer_item = QTableWidgetItem(result['layer_name'])
            # The result's index is stashed here (not the row position, which
            # changes on sort) so a click can look the feature back up.
            layer_item.setData(Qt_UserRole, row)
            self.table_results.setItem(row, 0, layer_item)

            id_item = QTableWidgetItem()
            id_item.setData(Qt_EditRole, result['feature_id'])
            self.table_results.setItem(row, 1, id_item)

            status_item = QTableWidgetItem(result['status'])
            if result['status'] == u'Inside':
                status_item.setBackground(QColor(173, 216, 230))
            else:
                status_item.setBackground(QColor(144, 238, 144))
            self.table_results.setItem(row, 2, status_item)

            layer = layer_cache.get(result['layer_id'])
            attr_values = {}
            if layer is not None:
                feat = layer.getFeature(result['feature_id'])
                if feat.isValid():
                    for f in layer.fields():
                        attr_values[f.name()] = feat[f.name()]

            for col, field_name in enumerate(field_names, start=len(base_headers)):
                val = attr_values.get(field_name)
                attr_item = QTableWidgetItem()
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    attr_item.setData(Qt_EditRole, val)
                else:
                    attr_item.setData(Qt_EditRole, '' if val is None else str(val))
                self.table_results.setItem(row, col, attr_item)

        self.table_results.setSortingEnabled(True)

        count_text = f'Results found: {len(results)}'
        notes = []
        if self.results_src_only_selected:
            notes.append(u'search: selected only')
        if self.results_ref_only_selected:
            notes.append(u'reference: selected only')
        if notes:
            count_text += u'  (' + u'; '.join(notes) + u')'
        self._base_count_text = count_text
        self._total_result_count = len(results)
        self.lbl_result_count.setText(count_text)

    def _reset_filter_controls(self, headers):
        """Repopulate the filter's field dropdown for the current result
        columns and clear any previous filter text, without re-triggering
        apply_filter for each intermediate change."""
        self.cmb_filter_field.blockSignals(True)
        self.txt_filter_value.blockSignals(True)
        self.cmb_filter_field.clear()
        self.cmb_filter_field.addItem(u'All')
        self.cmb_filter_field.addItems(headers)
        self.txt_filter_value.clear()
        self.cmb_filter_field.blockSignals(False)
        self.txt_filter_value.blockSignals(False)

    def apply_filter(self):
        """Show only rows matching the filter text. With 'All' selected,
        a row matches if any column contains the text; otherwise only the
        chosen column is checked. An empty filter text shows every row
        from the last search again."""
        if self.table_results.rowCount() == 0:
            return

        field_index = self.cmb_filter_field.currentIndex()  # 0 = All
        text = self.txt_filter_value.text().strip().lower()
        visible_count = 0

        for row in range(self.table_results.rowCount()):
            if not text:
                match = True
            elif field_index <= 0:
                match = False
                for col in range(self.table_results.columnCount()):
                    item = self.table_results.item(row, col)
                    if item is not None and text in item.text().lower():
                        match = True
                        break
            else:
                item = self.table_results.item(row, field_index - 1)
                match = item is not None and text in item.text().lower()

            self.table_results.setRowHidden(row, not match)
            if match:
                visible_count += 1

        if text and visible_count != self._total_result_count:
            self.lbl_result_count.setText(
                f'{self._base_count_text}  —  Filter: '
                f'{visible_count}/{self._total_result_count} shown'
            )
        else:
            self.lbl_result_count.setText(self._base_count_text)

    def clear_filter(self):
        self.cmb_filter_field.blockSignals(True)
        self.cmb_filter_field.setCurrentIndex(0)
        self.cmb_filter_field.blockSignals(False)
        self.txt_filter_value.clear()
        self.apply_filter()

    def zoom_to_feature(self, layer, feat):
        """Zoom the map canvas to the given feature and highlight it via
        selection, regardless of the layer's CRS or the current view.
        Clears any selection left over on other layers from a previous
        click, since results can span multiple different source layers."""
        canvas = self.iface.mapCanvas()

        if self.results_src_only_selected or self.results_ref_only_selected:
            # The user's own selection (on source and/or reference layer) is
            # the analysis input here, so it must stay intact: zoom to the
            # feature and flash it instead of replacing/clearing selections.
            canvas.zoomToFeatureIds(layer, [feat.id()])
            canvas.flashFeatureIds(layer, [feat.id()])
            return

        for lyr in QgsProject.instance().mapLayers().values():
            if isinstance(lyr, QgsVectorLayer) and lyr is not layer:
                lyr.removeSelection()
        layer.removeSelection()
        layer.selectByIds([feat.id()])
        canvas.zoomToSelected(layer)
        canvas.refresh()

    def on_result_selected(self):
        selected = self.table_results.selectionModel().selectedRows()
        if not selected:
            return

        row = selected[0].row()
        # Column 0 carries the result's original index (see
        # populate_results_table), since sorting moves rows around.
        id_item = self.table_results.item(row, 0)
        if id_item is None:
            return
        result_index = id_item.data(Qt_UserRole)
        if result_index is None or result_index >= len(self.results):
            return
        result = self.results[result_index]

        layer = QgsProject.instance().mapLayer(result['layer_id'])
        if layer is None:
            return

        feat = layer.getFeature(result['feature_id'])

        if not feat.isValid():
            return

        self.zoom_to_feature(layer, feat)

    def _get_visible_results(self):
        """Results currently shown in the table, in their current (possibly
        sorted) order, skipping rows hidden by the active filter."""
        visible = []
        for row in range(self.table_results.rowCount()):
            if self.table_results.isRowHidden(row):
                continue
            item = self.table_results.item(row, 0)
            if item is None:
                continue
            idx = item.data(Qt_UserRole)
            if idx is None or idx >= len(self.results):
                continue
            visible.append(self.results[idx])
        return visible

    def export_csv(self):
        if not self.results:
            return

        export_results = self._get_visible_results()
        if not export_results:
            QMessageBox.information(
                self, u'Info',
                u'No results match the filter, nothing to save.'
            )
            return

        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, u'Save Results',
            u'overlap_analyzer_results.csv',
            u'CSV File (*.csv);;All Files (*)'
        )
        if not filepath:
            return

        try:
            layer_cache, field_names = self._collect_result_fields(export_results)
            headers = [u'Layer Name', u'Feature ID', u'Status'] + field_names

            with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(headers)

                for result in export_results:
                    layer = layer_cache.get(result['layer_id'])
                    row = [result['layer_name'], result['feature_id'], result['status']]

                    attr_values = {}
                    if layer is not None:
                        feat = layer.getFeature(result['feature_id'])
                        if feat.isValid():
                            for f_ in layer.fields():
                                val = feat[f_.name()]
                                attr_values[f_.name()] = '' if val is None else val

                    for field_name in field_names:
                        row.append(attr_values.get(field_name, ''))

                    writer.writerow(row)

            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(filepath))
            if not opened:
                QMessageBox.information(
                    self, u'Success',
                    f'Results were saved but could not be opened automatically:\n{filepath}'
                )
        except Exception as e:
            QMessageBox.critical(self, u'Error', f'An error occurred while saving the file:\n{str(e)}')
