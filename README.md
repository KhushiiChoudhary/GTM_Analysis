# GTM Analysis — E-Commerce Behavior Case Study

End-to-end Go-To-Market analysis on real e-commerce event data.
Covers funnel building, drop-off analysis, user segmentation, and data-backed recommendations.

---

## What is GTM Analysis?

GTM (Go-To-Market) analysis is the process of understanding how users move through your product — where they drop off and what drives them to convert.

The core funnel for e-commerce:

```
View  →  Add to Cart  →  Purchase
```

Each arrow is a conversion rate. GTM analysis finds where those rates are low and why.

---

## Dataset

**Source:** [E-Commerce Behavior Data — Kaggle](https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store)

- Download `2019-Oct.csv` and place it in `data/`
- ~42M rows, ~9GB — do not commit to git

| Column          | Meaning                                         |
|-----------------|-------------------------------------------------|
| `event_time`    | Timestamp                                       |
| `event_type`    | `view`, `cart`, or `purchase`                   |
| `product_id`    | Product identifier                              |
| `category_code` | Human-readable category (e.g. `electronics`)   |
| `brand`         | Brand name                                      |
| `price`         | Price in USD                                    |
| `user_id`       | Unique user identifier                          |
| `user_session`  | Session ID                                      |

---

## Project Structure

```
GTM_Analysis/
├── data/                     ← CSV files (gitignored — download from Kaggle)
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_funnel_analysis.ipynb
│   ├── 03_dropoff_analysis.ipynb
│   ├── 04_segmentation.ipynb
│   └── 05_recommendations.ipynb
├── outputs/                  ← Generated charts (gitignored)
├── requirements.txt
└── README.md
```

---

## Setup

```bash
pip install -r requirements.txt
jupyter notebook
```

Open `notebooks/01_data_exploration.ipynb` and follow the phases in order.

---

## The 5 Phases

### Phase 1 — Data Exploration
**Goal:** Understand the data before touching the analysis.

- Load a user-level sample (not `nrows` — that biases toward one time window)
- Check shape, dtypes, nulls
- Understand event distribution and price range

**Critical:** `category_code` has many nulls. This does not affect funnel counts (which use `user_id` + `event_type`) but does affect category-level segmentation.

```python
df_full = pd.read_csv("../data/2019-Oct.csv")
sampled_users = pd.Series(df_full["user_id"].unique()).sample(n=50_000, random_state=42)
df = df_full[df_full["user_id"].isin(sampled_users)].copy()
```

---

### Phase 2 — Funnel Analysis
**Goal:** Count unique users at each stage. Calculate stage-to-stage conversion rates.

**Rules:**
- Count unique users, not events — one user can view 50 products but is still 1 person in the funnel
- Use a sequential funnel — a user only counts at stage N if they completed stage N-1
- Any conversion rate above 100% means broken sampling or cross-period attribution

```python
view_users     = set(df[df["event_type"] == "view"]["user_id"])
cart_users     = set(df[df["event_type"] == "cart"]["user_id"]) & view_users
purchase_users = set(df[df["event_type"] == "purchase"]["user_id"]) & cart_users
```

**Industry benchmarks:**

| Stage            | Typical Rate |
|------------------|--------------|
| View → Cart      | 5% – 15%     |
| Cart → Purchase  | 20% – 40%    |

**Funnel leverage rule:** A 1% improvement at the top of the funnel beats a 5% improvement at the bottom — because the top has 10x more users. Fix the stage with the most volume first.

---

### Phase 3 — Drop-off Analysis
**Goal:** Find who is dropping off, at what stage, and form a testable hypothesis for why.

- Compare prices of abandoned carts vs completed purchases
- Break conversion down by category
- Check conversion rate by hour of day

**Framework — always use this structure:**

```
FINDING  → What the data shows (be specific with numbers)
SO WHAT  → Why it matters to the business
ACTION   → What specifically changes
METRIC   → How you measure if the fix worked
```

**Counterintuitive finding from this dataset:**
Abandoned carts had a *lower* median price than completed purchases. This means price is not the primary cause of abandonment — purchase intent at the time of carting is. The fix is not discounts; it is better engagement signals on product pages (reviews, social proof, urgency).

---

### Phase 4 — Segmentation
**Goal:** Break down users into groups to find who converts best and focus GTM effort.

**Segments built:**
- Price tier (Budget / Mid / Premium / Luxury)
- Top category by conversion rate
- Brand performance
- Day of week and hour of day

**RFM framework:**

| Letter | Stands For | Definition                        |
|--------|------------|-----------------------------------|
| R      | Recency    | When did the user last purchase?  |
| F      | Frequency  | How many times did they purchase? |
| M      | Monetary   | How much did they spend?          |

**The moveable middle:** Re-engagement campaigns have the highest ROI on mid-tier spenders — not your best customers (already engaged) and not your lowest (low ceiling). The mid tier has demonstrated real intent and still has upside.

---

### Phase 5 — Recommendations
**Goal:** Turn findings into prioritized, data-backed business decisions.

Every recommendation must answer 4 things:

```
FINDING : [specific number from your data]
SO WHAT : [business impact in plain English]
ACTION  : [exactly what changes]
METRIC  : [measurable target + timeframe]
```

Prioritize by: **Impact × Confidence ÷ Effort**

Never recommend fixing something your data shows is working.

---

## Key Concepts

| Term                  | Definition                                                                 |
|-----------------------|----------------------------------------------------------------------------|
| **Funnel**            | Sequence of steps toward a goal (view → cart → purchase)                   |
| **Conversion Rate**   | % of users who move from one stage to the next                             |
| **Drop-off**          | Users who leave the funnel at a specific stage                             |
| **Sequential Funnel** | Each stage requires completion of the previous stage                       |
| **Segmentation**      | Splitting users into groups to find behavioral patterns                    |
| **RFM**               | Recency / Frequency / Monetary — standard customer segmentation framework  |
| **Moveable Middle**   | The segment with the most untapped potential — highest re-engagement ROI   |
| **Funnel Leverage**   | Improvements at higher funnel stages compound through higher user volumes  |
| **Cross-period Attribution** | A user's events span multiple files — single-month analysis can overcount purchasers |
| **AOV**               | Average Order Value                                                        |
| **CAC**               | Customer Acquisition Cost                                                  |
| **LTV**               | Lifetime Value                                                             |
| **ROMI**              | Return on Marketing Investment                                             |

---

## Common Mistakes to Avoid

| Mistake | Why it's wrong | Fix |
|--------|----------------|-----|
| Sampling with `nrows=N` | Biases toward one time window if data is sorted chronologically | Sample by user ID |
| Counting events instead of users | Inflates numbers — one user can have 50 view events | Use `.nunique()` on `user_id` |
| Not enforcing sequential funnel | Purchasers can exceed carters due to cross-period data | Use set intersection (`&`) between stages |
| Conversion rate > 100% | Mathematically impossible — stop and investigate | Fix sampling or funnel logic |
| Recommending fixes for working stages | Wastes effort | Check benchmark before recommending |
| Using averages without segmentation | Hides which sub-groups are actually the problem | Always break down by segment |

---

## What Good GTM Analysis Looks Like

By the end of this project you should be able to answer:

1. What is the end-to-end conversion rate for this store?
2. At which funnel stage is the biggest drop-off?
3. Which product category has the highest conversion rate?
4. Which user segment has the most untapped revenue potential?
5. Write one complete recommendation with a number, a business reason, a specific action, and a measurable target.

If you can answer all 5 from your data — you have done GTM analysis.
