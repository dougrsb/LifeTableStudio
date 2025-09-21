# i18n.py — EN-only
STR = {
    "en": {
        "app_title": "LifeTableStudio",
        "theme": "Theme",
        "console_ready": "Ready.",
        "loaded_counts": "Loaded: {n_ind} individuals, {n_eggs} eggs.",
        "progress": "Progress",
        "res_treatment": "Treatment",
        "res_meanlife": "mean_lifespan",
        "res_n": "n_individuals",
        "tab_data": "Data",
        "tab_results": "Results",
        "tab_charts": "Charts",
        "tab_console": "Console",
        "tab_stats": "Statistics",
        "sidebar_title": "Project",
        "btn_tpl_en": "Download template",
        "btn_open_excel": "Open filled workbook...",
        "btn_run": "Run analysis",
        "btn_export": "Export results (Excel)",
        "cite_style": "Style",
        "btn_cite": "Copy citation...",
        "charts_metric": "Metric",
        "charts_overlay": "Overlay (multiple treatments on the same chart)",
        "charts_treatments": "Treatments:",
        "charts_dpi": "DPI",
        "charts_format": "Format",
        "charts_width": "Width (in)",
        "charts_height": "Height (in)",
        "btn_preview": "Preview chart",
        "btn_save_chart": "Save current chart...",
        "btn_export_all": "Export EVERYTHING (figures + PDF + ZIP)...",
        "btn_export_fmt_table": "Export formatted table (Excel)",
        "age_days": "Age (days)",
        "lx_label": "lx", "mx_label": "mx", "ex_label": "ex",
        "lx_title": "Survivorship (lx)",
        "mx_title": "Fecundity (mx)",
        "ex_title": "Life expectancy (ex)",
        "lx_overlay_title": "Survivorship",
        "mx_overlay_title": "Fecundity",
        "ex_overlay_title": "Life expectancy",
        "boot_iters": "Iterations (n-boot)",
        "seed": "Seed (optional)",
        "alpha": "α (significance)",
        "param": "Parameter",
        "reuse": "Reuse samples (no recompute)",
        "run_boot": "Run bootstrap",
        "update_view": "Update view",
        "boot_note_title": "This bootstrap run info",
        "boot_note_prefix": "Displayed results use",
        "boot_note_tip": "Tip: set a seed (integer, e.g., 2024) for reproducibility and keep \"Reuse samples\" ON to switch parameters without recomputing. Re-run when you change n_boot, seed, or data.",
        "pairs_hdr": "Pairwise comparisons (95% CI and p_bootstrap)",
        "letters_hdr": "Letters (CLD) by parameter",
        "se_hdr": "Means ± SE per parameter (bootstrap)",
        "cancel": "Cancel",
        "instr_title": "Instructions",
        "instr_text": (
            "1) Click 'Download template'.\n"
            "2) Fill the workbook using sheets:\n"
            "   - 'individuals' with columns: Treatment, ID, Sex, ImmatureDays, AdultDays\n"
            "   - 'eggs' with columns: Treatment, FemaleID, AdultDay, Eggs\n"
            "3) Save and 'Open filled workbook...'.\n"
            "4) Click 'Run analysis' to compute summary and curves.\n"
            "5) Go to Statistics → set n-boot, seed, α → 'Run bootstrap'.\n"
            "6) Use 'Export results (Excel)' or 'Export formatted table (Excel)'."
        ),
        "export_ok": "Exported.",
        "export_ok_plus": "Exported with bootstrap sheets."
    }
}

def L(key: str, default: str = "") -> str:
    return STR["en"].get(key, default or key)
