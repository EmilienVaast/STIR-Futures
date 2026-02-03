import pandas as pd

def print_dashed_table(df: pd.DataFrame, cols: list[str]) -> None:
    df = df[cols].copy()
    widths = {c: max(len(c), df[c].astype(str).map(len).max()) for c in cols}

    def fmt_row(d: dict) -> str:
        return " | ".join(f"{str(d[c]):<{widths[c]}}" for c in cols)

    header = fmt_row({c: c for c in cols})
    sep = "-" * len(header)

    print(sep)
    print(header)
    print(sep)
    for _, r in df.iterrows():
        print(fmt_row(r.to_dict()))
    print(sep)
