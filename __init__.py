# -*- coding: utf-8 -*-
def classFactory(iface):
    from .plugin import OverlapAnalyzerPlugin
    return OverlapAnalyzerPlugin(iface)