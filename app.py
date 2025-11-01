# app.py
import os
import random
from flask import Flask, render_template, request, redirect, url_for, flash
from data_models import db, Author, Book

app = Flask(__name__)
app.secret_key = "dev-secret"  # für Flash-Messages

# --- DB URI ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(basedir, 'data/library.sqlite')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# Tabellen einmalig anlegen (beim ersten Start)
with app.app_context():
    db.create_all()


# -------- Hilfsfunktionen --------
def get_sorted_books(sort: str | None, query: str | None = None):
    q = Book.query
    if query:
        like = f"%{query}%"
        q = q.join(Author, isouter=True).filter(
            db.or_(
                Book.title.ilike(like),
                Author.name.ilike(like)
            )
        )
    if sort == "author":
        q = q.join(Author, isouter=True).order_by(Author.name.asc().nulls_last(), Book.title.asc())
    else:
        q = q.order_by(Book.title.asc())
    return q.all()


# -------- Home (mit Suche & Sortierung) --------
@app.route("/")
def home():
    sort = request.args.get("sort")
    query = request.args.get("q", "").strip() or None
    books = get_sorted_books(sort, query)
    message = None
    if query and not books:
        message = f'No results for "{query}".'
    return render_template("home.html", books=books, sort=sort, query=query, message=message)


# -------- Autor hinzufügen --------
@app.route("/add_author", methods=["GET", "POST"])
def add_author():
    msg = None
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        birth_date = (request.form.get("birth_date") or "").strip()
        date_of_death = (request.form.get("date_of_death") or "").strip()
        if not name:
            msg = "Author name is required."
        else:
            # Duplikate vermeiden
            existing = Author.query.filter_by(name=name).first()
            if existing:
                msg = "Author already exists."
            else:
                a = Author(name=name, birth_date=birth_date, date_of_death=date_of_death)
                db.session.add(a)
                db.session.commit()
                msg = f"Author '{name}' saved."
    return render_template("add_author.html", msg=msg)


# -------- Buch hinzufügen --------
@app.route("/add_book", methods=["GET", "POST"])
def add_book():
    msg = None
    authors = Author.query.order_by(Author.name.asc()).all()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        isbn = (request.form.get("isbn") or "").strip()
        publication_year = (request.form.get("publication_year") or "").strip()
        author_id = request.form.get("author_id")

        if not title or not author_id:
            msg = "Title and Author are required."
        else:
            b = Book(title=title, isbn=isbn, publication_year=publication_year, author_id=int(author_id))
            db.session.add(b)
            db.session.commit()
            msg = f"Book '{title}' saved."
            # Optional: direkt zurück zur Startseite
            # return redirect(url_for("home"))
    return render_template("add_book.html", msg=msg, authors=authors)


# -------- Buch löschen --------
@app.route("/book/<int:book_id>/delete", methods=["POST"])
def delete_book(book_id):
    b = Book.query.get_or_404(book_id)
    title = b.title
    db.session.delete(b)
    db.session.commit()
    flash(f"Deleted book: {title}")
    return redirect(url_for("home"))


# -------- Autor löschen (Cascade löscht dessen Bücher) --------
@app.route("/author/<int:author_id>/delete", methods=["POST"])
def delete_author(author_id):
    a = Author.query.get_or_404(author_id)
    name = a.name
    db.session.delete(a)  # durch cascade werden auch seine Bücher gelöscht
    db.session.commit()
    flash(f"Deleted author '{name}' and all their books.")
    return redirect(url_for("home"))


# -------- Detailseiten --------
@app.route("/book/<int:book_id>")
def book_detail(book_id):
    b = Book.query.get_or_404(book_id)
    return render_template("book_detail.html", book=b)


@app.route("/author/<int:author_id>")
def author_detail(author_id):
    a = Author.query.get_or_404(author_id)
    return render_template("author_detail.html", author=a)


# -------- Bewertung setzen --------
@app.route("/book/<int:book_id>/rate", methods=["POST"])
def rate_book(book_id):
    b = Book.query.get_or_404(book_id)
    try:
        rating = int(request.form.get("rating", ""))
    except ValueError:
        rating = None
    if rating is None or rating < 1 or rating > 10:
        flash("Rating must be an integer between 1 and 10.")
        return redirect(url_for("book_detail", book_id=book_id))
    b.rating = rating
    db.session.commit()
    flash(f"Saved rating {rating} for '{b.title}'.")
    return redirect(url_for("book_detail", book_id=book_id))


# -------- Empfehlung (ohne externe KI) --------
@app.route("/recommend")
def recommend():
    # Heuristik: höchstbewertetes Buch; wenn nichts bewertet: zufälliges
    books = Book.query.all()
    pick = None
    rated = [b for b in books if b.rating]
    if rated:
        rated.sort(key=lambda x: x.rating, reverse=True)
        pick = rated[0]
    elif books:
        pick = random.choice(books)
    return render_template("recommend.html", book=pick)


if __name__ == "__main__":
    # anderen Port wählen, damit nichts blockiert
    app.run(host="0.0.0.0", port=5002, debug=True)