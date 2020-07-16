import argparse
import logging
import datetime
import spacy
import pandas as pd

# useful stuff
from collections import Counter
from string import punctuation
import numpy as np
import pandas as pd

# db
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

# project specific
from db import Base, Article, Posting, PostingRating, User

# arguments
parser = argparse.ArgumentParser()
parser.add_argument("--verbose", help="increase output verbosity", action="store_true")


# logging
FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
logging.basicConfig(
    filename=f"log/{datetime.datetime.now()}_statistics.log", format=FORMAT, level=20
)
logger = logging.getLogger("sentiment")

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# create formatter
formatter = logging.Formatter(FORMAT)

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)


def get_db_session(echo=False):
    engine = create_engine("sqlite:///postings.db", encoding="utf-8", echo=echo)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def get_time_stats(article_id):
    posting_times = [
        t[0]
        for t in session.query(Posting.posting_date)
        .filter(Posting.article_id == article_id)
        .order_by(Posting.posting_date)
    ]
    time_series = pd.Series(posting_times, dtype="datetime64[ns]")
    df = pd.DataFrame(time_series)
    logger.info(time_series.mean())
    # logger.info(time_series.median())
    logger.info(time_series.describe())


def get_posting_stats(article_id, limit=20):
    user_postings = (
        session.query(
            User.user_name,
            func.count(Posting.user_id),
            func.sum(Posting.positive_rating),
            func.sum(Posting.negative_rating),
        )
        .filter(Posting.user_id == User.user_id)
        .filter(User.user_name != "")
        .filter(Posting.article_id == article_id)
        .group_by(Posting.user_id)
        .order_by(func.count(Posting.user_id).desc())
    )
    user_stats = [(x[0], x[1], x[2], x[3]) for x in user_postings]
    df = pd.DataFrame(
        user_stats,
        columns=["user_name", "posting_count", "positive_ratings", "negative_ratings"],
    )
    logger.info(df.describe())
    user_ids = [
        x[0]
        for x in session.query(Posting.user_id).filter(Posting.article_id == article_id)
    ]
    user_ids += [
        x[0]
        for x in session.query(PostingRating.user_id, Posting.posting_id)
        .filter(PostingRating.posting_id == Posting.posting_id)
        .filter(Posting.article_id == article_id)
    ]
    user_ids = set(user_ids)
    positive_ratings = (
        session.query(func.sum(Posting.positive_rating))
        .filter(Posting.article_id == article_id)
        .first()[0]
    )

    negative_ratings = (
        session.query(func.sum(Posting.negative_rating))
            .filter(Posting.article_id == article_id)
            .first()
    )[0]

    logger.info(f"Interactions: {len(user_ids)} {positive_ratings} {negative_ratings}")


def get_posting_entities(article_id, limit=30):
    text = [text[0] + "\n" + text[1] for text in
            session.query(Posting.posting_title,
                          Posting.posting_content).filter(
                Posting.article_id == article_id)]

    text = "".join(text)
    doc = nlp(text)
    entities = [ent.text.lower() for ent in [ents for ents in doc.ents]]
    entitiy_frequency = Counter(entities)
    logger.info(f"Entity Frequency")
    for (entity, frequency) in entitiy_frequency.most_common(limit):
        logger.info(f"{entity} {frequency}")


if __name__ == "__main__":
    t1 = datetime.datetime.now()
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(10)
    session = get_db_session(args.verbose)
    nlp = spacy.load("de_core_news_lg")

    for article in session.query(Article):
        logger.info(f"Getting stats for article: {article.article_url}")
        get_time_stats(article.article_id)
        get_posting_stats(article.article_id)
        get_posting_entities(article.article_id)

    session.close()
    logger.info(
        f"Completed. Processing took {(datetime.datetime.now() - t1).seconds}s."
    )
