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
logging.basicConfig(filename="log/standard_postings.log", format=FORMAT, level=20)
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
    "https://www.derstandard.at/story/2000112608982/fpoe-praesentiert-historikerbericht",
    "https://www.derstandard.at/story/2000114104569/fpoe-historikerberichtexperten-bewerten-blaues-papier",
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
    engine = create_engine("sqlite:///postings.db", encoding="utf-8", echo=echo)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def accept_cookies():
    try:
        # check if privacywall pops up
        if driver.find_element_by_class_name("privacywall-info"):
            # accept neo-liberal surveillance capitalism
            driver.find_element_by_class_name("js-privacywall-agree").click()
            logger.debug("Cookies accepted.")
    except NoSuchElementException:
        logger.debug("No privacywall was displayed.")


def find_posting_ids():
    return [
        posting.get_attribute("data-postingid")
        for posting in driver.find_elements_by_css_selector(
            "div#postinglist div.posting"
        )
    ]


def get_last_crawled_posting_id_for_article(article_id):
    # get reference id for last inserted posting
    last_posting_id = (
        session.query(func.max(Posting.posting_id))
        .filter(Posting.article_id == article_id)
        .first()[0]
    )
    logger.info(f"last posting id: {last_posting_id}")
    if last_posting_id:
        last_posting_ref_id = session.query(Posting).get(last_posting_id).posting_ref_id
        logger.info(f"last posting ref id: {last_posting_ref_id}")
        return last_posting_ref_id
    return None


def go_to_page_with_posting_id(posting_ref_id, page_count):
    while driver.find_element_by_class_name("forum-tb-btnnext").is_enabled():
        try:
            driver.find_element_by_css_selector(
                f"div#postinglist div.posting[data-postingid='{posting_ref_id}']"
            )
            logger.info(f"Found posting with id {posting_ref_id} on page {page_count}")
            break  # found page including last posting id
        except NoSuchElementException:
            logger.debug(
                f"Couldn't find posting with id {posting_ref_id} on page {page_count}"
            )
            page_count += 1
            driver.find_element_by_class_name("forum-tb-btnnext").click()
            time.sleep(3)
    return page_count


def get_posting_user_data():
    try:
        user_name = posting.find_element_by_css_selector(
            "a.upost-usercontainer strong.upost-communityname"
        ).text
        logger.debug(f"User name found: {user_name}")
    except NoSuchElementException:  # deleted user
        logger.debug("No user name found, assuming user was deleted.")
        user_name = "<DELETED USER>"

    try:
        posting.find_element_by_css_selector("span.upost-verified-identity")
        logger.debug(f"User {user_name} is verified.")
        verified = True
    except NoSuchElementException:
        logger.debug(f"User {user_name} is not verified.")
        verified = False

    try:
        user_organization = posting.find_element_by_css_selector(
            "span.upost-organization-identity"
        ).text
        logger.debug(f"User {user_name} added organization information.")
    except NoSuchElementException:
        logger.debug(f"User {user_name} added no organization information.")
        user_organization = None

    try:
        posting.find_element_by_css_selector("span.upost-supporter")
        logger.debug(f"User {user_name} is a supporter.")
        supporter = True
    except NoSuchElementException:
        logger.debug(f"User {user_name} is no supporter.")
        supporter = False

    try:
        follower_count = posting.find_element_by_css_selector(
            "span.upost-follower"
        ).text
        follower_count = int(follower_count)
        logger.debug(f"User {user_name} has {follower_count} followers.")
    except (NoSuchElementException, ValueError) as ex:
        follower_count = 0
        logger.warning(
            f"Couldn't detect follower count, assuming user {user_name} has {follower_count} followers. Exception was: {ex}"
        )

    return user_name, verified, user_organization, supporter, follower_count


def get_posting_data():
    try:
        parent_posting_ref_id = posting.get_attribute("data-parentpostingid")
        logger.debug(f"Posting is a reply to posting with id: {parent_posting_ref_id}.")
    except TypeError:
        parent_posting_ref_id = None

    posting_date = datetime.datetime.strptime(
        posting.find_element_by_css_selector("span.js-timestamp").text.strip(),
        "%d. %B %Y, %H:%M:%S",
    )
    logger.debug(f"Posting date is {posting_date}.")

    try:
        negative_rating_count = posting.find_element_by_css_selector(
            "span.ratings-negative-count"
        ).text
        negative_rating_count = (
            int(negative_rating_count) if len(negative_rating_count) else 0
        )
        logger.debug(f"Posting's negative rating count is {negative_rating_count}.")
    except (NoSuchElementException, ValueError) as ex:
        negative_rating_count = 0
        logger.warning(
            f"Couldn't detect posting's negative rating count, assuming is is 0. Exception was: {ex}"
        )

    try:
        positive_rating_count = posting.find_element_by_css_selector(
            "span.ratings-positive-count"
        ).text
        positive_rating_count = (
            int(positive_rating_count) if len(positive_rating_count) else 0
        )
        logger.debug(f"Posting's positive rating count is {positive_rating_count}.")
    except (NoSuchElementException, ValueError) as ex:
        positive_rating_count = 0
        logger.warning(
            f"Couldn't detect posting's positive rating count, assuming is is 0. Exception was: {ex}"
        )
    posting_title = posting.find_element_by_css_selector(
        "div.upost-content div.upost-body h4.upost-title"
    ).text
    logger.debug(f"Posting title is {posting_title}.")

    posting_content = posting.find_element_by_css_selector(
        "div.upost-content div.upost-body div.upost-text"
    ).text
    logger.debug(f"Posting content is {posting_content}.")

    return (
        parent_posting_ref_id,
        posting_date,
        negative_rating_count,
        positive_rating_count,
        posting_title,
        posting_content,
    )


def get_posting_rating_users():
    # scroll to ratings, as it's sometimes out of viewport and therefore not interactable
    ActionChains(driver).move_to_element(
        driver.find_element_by_css_selector("div.js-ratings")
    ).perform()
    posting.find_element_by_css_selector("div.js-ratings").click()
    time.sleep(3)
    # expand user list if necessary
    try:
        while driver.find_element_by_class_name("js-ratings-log-showmore"):
            driver.find_element_by_class_name("js-ratings-log-showmore").click()
            time.sleep(3)
    except NoSuchElementException:
        pass
    rating_list = []
    for rating in driver.find_elements_by_css_selector("ul#js-ratings-log-entries li"):
        try:
            rating_user_name = rating.find_element_by_css_selector(
                "a.ratings-log-communityname"
            ).text
            logger.debug(f"User {rating_user_name} rated posting.")
        except NoSuchElementException:
            logger.debug("No user name found, assuming user was deleted.")
            rating_user_name = "<DELETED USER>"

        rating_positive = rating.get_attribute("data-rate") == "positive"
        if rating_positive:
            logger.debug(f"Posting was rated positive by {rating_user_name}.")
        else:
            logger.debug(f"Posting was rated negative by {rating_user_name}.")

        try:
            rating.find_element_by_css_selector("a.ratings-log-is-byverifieduser")
            rating_user_verified = True
            logger.debug(f"User {rating_user_name} is verified.")
        except NoSuchElementException:
            rating_user_verified = False
            logger.debug(f"User {rating_user_name} is not verified.")
        rating_positive = rating.get_attribute("data-rate") == "positive"
        rating_list.append((rating_user_name, rating_user_verified, rating_positive))

    posting.find_element_by_css_selector("div.js-ratings").click()
    return rating_list


if __name__ == "__main__":
    t1 = datetime.datetime.now()
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(10)
    session = get_db_session(args.verbose)
    logger.info("Established database connection.")
    driver = setup_webdriver(args.no_headless)
    logger.info("Setup webdriver.")
    for url in url_list:
        logger.info(f"Crawling postings for url: {url}")
        driver.get(url)
        time.sleep(3)
        accept_cookies()
        time.sleep(3)

        article = session.query(Article).filter(Article.article_url == url).first()
        if article is None:
            article_title = driver.find_element_by_css_selector("h1.article-title").text
            article_publication_date = datetime.datetime.strptime(
                driver.find_element_by_css_selector("p.article-pubdate").text.strip(),
                "%d. %B %Y, %H:%M",
            )
            article = Article(article_title, url, article_publication_date)
            session.add(article)
            session.commit()

        page_count = 1
        if args.continue_article:
            if article.article_id != args.continue_article:
                logger.debug(
                    f"Skipping article {article} with id {article.article_id}."
                )
                continue
            last_posting_ref_id = get_last_crawled_posting_id_for_article(
                article.article_id
            )
            if last_posting_ref_id:
                page_count = go_to_page_with_posting_id(last_posting_ref_id, page_count)
                time.sleep(3)
            else:
                logger.warning(f"Couldn't find a posting for article: {article}")

        retries = args.retries
        posting_ids = find_posting_ids()
        logger.debug(
            f"Found {len(posting_ids)} postings with ids: {posting_ids} on page {page_count}."
        )
        continue_crawling = False
        if len(posting_ids):
            continue_crawling = True
        while continue_crawling:
            for posting_ref_id in posting_ids:
                posting = driver.find_element_by_css_selector(
                    f"div#postinglist div.posting[data-postingid='{posting_ref_id}']"
                )
                crawled_posting = False
                while not crawled_posting:
                    try:
                        # collect user, posting and rating data
                        (
                            user_name,
                            verified,
                            user_organization,
                            supporter,
                            follower_count,
                        ) = get_posting_user_data()
                        (
                            parent_posting_ref_id,
                            posting_date,
                            negative_rating_count,
                            positive_rating_count,
                            posting_title,
                            posting_content,
                        ) = get_posting_data()
                        rating_list = []
                        if negative_rating_count or positive_rating_count:
                            rating_list = get_posting_rating_users()
                    except Exception as ex:
                        retries -= 1
                        logger.error(
                            f"Couldn't process posting with id {posting_ref_id} on page {page_count}. Exception: {ex}. Retries left: {retries}."
                        )
                        if not retries:
                            break
                    else:
                        crawled_posting = True
                        # update database
                        user = (
                            session.query(User)
                            .filter(User.user_name == user_name)
                            .first()
                        )
                        if user is None:
                            user = User(
                                user_name,
                                verified,
                                follower_count,
                                user_organization,
                                supporter,
                            )
                            db_statement_info = "Added new"
                        else:
                            user.verified = verified
                            if user.follower_count is None:
                                user.follower_count = follower_count
                            elif follower_count > user.follower_count:
                                # only update follower count if follower count > as current info
                                user.follower_count = follower_count
                            user.user_organization = user_organization
                            user.supporter = supporter
                            db_statement_info = "Updated"
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
                                parent_posting_ref_id,
                                posting_date,
                                negative_rating_count,
                                positive_rating_count,
                                posting_title,
                                posting_content,
                            )
                            db_statement_info = "Added new"
                        else:
                            posting.parent_posting_ref_id = parent_posting_ref_id
                            posting.posting_date = posting_date
                            posting.negative_rating_count = negative_rating_count
                            posting.positive_rating_count = positive_rating_count
                            posting.posting_title = posting_title
                            posting.posting_content = posting_content
                            db_statement_info = "Updated"
                        session.add(posting)
                        session.commit()
                        logger.info(f"{db_statement_info} Posting: {posting}")

                        for (user_name, verified, rating_positive) in rating_list:
                            user = (
                                session.query(User)
                                .filter(User.user_name == user_name)
                                .first()
                            )
                            if user is None:
                                user = User(user_name, verified)
                                session.add(user)
                                session.commit()
                                logger.debug(f"Added new user: {user}")
                            posting_rating = (
                                session.query(PostingRating)
                                .filter(
                                    PostingRating.posting_id == posting.posting_id,
                                    PostingRating.user_id == user.user_id,
                                )
                                .first()
                            )
                            if posting_rating is None:
                                posting_rating = PostingRating(rating_positive)
                                posting_rating.posting = posting
                                posting_rating.user = user
                                db_statement_info = "Added new"
                            else:
                                posting_rating.positive = rating_positive
                                db_statement_info = "Updated"
                            session.add(posting_rating)
                            session.commit()
                            logger.info(
                                f"{db_statement_info} PostingRating: {posting_rating}"
                            )

                if not retries:
                    logger.warning(f"Max of {args.retries} retries exceeded.")
                    break

            # go to next page
            continue_crawling = False
            if (
                retries
                and driver.find_element_by_class_name("forum-tb-btnnext").is_enabled()
            ):
                driver.find_element_by_class_name("forum-tb-btnnext").click()
                page_count += 1
                time.sleep(3)
                posting_ids = find_posting_ids()
                logger.info(
                    f"Crawling {len(posting_ids)} postings on page: {page_count}."
                )
                logger.debug(
                    f"Found  postings with ids: {posting_ids} on page {page_count}."
                )
                continue_crawling = True

    # close
    session.close()
    driver.quit()
    logger.info(
        f"Completed. Processing took {(datetime.datetime.now() - t1).seconds}s."
    )
