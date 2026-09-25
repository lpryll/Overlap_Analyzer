def classFactory(iface):
    from .overlap_analyzer import OverlapAnalyzer
    return OverlapAnalyzer(iface)
