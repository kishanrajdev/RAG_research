from utils.db import get_database
from utils.rate_limiter import RateLimiter
import uuid
import json

db = get_database()
reviews = db.get_container_client("reviews")

rate_limiter = RateLimiter(2000, 60)

inserted_count = 0

with open("data/All_Beauty.jsonl", "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, start=1):
        review = json.loads(line)

        doc = {
            "id": str(uuid.uuid4()),
            "asin": review.get("asin"),
            "parent_asin": review.get("parent_asin"),
            "text": review.get("text"),
            "title": review.get("title"),
            "rating": review.get("rating"),
            "timestamp": review.get("timestamp"),
            "user_id": review.get("user_id"),
            "verified_purchase": review.get("verified_purchase"),
            "helpful_vote": review.get("helpful_vote")
        }

        rate_limiter.wait()
        try:
            reviews.upsert_item(doc)
        except Exception as e:
            print(f"❌ Upsert failed for line {line_num}: {e}")
            continue

        inserted_count += 1
        if inserted_count % 10 == 0:
            print(f"✅ Inserted {inserted_count} products")

print("🎉 Finished ingesting products")