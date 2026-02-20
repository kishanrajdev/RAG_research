from utils.db import get_database
import pandas as pd
import spacy
from collections import Counter


# -----------------------------
# 1. Fetch reviews from Cosmos
# -----------------------------
db = get_database()
reviews = db.get_container_client("reviews")

PARENT_ASIN = "B00R1TAN7I"

query = """
SELECT
    c.id,
    c.title,
    c.text
FROM c
WHERE c.parent_asin = @asin
"""

items = list(
    reviews.query_items(
        query=query,
        parameters=[{"name": "@asin", "value": PARENT_ASIN}],
        enable_cross_partition_query=True,
    )
)

df = pd.DataFrame(items)
print(f"Fetched {len(df)} reviews")


# -----------------------------
# 2. Sentence splitting
# -----------------------------
nlp = spacy.load("en_core_web_sm")

def split_sentences(text: str):
    if not text or not isinstance(text, str):
        return []
    doc = nlp(text)
    return [s.text.strip() for s in doc.sents if len(s.text.strip()) > 2]


rows = []
for _, row in df.iterrows():
    rid = row["id"]

    for sent in split_sentences(row.get("title", "")):
        rows.append({"review_id": rid, "source": "title", "sentence": sent})

    for sent in split_sentences(row.get("text", "")):
        rows.append({"review_id": rid, "source": "text", "sentence": sent})

sent_df = pd.DataFrame(rows)
print(sent_df["source"].value_counts())
print(f"Extracted {len(sent_df)} sentences")


# -----------------------------
# 3. Candidate aspect extraction
# -----------------------------
def extract_candidate_aspects(sentence: str):
    doc = nlp(sentence)
    aspects = []

    for chunk in doc.noun_chunks:
        # skip pure pronouns/determiners
        if chunk.root.pos_ in {"PRON", "DET", "NUM"}:
            continue

        # skip interrogatives
        if chunk.root.lemma_ in {"what", "which", "who", "when", "where", "why", "how"}:
            continue

        aspects.append(chunk.text.lower().strip())

    return aspects


sent_df["candidate_aspects"] = sent_df["sentence"].apply(extract_candidate_aspects)

raw_counter = Counter(
    a for aspects in sent_df["candidate_aspects"] for a in aspects
)
print("Top raw aspects:")
print(raw_counter.most_common(20))


# -----------------------------
# 4. Aspect normalization (FIXED)
# -----------------------------
META_HEADS = {
    "star", "rating", "review",
    "product", "item",
    "time", "one"
}

KINSHIP_TERMS = {
    "husband", "wife", "son", "daughter",
    "mom", "mother", "dad", "father",
    "child", "kids", "people", "person"
}

def normalize_aspect(aspect_text: str):
    doc = nlp(aspect_text)

    # drop people/entities (e.g. "my husband")
    if any(tok.ent_type_ == "PERSON" for tok in doc):
        return None

    head = None
    modifiers = []

    for tok in doc:
        if tok.pos_ == "NOUN" and head is None:
            head = tok.lemma_.lower()
        elif tok.dep_ in {"compound", "amod"} and tok.pos_ in {"ADJ", "NOUN"}:
            modifiers.append(tok.lemma_.lower())

    if not head:
        return None

    # drop meta-review artifacts
    if head in META_HEADS:
        return None

        # drop human references
    if head in KINSHIP_TERMS:
        return None

    # keep meaningful compounds (e.g. "boar bristle brush")
    if modifiers:
        return " ".join(modifiers + [head])

    return head


sent_df["normalized_aspects"] = sent_df["candidate_aspects"].apply(
    lambda aspects: [
        a for a in (normalize_aspect(x) for x in aspects) if a is not None
    ]
)


# -----------------------------
# 5. Inspect final aspects
# -----------------------------
final_counter = Counter(
    a for aspects in sent_df["normalized_aspects"] for a in aspects
)

print("Top normalized aspects:")
print(final_counter.most_common(20))
