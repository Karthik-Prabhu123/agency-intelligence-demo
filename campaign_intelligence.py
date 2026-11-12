"""Evidence-led, rule-based campaign diagnostics for Agency Intelligence V1.2.1."""
from __future__ import annotations

import pandas as pd


def _sum_known(values: pd.Series) -> float:
    """Sum known observations, retaining NaN when every observation is missing."""
    result = values.sum(min_count=1)
    return float(result) if pd.notna(result) else float("nan")


def build_campaign_summary(data: pd.DataFrame) -> pd.DataFrame:
    if data is None or data.empty:
        return pd.DataFrame()
    summary = data.groupby(["platform", "campaign"], dropna=False, as_index=False).agg(
        spend=("spend", "sum"),
        conversions=("conversions", "sum"),
        revenue=("revenue", "sum"),
        clicks=("clicks", _sum_known),
        impressions=("impressions", _sum_known),
    )
    summary["roas"] = summary["revenue"].div(summary["spend"].where(summary["spend"] > 0))
    summary["cpa"] = summary["spend"].div(summary["conversions"].where(summary["conversions"] > 0))
    summary["ctr"] = summary["clicks"].div(summary["impressions"].where(summary["impressions"] > 0)) * 100
    total_spend = float(summary["spend"].sum())
    summary["spend_share_pct"] = summary["spend"].div(total_spend).mul(100) if total_spend > 0 else float("nan")
    summary["spend_without_conversions"] = summary["spend"].where(summary["conversions"] <= 0, 0.0)
    return summary.sort_values("spend", ascending=False).reset_index(drop=True)


def analyse_campaigns(
    data: pd.DataFrame,
    target_roas: float = 2.0,
    minimum_spend: float = 50.0,
    minimum_conversions_for_scale: float = 5.0,
    decline_threshold_pct: float = 20.0,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Return campaign summary, findings and data-quality/interpretation notes."""
    summary = build_campaign_summary(data)
    findings: list[dict] = []
    notes: list[str] = []
    if summary.empty:
        return summary, pd.DataFrame(), ["No processed campaign data is available."]

    def add(priority: str, category: str, row: pd.Series, evidence: str, action: str):
        spend_without_conversions = float(row["spend_without_conversions"])
        findings.append({
            "Priority": priority,
            "Finding": category,
            "Platform": row["platform"],
            "Campaign": row["campaign"],
            "Evidence": evidence,
            "Recommended action": action,
            "Spend": float(row["spend"]),
            "Spend share": float(row["spend_share_pct"]) if pd.notna(row["spend_share_pct"]) else float("nan"),
            "Spend without conversions": spend_without_conversions,
            "ROAS": float(row["roas"]) if pd.notna(row["roas"]) else float("nan"),
            "Conversions": float(row["conversions"]),
        })

    if summary["revenue"].sum() <= 0:
        notes.append("No attributed conversion value is present. ROAS-based decisions and scaling signals are unavailable until conversion value is mapped or supplied.")
    if summary["conversions"].sum() <= 0:
        notes.append("No conversions were recorded in the imported data. Check the conversion mapping and reporting period before treating this as a performance problem.")
    if summary["clicks"].isna().all():
        notes.append("Clicks were not supplied in the import. Click-dependent metrics such as CPC cannot be assessed.")
    if summary["impressions"].isna().all():
        notes.append("Impressions were not supplied in the import. Impression-dependent metrics such as CTR cannot be assessed.")
    elif summary["impressions"].isna().any():
        notes.append("Impressions are missing for some campaigns. CTR is shown as N/A wherever the required data is unavailable.")

    # Material spend without reported conversions. The spend itself is the
    # observed exposure, not a claim that the amount is recoverable waste.
    for _, row in summary.iterrows():
        if row.spend >= minimum_spend and row.conversions <= 0:
            share = row.spend_share_pct
            share_text = f" ({share:.1f}% of client spend)" if pd.notna(share) else ""
            add("High", "Spend without conversions", row,
                f"{row.spend:,.2f} spent with 0 reported conversions{share_text}; this is spend with no attributed conversions in the supplied data, not confirmed recoverable waste.",
                "First verify conversion tracking, attribution settings and the reporting period. Then inspect landing-page experience, audience and placements. Consider a controlled spend cap only after confirming the data is accurate.")

    # Relative efficiency screen using the client's own observed campaign mix.
    positive_cpa = summary.loc[summary.conversions > 0, "cpa"].dropna()
    if len(positive_cpa) >= 2:
        peer_cpa = float(positive_cpa.median())
        spend_cutoff = float(summary.spend.quantile(0.75))
        for _, row in summary.iterrows():
            if row.spend >= max(minimum_spend, spend_cutoff) and row.conversions > 0 and pd.notna(row.cpa) and row.cpa > peer_cpa * 1.5:
                add("Medium", "High spend, elevated CPA", row,
                    f"Spend {row.spend:,.2f} ({row.spend_share_pct:.1f}% of client spend); CPA {row.cpa:,.2f}, above 1.5× the account's median CPA ({peer_cpa:,.2f}).",
                    "Review audience, keyword/placement mix and creative. Test any budget reallocation gradually and compare results over a consistent period.")

    # Conservative opportunity signal: require meaningful conversion volume,
    # attributed value and the user-selected ROAS threshold. This is not proof
    # of profitability because margin, refunds and incrementality are unknown.
    for _, row in summary.iterrows():
        if (row.spend >= minimum_spend and row.conversions >= minimum_conversions_for_scale
                and row.revenue > 0 and pd.notna(row.roas) and row.roas >= target_roas):
            add("Opportunity", "Potential scaling candidate", row,
                f"ROAS {row.roas:.2f}× meets/exceeds the selected {target_roas:.2f}× screening target, with {row.conversions:,.1f} reported conversions and {row.spend:,.2f} spend.",
                "This is a candidate for a controlled test, not an automatic budget recommendation. Before increasing spend, confirm contribution margin, conversion quality, tracking stability and capacity; then raise budget incrementally and monitor marginal CPA/ROAS.")

    # Compare first and second halves only when enough distinct dates exist.
    dated = data.copy()
    if "date" in dated.columns:
        dated["date"] = pd.to_datetime(dated["date"], errors="coerce")
        dated = dated.dropna(subset=["date"])
    else:
        dated = pd.DataFrame()
    if not dated.empty and dated["date"].nunique() >= 4:
        for (platform, campaign), group in dated.groupby(["platform", "campaign"]):
            daily = group.groupby("date", as_index=False).agg(spend=("spend", "sum"), conversions=("conversions", "sum"))
            if daily["date"].nunique() < 4:
                continue
            daily = daily.sort_values("date")
            split = len(daily) // 2
            first, second = daily.iloc[:split], daily.iloc[split:]
            first_conv, second_conv = float(first.conversions.sum()), float(second.conversions.sum())
            first_spend, second_spend = float(first.spend.sum()), float(second.spend.sum())
            if first_conv >= 2 and first_spend > 0:
                first_cpa = first_spend / first_conv
                second_cpa = second_spend / second_conv if second_conv > 0 else float("inf")
                if second_cpa > first_cpa * (1 + decline_threshold_pct / 100):
                    row = summary[(summary.platform == platform) & (summary.campaign == campaign)].iloc[0]
                    second_text = "no conversions" if second_conv <= 0 else f"{second_cpa:,.2f} CPA"
                    add("Medium", "Recent efficiency deterioration", row,
                        f"CPA moved from {first_cpa:,.2f} in the first half to {second_text} in the second half of available dates.",
                        "Check recent changes to budget, bids, targeting, creative and tracking. Compare like-for-like days before making major changes.")
    else:
        notes.append("A performance-decline check needs at least four distinct valid reporting dates. No trend conclusion has been made.")

    notes.append("ROAS and conversion figures are platform-reported. Profitability cannot be confirmed without margins, refunds, fees and conversion-quality data. Treat all findings as investigation signals, not guaranteed outcomes.")
    if not findings:
        notes.append("No rule-based alerts were triggered using the current screening thresholds. This does not guarantee that every campaign is performing well.")

    findings_df = pd.DataFrame(findings)
    if not findings_df.empty:
        priority_order = {"High": 0, "Medium": 1, "Opportunity": 2}
        findings_df["_order"] = findings_df["Priority"].map(priority_order)
        findings_df = findings_df.sort_values(["_order", "Spend"], ascending=[True, False]).drop(columns="_order").reset_index(drop=True)
    return summary, findings_df, notes
