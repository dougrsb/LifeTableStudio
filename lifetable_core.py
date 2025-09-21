
from __future__ import annotations
from dataclasses import dataclass
from typing import List
import numpy as np
import pandas as pd

@dataclass
class Series:
    age: List[int]
    lx: List[float]
    mx: List[float]
    ex: List[float]

def _std_cols(df_ind: pd.DataFrame, df_eggs: pd.DataFrame):
    cols_pt = {"Tratamento":"Treatment","ID":"ID","Sexo":"Sex","DiasImaturos":"ImmatureDays","DiasAdulto":"AdultDays"}
    cols_en = {"Treatment":"Treatment","ID":"ID","Sex":"Sex","ImmatureDays":"ImmatureDays","AdultDays":"AdultDays"}
    if set(cols_pt).issubset(df_ind.columns): df_ind = df_ind.rename(columns=cols_pt)
    elif set(cols_en).issubset(df_ind.columns): df_ind = df_ind.rename(columns=cols_en)
    else: raise ValueError("Individuals sheet has unexpected columns.")
    eggs_pt = {"Tratamento":"Treatment","ID_femea":"FemaleID","DiaAdulto":"AdultDay","Ovos":"Eggs"}
    eggs_en = {"Treatment":"Treatment","FemaleID":"FemaleID","AdultDay":"AdultDay","Eggs":"Eggs"}
    if set(eggs_pt).issubset(df_eggs.columns): df_eggs = df_eggs.rename(columns=eggs_pt)
    elif set(eggs_en).issubset(df_eggs.columns): df_eggs = df_eggs.rename(columns=eggs_en)
    else: raise ValueError("Eggs sheet has unexpected columns.")
    df_ind["Treatment"] = df_ind["Treatment"].astype(str)
    df_eggs["Treatment"] = df_eggs["Treatment"].astype(str)
    return df_ind, df_eggs

def _lifetable_for_treatment(ind: pd.DataFrame, eggs: pd.DataFrame):
    ind = ind.copy(); eggs = eggs.copy()
    ind["Lifespan"] = ind["ImmatureDays"].fillna(0).astype(int) + ind["AdultDays"].fillna(0).astype(int)
    n0 = len(ind); max_age = int(ind["Lifespan"].max() if n0>0 else 0)
    ages = list(range(0, max_age+1))
    lx = []
    for x in ages:
        alive = (ind["Lifespan"] > x).sum()
        lx.append(alive / n0 if n0>0 else 0.0)
    fem0 = (ind["Sex"].astype(str).str.upper().str.startswith("F")).sum()
    mx = [0.0]*(max_age+1)
    if fem0>0 and not eggs.empty:
        avg_imm = int(round(ind["ImmatureDays"].fillna(0).mean()))
        eg = eggs.copy(); eg["AbsAge"] = eg["AdultDay"].fillna(0).astype(int) + avg_imm
        agg = eg.groupby("AbsAge")["Eggs"].sum()
        for x,v in agg.items():
            if 0<=x<=max_age: mx[x] = float(v)/max(fem0,1)
    Lx = [(lx[i] + (lx[i+1] if i+1<len(lx) else 0))/2.0 for i in range(len(lx))]
    Tx = list(reversed(np.cumsum(list(reversed(Lx)))))
    ex = [ (Tx[i]/lx[i] if lx[i]>0 else 0.0) for i in range(len(lx)) ]
    lx_arr = np.array(lx); mx_arr = np.array(mx); x_arr = np.arange(len(lx))
    R0 = float(np.sum(lx_arr*mx_arr))
    T = float(np.sum(x_arr*lx_arr*mx_arr)/R0) if R0>0 else 0.0
    def f(r): return np.sum(lx_arr*mx_arr*np.exp(-r*x_arr)) - 1.0
    r_low, r_high = -1.0, 1.0; fl, fh = f(r_low), f(r_high); tries=0
    while fl*fh>0 and tries<10: r_low-=1.0; r_high+=1.0; fl, fh = f(r_low), f(r_high); tries+=1
    rm = 0.0
    if fl*fh<=0:
        for _ in range(60):
            r_mid=(r_low+r_high)/2.0; fm=f(r_mid)
            if abs(fm)<1e-8: break
            if fl*fm<=0: r_high, fh = r_mid, fm
            else: r_low, fl = r_mid, fm
        rm = (r_low+r_high)/2.0
    lam = float(np.exp(rm))
    DT = (np.log(2)/rm) if rm>0 else float("nan")
    e0 = float(ex[0]) if ex else 0.0
    vida_media = float(ind["Lifespan"].mean()) if n0>0 else 0.0
    import pandas as pd
    summary = pd.DataFrame([{
        "Tratamento": ind["Treatment"].iloc[0] if n0>0 else "",
        "R0": R0, "T": T, "rm": rm, "lambda": lam, "DT": DT, "e0": e0, "vida_media": vida_media, "n_individuos": n0
    }])
    s = Series(age=ages, lx=lx, mx=mx, ex=ex)
    return summary, s

def analyze_by_treatment(df_ind: pd.DataFrame, df_eggs: pd.DataFrame):
    df_ind, df_eggs = _std_cols(df_ind, df_eggs)
    treatments = sorted(df_ind["Treatment"].unique())
    import pandas as pd
    all_rows = []; series_map = {}
    for tr in treatments:
        summ, s = _lifetable_for_treatment(df_ind[df_ind["Treatment"]==tr], df_eggs[df_eggs["Treatment"]==tr])
        all_rows.append(summ); series_map[tr]=s
    return pd.concat(all_rows, ignore_index=True), series_map

def export_results(path, summary_df, series_map):
    with pd.ExcelWriter(path, engine="xlsxwriter") as w:
        summary_df.to_excel(w, sheet_name="summary", index=False)
        for tr,s in series_map.items():
            pd.DataFrame({"age": s.age, "lx": s.lx, "mx": s.mx, "ex": s.ex}).to_excel(w, sheet_name=f"series_{tr}"[:31], index=False)
