import os
from datetime import datetime
from typing import Optional

from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.exceptions import NotFound, BadRequest, InternalServerError

from data_models import db, Author, Book

# -----------------------------
# App & DB setup
# -----------------------------
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

basedir = os.path.abspath(os.path.dirname(__file__))
os.makedirs(os.path.join(basedir, "data"), exist_ok=True)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(basedir, 'data/library.sqlite')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()


# -----------------------------
# Helper / Validation
# -----------------------------
def parse_date(value: str) -> Optional[datetime.date]:
    """
    Parse a date string in ISO format (YYYY-MM-DD). Returns date or None if empty.
    Raises BadRequest on invalid format.
    """
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise BadRequest("Invalid date format. Use YYYY-MM-DD.") from exc


def validate_author_payload(name: str, birth_date_str: str, death_date_str: str) -> tuple[str, Optional[datetime.date], Optional[datetime.date]]:
    """
    Validate author creation/update payload.
    - name must be non-empty
    - dates must be valid (YYYY-MM-DD) if provided
    - death date must be >= birth date (if both provided)
    """
    name = (name or "").strip()
    if not name:
        raise BadRequest("Author name cannot be empty.")

    birth_date = parse_date(birth_date_str)
    death_date = parse_date(death_date_str)

    if birth_date and death_date and death_date < birth_date:
        raise BadRequest("Date of death cannot be earlier than birth date.")

    return name, birth_date, death_date


def validate_book_payload(title: str, publication_year_str: str, author_id_str: str) -> tuple[str, int, int]:
    """
    Validate book creation/update payload.
    - title must be non-empty
    - publication_year must be integer and reasonable
    - author_id must be integer (existing author checked elsewhere)
    """
    title = (title or "").strip()
    if not title:
        raise BadRequest("Book title cannot be empty.")

    # year checks
    publication_year_str = (publication_year_str or "").strip()
    if not publication_year_str.isdigit():
        raise BadRequest("Publication year must be a number.")
    publication_year = int(publication_year_str)
    if publication_year < 0 or publication_year > datetime.now().year + 1:
        raise BadRequest("Publication year seems invalid.")

    # author id checks
    author_id_str = (author_id_str or "").strip()
    if not author_id_str.isdigit():
        raise BadRequest("author_id must be a valid integer.")
    author_id = int(author_id_str)

    return title, publication_year, author_id


# -----------------------------
# Error handlers (one template)
# -----------------------------
@app.errorhandler(404)
def handle_404(e):
    return render_template("error.html", code=404, message="Page not found."), 404


@app.errorhandler(400)
def handle_400(e):
    return render_template("error.html", code=400, message=str(e)), 400


@app.errorhandler(500)
def handle_500(e):
    return render_template("error.html", code=500, message="Internal server error."), 500


# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def home():
    """
    Home page: list books (with optional sort/search) and provide links to add authors/books.
    Query params:
      - sort: title|year|author
      - direction: asc|desc
      - q: search term (matches title or author name)
    """
    sort = (request.args.get("sort") or "").lower()
    direction = (request.args.get("direction") or "asc").lower()
    query = (request.args.get("q") or "").strip()

    q = Book.query.join(Author)

    if query:
        like = f"%{query}%"
        q = q.filter((Book.title.ilike(like)) | (Author.name.ilike(like)))

    # sorting
    if sort == "title":
        order_col = Book.title
    elif sort in ("year", "publication_year"):
        order_col = Book.publication_year
    elif sort == "author":
        order_col = Author.name
    else:
        # default stable order by id
        order_col = Book.id

    if direction == "desc":
        q = q.order_by(order_col.desc())
    else:
        q = q.order_by(order_col.asc())

    books = q.all()
    authors = Author.query.order_by(Author.name.asc()).all()
    return render_template("home.html", books=books, authors=authors, sort=sort, direction=direction, q=query)


@app.route("/add_author", methods=["GET", "POST"])
def add_author():
    """
    Add a new author with validation and duplicate check.
    """
    if request.method == "POST":
        try:
            name, birth_date, death_date = validate_author_payload(
                request.form.get("name"),
                request.form.get("birth_date"),
                request.form.get("death_date"),
            )

            # Duplicate check: same name (case-insensitive) and same birth_date if provided
            existing = Author.query.filter(
                db.func.lower(Author.name) == name.lower()
            ).all()

            for a in existing:
                # consider duplicates if either both have same birth_date, or birth_date omitted by both
                if (a.birth_date == birth_date) or (a.birth_date is None and birth_date is None):
                    raise BadRequest("Author already exists.")

            author = Author(name=name, birth_date=birth_date, date_of_death=death_date)
            db.session.add(author)
            db.session.commit()
            flash("Author added successfully.", "success")
            return redirect(url_for("home"))

        except BadRequest as br:
            db.session.rollback()
            flash(str(br), "error")
        except Exception as exc:
            db.session.rollback()
            app.logger.exception("Failed to add author")
            raise InternalServerError("Database error while adding author.") from exc

    return render_template("add_author.html")


@app.route("/add_book", methods=["GET", "POST"])
def add_book():
    """
    Add a new book with validation, duplicate title check, and author existence check.
    """
    authors = Author.query.order_by(Author.name.asc()).all()

    if request.method == "POST":
        try:
            title, publication_year, author_id = validate_book_payload(
                request.form.get("title"),
                request.form.get("publication_year"),
                request.form.get("author_id"),
            )

            author = Author.query.get(author_id)
            if not author:
                raise BadRequest("Selected author does not exist.")

            # Duplicate title check (case-insensitive) - global
            dup = Book.query.filter(db.func.lower(Book.title) == title.lower()).first()
            if dup:
                raise BadRequest("A book with this title already exists.")

            book = Book(
                title=title,
                publication_year=publication_year,
                author_id=author_id,
                isbn=(request.form.get("isbn") or "").strip() or None,
            )
            db.session.add(book)
            db.session.commit()
            flash("Book added successfully.", "success")
            return redirect(url_for("home"))

        except BadRequest as br:
            db.session.rollback()
            flash(str(br), "error")
        except Exception as exc:
            db.session.rollback()
            app.logger.exception("Failed to add book")
            raise InternalServerError("Database error while adding book.") from exc

    return render_template("add_book.html", authors=authors)


@app.route("/update/<int:book_id>", methods=["GET", "POST"])
def update(book_id: int):
    """
    Update an existing book's details.
    """
    book = Book.query.get(book_id)
    if not book:
        raise NotFound("Book not found.")

    authors = Author.query.order_by(Author.name.asc()).all()

    if request.method == "POST":
        try:
            title, publication_year, author_id = validate_book_payload(
                request.form.get("title"),
                request.form.get("publication_year"),
                request.form.get("author_id"),
            )

            author = Author.query.get(author_id)
            if not author:
                raise BadRequest("Selected author does not exist.")

            # If title changed, ensure not duplicate
            if title.lower() != book.title.lower():
                dup = Book.query.filter(db.func.lower(Book.title) == title.lower()).first()
                if dup:
                    raise BadRequest("A book with this title already exists.")

            book.title = title
            book.publication_year = publication_year
            book.author_id = author_id
            # Optional: allow updating ISBN
            new_isbn = (request.form.get("isbn") or "").strip()
            book.isbn = new_isbn or None

            db.session.commit()
            flash("Book updated successfully.", "success")
            return redirect(url_for("home"))

        except BadRequest as br:
            db.session.rollback()
            flash(str(br), "error")
        except Exception as exc:
            db.session.rollback()
            app.logger.exception("Failed to update book")
            raise InternalServerError("Database error while updating book.") from exc

    return render_template("update.html", book=book, authors=authors)


@app.route("/book/<int:book_id>/delete", methods=["POST"])
def delete_book(book_id: int):
    """
    Delete a book by id. Optionally remove author if they have no more books.
    """
    book = Book.query.get(book_id)
    if not book:
        raise NotFound("Book not found.")

    try:
        author = book.author
        db.session.delete(book)
        db.session.commit()

        # Optional: clean up orphan authors (no books left)
        if author and not author.books:
            db.session.delete(author)
            db.session.commit()

        flash("Book deleted successfully.", "success")
        return redirect(url_for("home"))

    except Exception as exc:
        db.session.rollback()
        app.logger.exception("Failed to delete book")
        raise InternalServerError("Database error while deleting book.") from exc


if __name__ == "__main__":
    # You can change the port if 5000 is taken
    app.run(host="0.0.0.0", port=5000, debug=True)