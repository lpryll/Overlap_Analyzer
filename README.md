# Overlap Analyzer

A QGIS plugin that analyzes how polygons of a **target layer** overlap with one or more **constraint / overlay layers**, and reports both the individual overlaps and the **dissolved net residual area** that is left after all overlaps are removed.

The analysis runs in the background (`QgsTask`), so QGIS stays responsive while large layers are processed.

- QGIS 3.22 and later, including QGIS 4 (Qt5 / PyQt5 and Qt6 / PyQt6)
- Interface and reports in **Turkish or English**, depending on the Windows display language

---

## Features

- **Multi-layer analysis:** check one target polygon layer against any number of constraint layers in a single run.
- **Per-layer ID field:** choose which attribute identifies the features of each layer in the reports.
- **Selected features only:** optionally analyze only the selected target polygons.
- **Sliver threshold:** ignore micro overlaps below a minimum area (m²).
- **Two result views**
  - *Detailed Overlap Matrix* - one row per target / overlay feature pair.
  - *Net Residual Area Summary* - one row per target polygon. Overlapping constraints are dissolved first (`unaryUnion`), so areas covered by several layers are not counted twice.
- **Filters:** filter the results by **Target ID** and by **Overlay ID**. Type part of an ID, or several IDs separated by commas.
- **Tick boxes:** tick one or more target objects in the result lists (the tick is kept in sync between both tabs). *Tick Visible* ticks everything the filters currently show, *Clear Ticks* removes all ticks.
- **Map interaction:** click a result row to zoom to it and flash it on the map.
- **Outputs:** graduated map layer, CSV export, and a PDF info card with a map snapshot.

---

## Installation

1. In QGIS open **Plugins > Manage and Install Plugins > Install from ZIP**.
2. Select `overlap_analyzer.zip` and install.
3. Restart QGIS (also required after an update, otherwise QGIS may keep running the old code).

---

## Usage

1. Open **Overlap Analyzer** from the Plugins menu or the toolbar.
2. **Target layer:** select the polygon layer, the ID field, and (optionally) *Analyze only selected polygons*. Set the sliver threshold if needed.
3. **Constraint / overlay layers:** tick the layers to check against and choose the ID field to show for each of them.
4. Click **Run Multi-Layer Overlap Analysis**. Progress is shown while the task runs; it can be cancelled.
5. Review the results in the two tabs, use the filters and tick boxes to narrow them down.
6. Use the output buttons:
   - **Add Overlaps as Graduated Layer** - adds the overlaps to the map, colored by overlap ratio (low 0-15%, medium 15-50%, high 50%+).
   - **Export to Excel (CSV)** - saves the net residual summary and the detailed matrix to a CSV file.
   - **Generate PDF Info Card with Map** - see below.

---

## PDF info card

The PDF contains a map snapshot, KPI boxes, the net residual area summary and the detailed overlap matrix. Overlapping areas are highlighted on the map with a semi-transparent (50%) red fill.

Which objects are included is decided in this order:

| Priority | Situation | Result |
|---|---|---|
| 1 | One or more objects are **ticked** | Only the ticked objects |
| 2 | A result row is **selected** in the list | That row's target object |
| 3 | Target features are **selected on the map** | Those objects |
| 4 | A **filter** is active | The objects shown by the filter |
| 5 | None of the above | The whole list in one combined card |

When more than one object is in scope, a **single multi-page PDF** is created: every object gets its own page(s) with its own map (zoomed to the object), KPIs, summary and detail tables.

The line under the output buttons ("PDF scope") always shows what the next PDF will contain.

---

## Result columns

**Detailed Overlap Matrix:** Target ID, overlay layer, overlay ID, target area (Ha), overlap area (m² and Ha), overlap ratio (%).

**Net Residual Area Summary:** Target ID, total target area (Ha), dissolved overlap (Ha), true constraint ratio (%), net residual area (Ha and m²).

---

## Language

The language is chosen automatically from the **Windows display language**:

- Turkish Windows: Turkish interface, reports, CSV headers and field names.
- Any other language: English.

The language is read once when the plugin starts, so restart QGIS after changing the Windows language. For testing, the `OVERLAP_ANALYZER_LANG` environment variable (`tr` or `en`) overrides the detection.

Layer names, feature IDs and attribute values are shown exactly as they are in your data and are not translated.

---

## Changelog

### 2.1.0
- Interface and reports follow the Windows language (Turkish on Turkish Windows, English otherwise)
- Target ID and Overlay ID filters for the results lists
- Tick boxes for multi-object selection in the results lists
- PDF info card can be generated for the selected, ticked or filtered objects only, with the map zoomed to them
- Multiple objects produce a single multi-page PDF (one page, map and info card per object)
- Overlapping areas are highlighted with a semi-transparent fill on the PDF map
- Wording updated to "Net Residual Area"
- Fixed an error when reopening the dialog

---

## Türkçe özet

**Overlap Analyzer**, bir hedef poligon katmanının bir veya birden fazla kısıt / çakışma katmanıyla kesişimlerini hesaplayan bir QGIS eklentisidir. Tek tek çakışmaların yanında, tüm çakışmalar birleştirildikten sonra geriye kalan **net kalan alanı** da raporlar.

- Windows görüntüleme dili Türkçe ise arayüz ve raporlar Türkçe, diğer dillerde İngilizce çalışır.
- Sonuç listelerinde **Hedef ID** ve **Çakışan ID** filtresi vardır; satır başındaki kutularla birden fazla nesne işaretlenebilir.
- **Harita kesitli PDF bilgi kartı** yalnızca işaretli, seçili veya filtrelenmiş nesneler için üretilebilir. Birden fazla nesne varsa tek, çok sayfalı bir PDF oluşur ve her nesne kendi haritası ve bilgi kartıyla ayrı sayfada yer alır. Çakışan alanlar haritada %50 saydam kırmızıyla vurgulanır.
- Kurulum: **Eklentiler > Eklentileri Yönet ve Kur > ZIP'ten Kur**. Güncelleme sonrası QGIS'i yeniden başlatın.

---

## Author

Alper Yolal (LPRYLL)
