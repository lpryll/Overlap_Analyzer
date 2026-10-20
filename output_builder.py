# -*- coding: utf-8 -*-
import csv
from qgis.core import (
    QgsVectorLayer,
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsProject,
    QgsGraduatedSymbolRenderer,
    QgsRendererRange,
    QgsFillSymbol
)

from .compat import field_type
from .i18n import tr, tr_list

FIELD_STRING = field_type("String", "QString")
FIELD_DOUBLE = field_type("Double", "Double")


def create_overlap_memory_layer(results: list, crs_authid: str) -> QgsVectorLayer:
    uri = f"MultiPolygon?crs={crs_authid}"
    mem_layer = QgsVectorLayer(uri, tr("mem_layer_name"), "memory")
    provider = mem_layer.dataProvider()

    fields = [
        QgsField(tr("fld_base_id"), FIELD_STRING),
        QgsField(tr("fld_ov_layer"), FIELD_STRING),
        QgsField(tr("fld_ov_id"), FIELD_STRING),
        QgsField(tr("fld_base_ha"), FIELD_DOUBLE),
        QgsField(tr("fld_ov_m2"), FIELD_DOUBLE),
        QgsField(tr("fld_ov_ha"), FIELD_DOUBLE),
        QgsField(tr("fld_ov_pct"), FIELD_DOUBLE),
        QgsField(tr("fld_rem_ha"), FIELD_DOUBLE)
    ]
    provider.addAttributes(fields)
    mem_layer.updateFields()

    features = []
    for row in results:
        feat = QgsFeature(mem_layer.fields())
        feat.setGeometry(QgsGeometry.fromWkt(row["geometry_wkt"]))
        feat.setAttributes([
            row["base_id"],
            row["overlay_layer"],
            row["overlay_id"],
            row["base_area_ha"],
            row["overlap_area_m2"],
            row["overlap_area_ha"],
            row["overlap_pct"],
            row["remaining_area_ha"]
        ])
        features.append(feat)

    provider.addFeatures(features)
    mem_layer.updateExtents()

    ranges = [
        (0.0, 15.0, tr("sym_low"), "#fee08b"),
        (15.0, 50.0, tr("sym_med"), "#fdae61"),
        (50.0, 100.0, tr("sym_high"), "#d73027")
    ]
    renderer_ranges = []
    for min_v, max_v, label, color_hex in ranges:
        symbol = QgsFillSymbol.createSimple({
            'color': color_hex,
            'outline_color': '#2b2b2b',
            'outline_width': '0.3'
        })
        symbol.setOpacity(0.65)
        renderer_ranges.append(QgsRendererRange(min_v, max_v, symbol, label))

    renderer = QgsGraduatedSymbolRenderer(tr("fld_ov_pct"), renderer_ranges)
    mem_layer.setRenderer(renderer)

    QgsProject.instance().addMapLayer(mem_layer)
    return mem_layer


def export_results_to_csv(detail_results: list, net_results: list, filepath: str):
    with open(filepath, mode='w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=';')
        
        writer.writerow([tr("csv_sec1")])
        writer.writerow(tr_list("csv_hdr_net"))
        for n in net_results:
            writer.writerow([
                n["base_id"], n["base_area_ha"], n["union_overlap_ha"],
                n["union_overlap_pct"], n["net_usable_ha"], n["net_usable_m2"]
            ])

        writer.writerow([])
        writer.writerow([tr("csv_sec2")])
        writer.writerow(tr_list("csv_hdr_detail"))
        for r in detail_results:
            writer.writerow([
                r["base_id"], r["overlay_layer"], r["overlay_id"],
                r["base_area_m2"], r["base_area_ha"],
                r["overlap_area_m2"], r["overlap_area_ha"],
                r["overlap_pct"], r["remaining_area_ha"]
            ])
