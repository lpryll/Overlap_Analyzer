# -*- coding: utf-8 -*-
"""Qt5 / Qt6 and QGIS 3 / 4 compatibility helpers.

Fully scoped enums (e.g. Qt.ItemDataRole.UserRole) are used where available;
older bindings that only expose the flat names are handled in one place here
so the rest of the plugin stays free of version checks.
"""
from qgis.core import Qgis, QgsMessageLog, QgsWkbTypes
from qgis.PyQt.QtCore import QVariant, QMetaType

PLUGIN_LOG_TAG = "OverlapAnalyzer"


def enum_value(owner, scope, name):
    """Return owner.<scope>.<name> (scoped enum), falling back to owner.<name>."""
    scoped = getattr(owner, scope, None)
    if scoped is not None and hasattr(scoped, name):
        return getattr(scoped, name)
    return getattr(owner, name)


def polygon_geometry_type():
    """Polygon geometry type enum for the running QGIS version."""
    qgis_geometry_type = getattr(Qgis, "GeometryType", None)
    if qgis_geometry_type is not None and hasattr(qgis_geometry_type, "Polygon"):
        return qgis_geometry_type.Polygon
    return enum_value(QgsWkbTypes, "GeometryType", "PolygonGeometry")


def field_type(variant_name, meta_name):
    """Field type for QgsField: QVariant type where it exists, QMetaType otherwise (Qt6 / QGIS 4)."""
    legacy = getattr(QVariant, variant_name, None)
    if legacy is not None:
        return legacy
    return enum_value(QMetaType, "Type", meta_name)


def log_message(message, level="Info"):
    """Write to the QGIS message log. level: Info, Warning or Critical."""
    QgsMessageLog.logMessage(message, PLUGIN_LOG_TAG, enum_value(Qgis, "MessageLevel", level))
