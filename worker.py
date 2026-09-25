# -*- coding: utf-8 -*-
"""
Worker thread for intersection analysis.
Uses QThread subclass pattern for Qt5/Qt6 safety.
"""
from qgis.PyQt.QtCore import QThread, pyqtSignal
from qgis.core import (
    QgsGeometry, QgsWkbTypes, QgsProject,
    QgsCoordinateTransform, QgsVectorLayer,
    QgsFeatureRequest
)


class IntersectionThread(QThread):

    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, source_layers, reference_layer, buffer_distance=0,
                 selected_fids=None, reference_fids=None):
        """selected_fids: None -> analyse every feature of each source layer.
        Otherwise a dict {layer_id: [feature ids]}; only those features are
        analysed (snapshot of the selection taken in the GUI thread when the
        analysis was started). Layers missing from the dict are skipped.

        reference_fids: None -> use every feature of the reference layer.
        Otherwise a list of reference feature ids; only those are used."""
        super().__init__()
        self.source_layers = source_layers
        self.reference_layer = reference_layer
        self.buffer_distance = buffer_distance
        self.selected_fids = selected_fids
        self.reference_fids = reference_fids
        self._is_running = True

    def run(self):
        try:
            results = []
            total_layers = len(self.source_layers)
            ref_raw_features = self._load_reference_features_raw()
            ref_is_line = self._is_line_layer(self.reference_layer)

            if not ref_raw_features:
                self.finished.emit(results)
                return

            # Reference geometries must be reprojected (and buffered) separately
            # for each source layer's own CRS, since selected layers can have
            # different CRSs. Cache the result per CRS so repeated layers in the
            # same CRS don't redo the work.
            ref_features_by_crs = {}

            for layer_idx, source_layer in enumerate(self.source_layers):
                if not self._is_running:
                    break

                self.progress.emit(int((layer_idx / total_layers) * 100))

                ref_features = self._get_reference_features_for_crs(
                    source_layer.crs(), ref_raw_features, ref_features_by_crs
                )

                if self.selected_fids is not None:
                    fids = self.selected_fids.get(source_layer.id())
                    if not fids:
                        continue
                    request = QgsFeatureRequest().setFilterFids(fids)
                    source_features = source_layer.getFeatures(request)
                else:
                    source_features = source_layer.getFeatures()

                for source_feat in source_features:
                    if not self._is_running:
                        break

                    source_geom = source_feat.geometry()
                    if source_geom.isNull() or source_geom.isEmpty():
                        continue

                    geom_type = QgsWkbTypes.displayString(
                        source_geom.wkbType()
                    )

                    for ref_geom, ref_id in ref_features:
                        if source_geom.intersects(ref_geom):
                            if not ref_is_line and source_geom.within(ref_geom):
                                status = u'Inside'
                            else:
                                status = u'Intersects'
                            results.append({
                                'layer_name': source_layer.name(),
                                'layer_id': source_layer.id(),
                                'feature_id': source_feat.id(),
                                'geom_type': geom_type,
                                'ref_feature_id': ref_id,
                                'status': status,
                            })
                            break

                self.progress.emit(int(((layer_idx + 1) / total_layers) * 100))

            self.finished.emit(results)

        except Exception as e:
            self.error.emit(str(e))

    def _is_line_layer(self, layer):
        if not isinstance(layer, QgsVectorLayer):
            return False
        geom_type = layer.geometryType()
        return geom_type == QgsWkbTypes.GeometryType.LineGeometry

    def _load_reference_features_raw(self):
        """Load reference geometries once, kept in the reference layer's own
        (native) CRS. No reprojection or buffering happens here — that is
        done per source-layer CRS in _get_reference_features_for_crs, since
        different selected source layers can have different CRSs."""
        ref_features = []
        if self.reference_fids is not None:
            request = QgsFeatureRequest().setFilterFids(self.reference_fids)
            ref_iter = self.reference_layer.getFeatures(request)
        else:
            ref_iter = self.reference_layer.getFeatures()
        for feat in ref_iter:
            geom = feat.geometry()
            if geom.isNull() or geom.isEmpty():
                continue
            ref_features.append((QgsGeometry(geom), feat.id()))
        return ref_features

    def _get_reference_features_for_crs(self, target_crs, ref_raw_features, cache):
        cache_key = target_crs.authid() or target_crs.toWkt()
        if cache_key in cache:
            return cache[cache_key]

        ref_crs = self.reference_layer.crs()
        transform = None
        if target_crs != ref_crs:
            transform = QgsCoordinateTransform(
                ref_crs, target_crs, QgsProject.instance()
            )

        # Buffer distance: apply in the target (source layer) CRS units (meters)
        buffer_dist = self.buffer_distance

        ref_features = []
        for raw_geom, feat_id in ref_raw_features:
            # Clone so each CRS gets its own transform starting from the
            # original, untouched geometry.
            geom = QgsGeometry(raw_geom)
            if transform:
                geom.transform(transform)
            if buffer_dist > 0:
                geom = geom.buffer(buffer_dist, 32)
            ref_features.append((geom, feat_id))

        cache[cache_key] = ref_features
        return ref_features

    def stop(self):
        self._is_running = False
