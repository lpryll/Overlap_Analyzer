# -*- coding: utf-8 -*-
"""
Çok dilli metin desteği / Simple two-language (TR / EN) text support.

Kural / Rule:
    * Windows (sistem) dili Türkçe ise  -> arayüz ve raporlar Türkçe
    * Diğer tüm dillerde                -> arayüz ve raporlar İngilizce

Test için ortam değişkeni ile zorlanabilir / can be forced for testing:
    OVERLAP_ANALYZER_LANG=tr  veya  OVERLAP_ANALYZER_LANG=en
"""
import os

_LANG = None


def _detect_language() -> str:
    forced = os.environ.get("OVERLAP_ANALYZER_LANG", "").strip().lower()
    if forced in ("tr", "en"):
        return forced
    try:
        from qgis.PyQt.QtCore import QLocale
        loc = QLocale.system()
        ui_langs = [str(x) for x in loc.uiLanguages()]
        # Windows görüntüleme dili öncelikli; yoksa bölgesel ayar adı
        primary = ui_langs[0] if ui_langs else loc.name()
        primary = primary.lower().replace("_", "-")
        return "tr" if primary.startswith("tr") else "en"
    except Exception:
        return "en"


def get_language() -> str:
    """'tr' veya 'en' döner (ilk çağrıda belirlenir ve saklanır)."""
    global _LANG
    if _LANG is None:
        _LANG = _detect_language()
    return _LANG


TRANSLATIONS = {
    # --- Pencere / genel -------------------------------------------------
    "window_title": {
        "en": "Overlap Analyzer Pro - Multi-Layer & Net Area Analysis",
        "tr": "Overlap Analyzer Pro - Çoklu Katman & Net Alan Analizi"},
    "status_tip": {
        "en": "Multi-layer overlap and dissolved net residual area analysis",
        "tr": "Çoklu katman çakışma ve birleşik net kullanılabilir alan analizi"},
    "task_desc": {
        "en": "Overlap Analyzer - Multi-Layer Overlap Analysis",
        "tr": "Overlap Analyzer - Çoklu Çakışma Analizi"},
    "grp_base": {
        "en": "1. Target (Base) Layer Selection",
        "tr": "1. Hedef (Ana) Katman Seçimi"},
    "lbl_base_layer": {
        "en": "Target Polygon Layer:",
        "tr": "Hedef Poligon Katmanı:"},
    "lbl_base_field": {
        "en": "Unique Identifier (ID/Name) Field:",
        "tr": "Tekil Tanımlayıcı (ID/Ad) Alanı:"},
    "chk_only_selected": {
        "en": "Analyze only selected polygons",
        "tr": "Yalnızca seçili poligonları analiz et"},
    "lbl_sliver": {
        "en": "Sliver (Micro Overlap) Threshold (m²):",
        "tr": "Sliver (Mikro Hata) Eşiği (m²):"},
    "grp_overlays": {
        "en": "2. Constraint / Overlay Layers (Multi-Select)",
        "tr": "2. Kısıt / Çakışma Kontrol Katmanları (Çoklu Seçim)"},
    "btn_sel_all": {"en": "Select All", "tr": "Tümünü Seç"},
    "btn_desel_all": {"en": "Deselect All", "tr": "Seçimi Kaldır"},
    "btn_refresh": {"en": "Refresh Layer List", "tr": "Katman Listesini Yenile"},
    "ov_col_include": {"en": "Include", "tr": "Analize Dahil Et"},
    "ov_col_layer": {"en": "Layer Name", "tr": "Katman Adı"},
    "ov_col_field": {
        "en": "Report ID/Name Field",
        "tr": "Raporda Görünecek ID/Ad Sütunu"},
    "use_feat_id": {"en": "[Use Feature ID]", "tr": "[Feature ID Kullan]"},
    "btn_run": {
        "en": "🚀 Run Multi-Layer Overlap Analysis",
        "tr": "🚀 Çoklu Çakışma Analizini Başlat"},
    "btn_cancel": {"en": "Cancel", "tr": "İptal"},
    "tab_detail": {
        "en": "📌 Detailed Overlap Matrix",
        "tr": "📌 Detaylı Çakışma Matrisi"},
    "hint_detail": {
        "en": "💡 Tip: Click any row to zoom to and flash the corresponding overlap geometry on the map.",
        "tr": "💡 İpucu: Satıra tıklayarak haritada ilgili çakışma parçasına odaklanabilir ve parlatabilirsiniz."},
    "tab_net": {
        "en": "✅ Net Residual Area Summary (Dissolved / UnaryUnion)",
        "tr": "✅ Net Kullanılabilir Alan Özeti (Dissolved / UnaryUnion)"},
    "hint_net": {
        "en": "💡 Info: Overlapping constraints are dissolved via unaryUnion. Click a row to flash the NET RESIDUAL AREA on the map.",
        "tr": "💡 Bilgi: Üst üste binen kısıtlar unaryUnion ile tekilleştirilmiştir. Satıra tıkladığınızda geriye kalan NET KULLANILABİLİR ALAN haritada parlatılır."},

    # --- Hedef ID filtresi -------------------------------------------------
    "lbl_filter_id": {"en": "Filter by Target ID:", "tr": "Hedef ID Filtresi:"},
    "ph_filter_id": {
        "en": "Type a Target ID (separate multiple IDs with commas)",
        "tr": "Hedef ID yazın (birden fazla için virgülle ayırın)"},
    "lbl_filter_count": {
        "en": "Targets shown: {v} / {t}",
        "tr": "Gösterilen hedef: {v} / {t}"},
    "warn_no_filter_match": {
        "en": "No records match the current filter.",
        "tr": "Geçerli filtreyle eşleşen kayıt yok."},
    "lbl_filter_ov": {"en": "Filter by Overlay ID:", "tr": "Çakışan ID Filtresi:"},
    "ph_filter_ov": {
        "en": "Type an Overlay ID (separate multiple IDs with commas)",
        "tr": "Çakışan ID yazın (birden fazla için virgülle ayırın)"},
    "btn_check_visible": {"en": "Tick Visible", "tr": "Görünenleri İşaretle"},
    "btn_uncheck_all": {"en": "Clear Ticks", "tr": "İşaretleri Temizle"},
    "lbl_pdf_scope_checked": {
        "en": "PDF scope: {n} ticked object(s) ({ids})",
        "tr": "PDF kapsamı: işaretli {n} nesne ({ids})"},
    "lbl_pdf_scope_all": {
        "en": "PDF scope: entire list",
        "tr": "PDF kapsamı: tüm liste"},
    "lbl_pdf_scope_sel": {
        "en": "PDF scope: {ids}",
        "tr": "PDF kapsamı: {ids}"},
    "pdf_scope": {"en": "Scope (Target ID):", "tr": "Kapsam (Hedef ID):"},

    # --- Tablo sütunları -------------------------------------------------
    "col_base_id": {"en": "Target ID", "tr": "Hedef ID"},
    "col_ov_layer": {"en": "Overlay Layer", "tr": "Çakışan Katman"},
    "col_ov_id": {"en": "Overlay ID", "tr": "Çakışan ID"},
    "col_base_ha": {"en": "Target Area (Ha)", "tr": "Hedef Alan (Ha)"},
    "col_ov_m2": {"en": "Overlap Area (m²)", "tr": "Çakışma Alanı (m²)"},
    "col_ov_ha": {"en": "Overlap Area (Ha)", "tr": "Çakışma Alanı (Ha)"},
    "col_ov_pct": {"en": "Overlap Ratio (%)", "tr": "Çakışma Oranı (%)"},
    "col_rem_ha": {"en": "Remaining Area (Ha)", "tr": "Kalan Alan (Ha)"},
    "col_tot_base_ha": {"en": "Total Target Area (Ha)", "tr": "Toplam Hedef Alan (Ha)"},
    "col_union_ha": {"en": "Dissolved Overlap (Ha)", "tr": "Birleşik Net Çakışma (Ha)"},
    "col_union_pct": {"en": "True Constraint Ratio (%)", "tr": "Gerçek Kısıt Oranı (%)"},
    "col_net_ha": {"en": "Net Residual Area (Ha)", "tr": "Net Kullanılabilir Alan (Ha)"},
    "col_net_m2": {"en": "Net Residual Area (m²)", "tr": "Net Kullanılabilir Alan (m²)"},

    # --- Çıktı butonları / iletiler ----------------------------------------
    "btn_add_layer": {
        "en": "🗺️ Add Overlaps as Graduated Layer",
        "tr": "🗺️ Çakışmaları Renkli Katman Olarak Ekle"},
    "btn_export_csv": {
        "en": "📊 Export to Excel (CSV)",
        "tr": "📊 Excel (CSV) Kaydet"},
    "btn_export_pdf": {
        "en": "📄 Generate PDF Info Card with Map",
        "tr": "📄 Harita Kesitli PDF Bilgi Kartı Üret"},
    "warn_title": {"en": "Warning", "tr": "Uyarı"},
    "warn_no_base": {
        "en": "Please select a target polygon layer.",
        "tr": "Lütfen bir hedef poligon katmanı seçin."},
    "warn_no_ov": {
        "en": "Please select at least one constraint/overlay layer.",
        "tr": "Lütfen çakıştırılacak en az bir kısıt katmanı seçin."},
    "mem_layer_name": {
        "en": "Overlap_Analysis_Results",
        "tr": "Çakışma_Analiz_Sonuçları"},
    "sym_low": {
        "en": "Low Overlap (0% - 15%)",
        "tr": "Düşük Çakışma (%0 - %15)"},
    "sym_med": {
        "en": "Medium Overlap (15% - 50%)",
        "tr": "Orta Çakışma (%15 - %50)"},
    "sym_high": {
        "en": "High/Critical Overlap (50%+)",
        "tr": "Yüksek/Kritik Çakışma (%50+)"},
    "msg_layer_added": {
        "en": "Overlap layer added to the map with graduated symbology.",
        "tr": "Çakışma katmanı derecelendirilmiş sembolojiyle haritaya eklendi."},
    "dlg_save_csv": {"en": "Save Overlap Report", "tr": "Çakışma Raporunu Kaydet"},
    "dlg_save_pdf": {"en": "Save PDF Info Card", "tr": "PDF Bilgi Kartını Kaydet"},
    "dlg_csv_default": {
        "en": "Overlap_Analyzer_Report.csv",
        "tr": "Overlap_Analyzer_Raporu.csv"},
    "dlg_pdf_default": {
        "en": "Overlap_Info_Card.pdf",
        "tr": "Cakisma_Bilgi_Karti.pdf"},
    "dlg_pdf_prefix": {"en": "Overlap_Info_Card", "tr": "Cakisma_Bilgi_Karti"},
    "msg_pdf_multi_saved": {
        "en": "{n}-page PDF Info Card generated (one page per object):",
        "tr": "{n} sayfalı PDF Bilgi Kartı oluşturuldu (her nesne ayrı sayfada):"},
    "lbl_pdf_separate": {
        "en": " - one PDF, one page per object",
        "tr": " - tek PDF, her nesne ayrı sayfada"},
    "filter_csv": {"en": "CSV File (*.csv)", "tr": "CSV Dosyası (*.csv)"},
    "filter_pdf": {"en": "PDF File (*.pdf)", "tr": "PDF Dosyası (*.pdf)"},
    "msg_success": {"en": "Success", "tr": "Başarılı"},
    "msg_csv_saved": {
        "en": "CSV report saved successfully:",
        "tr": "CSV raporu başarıyla kaydedildi:"},
    "msg_pdf_saved": {
        "en": "PDF Info Card generated successfully:",
        "tr": "PDF Bilgi Kartı başarıyla oluşturuldu:"},
    "msg_pdf_err_title": {
        "en": "PDF Generation Error",
        "tr": "PDF Üretim Hatası"},
    "msg_pdf_err": {
        "en": "Error generating PDF report:",
        "tr": "Rapor oluşturulurken hata oluştu:"},

    # --- Günlük (log) mesajları --------------------------------------------
    "log_done": {
        "en": "Overlap Analyzer: {n} significant overlaps detected.",
        "tr": "Overlap Analyzer: {n} adet anlamlı çakışma tespit edildi."},
    "log_error": {
        "en": "Overlap Analyzer Error: {e}",
        "tr": "Overlap Analyzer Hatası: {e}"},

    # --- Bellek katmanı alan adları ----------------------------------------
    "fld_base_id": {"en": "Target_ID", "tr": "Hedef_ID"},
    "fld_ov_layer": {"en": "Overlay_Layer", "tr": "Kisit_Katmani"},
    "fld_ov_id": {"en": "Overlay_ID", "tr": "Kisit_ID"},
    "fld_base_ha": {"en": "Target_Area_Ha", "tr": "Hedef_Alan_Ha"},
    "fld_ov_m2": {"en": "Overlap_Area_m2", "tr": "Cakisma_Alan_m2"},
    "fld_ov_ha": {"en": "Overlap_Area_Ha", "tr": "Cakisma_Alan_Ha"},
    "fld_ov_pct": {"en": "Overlap_Ratio_Pct", "tr": "Cakisma_Oran_Pct"},
    "fld_rem_ha": {"en": "Remaining_Area_Ha", "tr": "Kalan_Alan_Ha"},

    # --- CSV (başlık listeleri "|" ile ayrılır) ------------------------------
    "csv_sec1": {
        "en": "=== 1. DISSOLVED NET RESIDUAL AREA SUMMARY (UNARY UNION) ===",
        "tr": "=== 1. BİRLEŞİK NET KULLANILABİLİR ALAN ÖZETİ (DISSOLVED / UNARY UNION) ==="},
    "csv_hdr_net": {
        "en": "Target_ID|Gross_Target_Area_Ha|Dissolved_Overlap_Ha|True_Constraint_Ratio_%|Net_Residual_Area_Ha|Net_Residual_Area_m2",
        "tr": "Hedef_ID|Brüt_Hedef_Alan_Ha|Birleşik_Net_Çakışma_Ha|Gerçek_Kısıt_Oranı_%|Net_Kullanılabilir_Alan_Ha|Net_Kullanılabilir_Alan_m2"},
    "csv_sec2": {
        "en": "=== 2. LAYER-BY-LAYER DETAILED OVERLAP MATRIX ===",
        "tr": "=== 2. KATMAN BAZLI DETAYLI ÇAKIŞMA MATRİSİ ==="},
    "csv_hdr_detail": {
        "en": "Target_ID|Overlay_Layer|Overlay_ID|Target_Area_m2|Target_Area_Ha|Overlap_Area_m2|Overlap_Area_Ha|Overlap_Percent_%|Remaining_Area_Ha",
        "tr": "Hedef_ID|Çakışan_Katman|Çakışan_ID|Hedef_Alan_m2|Hedef_Alan_Ha|Çakışma_Alan_m2|Çakışma_Alan_Ha|Çakışma_Yüzdesi_%|Kalan_Alan_Ha"},

    # --- PDF bilgi kartı ----------------------------------------------------
    "date_fmt": {"en": "%Y-%m-%d %H:%M", "tr": "%d.%m.%Y %H:%M"},
    "pct_fmt": {"en": "{v:.2f}%", "tr": "%{v:.2f}"},
    "pdf_title": {
        "en": "SPATIAL OVERLAP AND NET RESIDUAL AREA INFO CARD",
        "tr": "MEKÂNSAL ÇAKIŞMA VE NET ALAN BİLGİ KARTI"},
    "pdf_target_layer": {"en": "Target Layer:", "tr": "Hedef Katman:"},
    "pdf_crs": {"en": "Reference CRS:", "tr": "Referans CRS:"},
    "pdf_date": {"en": "Report Date:", "tr": "Rapor Tarihi:"},
    "pdf_generator": {"en": "Generated by:", "tr": "Üretici:"},
    "pdf_kpi_targets": {
        "en": "Analyzed Target Polygons",
        "tr": "İncelenen Hedef Poligon"},
    "pdf_kpi_count_fmt": {"en": "{n}", "tr": "{n} Adet"},
    "pdf_kpi_gross": {"en": "Total Gross Area", "tr": "Toplam Brüt Alan"},
    "pdf_kpi_union": {
        "en": "Dissolved Constraint Area",
        "tr": "Birleşik (Tekil) Kısıt Alanı"},
    "pdf_kpi_intersections_fmt": {
        "en": "({n} Intersections)",
        "tr": "({n} Kesişim)"},
    "pdf_kpi_usable": {"en": "Net Residual Area", "tr": "Net Kullanılabilir Alan"},
    "pdf_sec1": {
        "en": "1. Map Snapshot & Spatial Context",
        "tr": "1. Harita Kesiti ve Konum Görünümü"},
    "pdf_sec2": {
        "en": "2. Dissolved Net Residual Area Summary (UnaryUnion)",
        "tr": "2. Birleşik Net Kullanılabilir Alan Özeti (Dissolved / UnaryUnion)"},
    "pdf_sec3": {
        "en": "3. Layer-by-Layer Detailed Overlap Matrix",
        "tr": "3. Katman Bazlı Detaylı Çakışma Matrisi"},
    "pdf_th_base_id": {"en": "Target ID", "tr": "Hedef ID"},
    "pdf_th_gross_ha": {"en": "Gross Area (Ha)", "tr": "Brüt Alan (Ha)"},
    "pdf_th_union_ha": {"en": "Dissolved Overlap (Ha)", "tr": "Birleşik Çakışma (Ha)"},
    "pdf_th_true_pct": {"en": "True Constraint (%)", "tr": "Gerçek Kısıt (%)"},
    "pdf_th_net_ha": {"en": "Net Residual Area (Ha)", "tr": "Net Kalan Alan (Ha)"},
    "pdf_th_net_m2": {"en": "Net Residual Area (m²)", "tr": "Net Kalan Alan (m²)"},
    "pdf_th_ov_layer": {
        "en": "Constraint / Overlay Layer",
        "tr": "Kısıt / Kontrol Katmanı"},
    "pdf_th_ov_obj": {"en": "Overlapping Feature ID", "tr": "Çakışan Obje ID"},
    "pdf_th_target_ha": {"en": "Target Area (Ha)", "tr": "Hedef Alan (Ha)"},
    "pdf_th_ov_m2": {"en": "Overlap (m²)", "tr": "Çakışma (m²)"},
    "pdf_th_ov_ha": {"en": "Overlap (Ha)", "tr": "Çakışma (Ha)"},
    "pdf_th_ratio": {"en": "Ratio (%)", "tr": "Oran (%)"},
    "pdf_map_legend": {
        "en": "Red semi-transparent area (50%): overlapping region",
        "tr": "Kırmızı yarı saydam (%50) alan: çakışan bölge"},
    "pdf_no_overlap": {
        "en": "No spatial overlaps or constraints detected.",
        "tr": "Herhangi bir kısıt veya çakışma tespit edilmemiştir."},
    "pdf_footer": {
        "en": "This technical report was automatically generated by the QGIS <b>Overlap Analyzer Pro</b> plugin.",
        "tr": "Bu teknik bilgi notu QGIS <b>Overlap Analyzer Pro</b> eklentisi tarafından otomatik üretilmiştir."},
}


def tr(key: str, **kwargs) -> str:
    """Anahtarın aktif dildeki metnini döner (Türkçe değilse İngilizce).

    İsteğe bağlı kwargs ile str.format uygulanır: tr("log_done", n=5)
    """
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    text = entry.get(get_language()) or entry.get("en", key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text


def tr_list(key: str) -> list:
    """'|' ile ayrılmış çeviriyi liste olarak döner (tablo/CSV başlıkları için)."""
    return tr(key).split("|")
