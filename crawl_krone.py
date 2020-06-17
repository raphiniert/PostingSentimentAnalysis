import argparse
import datetime
import locale
import logging
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains

# db
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from db import Base, Article, Posting, PostingRating, User

# set german locale for accurate datetime parsing
locale.setlocale(locale.LC_TIME, "de_AT")

# arguments
parser = argparse.ArgumentParser()
parser.add_argument(
    "--continue-article", help="continue crawling with article", type=int, default=0
)
parser.add_argument("--retries", help="max retries per article", type=int, default=10)
parser.add_argument("--verbose", help="increase output verbosity", action="store_true")
parser.add_argument(
    "--no-headless", help="don't run chrome headless", action="store_false"
)

# logging
FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
logging.basicConfig(
    filename=f"log/{datetime.datetime.now()}_krone_postings.log",
    format=FORMAT,
    level=20,
)
logger = logging.getLogger("postings")

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# create formatter
formatter = logging.Formatter(FORMAT)

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)

# urls to crawl
url_list = [
    ("https://talk.krone.at/embed/stream?asset_url=https%3A%2F%2Fwww.krone.at%2F2066690&initialWidth=610&childId=coral-container&parentTitle=FP%C3%96%20pr%C3%A4sentiert%20endlich%20ihren%20Historikerbericht%20%7C%20krone.at&parentUrl=https%3A%2F%2Fwww.krone.at%2F2066690", "FPÖ präsentiert endlich ihren Historikerbericht", datetime.datetime.strptime("2019-12-23 10:51:00", "%Y-%m-%d %H:%M:%S")),
    (
        "https://talk.krone.at/embed/stream?asset_url=https%3A%2F%2Fwww.krone.at%2F2090973&initialWidth=610&childId=coral-container&parentTitle=FP%C3%96-Historikerbericht%20ist%20eine%20%E2%80%9EThemenverfehlung%E2%80%9C%20%7C%20krone.at&parentUrl=https%3A%2F%2Fwww.krone.at%2F2090973",
        "FPÖ-Historikerbericht ist eine „Themenverfehlung“",
        datetime.datetime.strptime("2020-02-03 12:45:00", "%Y-%m-%d %H:%M:%S"),
    ),
]


def setup_webdriver(run_headless=True):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    if run_headless:
        logger.info("Initializing Chrome with headless option.")
    else:
        logger.info("Initializing Chrome without headless option.")
    return webdriver.Chrome(
        executable_path="bin/chromedriver",
        # Optional argument, if not specified will search path.
        options=chrome_options,
    )


def get_db_session(echo=False):
    engine = create_engine("sqlite:///postings_krone.db", encoding="utf-8", echo=echo)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def crawl_replies(origin_comment, level):
    parent_posting_ref_id = origin_comment.get_attribute("id")
    logger.debug(f"Crawling replies for {parent_posting_ref_id}")
    for reply in origin_comment.find_elements_by_css_selector(
        f"div.talk-stream-comment-wrapper-level-{level}"
    ):
        # reply = reply.find_element_by_css_selector(f"div.talk-stream-comment-level-{level}")
        reply_posting_ref_id = reply.get_attribute("id")
        reply_user_name = reply.find_element_by_css_selector(
            "button.talk-plugin-author-menu-button span"
        ).text
        reply_date = datetime.datetime.strptime(
            reply.find_element_by_css_selector(
                "div.talk-stream-comment-published-date span"
            ).get_attribute("title"),
            "%m/%d/%Y, %H:%M:%S %p",
        )
        reply_content = reply.find_element_by_css_selector(
            "div.talk-slot-comment-content"
        ).text
        try:
            reply_positive_rating_count = int(
                reply.find_element_by_css_selector("span.talk-plugin-upvote-count").text
            )
        except ValueError:
            reply_positive_rating_count = 0
        try:
            reply_negative_rating_count = int(
                reply.find_element_by_css_selector(
                    "span.talk-plugin-downvote-count"
                ).text
            )
        except ValueError:
            reply_negative_rating_count = 0

        user = session.query(User).filter(User.user_name == reply_user_name).first()
        if user is None:
            user = User(reply_user_name, False, 0, None, False,)
            db_statement_info = "Added new"
            session.add(user)
            session.commit()
            logger.info(f"{db_statement_info} User: {user}")

        posting = (
            session.query(Posting)
            .filter(Posting.posting_ref_id == reply_posting_ref_id)
            .first()
        )
        if posting is None:
            posting = Posting(
                article.article_id,
                user.user_id,
                reply_posting_ref_id,
                parent_posting_ref_id,
                reply_date,
                reply_negative_rating_count,
                reply_positive_rating_count,
                "",
                reply_content,
            )
            db_statement_info = "Added new"
            session.add(posting)
            session.commit()
            logger.info(f"{db_statement_info} Posting: {posting}")

        # crawl replies
        if len(
            reply.find_elements_by_css_selector(
                f"div.talk-stream-comment-wrapper-level-{level + 1}"
            )
        ):
            crawl_replies(reply, level + 1)


if __name__ == "__main__":
    t1 = datetime.datetime.now()
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(10)
    session = get_db_session(args.verbose)
    logger.info("Established database connection.")
    driver = setup_webdriver(args.no_headless)
    logger.info("Setup webdriver.")
    for (url, article_title, article_publication_date) in url_list:
        logger.info(f"Crawling postings for url: {url}")
        driver.get(url)
        time.sleep(3)

        article = session.query(Article).filter(Article.article_url == url).first()
        if article is None:
            article = Article(article_title, url, article_publication_date)
            session.add(article)
            session.commit()

        # extend all comments
        extend_comments = True
        while extend_comments:
            try:
                driver.find_element_by_css_selector(
                    "button.talk-load-more-button"
                ).click()
                logger.debug("Clicked weitere Kommentare anzeigen.")
                time.sleep(3)
            except NoSuchElementException:
                extend_comments = False

        level = 0
        for comment in driver.find_elements_by_css_selector(
            f"div.talk-stream-comment-wrapper-level-{level}"
        ):
            top_level_posting = comment.find_element_by_css_selector(
                f"div.talk-stream-comment-level-{level}"
            )
            posting_ref_id = comment.get_attribute("id")
            user_name = comment.find_element_by_css_selector(
                "button.talk-plugin-author-menu-button span"
            ).text
            posting_date = datetime.datetime.strptime(
                comment.find_element_by_css_selector(
                    "div.talk-stream-comment-published-date span"
                ).get_attribute("title"),
                "%m/%d/%Y, %H:%M:%S %p",
            )
            posting_content = comment.find_element_by_css_selector(
                "div.talk-slot-comment-content"
            ).text
            try:
                positive_rating_count = int(
                    comment.find_element_by_css_selector(
                        "span.talk-plugin-upvote-count"
                    ).text
                )
            except ValueError:
                positive_rating_count = 0
            try:
                negative_rating_count = int(
                    comment.find_element_by_css_selector(
                        "span.talk-plugin-downvote-count"
                    ).text
                )
            except ValueError:
                negative_rating_count = 0

            user = session.query(User).filter(User.user_name == user_name).first()
            if user is None:
                user = User(user_name, False, 0, None, False,)
                db_statement_info = "Added new"
                session.add(user)
                session.commit()
                logger.info(f"{db_statement_info} User: {user}")

            posting = (
                session.query(Posting)
                .filter(Posting.posting_ref_id == posting_ref_id)
                .first()
            )
            if posting is None:
                posting = Posting(
                    article.article_id,
                    user.user_id,
                    posting_ref_id,
                    None,
                    posting_date,
                    negative_rating_count,
                    positive_rating_count,
                    "",
                    posting_content,
                )
                db_statement_info = "Added new"
                session.add(posting)
                session.commit()
                logger.info(f"{db_statement_info} Posting: {posting}")

            # crawl replies
            crawl_replies(comment, level + 1)
            # break

    # close
    session.close()
    driver.quit()
    logger.info(
        f"Completed. Processing took {(datetime.datetime.now() - t1).seconds}s."
    )
