import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class ColumnMap:
    event_type: str
    user_id: str
    price: Optional[str] = None
    timestamp: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None


EVENT_ALIASES = {
    "view": ["view", "pageview", "product_view", "browse"],
    "cart": ["cart", "add_to_cart", "addtocart", "add", "basket"],
    "purchase": ["purchase", "buy", "order", "checkout", "paid", "transaction"],
}


def normalize_event(val: str) -> str:
    v = str(val).lower().strip()
    for canonical, aliases in EVENT_ALIASES.items():
        if v in aliases:
            return canonical
    return v


class GTMEngine:
    def __init__(self, df: pd.DataFrame, col_map: ColumnMap):
        self.col = col_map
        self.df = self._prepare(df.copy())
        self.funnel = self._build_funnel()

    def _prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        et = self.col.event_type
        df[et] = df[et].apply(normalize_event)

        if self.col.timestamp:
            df[self.col.timestamp] = pd.to_datetime(df[self.col.timestamp], errors="coerce")
            df["_hour"] = df[self.col.timestamp].dt.hour
            df["_day_of_week"] = df[self.col.timestamp].dt.dayofweek

        if self.col.price:
            df["_price_tier"] = pd.cut(
                df[self.col.price],
                bins=[0, 50, 200, 500, 99_999],
                labels=["Budget ($0–50)", "Mid ($50–200)", "Premium ($200–500)", "Luxury ($500+)"],
            )

        if self.col.category:
            df["_top_category"] = (
                df[self.col.category].astype(str).str.split(".").str[0].str.lower()
            )

        return df

    def _build_funnel(self) -> dict:
        et = self.col.event_type
        uid = self.col.user_id

        view_users = set(self.df[self.df[et] == "view"][uid])
        cart_users = set(self.df[self.df[et] == "cart"][uid]) & view_users
        purchase_users = set(self.df[self.df[et] == "purchase"][uid]) & cart_users

        v = len(view_users)
        c = len(cart_users)
        p = len(purchase_users)

        return {
            "views": v,
            "carts": c,
            "purchases": p,
            "view_to_cart": c / v if v else 0,
            "cart_to_purchase": p / c if c else 0,
            "end_to_end": p / v if v else 0,
            "cart_abandoned": c - p,
            "view_users": view_users,
            "cart_users": cart_users,
            "purchase_users": purchase_users,
        }

    # ── Price analysis ─────────────────────────────────────────────────────────

    def get_price_analysis(self) -> Optional[dict]:
        if not self.col.price:
            return None

        et, uid, price = self.col.event_type, self.col.user_id, self.col.price
        abandoned = self.funnel["cart_users"] - self.funnel["purchase_users"]

        abn_prices = self.df[
            (self.df[et] == "cart") & (self.df[uid].isin(abandoned))
        ][price].dropna()

        pur_prices = self.df[
            (self.df[et] == "purchase") & (self.df[uid].isin(self.funnel["purchase_users"]))
        ][price].dropna()

        return {
            "abandoned_median": abn_prices.median(),
            "purchased_median": pur_prices.median(),
            "abandoned_prices": abn_prices,
            "purchased_prices": pur_prices,
        }

    # ── Category analysis ──────────────────────────────────────────────────────

    def get_category_funnel(self) -> Optional[pd.DataFrame]:
        if not self.col.category or "_top_category" not in self.df.columns:
            return None

        et, uid = self.col.event_type, self.col.user_id
        df = self.df[self.df["_top_category"].notna()]

        views = df[df[et] == "view"].groupby("_top_category")[uid].nunique()
        purchases = df[df[et] == "purchase"].groupby("_top_category")[uid].nunique()

        result = pd.DataFrame({"views": views, "purchases": purchases}).fillna(0)
        result = result[result["views"] >= 100]
        result["conversion_rate"] = (result["purchases"] / result["views"] * 100).round(2)
        return result.sort_values("conversion_rate", ascending=False)

    # ── Hourly analysis ────────────────────────────────────────────────────────

    def get_hourly_analysis(self) -> Optional[pd.Series]:
        if not self.col.timestamp or "_hour" not in self.df.columns:
            return None

        et, uid = self.col.event_type, self.col.user_id
        hourly_views = self.df[self.df[et] == "view"].groupby("_hour")[uid].nunique()
        hourly_purchases = self.df[self.df[et] == "purchase"].groupby("_hour")[uid].nunique()
        return (hourly_purchases / hourly_views * 100).fillna(0).reindex(range(24), fill_value=0)

    # ── Day of week analysis ───────────────────────────────────────────────────

    def get_day_of_week_analysis(self) -> Optional[pd.Series]:
        if "_day_of_week" not in self.df.columns:
            return None

        day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        et, uid = self.col.event_type, self.col.user_id

        day_views = self.df[self.df[et] == "view"].groupby("_day_of_week")[uid].nunique()
        day_purchases = self.df[self.df[et] == "purchase"].groupby("_day_of_week")[uid].nunique()
        rate = (day_purchases / day_views * 100).fillna(0).reindex(range(7), fill_value=0)
        rate.index = day_labels
        return rate

    # ── Price tier funnel ──────────────────────────────────────────────────────

    def get_price_tier_funnel(self) -> Optional[pd.DataFrame]:
        if not self.col.price or "_price_tier" not in self.df.columns:
            return None

        et, uid = self.col.event_type, self.col.user_id
        rows = []

        for tier in self.df["_price_tier"].cat.categories:
            tdf = self.df[self.df["_price_tier"] == tier]
            tv = set(tdf[tdf[et] == "view"][uid])
            tc = set(tdf[tdf[et] == "cart"][uid]) & tv
            tp = set(tdf[tdf[et] == "purchase"][uid]) & tc
            rows.append({
                "tier": str(tier),
                "views": len(tv),
                "carts": len(tc),
                "purchases": len(tp),
                "view_to_cart": len(tc) / len(tv) * 100 if tv else 0,
                "cart_to_purchase": len(tp) / len(tc) * 100 if tc else 0,
            })

        return pd.DataFrame(rows).set_index("tier")

    # ── Brand funnel ───────────────────────────────────────────────────────────

    def get_brand_funnel(self) -> Optional[pd.DataFrame]:
        if not self.col.brand:
            return None

        et, uid, brand = self.col.event_type, self.col.user_id, self.col.brand
        df = self.df[self.df[brand].notna()]

        brand_views = df[df[et] == "view"].groupby(brand)[uid].nunique()
        brand_purchases = df[df[et] == "purchase"].groupby(brand)[uid].nunique()

        result = pd.DataFrame({"views": brand_views, "purchases": brand_purchases}).fillna(0)
        result = result[result["views"] >= 200]
        result["conversion_rate"] = (result["purchases"] / result["views"] * 100).round(2)
        return result.sort_values("conversion_rate", ascending=False)

    # ── RFM segments ───────────────────────────────────────────────────────────

    def get_rfm_segments(self) -> Optional[pd.DataFrame]:
        if not self.col.price or not self.col.timestamp:
            return None

        et, uid, price, ts = (
            self.col.event_type, self.col.user_id, self.col.price, self.col.timestamp
        )
        purchase_df = self.df[self.df[et] == "purchase"].copy()
        if purchase_df.empty:
            return None

        latest = self.df[ts].max()
        rfm = purchase_df.groupby(uid).agg(
            total_purchases=(ts, "count"),
            total_spend=(price, "sum"),
            last_purchase=(ts, "max"),
        ).reset_index()

        rfm["days_since"] = (latest - rfm["last_purchase"]).dt.days

        try:
            rfm["spend_tier"] = pd.qcut(
                rfm["total_spend"], q=3,
                labels=["Low Spender", "Mid Spender", "High Spender"],
                duplicates="drop",
            )
        except ValueError:
            rfm["spend_tier"] = "Mid Spender"

        return rfm

    # ── Auto recommendations ───────────────────────────────────────────────────

    def generate_recommendations(self) -> list:
        f = self.funnel
        v2c = f["view_to_cart"] * 100
        c2p = f["cart_to_purchase"] * 100
        recs = []

        # Product page engagement
        if v2c < 15:
            additional_carts = int(f["views"] * 0.02)
            additional_purchases = int(additional_carts * f["cart_to_purchase"])
            recs.append({
                "title": "Improve Product Page Engagement",
                "finding": f"View→Cart rate is {v2c:.1f}% (benchmark: 5–15%). 89% of viewers leave without engaging.",
                "so_what": f"A +2pp improvement drives ~{additional_carts:,} more carts → ~{additional_purchases:,} additional purchases.",
                "action": "A/B test: add customer reviews, better product images, and explicit CTAs on product pages.",
                "metric": "View→Cart rate; target: +2pp in 30 days",
                "impact": "High" if v2c < 8 else "Medium",
                "effort": "Medium",
            })

        # Checkout friction
        if c2p < 30:
            additional = int(f["carts"] * 0.05)
            recs.append({
                "title": "Reduce Checkout Friction",
                "finding": f"Cart→Purchase rate is {c2p:.1f}% (benchmark: 20–40%).",
                "so_what": f"A +5pp improvement recovers ~{additional:,} purchases from existing cart users.",
                "action": "Audit checkout: remove unnecessary form fields, add trust badges, offer guest checkout.",
                "metric": "Cart→Purchase rate; target: +5pp in 60 days",
                "impact": "High",
                "effort": "Low",
            })

        # Cart abandonment email
        abandoned = f["cart_abandoned"]
        if abandoned > 0:
            price_data = self.get_price_analysis()
            median_val = price_data["abandoned_median"] if price_data else 0
            recovery = int(abandoned * 0.07)
            revenue = int(recovery * median_val) if median_val else 0
            rev_str = f" (~${revenue:,} revenue)" if revenue else ""
            recs.append({
                "title": "Cart Abandonment Email Campaign",
                "finding": f"{abandoned:,} users added to cart but did not purchase.",
                "so_what": f"Even 7% recovery = {recovery:,} additional purchases{rev_str}.",
                "action": "3-email sequence: reminder (1hr) → social proof (24hr) → discount (72hr).",
                "metric": "Cart recovery rate; target: 5–8% in 60 days",
                "impact": "High",
                "effort": "Medium",
            })

        # Category budget reallocation
        cat_data = self.get_category_funnel()
        if cat_data is not None and len(cat_data) >= 2:
            top_cat = cat_data.index[0]
            top_rate = cat_data.iloc[0]["conversion_rate"]
            avg_rate = cat_data["conversion_rate"].mean()
            if top_rate > avg_rate * 1.3:
                recs.append({
                    "title": "Reallocate GTM Budget to High-Converting Categories",
                    "finding": f"'{top_cat}' converts at {top_rate:.1f}% vs category average of {avg_rate:.1f}%.",
                    "so_what": "Paid budget spent on low-converting categories has 3–5× worse ROI.",
                    "action": f"Shift 20–30% of paid acquisition budget toward '{top_cat}'. Test for 4 weeks.",
                    "metric": "ROMI by category; target: +15% in 30 days",
                    "impact": "High",
                    "effort": "Low",
                })

        return recs
