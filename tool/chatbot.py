import re
from gtm_engine import GTMEngine

PRESET_QUESTIONS = [
    "What is my funnel conversion rate?",
    "How many users abandoned their cart?",
    "Which category converts best?",
    "What is the peak purchase hour?",
    "What should I fix first?",
    "What is the average purchase price?",
    "How many total users are there?",
    "Which price tier converts worst?",
    "Which brand performs best?",
    "Give me a full summary.",
]

PATTERNS = [
    (r"funnel|conversion rate|how many convert|view.?to.?cart|cart.?to.?purchase|stages", "funnel"),
    (r"abandon|who left|drop.?off|cart.*not.*buy|didn.t.*buy|didn.t purchase", "abandonment"),
    (r"best category|top category|category.*convert|which category|category perform", "best_category"),
    (r"peak hour|best time|when.*buy|what time|email.*time|schedule.*email|retarget", "peak_hour"),
    (r"recommend|what should|improve|fix|action|priority|where.*focus|next step", "recommendations"),
    (r"price|average.*spend|median.*price|how much|cost|expensive|cheap", "price"),
    (r"total user|how many user|user count|visitors|how many people|audience size", "user_count"),
    (r"price tier|budget|luxury|premium|mid.tier|segment.*price|tier", "price_tier"),
    (r"brand|top brand|best brand|which brand|brand perform", "brands"),
    (r"day|week|weekday|weekend|best day|worst day", "day_of_week"),
    (r"summary|overview|tell me|what.*data|how.*store|general|start|begin", "summary"),
]


class GTMChatbot:
    def __init__(self, engine: GTMEngine):
        self.engine = engine

    def answer(self, question: str) -> dict:
        q = question.lower().strip()

        for pattern, handler_key in PATTERNS:
            if re.search(pattern, q):
                return getattr(self, f"_handle_{handler_key}")()

        return {
            "text": (
                "I didn't catch that. Try one of the preset questions, or ask about: "
                "**conversion rates**, **cart abandonment**, **categories**, "
                "**peak hours**, **prices**, or **recommendations**."
            ),
            "chart": None,
        }

    # ── Handlers ───────────────────────────────────────────────────────────────

    def _handle_funnel(self) -> dict:
        f = self.engine.funnel
        v2c = f["view_to_cart"] * 100
        c2p = f["cart_to_purchase"] * 100
        e2e = f["end_to_end"] * 100

        v2c_status = (
            "⚠️ Below benchmark (5–15%)" if v2c < 5
            else "✅ Above benchmark" if v2c > 15
            else "→ Within normal range"
        )
        c2p_status = (
            "⚠️ Below benchmark (20–40%)" if c2p < 20
            else "✅ Above benchmark" if c2p > 40
            else "→ Within normal range"
        )

        text = (
            f"**Funnel Conversion Rates**\n\n"
            f"| Stage | Your Rate | Benchmark | Status |\n"
            f"|---|---|---|---|\n"
            f"| View → Cart | {v2c:.1f}% | 5–15% | {v2c_status} |\n"
            f"| Cart → Purchase | {c2p:.1f}% | 20–40% | {c2p_status} |\n"
            f"| View → Purchase | {e2e:.1f}% | — | end-to-end |\n\n"
        )

        if v2c < c2p:
            text += (
                f"💡 **Key insight:** Your biggest drop is at the top of the funnel. "
                f"Fixing View→Cart (+1pp) will have more impact than fixing Cart→Purchase (+1pp) "
                f"because you have {f['views']:,} viewers vs {f['carts']:,} cart users."
            )

        return {"text": text, "chart": "funnel"}

    def _handle_abandonment(self) -> dict:
        f = self.engine.funnel
        abandoned = f["cart_abandoned"]
        price_data = self.engine.get_price_analysis()

        text = f"**Cart Abandonment Analysis**\n\n- **{abandoned:,} users** added to cart but did not purchase.\n"

        if price_data:
            abn = price_data["abandoned_median"]
            pur = price_data["purchased_median"]
            text += f"- Median abandoned cart price: **${abn:.2f}**\n"
            text += f"- Median completed purchase price: **${pur:.2f}**\n\n"

            if abn > pur * 1.1:
                text += (
                    "💡 Abandoned carts are priced **higher** than completed purchases. "
                    "Price sensitivity is a likely factor. Consider showing installment options or "
                    "a free shipping threshold at checkout."
                )
            elif abn < pur * 0.9:
                text += (
                    "💡 Abandoned carts are priced **lower** than completed purchases. "
                    "Price is NOT the main issue — low purchase intent at the time of carting is. "
                    "Fix product pages to attract more intentional buyers, not discounts."
                )
            else:
                text += (
                    "💡 Price difference is minimal. Abandonment is likely due to "
                    "UX friction or low intent. Audit your checkout flow."
                )

        recovery_5 = int(abandoned * 0.05)
        recovery_10 = int(abandoned * 0.10)
        text += f"\n\n**Recovery opportunity:** A 5–10% email recovery rate = **{recovery_5}–{recovery_10} additional purchases**."

        return {"text": text, "chart": "price_comparison"}

    def _handle_best_category(self) -> dict:
        cat_data = self.engine.get_category_funnel()
        if cat_data is None or len(cat_data) == 0:
            return {
                "text": "Category data is unavailable. Make sure you mapped the **category** column.",
                "chart": None,
            }

        top5 = cat_data.head(5)
        bot3 = cat_data.tail(3)
        avg = cat_data["conversion_rate"].mean()

        text = f"**Category Conversion Rates** (avg: {avg:.1f}%)\n\n**Top categories:**\n"
        for cat, row in top5.iterrows():
            bar = "🟩" * min(int(row["conversion_rate"] / 2), 10)
            text += f"- **{cat}**: {row['conversion_rate']:.1f}% {bar}\n"

        text += "\n**Lowest categories:**\n"
        for cat, row in bot3.iterrows():
            text += f"- {cat}: {row['conversion_rate']:.1f}%\n"

        best = cat_data.index[0]
        best_rate = cat_data.iloc[0]["conversion_rate"]
        text += (
            f"\n💡 Focus paid acquisition on **{best}** ({best_rate:.1f}% conversion). "
            f"It converts {best_rate / avg:.1f}× the average — every ad dollar goes further here."
        )

        return {"text": text, "chart": "category"}

    def _handle_peak_hour(self) -> dict:
        hourly = self.engine.get_hourly_analysis()
        if hourly is None:
            return {
                "text": "Hourly analysis requires a **timestamp** column. Make sure it's mapped.",
                "chart": None,
            }

        peak = int(hourly.idxmax())
        peak_rate = hourly.max()
        low = int(hourly.idxmin())
        low_rate = hourly.min()

        text = (
            f"**Peak Purchase Hours**\n\n"
            f"- 🔝 Highest conversion: **{peak}:00 UTC** ({peak_rate:.1f}%)\n"
            f"- 🔻 Lowest conversion: **{low}:00 UTC** ({low_rate:.1f}%)\n\n"
            f"💡 **Schedule** cart abandonment emails and retargeting ads to land around **{peak}:00 UTC**. "
            f"Users who receive messages at peak intent times are more likely to complete the purchase."
        )

        return {"text": text, "chart": "hourly"}

    def _handle_recommendations(self) -> dict:
        recs = self.engine.generate_recommendations()
        if not recs:
            return {
                "text": "No issues detected — your funnel metrics are within or above benchmarks. "
                        "Focus on driving more top-of-funnel traffic.",
                "chart": None,
            }

        impact_order = {"High": 0, "Medium": 1, "Low": 2}
        recs = sorted(recs, key=lambda r: (impact_order.get(r["impact"], 9), r["effort"] == "High"))

        text = "**Top Recommendations (priority order)**\n\n"
        for i, rec in enumerate(recs, 1):
            impact_icon = "🔴" if rec["impact"] == "High" else "🟡" if rec["impact"] == "Medium" else "🟢"
            text += f"**{i}. {rec['title']}** {impact_icon} Impact: {rec['impact']} | Effort: {rec['effort']}\n"
            text += f"> {rec['finding']}\n"
            text += f"- **Action:** {rec['action']}\n"
            text += f"- **Metric:** {rec['metric']}\n\n"

        return {"text": text, "chart": None}

    def _handle_price(self) -> dict:
        price_data = self.engine.get_price_analysis()
        if price_data is None:
            return {
                "text": "Price data is unavailable. Make sure you mapped the **price** column.",
                "chart": None,
            }

        pur = price_data["purchased_prices"]
        median = pur.median()
        store_type = (
            "budget/impulse-buy" if median < 50
            else "mid-range" if median < 200
            else "premium"
        )

        text = (
            f"**Purchase Price Analysis**\n\n"
            f"| Stat | Value |\n"
            f"|---|---|\n"
            f"| Median | **${median:.2f}** |\n"
            f"| Mean | ${pur.mean():.2f} |\n"
            f"| Min | ${pur.min():.2f} |\n"
            f"| Max | ${pur.max():.2f} |\n"
            f"| 25th pct | ${pur.quantile(0.25):.2f} |\n"
            f"| 75th pct | ${pur.quantile(0.75):.2f} |\n\n"
            f"💡 Median purchase is **${median:.0f}** — this is a **{store_type}** store. "
            f"Cart abandonment emails should emphasize {'convenience' if median < 50 else 'value and trust' if median < 200 else 'exclusivity and quality'}."
        )

        return {"text": text, "chart": "price_dist"}

    def _handle_user_count(self) -> dict:
        f = self.engine.funnel
        text = (
            f"**User Count Breakdown**\n\n"
            f"| Stage | Unique Users |\n"
            f"|---|---|\n"
            f"| Viewed a product | **{f['views']:,}** |\n"
            f"| Added to cart | **{f['carts']:,}** |\n"
            f"| Completed purchase | **{f['purchases']:,}** |\n"
            f"| Abandoned cart | **{f['cart_abandoned']:,}** |\n\n"
            f"**{f['end_to_end']*100:.1f}%** of all visitors eventually purchased."
        )
        return {"text": text, "chart": "funnel"}

    def _handle_price_tier(self) -> dict:
        tier_data = self.engine.get_price_tier_funnel()
        if tier_data is None:
            return {
                "text": "Price tier analysis requires a **price** column. Make sure it's mapped.",
                "chart": None,
            }

        text = "**Conversion by Price Tier**\n\n| Tier | View→Cart | Cart→Purchase |\n|---|---|---|\n"
        for tier, row in tier_data.iterrows():
            v2c = row.get("view_to_cart", 0)
            c2p = row.get("cart_to_purchase", 0)
            c2p_str = f"{c2p:.1f}%" if c2p <= 100 else "⚠️ data issue"
            text += f"| {tier} | {v2c:.1f}% | {c2p_str} |\n"

        valid = tier_data[tier_data["cart_to_purchase"] <= 100]
        if len(valid) > 0:
            worst = valid["cart_to_purchase"].idxmin()
            text += f"\n💡 **{worst}** has the lowest cart-to-purchase rate. Checkout improvements here will have the most impact."

        return {"text": text, "chart": "price_tier"}

    def _handle_brands(self) -> dict:
        brand_data = self.engine.get_brand_funnel()
        if brand_data is None:
            return {
                "text": "Brand data is unavailable. Make sure you mapped the **brand** column.",
                "chart": None,
            }

        top5 = brand_data.head(5)
        text = "**Top 5 Brands by Conversion Rate**\n\n| Brand | Conversion Rate | Viewers |\n|---|---|---|\n"
        for brand, row in top5.iterrows():
            text += f"| {brand} | **{row['conversion_rate']:.1f}%** | {int(row['views']):,} |\n"

        best = brand_data.index[0]
        text += f"\n💡 Feature **{best}** prominently in ads and homepage — it has the highest purchase intent among browsers."

        return {"text": text, "chart": "brand"}

    def _handle_day_of_week(self) -> dict:
        day_data = self.engine.get_day_of_week_analysis()
        if day_data is None:
            return {
                "text": "Day-of-week analysis requires a **timestamp** column.",
                "chart": None,
            }

        best_day = day_data.idxmax()
        worst_day = day_data.idxmin()

        text = (
            f"**Conversion Rate by Day of Week**\n\n"
            f"- 🔝 Best day: **{best_day}** ({day_data.max():.1f}%)\n"
            f"- 🔻 Worst day: **{worst_day}** ({day_data.min():.1f}%)\n\n"
            f"💡 Schedule promotions and emails to land on **{best_day}** for maximum conversion."
        )

        return {"text": text, "chart": "day_of_week"}

    def _handle_summary(self) -> dict:
        f = self.engine.funnel
        v2c = f["view_to_cart"] * 100
        c2p = f["cart_to_purchase"] * 100

        issues = []
        if v2c < 5:
            issues.append(f"View→Cart is {v2c:.1f}% — well below benchmark. Product pages need work.")
        elif v2c < 15:
            issues.append(f"View→Cart is {v2c:.1f}% — within range but has room to grow.")
        if c2p < 20:
            issues.append(f"Cart→Purchase is {c2p:.1f}% — below benchmark. Checkout friction likely.")
        if f["cart_abandoned"] > f["purchases"]:
            issues.append(f"{f['cart_abandoned']:,} cart abandoners — email campaign opportunity.")

        text = (
            f"**Store Overview**\n\n"
            f"- {f['views']:,} visitors → {f['carts']:,} carted → {f['purchases']:,} purchased\n"
            f"- End-to-end conversion: **{f['end_to_end']*100:.1f}%**\n\n"
        )

        if issues:
            text += "**What needs attention:**\n"
            for issue in issues:
                text += f"- ⚠️ {issue}\n"
        else:
            text += "✅ Funnel metrics are within or above industry benchmarks.\n"

        text += "\nAsk me about: categories, pricing, peak hours, brands, segmentation, or recommendations."

        return {"text": text, "chart": "funnel"}
