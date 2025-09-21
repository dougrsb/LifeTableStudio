
from __future__ import annotations
from pathlib import Path
import zipfile
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

plt.rcParams.update({
    "font.size": 12,
    "axes.titlesize": 18,
    "axes.labelsize": 14,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
    "legend.fontsize": 11,
    "axes.grid": True,
    "grid.linestyle": "--",
    "grid.alpha": 0.3,
    "lines.linewidth": 2.5,
    "lines.markersize": 6,
})

def _lab(labels, key, default): return (labels or {}).get(key, default)
def _prep(ax, xlab, ylab, title):
    ax.set_xlabel(xlab); ax.set_ylabel(ylab); ax.set_title(title, pad=12); ax.margins(x=0.02, y=0.05)
def _single(fig_size): return plt.subplots(figsize=fig_size, dpi=120, constrained_layout=True)

def _series_plot(ax, s, kind):
    y = getattr(s, kind)
    ax.plot(s.age, y, marker="o")

def _multi_plot(series_map, treatments, overlay, labels, fig_size, kind):
    title_s = _lab(labels, f"{kind}_title", f"{kind} — "+"{trt}")
    title_o = _lab(labels, f"{kind}_overlay_title", f"{kind} — Overlays")
    ylab = _lab(labels, f"{kind}_label", kind)
    xlab = _lab(labels, "age_days", "Age (days)")
    if overlay:
        fig, ax = _single(fig_size)
        for tr in treatments:
            s = series_map[tr]
            _series_plot(ax, s, kind)
            ax.legend_.remove() if ax.get_legend() else None
        for tr in treatments:
            s = series_map[tr]
            ax.plot(s.age, getattr(s, kind), marker="o", label=str(tr))
        _prep(ax, xlab, ylab, title_o); ax.legend(frameon=False); return fig
    else:
        rows = len(treatments)
        fig_h = max(3.2, fig_size[1]*rows*0.95)
        fig, axs = plt.subplots(rows,1, figsize=(fig_size[0], fig_h), dpi=120, sharex=True, constrained_layout=True)
        if rows==1: axs=[axs]
        for ax,tr in zip(axs, treatments):
            s = series_map[tr]
            ax.plot(s.age, getattr(s, kind), marker="o", label=str(tr))
            _prep(ax, xlab, ylab, title_s.format(trt=tr)); ax.legend(frameon=False)
        return fig

def fig_lx(series_map, treatments=None, overlay=True, labels=None, fig_size=(8,6)):
    treatments = list(series_map.keys()) if not treatments else treatments
    return _multi_plot(series_map, treatments, overlay, labels, fig_size, "lx")

def fig_mx(series_map, treatments=None, overlay=True, labels=None, fig_size=(8,6)):
    treatments = list(series_map.keys()) if not treatments else treatments
    return _multi_plot(series_map, treatments, overlay, labels, fig_size, "mx")

def fig_ex(series_map, treatments=None, overlay=True, labels=None, fig_size=(8,6)):
    treatments = list(series_map.keys()) if not treatments else treatments
    return _multi_plot(series_map, treatments, overlay, labels, fig_size, "ex")

def export_all_figures(series_map, out_dir, dpis=(300,600), formats=("png","jpg","eps"), labels=None, fig_size=(8,6)):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    paths=[]; trts=list(series_map.keys())
    for maker,name in [(fig_lx,"overlay_lx"),(fig_mx,"overlay_mx"),(fig_ex,"overlay_ex")]:
        fig = maker(series_map, trts, True, labels, fig_size)
        for dpi in dpis:
            for fmt in formats:
                p = out / f"{name}_{dpi}dpi.{fmt}"; fig.savefig(p, dpi=dpi, format=fmt, bbox_inches="tight"); paths.append(str(p))
        plt.close(fig)
    for tr in trts:
        s_map={tr:series_map[tr]}
        for maker,base in [(fig_lx,f"{tr}_lx"),(fig_mx,f"{tr}_mx"),(fig_ex,f"{tr}_ex")]:
            fig = maker(s_map,[tr],True,labels,fig_size)
            for dpi in dpis:
                for fmt in formats:
                    p = out / f"{base}_{dpi}dpi.{fmt}"; fig.savefig(p, dpi=dpi, format=fmt, bbox_inches="tight"); paths.append(str(p))
            plt.close(fig)
    return paths

def make_pdf_report(summary_df, series_map, out_pdf, labels=None, fig_size=(8,6)):
    pdfp = Path(out_pdf); pdfp.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(pdfp) as pdf:
        fig, ax = plt.subplots(figsize=(11.69, 8.27), dpi=150, constrained_layout=True)
        ax.axis("off"); ax.set_title("Life Table Summary", fontsize=16, weight="bold", pad=12)
        tbl = ax.table(cellText=summary_df.round(4).values, colLabels=summary_df.columns.tolist(), loc="center")
        tbl.auto_set_font_size(False); tbl.set_fontsize(8); tbl.scale(1,1.2)
        pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)
        for mk in (fig_lx, fig_mx, fig_ex):
            fig = mk(series_map, treatments=list(series_map.keys()), overlay=True, labels=labels, fig_size=fig_size)
            pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)
    return str(pdfp)

def zip_outputs(zip_path, files):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            p = Path(f)
            if p.exists(): z.write(p, p.name)
    return str(zip_path)
