# -*- coding: utf-8 -*-
from qgis.core import (
    QgsProject,
    QgsTask,
    QgsMessageLog,
    Qgis,
    QgsSpatialIndex,
    QgsGeometry,
    QgsFeature,
    QgsVectorLayer,
    QgsWkbTypes,
    QgsCoordinateTransform,
    QgsDistanceArea
)
from qgis.PyQt.QtCore import pyqtSignal

from .compat import enum_value, polygon_geometry_type
from .i18n import tr


class OverlapAnalysisTask(QgsTask):
    analysisFinished = pyqtSignal(list, list, dict)

    def __init__(self, base_layer: QgsVectorLayer, overlay_layers: list,
                 base_id_field: str, min_sliver_area: float = 0.01,
                 only_selected: bool = False):
        super().__init__(tr("task_desc"), enum_value(QgsTask, "Flag", "CanCancel"))
        self.base_layer = base_layer
        self.overlay_layers = overlay_layers
        self.base_id_field = base_id_field
        self.min_sliver_area = min_sliver_area
        self.only_selected = only_selected

        self.results = []
        self.net_summaries = []
        self.summary = {}
        self.exception = None

        self.da = QgsDistanceArea()
        self.da.setSourceCrs(self.base_layer.crs(), QgsProject.instance().transformContext())
        self.da.setEllipsoid(QgsProject.instance().ellipsoid())

    def measure_area(self, geom: QgsGeometry) -> float:
        if self.base_layer.crs().isGeographic():
            return self.da.measureArea(geom)
        return geom.area()

    def run(self) -> bool:
        try:
            base_features = (
                list(self.base_layer.selectedFeatures())
                if self.only_selected and self.base_layer.selectedFeatureCount() > 0
                else list(self.base_layer.getFeatures())
            )
            total_base = len(base_features)
            if total_base == 0:
                return False

            overlay_cache = []
            transform_context = QgsProject.instance().transformContext()

            for ov_layer, ov_id_field in self.overlay_layers:
                if not ov_layer or not ov_layer.isValid():
                    continue

                transform = None
                if ov_layer.crs() != self.base_layer.crs():
                    transform = QgsCoordinateTransform(
                        ov_layer.crs(), self.base_layer.crs(), transform_context
                    )

                spatial_index = QgsSpatialIndex()
                feature_map = {}

                for feat in ov_layer.getFeatures():
                    geom = feat.geometry()
                    if not geom or geom.isEmpty():
                        continue
                    if not geom.isGeosValid():
                        geom = geom.makeValid()
                    if transform:
                        geom.transform(transform)

                    feat_copy = QgsFeature(feat)
                    feat_copy.setGeometry(geom)
                    spatial_index.addFeature(feat_copy)
                    feature_map[feat.id()] = feat_copy

                overlay_cache.append({
                    "name": ov_layer.name(),
                    "id_field": ov_id_field,
                    "index": spatial_index,
                    "features": feature_map
                })

            for idx, base_feat in enumerate(base_features):
                if self.isCanceled():
                    return False

                base_geom = base_feat.geometry()
                if not base_geom or base_geom.isEmpty():
                    continue
                if not base_geom.isGeosValid():
                    base_geom = base_geom.makeValid()

                base_area_m2 = self.measure_area(base_geom)
                if base_area_m2 <= 0:
                    continue

                base_identifier = (
                    str(base_feat[self.base_id_field])
                    if self.base_id_field and self.base_id_field in base_feat.fields().names()
                    else f"ID_{base_feat.id()}"
                )

                engine = QgsGeometry.createGeometryEngine(base_geom.constGet())
                engine.prepareGeometry()

                intersected_geoms_for_base = []

                for ov_data in overlay_cache:
                    ov_name = ov_data["name"]
                    ov_field = ov_data["id_field"]
                    candidate_ids = ov_data["index"].intersects(base_geom.boundingBox())

                    for cand_id in candidate_ids:
                        cand_feat = ov_data["features"][cand_id]
                        cand_geom = cand_feat.geometry()

                        if engine.intersects(cand_geom.constGet()):
                            inter_geom = base_geom.intersection(cand_geom)
                            if not inter_geom or inter_geom.isEmpty():
                                continue

                            inter_geom = inter_geom.convertToType(polygon_geometry_type(), True)
                            if not inter_geom or inter_geom.isEmpty():
                                continue

                            inter_area_m2 = self.measure_area(inter_geom)
                            if inter_area_m2 < self.min_sliver_area:
                                continue

                            intersected_geoms_for_base.append(inter_geom)

                            overlap_pct = (inter_area_m2 / base_area_m2) * 100.0
                            ov_identifier = (
                                str(cand_feat[ov_field])
                                if ov_field and ov_field in cand_feat.fields().names()
                                else f"ID_{cand_feat.id()}"
                            )

                            self.results.append({
                                "base_id": base_identifier,
                                "base_fid": base_feat.id(),
                                "overlay_layer": ov_name,
                                "overlay_id": ov_identifier,
                                "base_area_m2": round(base_area_m2, 2),
                                "base_area_ha": round(base_area_m2 / 10000.0, 4),
                                "overlap_area_m2": round(inter_area_m2, 2),
                                "overlap_area_ha": round(inter_area_m2 / 10000.0, 4),
                                "overlap_pct": round(min(overlap_pct, 100.0), 2),
                                "remaining_area_ha": round(max(base_area_m2 - inter_area_m2, 0.0) / 10000.0, 4),
                                "geometry_wkt": inter_geom.asWkt()
                            })

                            self.summary[ov_name] = self.summary.get(ov_name, 0.0) + inter_area_m2

                if intersected_geoms_for_base:
                    dissolved_overlap_geom = QgsGeometry.unaryUnion(intersected_geoms_for_base)
                    if not dissolved_overlap_geom.isGeosValid():
                        dissolved_overlap_geom = dissolved_overlap_geom.makeValid()

                    total_union_overlap_m2 = self.measure_area(dissolved_overlap_geom)
                    net_usable_geom = base_geom.difference(dissolved_overlap_geom)
                    net_usable_m2 = max(base_area_m2 - total_union_overlap_m2, 0.0)
                    net_overlap_pct = min((total_union_overlap_m2 / base_area_m2) * 100.0, 100.0)
                    usable_wkt = net_usable_geom.asWkt() if net_usable_geom and not net_usable_geom.isEmpty() else ""
                else:
                    total_union_overlap_m2 = 0.0
                    net_usable_m2 = base_area_m2
                    net_overlap_pct = 0.0
                    usable_wkt = base_geom.asWkt()

                self.net_summaries.append({
                    "base_id": base_identifier,
                    "base_fid": base_feat.id(),
                    "base_area_ha": round(base_area_m2 / 10000.0, 4),
                    "union_overlap_ha": round(total_union_overlap_m2 / 10000.0, 4),
                    "union_overlap_pct": round(net_overlap_pct, 2),
                    "net_usable_ha": round(net_usable_m2 / 10000.0, 4),
                    "net_usable_m2": round(net_usable_m2, 2),
                    "usable_geometry_wkt": usable_wkt
                })

                self.setProgress(((idx + 1) / total_base) * 100)

            return True

        except Exception as e:
            self.exception = e
            return False

    def finished(self, result: bool):
        if result:
            QgsMessageLog.logMessage(
                tr("log_done", n=len(self.results)),
                "OverlapAnalyzer", enum_value(Qgis, "MessageLevel", "Info")
            )
            self.analysisFinished.emit(self.results, self.net_summaries, self.summary)
        else:
            if self.exception:
                QgsMessageLog.logMessage(
                    tr("log_error", e=str(self.exception)),
                    "OverlapAnalyzer", enum_value(Qgis, "MessageLevel", "Critical")
                )
