from __future__ import annotations
import numpy as np, pandas as pd
from lifetable_core import analyze_by_treatment, _std_cols

def bootstrap_params(df_ind, df_eggs, n_boot=1000, random_state=None, progress=None, cancel=None):
    """
    Return dict[treatment] -> DataFrame of bootstrap values (R0, T, rm, lambda, DT).
    - df_ind, df_eggs: original data frames
    - progress(iter, total): optional callback
    - cancel(): optional function returning True to stop early
    """
    rng = np.random.default_rng(random_state)
    df_ind, df_eggs = _std_cols(df_ind.copy(), df_eggs.copy())
    trts = sorted(df_ind["Treatment"].unique())
    boots = {tr: pd.DataFrame(columns=["R0","T","rm","lambda","DT"]) for tr in trts}
    step = max(1, n_boot//100)

    # Pre-split by treatment for speed
    ind_by_tr = {tr: df_ind[df_ind["Treatment"]==tr].reset_index(drop=True) for tr in trts}
    eggs_by_tr = {tr: df_eggs[df_eggs["Treatment"]==tr].reset_index(drop=True) for tr in trts}

    for b in range(n_boot):
        if cancel is not None and cancel():
            break

        # Resample per treatment (individual-level bootstrap; eggs by FemaleID if available)
        ind_samp=[]; eggs_samp=[]
        for tr in trts:
            ind_t = ind_by_tr[tr]
            # avoid empty crash
            if len(ind_t) == 0:
                ind_boot = ind_t.copy()
            else:
                # row-resample with replacement
                idx = rng.integers(0, len(ind_t), size=len(ind_t))
                ind_boot = ind_t.iloc[idx].reset_index(drop=True)
            ind_samp.append(ind_boot)

            eg_t = eggs_by_tr[tr]
            if "FemaleID" in eg_t.columns and not eg_t.empty:
                groups = [g for _, g in eg_t.groupby("FemaleID")]
                if len(groups) > 0:
                    # resample whole females (cluster bootstrap)
                    idxg = rng.integers(0, len(groups), size=len(groups))
                    eg_boot = pd.concat([groups[i] for i in idxg], ignore_index=True)
                else:
                    eg_boot = eg_t.copy()
            else:
                eg_boot = eg_t.copy()
            eggs_samp.append(eg_boot)

        ind_samp = pd.concat(ind_samp, ignore_index=True) if ind_samp else pd.DataFrame()
        eggs_samp = pd.concat(eggs_samp, ignore_index=True) if eggs_samp else pd.DataFrame()

        summ, _ = analyze_by_treatment(ind_samp, eggs_samp)
        for _, row in summ.iterrows():
            tr = row["Tratamento"]
            boots[tr].loc[len(boots[tr])] = [row.get("R0"), row.get("T"), row.get("rm"), row.get("lambda"), row.get("DT")]

        if progress is not None and (b % step == 0):
            progress(b+1, n_boot)

    if progress is not None:
        progress(n_boot, n_boot)
    return boots

def pairwise_compare(boot_cache, param="R0"):
    trs = sorted(boot_cache.keys()); rows=[]
    for i in range(len(trs)):
        for j in range(i+1, len(trs)):
            A,B = trs[i], trs[j]
            a = boot_cache[A][param].astype(float).to_numpy() if param in boot_cache[A].columns else np.array([])
            b = boot_cache[B][param].astype(float).to_numpy() if param in boot_cache[B].columns else np.array([])
            n = min(len(a), len(b))
            if n==0: 
                continue
            mask = np.isfinite(a[:n]) & np.isfinite(b[:n])
            if mask.sum()==0:
                continue
            d = b[:n][mask]-a[:n][mask]
            ci_low, ci_high = np.percentile(d, [2.5,97.5])
            p = 2*min((d<=0).mean(), (d>=0).mean())
            rows.append({"param":param, "A":A, "B":B, "diff":float(d.mean()), "ci_low":float(ci_low), "ci_high":float(ci_high), "p_bootstrap":float(p), "n_boot":int(n)})
    return pd.DataFrame(rows)

def cld_from_pmatrix(trt_order, comp_df, alpha=0.05):
    letters={}; current='a'; letters[trt_order[0]]=current
    for t in trt_order[1:]:
        differs=False
        for prev in trt_order:
            if prev==t: break
            row = comp_df[((comp_df["A"]==prev)&(comp_df["B"]==t)) | ((comp_df["A"]==t)&(comp_df["B"]==prev))]
            if not row.empty and float(row.iloc[0]["p_bootstrap"]) < alpha:
                differs=True; break
        if differs: current = chr(ord(current)+1)
        letters[t]=current
    return pd.DataFrame({"Tratamento":trt_order, "Letras":[letters[t] for t in trt_order]})

def summarize_boot(boot_cache):
    "Return DataFrame with mean and SE for each parameter and treatment."
    rows=[]; params=["R0","T","rm","lambda","DT"]
    for tr, df in boot_cache.items():
        row={"Tratamento":tr}
        for p in params:
            if p not in df.columns:
                row[p+"_mean"] = float("nan")
                row[p+"_se"] = float("nan")
                continue
            arr = df[p].astype(float).to_numpy()
            arr = arr[np.isfinite(arr)]
            if p=="DT":
                arr = arr[arr>0]
            row[p+"_mean"] = float(np.nanmean(arr)) if arr.size else float("nan")
            row[p+"_se"]   = float(np.nanstd(arr, ddof=1)) if arr.size>1 else float("nan")
        rows.append(row)
    return pd.DataFrame(rows)
