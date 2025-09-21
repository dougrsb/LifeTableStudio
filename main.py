import io
import base64
from pathlib import Path
from datetime import datetime

import flet as ft
import matplotlib.pyplot as plt
import pandas as pd

from i18n import STR
from lifetable_core import analyze_by_treatment, export_results
from plot_utils import (
    fig_lx, fig_mx, fig_ex,
    export_all_figures, make_pdf_report, zip_outputs
)
from stats_bootstrap import (
    bootstrap_params, pairwise_compare, cld_from_pmatrix, summarize_boot
)

# ------------------------------------------------------------------
# Robust header normalizer (accept EN/PT and common variants)
# ------------------------------------------------------------------
def _normalize_headers(df: pd.DataFrame, which: str):
    def keyize(s):
        return str(s).strip().lower().replace(" ", "").replace("_","")
    cols = {keyize(c): c for c in df.columns}

    if which == "individuals":
        expected = ["Treatment","ID","Sex","ImmatureDays","AdultDays"]
        mapping = {
            "treatment":"Treatment","tratamento":"Treatment",
            "id":"ID",
            "sex":"Sex","sexo":"Sex",
            "immaturedays":"ImmatureDays","immatureday":"ImmatureDays",
            "diasimaturos":"ImmatureDays","immature_days":"ImmatureDays","juveniledays":"ImmatureDays",
            "adultdays":"AdultDays","adultday":"AdultDays",
            "diasadulto":"AdultDays","adult_days":"AdultDays",
        }
    else:  # eggs
        expected = ["Treatment","FemaleID","AdultDay","Eggs"]
        mapping = {
            "treatment":"Treatment","tratamento":"Treatment",
            "femaleid":"FemaleID","femeaid":"FemaleID","idfemea":"FemaleID","id_femea":"FemaleID","idfemale":"FemaleID",
            "adultday":"AdultDay","diaadulto":"AdultDay","diadulto":"AdultDay","dayadult":"AdultDay",
            "eggs":"Eggs","ovos":"Eggs",
        }

    norm = {}
    for k_std, v_std in mapping.items():
        if k_std in cols:
            norm[v_std] = df[cols[k_std]]
    missing = [c for c in expected if c not in norm]
    if missing:
        raise ValueError(f"{which.capitalize()} sheet is missing required columns: {missing}")
    out = pd.DataFrame({c: norm[c] for c in expected})

    if which == "individuals":
        if "Sex" in out.columns:
            sex_map = {"f":"F","female":"F","fêmea":"F","femea":"F",
                       "m":"M","male":"M","macho":"M"}
            out["Sex"] = out["Sex"].astype(str).str.strip().str.lower().map(sex_map).fillna(out["Sex"])
        for numcol in ["ImmatureDays","AdultDays"]:
            out[numcol] = pd.to_numeric(out[numcol], errors="coerce")
    else:
        for numcol in ["AdultDay","Eggs"]:
            out[numcol] = pd.to_numeric(out[numcol], errors="coerce")
    out["Treatment"] = out["Treatment"].astype(str).str.strip()
    return out


APP_DIR = Path(__file__).parent
TPL_DIR = APP_DIR / "assets" / "templates"
ICON_PATH = APP_DIR / "assets" / "icons" / "app_icon.png"


def main(page: ft.Page):
    page.window_icon = "assets/icons/app_icon.png"
    # Helpers
    def L(key: str, default: str):
        try:
            return STR.get(lang, {}).get(key, default)
        except Exception:
            return default

    def label_control(text: str, ctrl: ft.Control, w: int | None = None):
        lbl = ft.Text(text, size=12, weight="bold")
        if w is not None:
            ctrl.width = w
        return ft.Column([lbl, ctrl], spacing=4)

    def make_table_placeholder():
        return ft.DataTable(
            columns=[ft.DataColumn(ft.Text("—"))],
            rows=[ft.DataRow(cells=[ft.DataCell(ft.Text("—"))])],
        )

    # Bootstrap helpers
    def build_means_se_tables():
        if boot_cache is None:
            return None, None

        import pandas as _pd

        se_df = summarize_boot(boot_cache)
        if se_df is None or se_df.empty:
            return None, None

        params = ["R0", "T", "rm", "lambda", "DT"]
        letters_map = {p: {} for p in params}
        for p in params:
            comp = pairwise_compare(boot_cache, param=p)
            if comp is not None and len(comp):
                means = {t: float(boot_cache[t][p].astype(float).mean())
                         for t in boot_cache.keys()}
                trt_order = sorted(means.keys(), key=lambda k: means[k])
                cld_df = cld_from_pmatrix(
                    trt_order, comp,
                    alpha=float(alpha_dd.value or "0.05")
                )
                for _, r in cld_df.iterrows():
                    letters_map[p][r.get("Tratamento", r.get("Treatment", ""))] = r.get("Letras", r.get("Letters", ""))

        for p in params:
            se_df[p + "_letter"] = se_df["Tratamento"].map(
                lambda t: letters_map[p].get(t, "")
            )

        rows = []
        for _, row in se_df.iterrows():
            cells = [str(row["Tratamento"])]
            for p in ["R0","T","rm","lambda","DT"]:
                m = row.get(p + "_mean")
                s = row.get(p + "_se")
                letter = row.get(p + "_letter", "")
                if m is None or s is None or pd.isna(m) or pd.isna(s):
                    pretty = "–"
                else:
                    pretty = f"{m:.3g} ± {s:.3g}" + (f" {letter}" if letter else "")
                cells.append(pretty)

            rows.append(cells)

        formatted_df = _pd.DataFrame(
            rows,
            columns=["Treatment","R0 (±SE)","T (±SE)","rm (±SE)","λ (±SE)","DT (±SE)"],
        )
        return se_df.copy(), formatted_df

    # Page setup
    lang = "en"
    page.title = L("app_title", "LifeTableStudio")
    page.theme_mode = "light"
    page.window.width = 1200
    page.window.height = 780
    try:
        page.window.icon = str(ICON_PATH)
    except Exception:
        pass

    def on_theme_change(e):
        page.theme_mode = "dark" if e.control.value else "light"
        page.update()

    page.appbar = ft.AppBar(
        title=ft.Text(L("app_title", "LifeTableStudio")),
        actions=[
            ft.Text("   " + L("theme", "Theme") + ": "),
            ft.Switch(value=False, on_change=on_theme_change),
        ],
    )

    # State
    df_ind = df_eggs = summary_df = None
    series_map = {}
    boot_cache = None
    cancel_boot = False
    console = ft.Text(value=L("console_ready", "Ready."), selectable=True)

    def log(msg):
        console.value = str(msg)
        console.update()

    # Data & Results
    data_preview = ft.DataTable(columns=[ft.DataColumn(ft.Text("col"))], rows=[])

    result_cols = ["Tratamento","R0","T","rm","lambda","DT","e0","vida_media","n_individuos"]
    results_table = ft.DataTable(columns=[ft.DataColumn(ft.Text(c)) for c in result_cols], rows=[])

    def update_results_headers():
        headers = ["Treatment","R0","T","rm","lambda","DT","e0","mean_lifespan","n_individuals"]
        if hasattr(results_table, "columns") and len(results_table.columns) == len(headers):
            for i, col in enumerate(results_table.columns):
                try:
                    col.label.value = headers[i]
                except Exception:
                    col.label = ft.Text(headers[i])
            results_table.update()

    def load_excel(path: str):
        nonlocal df_ind, df_eggs
        try:
            xl = pd.ExcelFile(path)
            sheet_ind = "individuals" if "individuals" in xl.sheet_names else None
            sheet_eggs = "eggs" if "eggs" in xl.sheet_names else None
            if not sheet_ind or not sheet_eggs:
                raise ValueError("Sheets must be 'individuals' and 'eggs'.")

            df_ind = pd.read_excel(path, sheet_name=sheet_ind)
            df_ind = _normalize_headers(df_ind, 'individuals')
            df_eggs = pd.read_excel(path, sheet_name=sheet_eggs)
            df_eggs = _normalize_headers(df_eggs, 'eggs')

            data_preview.columns = [ft.DataColumn(ft.Text(c)) for c in df_ind.columns]
            data_preview.rows = [
                ft.DataRow(cells=[ft.DataCell(ft.Text(str(r[c]))) for c in df_ind.columns])
                for _, r in df_ind.head(10).iterrows()
            ]
            data_preview.update()
            log(f"Loaded: {len(df_ind)} individuals, {len(df_eggs)} eggs.")
        except Exception as e:
            log(f"Load error: {e}")

    # Charts
    chart_img = ft.Image(width=980, height=560, fit=ft.ImageFit.CONTAIN, visible=False)

    metric_dd = ft.Dropdown(value="lx", options=[ft.dropdown.Option("lx"), ft.dropdown.Option("mx"), ft.dropdown.Option("ex")], width=160)
    overlay_switch = ft.Switch(value=True)
    dpi_dd = ft.Dropdown(value="600", options=[ft.dropdown.Option("300"), ft.dropdown.Option("600")], width=120)
    fmt_dd = ft.Dropdown(value="png", options=[ft.dropdown.Option("png"), ft.dropdown.Option("jpg"), ft.dropdown.Option("eps")], width=130)
    width_in = ft.TextField(value="8", width=110, content_padding=ft.padding.symmetric(horizontal=8, vertical=6))
    height_in = ft.TextField(value="6", width=110, content_padding=ft.padding.symmetric(horizontal=8, vertical=6))
    treatments_label = ft.Text("Treatments:")

    tr_checks = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO)

    def refresh_treatments_checks():
        tr_checks.controls.clear()
        if series_map:
            for tr in series_map.keys():
                tr_checks.controls.append(ft.Checkbox(label=str(tr), value=True))
        tr_checks.update()

    def selected_treatments():
        return [c.label for c in tr_checks.controls if isinstance(c, ft.Checkbox) and c.value]

    def current_figsize():
        try:
            w = float(width_in.value or "8"); h = float(height_in.value or "6")
            if w <= 0 or h <= 0: return (8, 6)
            return (w, h)
        except Exception:
            return (8, 6)

    def _resize_preview():
        w, h = current_figsize()
        base = 980
        chart_img.width = base
        chart_img.height = int(base * (h / w))

    def render_chart_preview(e=None):
        if not series_map:
            log("No analysis loaded."); return
        sels = selected_treatments()
        if not sels:
            log("Select at least one treatment."); return

        labels = {
            "age_days": "Age (days)",
            "lx_label": "lx", "mx_label": "mx", "ex_label": "ex",
            "lx_title": "Survivorship (lx)", "mx_title": "Fecundity (mx)", "ex_title": "Life expectancy (ex)",
            "lx_overlay_title": "Survivorship", "mx_overlay_title": "Fecundity", "ex_overlay_title": "Life expectancy",
        }
        metric = metric_dd.value; overlay = overlay_switch.value
        _resize_preview(); fig_size = current_figsize()

        if metric == "lx": fig = fig_lx(series_map, sels, overlay, labels, fig_size)
        elif metric == "mx": fig = fig_mx(series_map, sels, overlay, labels, fig_size)
        else: fig = fig_ex(series_map, sels, overlay, labels, fig_size)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=160, bbox_inches="tight")
        plt.close(fig); buf.seek(0)
        chart_img.src_base64 = base64.b64encode(buf.read()).decode("ascii")
        chart_img.visible = True; chart_img.update()

    def save_current_chart(e=None):
        if not series_map: log("No analysis loaded."); return
        sels = selected_treatments()
        if not sels: log("Select at least one treatment."); return

        labels = {"age_days":"Age (days)","lx_label":"lx","mx_label":"mx","ex_label":"ex",
                  "lx_title":"Survivorship (lx)","mx_title":"Fecundity (mx)","ex_title":"Life expectancy (ex)",
                  "lx_overlay_title":"Survivorship","mx_overlay_title":"Fecundity","ex_overlay_title":"Life expectancy"}
        metric = metric_dd.value; overlay = overlay_switch.value; fig_size = current_figsize()

        if metric == "lx": fig = fig_lx(series_map, sels, overlay, labels, fig_size); name = f"chart_lx_{'overlay' if overlay else 'multi'}"
        elif metric == "mx": fig = fig_mx(series_map, sels, overlay, labels, fig_size); name = f"chart_mx_{'overlay' if overlay else 'multi'}"
        else: fig = fig_ex(series_map, sels, overlay, labels, fig_size); name = f"chart_ex_{'overlay' if overlay else 'multi'}"

        dpi = int(dpi_dd.value or "600"); fmt = (fmt_dd.value or "png").lower()

        def on_pick(res: ft.FilePickerResultEvent):
            if not res or not res.path: plt.close(fig); return
            outdir = Path(res.path); outdir.mkdir(parents=True, exist_ok=True)
            fig.savefig(outdir / f"{name}_{dpi}dpi.{fmt}", dpi=dpi, format=fmt, bbox_inches="tight")
            plt.close(fig); log(f"Figure saved to: {outdir}")

        fp = ft.FilePicker(on_result=on_pick); page.overlay.append(fp); page.update()
        fp.get_directory_path(dialog_title="Choose a folder to save the figure")

    # Analysis
    def run_analysis():
        nonlocal summary_df, series_map, boot_cache
        boot_cache = None
        if df_ind is None or df_eggs is None:
            log("No data loaded."); return
        try:
            summary_df, series_map = analyze_by_treatment(df_ind, df_eggs)
            results_table.columns = [ft.DataColumn(ft.Text(c)) for c in result_cols]
            rows = []
            for _, row in summary_df.iterrows():
                cells = []
                for c in result_cols:
                    v = row[c]
                    cells.append(ft.DataCell(ft.Text(f"{v:.6g}" if isinstance(v,(float,int)) else str(v))))
                rows.append(ft.DataRow(cells=cells))
            results_table.rows = rows; update_results_headers(); results_table.update()
            refresh_treatments_checks(); log("Done.")
        except Exception as e:
            log(f"Analysis error: {e}")

    # Exports
    def export_output():
        if summary_df is None: log("No data loaded."); return
        import pandas as _pd

        def on_pick(res: ft.FilePickerResultEvent):
            if not res or not res.path: return
            outdir = Path(res.path); outdir.mkdir(parents=True, exist_ok=True)
            out = outdir / "results.xlsx"
            with _pd.ExcelWriter(out, engine="xlsxwriter") as w:
                export_df = summary_df.rename(columns={
                    "Tratamento":"Treatment",
                    "vida_media":"mean_lifespan",
                    "n_individuos":"n_individuals"
                })
                export_df.to_excel(w, sheet_name="summary", index=False)
                for tr, s in series_map.items():
                    _pd.DataFrame({"age": s.age, "lx": s.lx, "mx": s.mx, "ex": s.ex}).to_excel(w, sheet_name=f"series_{tr}"[:31], index=False)
                se_df, fmt_df = build_means_se_tables()
                if se_df is not None: se_df.to_excel(w, sheet_name="means_se", index=False)
                if fmt_df is not None: fmt_df.to_excel(w, sheet_name="formatted_table", index=False)
            log(f"Exported. ({out})")

        fp = ft.FilePicker(on_result=on_pick); page.overlay.append(fp); page.update()
        fp.get_directory_path(dialog_title="Choose a folder to save 'results.xlsx'")

    def export_formatted_table(e=None):
        se_df, fmt_df = build_means_se_tables()
        if fmt_df is None: log("Run bootstrap first to build the formatted table."); return
        import pandas as _pd
        def on_pick(res: ft.FilePickerResultEvent):
            if not res or not res.path: return
            outdir = Path(res.path); outdir.mkdir(parents=True, exist_ok=True)
            out = outdir / "final_table_formatted.xlsx"
            with _pd.ExcelWriter(out, engine="xlsxwriter") as w:
                fmt_df.to_excel(w, sheet_name="table", index=False)
                wb = w.book; ws = w.sheets["table"]
                header_fmt = wb.add_format({"bold": True, "align": "center", "valign": "vcenter", "border": 1})
                cell_fmt = wb.add_format({"align": "center", "valign": "vcenter", "border": 1})
                ws.set_row(0, 18, header_fmt)
                nrows, ncols = fmt_df.shape
                for r in range(1, nrows + 1): ws.set_row(r, 16, cell_fmt)
                ws.set_column(0, 0, 14); ws.set_column(1, ncols - 1, 16)
            log(f"Formatted table exported to: {out}")
        fp = ft.FilePicker(on_result=on_pick); page.overlay.append(fp); page.update()
        fp.get_directory_path(dialog_title="Choose a folder to save 'final_table_formatted.xlsx'")

    def export_all(e=None):
        if summary_df is None or not series_map: log("No data loaded."); return
        labels = {"age_days":"Age (days)","lx_label":"lx","mx_label":"mx","ex_label":"ex",
                  "lx_title":"Survivorship (lx)","mx_title":"Fecundity (mx)","ex_title":"Life expectancy (ex)",
                  "lx_overlay_title":"Survivorship","mx_overlay_title":"Fecundity","ex_overlay_title":"Life expectancy"}
        fig_size = current_figsize()
        def on_pick(res: ft.FilePickerResultEvent):
            if not res or not res.path: return
            target = Path(res.path); target.mkdir(parents=True, exist_ok=True)
            figs_dir = target / "figures"
            files = export_all_figures(series_map, str(figs_dir), dpis=(300,600), formats=("png","jpg","eps"), labels=labels, fig_size=fig_size)
            out_xlsx = target / "results.xlsx"
            export_df = summary_df.rename(columns={"Tratamento":"Treatment","vida_media":"mean_lifespan","n_individuos":"n_individuals"})
            with pd.ExcelWriter(out_xlsx, engine="xlsxwriter") as w: export_df.to_excel(w, sheet_name="summary", index=False)
            files.append(str(out_xlsx))
            pdf_path = target / "LifeTable_Report.pdf"
            pdf = make_pdf_report(summary_df, series_map, str(pdf_path), labels=labels, fig_size=fig_size)
            files.append(pdf)
            zip_path = target / "LifeTable_Outputs.zip"; zip_outputs(str(zip_path), files)
            log(f"All exports generated. Folder: {target} | ZIP: {zip_path}")
        fp = ft.FilePicker(on_result=on_pick); page.overlay.append(fp); page.update()
        fp.get_directory_path(dialog_title="Choose a folder to EXPORT (figures + PDF + ZIP)")

    # Open & template
    def on_pick_open(e: ft.FilePickerResultEvent):
        path = None
        if e and getattr(e, "files", None) and e.files: path = e.files[0].path
        elif e and getattr(e, "path", None): path = e.path
        if path: load_excel(path)
        else: log("Open file cancelled.")

    fp_open = ft.FilePicker(on_result=on_pick_open); page.overlay.append(fp_open)

    def download_template_lang(code="en"):
        name = "lifetable_template.xlsx"
        def on_pick(res: ft.FilePickerResultEvent):
            if not res or not res.path: return
            target = Path(res.path); target.mkdir(parents=True, exist_ok=True)
            dst = target / name
            with open(TPL_DIR / name, "rb") as fsrc, open(dst, "wb") as fdst:
                fdst.write(fsrc.read())
            log(f"Template saved at: {dst}")
        fp = ft.FilePicker(on_result=on_pick); page.overlay.append(fp); page.update()
        fp.get_directory_path(dialog_title="Choose a folder to save the template")

    def show_instructions(e=None):
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(L("instr_title","Instructions")),
            content=ft.Text(L("instr_text","Fill the spreadsheet (sheets: 'individuals' and 'eggs') and load it via 'Open filled workbook...'"), selectable=True),
            actions=[ft.TextButton("OK", on_click=lambda ev: (setattr(dlg, "open", False), page.update()))],
        )
        page.dialog = dlg; dlg.open = True; page.update()

    # Sidebar
    sidebar_title = ft.Text("Project", weight=ft.FontWeight.BOLD, size=16)
    btn_tpl_en = ft.ElevatedButton(L("btn_tpl_en","Download template"), on_click=lambda e: download_template_lang("en"))
    btn_show_instr = ft.ElevatedButton("Spreadsheet instructions", on_click=show_instructions)
    btn_open_excel = ft.ElevatedButton("Open filled workbook...", on_click=lambda e: fp_open.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["xlsx"]))
    btn_run = ft.ElevatedButton("Run analysis", on_click=lambda e: run_analysis())
    btn_export = ft.ElevatedButton("Export results (Excel)", on_click=lambda e: export_output())

    cite_style = ft.Dropdown(value="APA", options=[ft.dropdown.Option("APA"), ft.dropdown.Option("ABNT")], width=120)
    btn_cite = ft.ElevatedButton(
    "Copy citation...",
    on_click=lambda e: page.set_clipboard(
        f"Barbosa, D. R. S. ({datetime.now().year}). LifeTableStudio [Computer software]. DOI: [xxxx]"
    )
)

    sidebar = ft.Container(
        content=ft.Column([sidebar_title, btn_tpl_en, btn_show_instr, btn_open_excel, btn_run, btn_export, ft.Row([ft.Text("Style:"), cite_style, btn_cite], spacing=8)], spacing=12),
        width=300, padding=16,
    )

    # Charts layout with explicit labels above controls
    charts_row = ft.Row(
        [
            label_control("Metric", metric_dd, 160),
            label_control("Overlay (multiple treatments on the same chart)", overlay_switch),
            label_control("DPI", dpi_dd, 120),
            label_control("Format", fmt_dd, 130),
            label_control("Width (in)", width_in, 110),
            label_control("Height (in)", height_in, 110),
        ],
        spacing=16,
        wrap=True,
    )

    btn_preview = ft.ElevatedButton("Preview chart", on_click=render_chart_preview)
    btn_save_chart = ft.ElevatedButton("Save current chart...", on_click=save_current_chart)
    btn_export_all = ft.ElevatedButton("Export EVERYTHING (figures + PDF + ZIP)...", on_click=export_all)
    btn_export_fmt = ft.ElevatedButton("Export formatted table (Excel)", on_click=export_formatted_table)

    charts_content = ft.Column(
        [
            charts_row,
            ft.Text("Treatments:"),
            ft.Container(content=tr_checks, height=140, width=420, bgcolor=ft.colors.with_opacity(0.03, ft.colors.BLUE_GREY_50), padding=8, border=ft.border.all(1, ft.colors.GREY_400)),
            ft.Row([btn_preview, btn_save_chart, btn_export_all, btn_export_fmt], spacing=10),
            ft.Divider(),
            chart_img,
        ],
        scroll=ft.ScrollMode.AUTO,
    )

    # Statistics layout (labels above controls)
    boot_iters = ft.TextField(value="1000", width=150, content_padding=ft.padding.symmetric(horizontal=8, vertical=6))
    seed_tf = ft.TextField(value="2024", width=150, content_padding=ft.padding.symmetric(horizontal=8, vertical=6))
    alpha_dd = ft.Dropdown(value="0.05", options=[ft.dropdown.Option("0.01"), ft.dropdown.Option("0.05"), ft.dropdown.Option("0.10")], width=140)
    param_dd = ft.Dropdown(value="R0", options=[ft.dropdown.Option(p) for p in ["R0", "T", "rm", "lambda", "DT"]], width=120, on_change=lambda e: refresh_boot_views())
    reuse_sw = ft.Switch(value=True, on_change=lambda e: update_boot_note())

    prog_bar = ft.ProgressBar(value=0, width=420)
    prog_label = ft.Text("Progress")
    cancel_btn = ft.TextButton("Cancel", on_click=lambda e: set_cancel())

    note_hdr = ft.Text("This bootstrap run info", weight="bold")
    boot_note = ft.Text("", selectable=True, size=12)

    def set_cancel():
        nonlocal cancel_boot
        cancel_boot = True

    def update_boot_note():
        txt = (f"Displayed results use n_boot={boot_iters.value}, seed={seed_tf.value or 'None'}, cache={'ON' if reuse_sw.value else 'OFF'}. "
               f"Tip: set a seed for reproducibility and keep 'Reuse samples' ON to switch parameters without recomputing.")
        boot_note.value = txt; boot_note.update()

    pairs_table = make_table_placeholder()
    letters_table = make_table_placeholder()
    means_se_table = make_table_placeholder()

    def df_to_table(df: pd.DataFrame, tbl: ft.DataTable):
        if df is None or getattr(df, 'empty', True):
            tbl.columns = [ft.DataColumn(ft.Text("—"))]; tbl.rows = [ft.DataRow(cells=[ft.DataCell(ft.Text("—"))])]; tbl.update(); return
        tbl.columns = [ft.DataColumn(ft.Text(str(c))) for c in df.columns]
        rows = []; 
        for _, r in df.iterrows():
            cells = [ft.DataCell(ft.Text(str(r[c]))) for c in df.columns]; rows.append(ft.DataRow(cells=cells))
        tbl.rows = rows; tbl.update()

    def refresh_boot_views():
        try:
            if boot_cache is not None:
                comp = pairwise_compare(boot_cache, param=(param_dd.value or "R0")); df_to_table(comp, pairs_table)
                if comp is not None and len(comp):
                    means = {t: float(boot_cache[t][(param_dd.value or "R0")].astype(float).mean()) for t in boot_cache.keys()}
                    trt_order = sorted(means.keys(), key=lambda k: means[k])
                    cld = cld_from_pmatrix(trt_order, comp, alpha=float(alpha_dd.value or "0.05"))
                    cld = cld.rename(columns={"Tratamento": "Treatment", "Letras": "Letters"}); df_to_table(cld, letters_table)
                else:
                    df_to_table(pd.DataFrame(), letters_table)
                _, fmt_df = build_means_se_tables(); df_to_table(fmt_df, means_se_table)
            else:
                df_to_table(pd.DataFrame(), pairs_table); df_to_table(pd.DataFrame(), letters_table); df_to_table(pd.DataFrame(), means_se_table)
        except Exception:
            pass

    def run_bootstrap(e=None):
        nonlocal boot_cache, cancel_boot
        if df_ind is None or df_eggs is None: log("No data loaded."); return
        if reuse_sw.value and boot_cache is not None:
            refresh_boot_views(); return

        n_boot = int(boot_iters.value or "1000")
        seed = None
        try: seed = int(seed_tf.value) if seed_tf.value not in (None, "", "None") else None
        except Exception: seed = None

        prog_bar.value = 0; prog_bar.update()
        prog_label.value = "Progress 0%"; prog_label.update()
        cancel_boot = False; log(f"Running bootstrap (n={n_boot}, α={alpha_dd.value}) ...")

        def _cb(iter_idx, total):
            try:
                frac = max(0.0, min(1.0, float(iter_idx) / float(total)))
                prog_bar.value = frac; prog_bar.update()
                prog_label.value = f"Progress {int(100*frac)}%"; prog_label.update()
            except Exception: pass
            return cancel_boot

        try:
            boot_cache = bootstrap_params(df_ind, df_eggs, n_boot=n_boot, random_state=seed, progress=_cb, cancel=lambda: cancel_boot)
            prog_bar.value = 1; prog_bar.update()
            prog_label.value = "Progress 100%"; prog_label.update()
            log("Bootstrap done.")
        except Exception as e2:
            log(f"Bootstrap error: {e2}"); boot_cache = None

        refresh_boot_views()

    run_boot_btn = ft.ElevatedButton("Run bootstrap", on_click=run_bootstrap)
    btn_update_view = ft.TextButton("Update view", on_click=lambda e: (refresh_boot_views(), update_boot_note()))

    stats_row = ft.Row(
        [
            label_control("Iterations (n-boot)", boot_iters, 150),
            label_control("Seed (optional)", seed_tf, 150),
            label_control("α (significance)", alpha_dd, 140),
            label_control("Parameter", param_dd, 120),
            label_control("Reuse samples (no recompute)", reuse_sw),
        ],
        spacing=16,
        wrap=True,
    )

    stats_content = ft.Column(
        [
            stats_row,
            ft.Row([prog_bar, ft.Text(" "), prog_label, cancel_btn], spacing=8),
            ft.Row([run_boot_btn, btn_update_view], spacing=10),
            ft.Container(ft.Column([note_hdr, boot_note], spacing=4), padding=ft.padding.only(top=6, bottom=6)),
            ft.Divider(),
            ft.Text("Pairwise comparisons (95% CI and p_bootstrap)", weight="bold"),
            pairs_table,
            ft.Divider(),
            ft.Text("Letters (CLD) by parameter", weight="bold"),
            letters_table,
            ft.Divider(),
            ft.Text("Means ± SE per parameter (bootstrap)", weight="bold"),
            means_se_table,
        ],
        scroll=ft.ScrollMode.AUTO,
    )

    # Tabs
    tabs = ft.Tabs(
        selected_index=2,
        tabs=[
            ft.Tab(text="Data", content=data_preview),
            ft.Tab(text="Results", content=results_table),
            ft.Tab(text="Charts", content=charts_content),
            ft.Tab(text="Console", content=console),
            ft.Tab(text="Statistics", content=stats_content),
        ],
        expand=1,
    )

    layout = ft.Row([sidebar, ft.Container(content=tabs, expand=True)], expand=True)

    # Mount
    page.add(layout)
    page.update()
    update_results_headers()
    update_boot_note()


if __name__ == "__main__":
    ft.app(target=main)