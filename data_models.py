# data_models.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Author(db.Model):
    __tablename__ = "author"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    birth_date = db.Column(db.String(50))
    date_of_death = db.Column(db.String(50))

    # Bücher-Beziehung – Cascade: löscht auch verwaiste Bücher beim Autor-Löschen
    books = db.relationship(
        "Book",
        back_populates="author",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Author {self.id} {self.name}>"

    def __str__(self):
        return self.name or f"Author {self.id}"


class Book(db.Model):
    __tablename__ = "book"
    id = db.Column(db.Integer, primary_key=True)
    isbn = db.Column(db.String(64))
    title = db.Column(db.String(300), nullable=False)
    publication_year = db.Column(db.String(20))
    # Bonus: Bewertung 1–10 (optional)
    rating = db.Column(db.Integer)

    author_id = db.Column(db.Integer, db.ForeignKey("author.id"), nullable=True)
    author = db.relationship("Author", back_populates="books")

    def __repr__(self):
        return f"<Book {self.id} {self.title}>"

    def __str__(self):
        return self.title or f"Book {self.id}"