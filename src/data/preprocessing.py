"""Daily aggregation utilities."""

import pandas as pd


def aggregate_daily(operations: pd.DataFrame, account: str | None = None) -> pd.DataFrame:
    """Return a continuous daily index with zero-flow days retained."""
    selected = operations if account is None else operations.loc[operations["account"] == account]
    if selected.empty:
        return pd.DataFrame(columns=["date", "inflow", "outflow", "net_flow"])
    grouped = selected.groupby("date")["amount"].agg(
        inflow=lambda s: s[s > 0].sum(),
        outflow=lambda s: -s[s < 0].sum(),
        net_flow="sum",
    )
    grouped = grouped.asfreq("D", fill_value=0).fillna(0)
    grouped.index.name = "date"
    return grouped.reset_index()
