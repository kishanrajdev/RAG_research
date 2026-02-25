import json
from collections import defaultdict
import heapq

INPUT_FILE = "data/Beauty_and_Personal_Care.jsonl"
TOP_K = 50

review_counts = defaultdict(int)

# Count reviews per ASIN
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    for line in f:
        try:
            review = json.loads(line)
            asin = review.get("asin")

            if asin:
                review_counts[asin] += 1

        except json.JSONDecodeError:
            continue

# Get top 50 using heap (efficient)
top_50 = heapq.nlargest(TOP_K, review_counts.items(), key=lambda x: x[1])

# Print results
list_of_asins = [asin for asin, count in top_50]
print("Top 50 ASINs by number of reviews:")
print(list_of_asins)
for rank, (asin, count) in enumerate(top_50, 1):
    print(f"{rank}. {asin} — {count} reviews")