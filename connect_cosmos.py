# python
import uuid
import time
import os
import json
from azure.cosmos import CosmosClient
from dotenv import load_dotenv
from openai import OpenAI

# load env vars
load_dotenv()

COSMOS_URI = os.environ["COSMOS_URI"]
COSMOS_KEY = os.environ["COSMOS_KEY"]
DB_NAME = os.environ["COSMOS_DB"]
PRODUCTS_CONTAINER = os.environ.get("COSMOS_PRODUCTS_CONTAINER")
JSONL_PATH = "data/meta_All_Beauty.jsonl"
EMBEDDING_MODEL = "text-embedding-3-large"
# MAX_INITIAL_INSERTS = 10  # limit to insert initially first N records

# connect
client = CosmosClient(COSMOS_URI, credential=COSMOS_KEY)
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# test connection
databases = list(client.list_databases())
print("✅ Connected to Cosmos DB")
print("Databases:", databases)

db = client.get_database_client(DB_NAME)
print(f"✅ Using database: {DB_NAME}")

products = db.get_container_client(PRODUCTS_CONTAINER)

class RateLimiter:
    """Simple token-bucket limiter: max_calls per period (seconds)."""
    def __init__(self, max_calls: int, period: float):
        self.max_calls = float(max_calls)
        self.period = float(period)
        self.allowance = float(max_calls)
        self.last_check = time.monotonic()

    def wait(self) -> None:
        while True:
            now = time.monotonic()
            elapsed = now - self.last_check
            self.last_check = now

            # refill tokens
            self.allowance += elapsed * (self.max_calls / self.period)
            if self.allowance > self.max_calls:
                self.allowance = self.max_calls

            # if we have a token, consume one and proceed
            if self.allowance >= 1.0:
                self.allowance -= 1.0
                return

            # otherwise sleep until a token should be available
            sleep_time = (1.0 - self.allowance) * (self.period / self.max_calls)
            time.sleep(sleep_time)

def build_product_embedding_text(product: dict) -> str:
    parts = []

    if product.get("title"):
        parts.append(product["title"])

    if product.get("main_category"):
        parts.append(f"Category: {product['main_category']}")

    if product.get("categories"):
        categories = ", ".join(product["categories"])
        parts.append(f"Subcategories: {categories}")

    if product.get("store"):
        parts.append(f"Brand: {product['store']}")

    if product.get("features"):
        features = "; ".join(product["features"])
        parts.append(f"Features: {features}")

    if product.get("description"):
        description = " ".join(product["description"])
        parts.append(f"Description: {description}")

    return ". ".join(parts)

rate_limiter = RateLimiter(2000, 60)

# ---------------- ingestion loop ----------------
inserted_count = 0
with open(JSONL_PATH, "r") as f:
    for line_num, line in enumerate(f, start=1):
        raw = json.loads(line)
        parent_asin = raw["parent_asin"]

        doc = {
            "id": str(uuid.uuid4()),
            "parent_asin": parent_asin,
            "main_category": raw.get("main_category"),
            "title": raw.get("title"),
            "average_rating": raw.get("average_rating"),
            "rating_number": raw.get("rating_number"),
            "features": raw.get("features", []),
            "description": raw.get("description", []),
            "price": raw.get("price"),
            "images": raw.get("images", []),
            "videos": raw.get("videos", []),
            "store": raw.get("store"),
            "categories": raw.get("categories", []),
            "details": raw.get("details", {}),
            "bought_together": raw.get("bought_together"),
            "embedding": None,
            "embedding_model": None,
            "doc_type": "product"
        }

        # embedding_text = build_product_embedding_text(doc)
        # if not embedding_text.strip():
        #     print(f"⚠️  Skipping line {line_num}: empty embedding text")
        #     continue
        #
        # # create embedding (catch errors and skip on failure)
        # try:
        #     embedding = openai_client.embeddings.create(
        #         model=EMBEDDING_MODEL,
        #         input=embedding_text
        #     ).data[0].embedding
        # except Exception as e:
        #     print(f"❌ Embedding failed for line {line_num}: {e}")
        #     continue
        #
        # doc["embedding"] = embedding
        # doc["embedding_model"] = EMBEDDING_MODEL

        # rate limit and upsert (only count successful upserts)
        rate_limiter.wait()
        try:
            products.upsert_item(doc)
        except Exception as e:
            print(f"❌ Upsert failed for line {line_num}: {e}")
            continue

        inserted_count += 1
        if inserted_count % 10 == 0:
            print(f"✅ Inserted {inserted_count} products")

        # if inserted_count >= MAX_INITIAL_INSERTS:
        #     print(f"🔒 Reached initial insert limit ({MAX_INITIAL_INSERTS}). Stopping.")
        #     break

print("🎉 Finished ingesting products")
