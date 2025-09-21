# LifeTableStudio

Interactive tool for life table construction and analysis, with automatic graph generation and population parameter estimation.

## Highlights (v2)
- IDE-style interface with tabs: **Data**, **Results**, **Charts**, **Console**
- Buttons: **Download template**, **Spreadsheet instructions**, **Open filled spreadsheet…**, **Run analysis**, **Export results (Excel)**
- Charts: **Lx, Mx, ex** (individual and overlay), export to **PNG/JPG/EPS** (300/600 dpi)
- **Export ALL**: creates `figures/`, optional `results.xlsx`, plus **PDF** and **ZIP** bundles

## Run
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
