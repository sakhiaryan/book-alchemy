from __future__ import annotations
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Author(db.Model):
    """
    Author model.
    """
    __tablename__ = "author"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    birth_date = db.Column(db.Date, nullable=True)
    date_of_death = db.Column(db.Date, nullable=True)

    # Relationship to Book; cascade delete-orphan removes books when author deleted
    books = db.relationship(
        "Book",
        back_populates="author",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Author id={self.id} name={self.name!r}>"

    def __str__(self) -> str:
        return f"{self.name}"


class Book(db.Model):
    """
    Book model.
    """
    __tablename__ = "book"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    isbn = db.Column(db.String(32), nullable=True, unique=False)
    title = db.Column(db.String(200), nullable=False, index=True)
    publication_year = db.Column(db.Integer, nullable=False)

    author_id = db.Column(
        db.Integer,
        db.ForeignKey("author.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author = db.relationship("Author", back_populates="books")

    def __repr__(self) -> str:
        return f"<Book id={self.id} title={self.title!r}>"

    def __str__(self) -> str:
        return f"{self.title}"