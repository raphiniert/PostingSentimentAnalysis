from sqlalchemy import (
    Column,
    Boolean,
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
# from sqlalchemy.orm import sessionmaker
Base = declarative_base()
# engine = create_engine("sqlite:///postings.db", encoding="utf-8", echo=True)
# Session = sessionmaker(bind=engine)


class Article(Base):
    __tablename__ = "articles"

    article_id = Column(Integer, primary_key=True)
    article_title = Column(String(1024), nullable=False)
    article_url = Column(String(256), unique=True)
    article_publication_date = Column(DateTime, nullable=False)

    def __init__(self, article_title, article_url, article_publication_date):
        self.article_title = article_title
        self.article_url = article_url
        self.article_publication_date = article_publication_date

    def __repr__(self):
        return f"<Article {self.article_title}>"


class PostingRating(Base):
    __tablename__ = "posting_ratings"

    posting_id = Column(Integer, ForeignKey("postings.posting_id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True)
    positive = Column(Boolean, nullable=False)
    # relationships
    posting = relationship("Posting", back_populates="users")
    user = relationship("User", back_populates="postings")

    def __init__(self, positive):
        self.positive = positive

    def __repr__(self):
        return f"<PostingRating {self.posting_id} {self.user_id} {self.positive}>"


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    user_name = Column(String(512), nullable=False, unique=True)
    user_organization = Column(String(512), nullable=True, default=None)
    verified = Column(Boolean, nullable=False, default=False)
    follower_count = Column(Integer, nullable=True, default=None)
    supporter = Column(Boolean, nullable=False, default=False)
    postings = relationship("PostingRating", back_populates="user")

    def __init__(
        self,
        user_name,
        verified,
        follower_count=None,
        user_organization=None,
        supporter=False,
    ):
        self.user_name = user_name
        self.verified = verified
        self.follower_count = follower_count
        self.user_organization = user_organization
        self.supporter = supporter

    def __repr__(self):
        return f"<User {self.user_name} ({self.follower_count})>"


class Posting(Base):
    __tablename__ = "postings"

    posting_id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey(Article.article_id), nullable=False)
    user_id = Column(Integer, ForeignKey(User.user_id), nullable=False)
    posting_ref_id = Column(String(256), nullable=False)
    parent_posting_ref_id = Column(String(256), nullable=True, default=None)
    posting_date = Column(DateTime, nullable=False)
    negative_rating = Column(Integer, nullable=False, default=0)
    positive_rating = Column(Integer, nullable=False, default=0)
    posting_title = Column(String(1024), nullable=True)
    posting_content = Column(Text, nullable=False)

    users = relationship("PostingRating", back_populates="posting")

    def __init__(
        self,
        article_id,
        user_id,
        posting_ref_id,
        parent_posting_ref_id,
        posting_date,
        negative_rating,
        positive_rating,
        posting_title,
        posting_content,
    ):
        self.article_id = article_id
        self.user_id = user_id
        self.posting_ref_id = posting_ref_id
        self.parent_posting_ref_id = parent_posting_ref_id
        self.posting_date = posting_date
        self.negative_rating = negative_rating
        self.positive_rating = positive_rating
        self.posting_title = posting_title
        self.posting_content = posting_content

    def __repr__(self):
        return f"<Posting {self.posting_ref_id} by {self.user_id}>"
