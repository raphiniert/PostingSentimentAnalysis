import argparse
import logging
import datetime
import spacy
import pandas as pd

# useful stuff
from collections import Counter
from string import punctuation

# db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# spacy and nlp stuff
from spacy.lang.de.stop_words import STOP_WORDS
from spacy.tokens import Token
from spacy_sentiws import spaCySentiWS

# machine learning
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline

# project specific
from db import Base, Article, Posting, PostingRating, User

# arguments
parser = argparse.ArgumentParser()
parser.add_argument("--verbose", help="increase output verbosity", action="store_true")


# logging
FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
logging.basicConfig(filename=f"log/{datetime.datetime.now()}_sentiment.log", format=FORMAT, level=20)
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


def get_cleaned_tokens(sentence):
    tokens = []
    # get tokens in lower case
    for token in sentence:
        if token.lemma_ != "-PRON-":
            tokens.append(token.lemma_.lower().strip())
        else:
            tokens.append(token.lower_)

    cleaned_tokens = []
    # filter out stop words and punctuation
    for token in tokens:
        if token not in STOP_WORDS and token not in punctuation:
            cleaned_tokens.append(token)
    return cleaned_tokens


def get_classify_postings(article_id):
    data_dict = {
        'posting_id': [],
        'article_id': [],
        'user_id': [],
        'posting_date': [],
        'negative_rating': [],
        'positive_rating': [],
        'posting_text': [],
        'sentiment': [],
        'entity': []
    }
    for posting in session.query(Posting).filter(Posting.article_id == article_id):
        text = posting.posting_title + "\n" + posting.posting_content
        sentiment = 0.0  # neutral
        doc = nlp(text)
        for ent in doc.ents:
            head = ent.root.head
            if head._.sentiws:
                sentiment = head._.sentiws

            if sentiment == 0.0:
                for token in doc:
                    if token.text == ent.text:
                        if sentiment == 0.0:
                            sents = [t._.sentiws for t in token.lefts if t._.sentiws] + [t._.sentiws for t in token.rights if t._.sentiws]

                            if len(sents) and min(sents) < 0.0:
                                sentiment = min(sents)
                            elif len(sents) and max(sents) > 0.0:
                                sentiment = max(sents)

                        if sentiment != 0.0:
                            break

            # logger.info(f"{ent} {head} {head._.sentiws}")
            data_dict['posting_id'].append(posting.posting_id)
            data_dict['article_id'].append(posting.article_id)
            data_dict['user_id'].append(posting.user_id)
            data_dict['posting_date'].append(posting.posting_date)
            data_dict['negative_rating'].append(posting.negative_rating)
            data_dict['positive_rating'].append(posting.positive_rating)
            data_dict['posting_text'].append(text)
            data_dict['sentiment'].append(sentiment)
            data_dict['entity'].append(ent.text)

    return pd.DataFrame(data_dict)


if __name__ == '__main__':
    t1 = datetime.datetime.now()
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(10)
    session = get_db_session(args.verbose)
    nlp = spacy.load("de_core_news_lg")
    sentiws = spaCySentiWS(sentiws_path='sentiws/')
    nlp.add_pipe(sentiws)
    # nlp = spacy.load("de_core_news_md")
    # nlp = spacy.load("de_core_news_sm")

    entities = ['fpö']

    for article in session.query(Article):
        logger.info(f"Getting sentiments article: {article.article_url}")
        classified_postings = get_classify_postings(article.article_id)
        logger.debug(classified_postings.describe())
        # for entity in entities:
        entity_df = classified_postings.loc[
            classified_postings['entity'].isin(entities) &
            classified_postings['sentiment'] != 0.0
        ]
        logger.info(entity_df.describe)

    session.close()
    logger.info(
        f"Completed. Processing took {(datetime.datetime.now() - t1).seconds}s."
    )