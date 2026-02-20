from utils.db import get_database
import pandas as pd
import spacy
from collections import Counter
import re


db = get_database()
reviews = db.get_container_client("reviews")

PARENT_ASIN = "B00R1TAN7I"

query = """
SELECT  c.id,
    c.title,
    c.text
FROM c
WHERE c.parent_asin = @asin
"""

items = list(reviews.query_items(
    query=query,
    parameters=[{"name": "@asin", "value": PARENT_ASIN}],
    enable_cross_partition_query=True
))

df = pd.DataFrame(items)
print(f"Fetched {len(df)} reviews")

nlp = spacy.load("en_core_web_sm")

def split_sentences(text):
    if not text or not isinstance(text, str):
        return []

    doc = nlp(text)
    return [sent.text.strip() for sent in doc.sents if len(sent.text.strip()) > 2]

rows = []

for _, row in df.iterrows():
    review_id = row["id"]

    # split title
    for sent in split_sentences(row.get("title", "")):
        rows.append({
            "review_id": review_id,
            "source": "title",
            "sentence": sent
        })

    # split review text
    for sent in split_sentences(row.get("text", "")):
        rows.append({
            "review_id": review_id,
            "source": "text",
            "sentence": sent
        })

sent_df = pd.DataFrame(rows)
print(sent_df["source"].value_counts())
print(f"Extracted {len(sent_df)} sentences")
print(sent_df.head(10))

STOP_ASPECTS = {
    "it", "this", "that", "they", "thing", "stuff",
    "product", "item", "one", "lot",
    "she", "he", "we", "you", "i", "my", "your", "his", "her", "its", "our", "their", "mine", "yours", "hers", "ours", "theirs",
    "something", "anything", "everything", "nothing", "someone", "anyone", "everyone", "no one", "somebody", "anybody", "everybody", "nobody", "itself", "themselves", "myself", "yourself", "himself", "herself", "ourselves", "themselves",
    "what", "who", "whom", "which", "whose", "where", "when", "why", "how",
    "all", "any", "both", "each", "few", "many", "several", "some", "such", "other", "another",
    "much", "more", "most", "several", "enough",
    "first", "second", "third", "next", "last"
}

def extract_candidate_aspects(sentence: str):
    doc = nlp(sentence)
    aspects = []

    for chunk in doc.noun_chunks:
        text = chunk.text.lower().strip()

        # remove pronouns / junk
        if text in STOP_ASPECTS:
            continue

        # remove very short or numeric chunks
        if len(text) < 3:
            continue

        # remove pure determiners
        if all(tok.pos_ == "DET" for tok in chunk):
            continue

        aspects.append(text)

    return aspects

sent_df["candidate_aspects"] = sent_df["sentence"].apply(extract_candidate_aspects)
print(sent_df["candidate_aspects"].value_counts())

# (sent_df["candidate_aspects"].str.len() > 0).mean()

aspect_counter = Counter(
    a for aspects in sent_df["candidate_aspects"] for a in aspects
)

print(aspect_counter.most_common(20))

def normalize_aspect_with_modifiers(aspect_text: str):
    doc = nlp(aspect_text)

    head = None
    modifiers = []

    for tok in doc:
        if tok.dep_ == "ROOT" and tok.pos_ == "NOUN":
            head = tok.lemma_.lower()
        elif tok.dep_ in {"amod", "compound"} and tok.pos_ in {"ADJ", "NOUN"}:
            modifiers.append(tok.lemma_.lower())

    if head:
        return " ".join(modifiers + [head])

    return aspect_text.lower()


sent_df["normalized_aspects"] = sent_df["candidate_aspects"].apply(
    lambda aspects: [normalize_aspect_with_modifiers(a) for a in aspects]
)


normalized_counter = Counter(
    a for aspects in sent_df["normalized_aspects"] for a in aspects
)

print(normalized_counter.most_common(20))