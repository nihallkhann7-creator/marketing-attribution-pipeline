# Attribution report: Brewline (synthetic data)

Period **2026-07-01 to 2026-08-29** (IST) · lookback window **30 days** · time-decay half-life **7 days**

## Headline

| Spend | Orders | New customers | Revenue | Blended CAC | Blended ROAS |
|---|---:|---:|---:|---:|---:|
| ₹18.97 L | 6,693 | 6,313 | ₹64.56 L | ₹300 | 3.40x |

## What the models disagree on

- **Meta Prospecting** gains the most when moving from last-touch to Markov (159 → 590 new customers, +271%). Last-click undervalues channels that open journeys.
- **Google Search Brand** loses the most (1592 → 1056, -34%): it often closes journeys that other channels started.
- CAC for **Meta Prospecting** ranges from ₹524 to ₹1,947 depending on the model. Budget decisions on this channel are the most model-sensitive.

![Model comparison](model_comparison.png)

## New customers by channel and model

| channel | First touch | Last touch | Last non-direct | Linear | Time decay | Position based | Markov |
|---|---:|---:|---:|---:|---:|---:|---:|
| Google Search Brand | 509 | 1592 | 1734 | 1074 | 1159 | 1059 | 1056 |
| Direct | 537 | 1060 | 225 | 869 | 906 | 828 | 883 |
| Meta Retargeting | 151 | 1053 | 1163 | 689 | 757 | 641 | 785 |
| Email | 222 | 665 | 738 | 500 | 527 | 466 | 585 |
| Organic Search | 846 | 443 | 559 | 643 | 612 | 644 | 643 |
| Google PMax | 649 | 416 | 507 | 534 | 517 | 534 | 517 |
| Google Search Generic | 1023 | 396 | 503 | 659 | 613 | 688 | 593 |
| Apple Search Ads | 332 | 227 | 262 | 275 | 267 | 278 | 279 |
| Affiliate | 454 | 222 | 249 | 305 | 288 | 324 | 231 |
| Meta Prospecting | 1296 | 159 | 276 | 606 | 521 | 676 | 590 |
| Referral | 278 | 62 | 78 | 141 | 127 | 157 | 130 |
| Unmapped | 16 | 18 | 19 | 18 | 18 | 18 | 20 |

## CAC by paid channel and model

| channel | First touch | Last touch | Last non-direct | Linear | Time decay | Position based | Markov |
|---|---:|---:|---:|---:|---:|---:|---:|
| Affiliate | ₹157 | ₹320 | ₹286 | ₹233 | ₹247 | ₹219 | ₹308 |
| Apple Search Ads | ₹530 | ₹775 | ₹671 | ₹640 | ₹658 | ₹632 | ₹629 |
| Google PMax | ₹433 | ₹675 | ₹554 | ₹525 | ₹543 | ₹526 | ₹543 |
| Google Search Brand | ₹493 | ₹158 | ₹145 | ₹234 | ₹217 | ₹237 | ₹238 |
| Google Search Generic | ₹559 | ₹1,443 | ₹1,136 | ₹867 | ₹932 | ₹830 | ₹963 |
| Meta Prospecting | ₹239 | ₹1,947 | ₹1,122 | ₹511 | ₹594 | ₹458 | ₹524 |
| Meta Retargeting | ₹1,570 | ₹225 | ₹204 | ₹344 | ₹313 | ₹370 | ₹302 |

## ROAS by paid channel and model

| channel | First touch | Last touch | Last non-direct | Linear | Time decay | Position based | Markov |
|---|---:|---:|---:|---:|---:|---:|---:|
| Affiliate | 5.98x | 2.85x | 3.18x | 3.97x | 3.74x | 4.23x | 3.23x |
| Apple Search Ads | 1.81x | 1.21x | 1.41x | 1.48x | 1.44x | 1.50x | 1.59x |
| Google PMax | 2.18x | 1.39x | 1.71x | 1.81x | 1.75x | 1.79x | 1.84x |
| Google Search Brand | 2.24x | 6.40x | 6.96x | 4.42x | 4.74x | 4.36x | 4.28x |
| Google Search Generic | 1.74x | 0.66x | 0.86x | 1.11x | 1.03x | 1.16x | 1.04x |
| Meta Prospecting | 4.01x | 0.49x | 0.87x | 1.87x | 1.60x | 2.09x | 1.93x |
| Meta Retargeting | 0.88x | 4.56x | 5.07x | 3.08x | 3.35x | 2.88x | 3.37x |

## Data-quality checks

| check | status | detail |
|---|---|---|
| raw_sessions: one row per key | PASS | 115,914 rows read, 0 duplicate keys, 115,914 rows stored |
| raw_orders: one row per key | PASS | 6,693 rows read, 0 duplicate keys, 6,693 rows stored |
| raw_ad_spend: one row per key | PASS | 927 rows read, 27 duplicate keys, 900 rows stored |
| Every order has a conversion path | PASS | 6,693 orders, 6,693 paths |
| Spend reconciles raw → mart | PASS | raw ₹1,896,769.58, mart ₹1,896,769.58 |
| No unmapped sessions | WARN | 300 sessions unmapped (e.g. test_campaign_do_not_use) |
| No unmapped spend | PASS | ₹0.00 unmapped |
| Credits sum to 1 per conversion | PASS | 6 models checked |
| All models reconcile to total orders & revenue | PASS | 7 models vs 6,693 orders / ₹6,455,579 |
| Session dates converted to IST | PASS | first IST date 2026-07-01 |
