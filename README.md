# GTM Analysis — E-Commerce Behavior Case Study

A hands-on, step-by-step project to learn **Go-To-Market (GTM) Analysis** using real e-commerce event data.
By the end of this project, you will be able to build a full funnel analysis, identify drop-off points, segment users, and present data-backed GTM recommendations.

---

## What is GTM Analysis?

**Go-To-Market (GTM) Analysis** is the process of understanding *how users move through your product or store*, where they drop off, and what drives them to convert (buy, subscribe, sign up).

It answers:
- Are people discovering your product? → **Awareness**
- Are people engaging with it? → **Consideration**
- Are people buying it? → **Conversion**
- Are people coming back? → **Retention**

---

## Project Structure

```
GTM_Analysis/
├── data/                     ← Put your CSV files here
│   └── 2019-Oct.csv
├── notebooks/                ← All analysis notebooks live here
│   ├── 01_data_exploration.ipynb
│   ├── 02_funnel_analysis.ipynb
│   ├── 03_dropoff_analysis.ipynb
│   ├── 04_segmentation.ipynb
│   └── 05_recommendations.ipynb
├── outputs/                  ← Saved charts and exports
├── README.md                 ← This file
└── requirements.txt          ← Python dependencies
```

---

## Dataset

**Source:** [E-Commerce Behavior Data — Kaggle](https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store)

**Download steps:**
1. Go to the Kaggle link above
2. Click **Download** (requires free Kaggle account)
3. Unzip the file
4. Place `2019-Oct.csv` inside the `data/` folder

**Columns in the dataset:**

| Column         | What it means                                        |
|----------------|------------------------------------------------------|
| `event_time`   | Timestamp of the event                               |
| `event_type`   | What happened: `view`, `cart`, or `purchase`         |
| `product_id`   | Unique ID of the product                             |
| `category_id`  | Numeric category ID                                  |
| `category_code`| Human-readable category (e.g. `electronics.phone`)  |
| `brand`        | Product brand                                        |
| `price`        | Price in USD                                         |
| `user_id`      | Unique ID of the user                                |
| `user_session` | Session ID (groups events within one visit)          |

---

## The GTM Funnel We Will Build

```
[AWARENESS]       All users who viewed a product
        ↓
[CONSIDERATION]   Users who added a product to cart
        ↓
[CONVERSION]      Users who completed a purchase
```

Each stage has a **conversion rate**. GTM analysis is about finding where this rate is low and *why*.

---

## Step-by-Step Learning Roadmap

### Phase 1 — Setup & Data Exploration (Notebook 01)

**Goal:** Understand what the data looks like before doing any analysis.

**Steps:**
1. Install dependencies
2. Load the dataset (sample 500k rows)
3. Inspect shape, dtypes, nulls
4. Understand event distribution
5. Check date range

**Key questions to answer:**
- How many total events are there?
- What % are views vs cart vs purchase?
- Are there null values? In which columns?
- What time period does the data cover?

**Code you will write:**
```python
import pandas as pd

df = pd.read_csv("../data/2019-Oct.csv", nrows=500000)

# Shape
print(df.shape)

# Column types
df.info()

# First look
df.head()

# Event distribution
df['event_type'].value_counts()

# Null check
df.isnull().sum()
```

---

### Phase 2 — Funnel Analysis (Notebook 02)

**Goal:** Count unique users at each stage of the funnel and calculate conversion rates.

**Concept — Why unique users, not events?**
One user can view 50 products. That's 50 events but still 1 user in the funnel.
GTM cares about *how many people* progressed, not how many times they clicked.

**Steps:**
1. Count unique `user_id` at each funnel stage
2. Calculate stage-to-stage conversion rates
3. Visualize the funnel

**Code you will write:**
```python
views     = df[df['event_type'] == 'view']['user_id'].nunique()
carts     = df[df['event_type'] == 'cart']['user_id'].nunique()
purchases = df[df['event_type'] == 'purchase']['user_id'].nunique()

print(f"Views:     {views:,}")
print(f"Carts:     {carts:,}")
print(f"Purchases: {purchases:,}")

view_to_cart     = carts / views
cart_to_purchase = purchases / carts

print(f"\nView → Cart conversion:     {view_to_cart:.1%}")
print(f"Cart → Purchase conversion: {cart_to_purchase:.1%}")
```

**Benchmark (industry averages):**
| Stage              | Typical Rate |
|--------------------|--------------|
| View → Cart        | 5% – 15%     |
| Cart → Purchase    | 20% – 40%    |

If your numbers are below these → that is your GTM problem to investigate.

---

### Phase 3 — Drop-off Analysis (Notebook 03)

**Goal:** Understand *who* is dropping off and *where*.

**Concept — The leaky bucket:**
Imagine your funnel is a bucket with holes. Users leak out at each stage.
Drop-off analysis finds the biggest holes.

**Steps:**
1. Find users who viewed but never carted
2. Find users who carted but never purchased
3. Analyze price distribution of abandoned carts
4. Analyze which categories have the highest drop-off

**Code you will write:**
```python
view_users     = set(df[df['event_type'] == 'view']['user_id'])
cart_users     = set(df[df['event_type'] == 'cart']['user_id'])
purchase_users = set(df[df['event_type'] == 'purchase']['user_id'])

# Users who viewed but never added to cart
view_only = view_users - cart_users
print(f"View-only users (no cart): {len(view_only):,}")

# Users who carted but never purchased
cart_abandoned = cart_users - purchase_users
print(f"Cart abandoned users: {len(cart_abandoned):,}")

# Price analysis of abandoned carts
abandoned_cart_df = df[
    (df['event_type'] == 'cart') &
    (df['user_id'].isin(cart_abandoned))
]
print(abandoned_cart_df['price'].describe())
```

**GTM interpretation:**
- High view-only → product discovery is working, but product pages aren't compelling
- High cart abandonment + high price → pricing/payment friction
- High cart abandonment in specific category → category-specific issue

---

### Phase 4 — Segmentation (Notebook 04)

**Goal:** Segment users by behavior to find your best and worst customer groups.

**Concept — Segmentation in GTM:**
Not all users are equal. GTM teams segment users to:
- Focus marketing spend on high-value segments
- Fix the experience for low-converting segments

**Segments we will build:**
1. **By category** — which product categories have the best conversion?
2. **By price tier** — do high-price products convert differently?
3. **By brand** — which brands drive the most purchases?
4. **By hour of day** — when are users most likely to buy?

**Code you will write:**
```python
# Conversion by category
category_funnel = df.groupby(['category_code', 'event_type'])['user_id'].nunique().unstack(fill_value=0)
category_funnel['conversion_rate'] = category_funnel['purchase'] / category_funnel['view']
category_funnel.sort_values('conversion_rate', ascending=False).head(10)

# Price tier segmentation
df['price_tier'] = pd.cut(df['price'], bins=[0, 50, 200, 500, 99999],
                          labels=['Budget', 'Mid', 'Premium', 'Luxury'])
price_funnel = df.groupby(['price_tier', 'event_type'])['user_id'].nunique().unstack(fill_value=0)
price_funnel['conversion_rate'] = price_funnel['purchase'] / price_funnel['view']
```

---

### Phase 5 — GTM Recommendations (Notebook 05)

**Goal:** Translate your analysis into business recommendations.

**Concept — The analyst's job:**
Numbers are worthless without decisions attached to them. This is where GTM analysis becomes strategy.

**Framework — What to write for each finding:**

```
FINDING:    [What the data shows]
SO WHAT:    [Why this matters to the business]
ACTION:     [What should be done]
METRIC:     [How to measure if the fix worked]
```

**Example:**
```
FINDING:    Cart → Purchase conversion is 12% vs industry avg of 30%
SO WHAT:    We are losing 18 out of every 100 cart users — that's direct revenue loss
ACTION:     A/B test: add trust badges + show free shipping threshold at checkout
METRIC:     Track cart_to_purchase rate weekly; target 20% in 60 days
```

---

## Setup Instructions

### 1. Install Python dependencies

```bash
pip install pandas matplotlib seaborn jupyter plotly
```

Or install from the requirements file:

```bash
pip install -r requirements.txt
```

### 2. Launch Jupyter

```bash
jupyter notebook
```

Then open `notebooks/01_data_exploration.ipynb`

---

## Key Concepts Glossary

| Term | Definition |
|------|-----------|
| **Funnel** | A sequence of steps users take toward a goal (view → cart → purchase) |
| **Conversion Rate** | % of users who move from one stage to the next |
| **Drop-off** | Users who leave the funnel at a specific stage |
| **Segmentation** | Splitting users into groups to find patterns |
| **Session** | A single visit by a user (a user can have multiple sessions) |
| **CAC** | Customer Acquisition Cost — what it costs to get one paying customer |
| **LTV** | Lifetime Value — how much revenue one customer generates over time |
| **AOV** | Average Order Value — mean purchase price |
| **Churn** | Users who stop engaging or buying |
| **Cohort** | A group of users who started in the same time period |

---

## What Good GTM Analysis Looks Like

After finishing this project you should be able to answer:
1. What % of users convert from awareness to purchase?
2. Where is the biggest drop in the funnel?
3. Which product category has the highest conversion rate?
4. What price range do most purchases fall into?
5. What concrete action would you recommend to improve conversion by 5%?

If you can answer all 5 with data — you have done GTM analysis.

---

## Progress Tracker

- [ ] Phase 1 — Data Exploration
- [ ] Phase 2 — Funnel Analysis
- [ ] Phase 3 — Drop-off Analysis
- [ ] Phase 4 — Segmentation
- [ ] Phase 5 — GTM Recommendations
