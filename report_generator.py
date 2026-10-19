# -*- coding: utf-8 -*-
from .i18n import tr
import datetime
import html
import re
from qgis.core import (
    QgsMapSettings,
    QgsMapRendererParallelJob,
    QgsGeometry,
    QgsVectorLayer,
    QgsFeature,
    QgsFillSymbol,
    QgsSingleSymbolRenderer
)
from qgis.PyQt.QtCore import QSize, QBuffer, QIODevice
from qgis.PyQt.QtGui import QImage, QColor, QTextDocument, QPageSize, QPageLayout
from qgis.PyQt.QtPrintSupport import QPrinter


class OverlapReportGenerator:
    @staticmethod
    def build_overlap_highlight_layer(overlap_results: list, crs_authid: str):
        """Çakışan alanları %50 saydam kırmızı ile gösteren geçici (bellek) katman üretir."""
        if not overlap_results or not crs_authid:
            return None
        layer = QgsVectorLayer(f"MultiPolygon?crs={crs_authid}", "overlap_highlight", "memory")
        if not layer.isValid():
            return None
        feats = []
        for r in overlap_results:
            wkt = r.get("geometry_wkt")
            if not wkt:
                continue
            geom = QgsGeometry.fromWkt(wkt)
            if not geom or geom.isEmpty():
                continue
            feat = QgsFeature(layer.fields())
            feat.setGeometry(geom)
            feats.append(feat)
        if not feats:
            return None
        layer.dataProvider().addFeatures(feats)
        layer.updateExtents()
        symbol = QgsFillSymbol.createSimple({
            "color": "231,76,60,128",          # %50 saydam kırmızı dolgu
            "outline_color": "192,57,43,255",  # belirgin kontur
            "outline_width": "0.5",
        })
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        return layer

    @staticmethod
    def render_map_snapshot_base64(canvas, target_wkt: str = None, width_px: int = 1200, height_px: int = 650,
                                   overlap_results: list = None, crs_authid: str = None) -> str:
        settings = QgsMapSettings(canvas.mapSettings())
        settings.setOutputSize(QSize(width_px, height_px))
        settings.setBackgroundColor(QColor(255, 255, 255))

        if target_wkt:
            geom = QgsGeometry.fromWkt(target_wkt)
            if geom and not geom.isEmpty():
                bbox = geom.boundingBox()
                bbox.scale(1.35)
                settings.setExtent(bbox)

        highlight_layer = OverlapReportGenerator.build_overlap_highlight_layer(overlap_results, crs_authid)
        if highlight_layer is not None:
            settings.setLayers([highlight_layer] + list(settings.layers()))

        job = QgsMapRendererParallelJob(settings)
        job.start()
        job.waitForFinished()

        img: QImage = job.renderedImage()

        buffer = QBuffer()
        try:
            open_mode = QIODevice.OpenModeFlag.WriteOnly
        except AttributeError:
            open_mode = QIODevice.WriteOnly

        buffer.open(open_mode)
        img.save(buffer, "PNG")
        base64_data = bytes(buffer.data().toBase64()).decode("utf-8")
        buffer.close()

        return f"data:image/png;base64,{base64_data}"

    @classmethod
    def _build_report_html(
        cls,
        canvas,
        base_layer_name: str,
        crs_authid: str,
        detail_results: list,
        net_results: list,
        focus_wkt: str = None,
        scope_label: str = None
    ) -> str:
        map_base64 = cls.render_map_snapshot_base64(
            canvas, target_wkt=focus_wkt,
            overlap_results=detail_results, crs_authid=crs_authid
        )
        now_str = datetime.datetime.now().strftime(tr("date_fmt"))

        total_targets = len(net_results)
        total_overlaps = len(detail_results)
        total_base_ha = sum(r["base_area_ha"] for r in net_results)
        total_union_overlap_ha = sum(r["union_overlap_ha"] for r in net_results)
        total_usable_ha = sum(r["net_usable_ha"] for r in net_results)

        net_rows_html = ""
        for r in net_results:
            badge_color = "#c0392b" if r["union_overlap_pct"] >= 50 else ("#d35400" if r["union_overlap_pct"] >= 15 else "#27ae60")
            net_rows_html += f"""
            <tr>
                <td style="font-weight:bold;">{r['base_id']}</td>
                <td align="right">{r['base_area_ha']:,.4f}</td>
                <td align="right">{r['union_overlap_ha']:,.4f}</td>
                <td align="right" style="color:{badge_color}; font-weight:bold;">{tr('pct_fmt', v=r['union_overlap_pct'])}</td>
                <td align="right" style="background-color:#eafaf1; font-weight:bold;">{r['net_usable_ha']:,.4f}</td>
                <td align="right">{r['net_usable_m2']:,.2f}</td>
            </tr>
            """

        detail_rows_html = ""
        if detail_results:
            for r in detail_results:
                row_bg = "#fdecea" if r["overlap_pct"] >= 50 else "#ffffff"
                detail_rows_html += f"""
                <tr style="background-color:{row_bg};">
                    <td>{r['base_id']}</td>
                    <td><b>{r['overlay_layer']}</b></td>
                    <td>{r['overlay_id']}</td>
                    <td align="right">{r['base_area_ha']:,.4f}</td>
                    <td align="right">{r['overlap_area_m2']:,.2f}</td>
                    <td align="right">{r['overlap_area_ha']:,.4f}</td>
                    <td align="right"><b>{tr('pct_fmt', v=r['overlap_pct'])}</b></td>
                </tr>
                """
        else:
            detail_rows_html = f"""
            <tr>
                <td colspan="7" align="center" style="color:#27ae60; padding:12px;">
                    <b>{tr("pdf_no_overlap")}</b>
                </td>
            </tr>
            """

        scope_html = (
            f" &nbsp;|&nbsp; <b>{tr('pdf_scope')}</b> {html.escape(str(scope_label))}"
            if scope_label else ""
        )

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 9.5pt; color: #2c3e50; margin: 0; padding: 0; }}
            .header-table {{ width: 100%; border-bottom: 2px solid #1a5276; padding-bottom: 8px; margin-bottom: 12px; }}
            .title {{ font-size: 15pt; font-weight: bold; color: #1a5276; }}
            .subtitle {{ font-size: 8.5pt; color: #5d6d7e; }}
            .kpi-table {{ width: 100%; margin-bottom: 14px; border-collapse: collapse; }}
            .kpi-box {{ background-color: #f4f6f7; border: 1px solid #d5dbdb; padding: 8px; text-align: center; width: 25%; }}
            .kpi-val {{ font-size: 12pt; font-weight: bold; color: #1a5276; }}
            .kpi-lbl {{ font-size: 8pt; color: #566573; }}
            .map-box {{ text-align: center; border: 1px solid #bdc3c7; padding: 6px; background-color: #fafafa; margin-bottom: 14px; }}
            .section-title {{ font-size: 11pt; font-weight: bold; color: #1a5276; border-left: 4px solid #1a5276; padding-left: 6px; margin-top: 14px; margin-bottom: 6px; }}
            table.data-table {{ width: 100%; border-collapse: collapse; font-size: 8.5pt; margin-bottom: 14px; }}
            table.data-table th {{ background-color: #1a5276; color: #ffffff; padding: 6px; text-align: left; border: 1px solid #1a5276; }}
            table.data-table td {{ padding: 5px 6px; border: 1px solid #d5dbdb; }}
            .footer {{ margin-top: 16px; font-size: 7.5pt; color: #7f8c8d; border-top: 1px solid #d5dbdb; padding-top: 6px; text-align: right; }}
        </style>
        </head>
        <body>
            <table class="header-table">
                <tr>
                    <td>
                        <div class="title">{tr("pdf_title")}</div>
                        <div class="subtitle"><b>{tr("pdf_target_layer")}</b> {base_layer_name} &nbsp;|&nbsp; <b>{tr("pdf_crs")}</b> {crs_authid}{scope_html}</div>
                    </td>
                    <td align="right" class="subtitle">
                        <b>{tr("pdf_date")}</b> {now_str}<br><b>{tr("pdf_generator")}</b> Overlap Analyzer Pro
                    </td>
                </tr>
            </table>
            <table class="kpi-table">
                <tr>
                    <td class="kpi-box"><div class="kpi-val">{tr("pdf_kpi_count_fmt", n=total_targets)}</div><div class="kpi-lbl">{tr("pdf_kpi_targets")}</div></td>
                    <td class="kpi-box"><div class="kpi-val">{total_base_ha:,.2f} Ha</div><div class="kpi-lbl">{tr("pdf_kpi_gross")}</div></td>
                    <td class="kpi-box"><div class="kpi-val" style="color:#c0392b;">{total_union_overlap_ha:,.2f} Ha {tr("pdf_kpi_intersections_fmt", n=total_overlaps)}</div><div class="kpi-lbl">{tr("pdf_kpi_union")}</div></td>
                    <td class="kpi-box" style="background-color:#eafaf1;"><div class="kpi-val" style="color:#1e8449;">{total_usable_ha:,.2f} Ha</div><div class="kpi-lbl">{tr("pdf_kpi_usable")}</div></td>
                </tr>
            </table>
            <div class="section-title">{tr("pdf_sec1")}</div>
            <div class="map-box"><img src="{map_base64}" width="640" /></div>
            <div class="subtitle" style="font-size:8pt;"><span style="color:#e74c3c;">&#9632;</span> {tr("pdf_map_legend")}</div>
            <div class="section-title">{tr("pdf_sec2")}</div>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>{tr("pdf_th_base_id")}</th><th align="right">{tr("pdf_th_gross_ha")}</th><th align="right">{tr("pdf_th_union_ha")}</th>
                        <th align="right">{tr("pdf_th_true_pct")}</th><th align="right">{tr("pdf_th_net_ha")}</th><th align="right">{tr("pdf_th_net_m2")}</th>
                    </tr>
                </thead>
                <tbody>{net_rows_html}</tbody>
            </table>
            <div class="section-title">{tr("pdf_sec3")}</div>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>{tr("pdf_th_base_id")}</th><th>{tr("pdf_th_ov_layer")}</th><th>{tr("pdf_th_ov_obj")}</th>
                        <th align="right">{tr("pdf_th_target_ha")}</th><th align="right">{tr("pdf_th_ov_m2")}</th><th align="right">{tr("pdf_th_ov_ha")}</th><th align="right">{tr("pdf_th_ratio")}</th>
                    </tr>
                </thead>
                <tbody>{detail_rows_html}</tbody>
            </table>
            <div class="footer">
                {tr("pdf_footer")}
            </div>
        </body>
        </html>
        """

        return html_content

    @staticmethod
    def _print_html(filepath: str, html_content: str):
        """HTML'i A4 dikey PDF olarak yazar (uzun tablolar otomatik sayfalanır)."""
        try:
            printer_mode = QPrinter.PrinterMode.HighResolution
            pdf_format = QPrinter.OutputFormat.PdfFormat
            a4_size = QPageSize.PageSizeId.A4
            portrait = QPageLayout.Orientation.Portrait
        except AttributeError:
            printer_mode = QPrinter.HighResolution
            pdf_format = QPrinter.PdfFormat
            a4_size = QPageSize.A4
            portrait = QPageLayout.Portrait

        printer = QPrinter(printer_mode)
        printer.setOutputFormat(pdf_format)
        printer.setOutputFileName(filepath)
        printer.setPageSize(QPageSize(a4_size))
        printer.setPageOrientation(portrait)

        doc = QTextDocument()
        doc.setHtml(html_content)
        doc.print_(printer) if hasattr(doc, "print_") else doc.print(printer)

    @classmethod
    def export_pdf_report(
        cls,
        filepath: str,
        canvas,
        base_layer_name: str,
        crs_authid: str,
        detail_results: list,
        net_results: list,
        focus_wkt: str = None,
        scope_label: str = None
    ) -> bool:
        """Tek sayfa grubu (tek kapsam) için PDF üretir."""
        html_content = cls._build_report_html(
            canvas, base_layer_name, crs_authid,
            detail_results, net_results, focus_wkt, scope_label
        )
        cls._print_html(filepath, html_content)
        return True

    @classmethod
    def export_multi_pdf_report(
        cls,
        filepath: str,
        canvas,
        base_layer_name: str,
        crs_authid: str,
        sections: list
    ) -> bool:
        """Çok sayfalı tek PDF: her bölüm (nesne) kendi haritası ve bilgi kartıyla yeni sayfada başlar.

        sections: [{"detail_results": [...], "net_results": [...],
                    "focus_wkt": str|None, "scope_label": str|None}, ...]
        """
        if not sections:
            return False

        head = ""
        bodies = []
        for idx, sec in enumerate(sections):
            page_html = cls._build_report_html(
                canvas, base_layer_name, crs_authid,
                sec.get("detail_results", []), sec.get("net_results", []),
                sec.get("focus_wkt"), sec.get("scope_label")
            )
            if idx == 0:
                m = re.search(r"^(.*?<body>)", page_html, re.S)
                head = m.group(1) if m else "<html><body>"
            m = re.search(r"<body>(.*)</body>", page_html, re.S)
            body = m.group(1) if m else page_html
            if idx > 0:
                # ilk üst bilgi tablosuna sayfa sonu ekle -> nesne yeni sayfada başlar
                body = body.replace(
                    '<table class="header-table">',
                    '<table class="header-table" style="page-break-before:always;">', 1
                )
            bodies.append(body)

        combined = head + "".join(bodies) + "</body></html>"
        cls._print_html(filepath, combined)
        return True
