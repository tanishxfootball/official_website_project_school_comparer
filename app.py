import os
import csv

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# ---------------- DATABASE CONFIG ---------------- #

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///schools.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

db = SQLAlchemy(app)

ALLOWED_BOARDS = {"CBSE", "ICSE", "State Board"}

# Provided master location dataset (state-city pairs).
RAW_LOCATION_DATA = {
    "state": [
        "Andhra Pradesh","Andhra Pradesh","Andhra Pradesh","Andhra Pradesh",
        "Arunachal Pradesh","Arunachal Pradesh",
        "Assam","Assam","Assam","Assam",
        "Bihar","Bihar","Bihar","Bihar",
        "Chhattisgarh","Chhattisgarh","Chhattisgarh",
        "Goa","Goa",
        "Gujarat","Gujarat","Gujarat","Gujarat","Gujarat",
        "Haryana","Haryana","Haryana",
        "Himachal Pradesh","Himachal Pradesh","Himachal Pradesh",
        "Jharkhand","Jharkhand","Jharkhand",
        "Karnataka","Karnataka","Karnataka","Karnataka","Karnataka",
        "Kerala","Kerala","Kerala","Kerala",
        "Madhya Pradesh","Madhya Pradesh","Madhya Pradesh","Madhya Pradesh",
        "Maharashtra","Maharashtra","Maharashtra","Maharashtra","Maharashtra","Maharashtra",
        "Manipur","Manipur",
        "Meghalaya","Meghalaya",
        "Mizoram","Mizoram",
        "Nagaland","Nagaland",
        "Odisha","Odisha","Odisha","Odisha",
        "Punjab","Punjab","Punjab",
        "Rajasthan","Rajasthan","Rajasthan","Rajasthan",
        "Sikkim","Sikkim",
        "Tamil Nadu","Tamil Nadu","Tamil Nadu","Tamil Nadu","Tamil Nadu",
        "Telangana","Telangana","Telangana",
        "Tripura","Tripura",
        "Uttar Pradesh","Uttar Pradesh","Uttar Pradesh","Uttar Pradesh","Uttar Pradesh",
        "Uttarakhand","Uttarakhand","Uttarakhand",
        "West Bengal","West Bengal","West Bengal","West Bengal"
    ],
    "city": [
        "Visakhapatnam","Vijayawada","Guntur","Nellore",
        "Itanagar","Tawang",
        "Guwahati","Silchar","Dibrugarh","Jorhat",
        "Patna","Gaya","Bhagalpur","Muzaffarpur",
        "Raipur","Bhilai","Bilaspur",
        "Panaji","Margao",
        "Ahmedabad","Surat","Vadodara","Rajkot","Gandhinagar",
        "Gurugram","Faridabad","Hisar",
        "Shimla","Manali","Dharamshala",
        "Ranchi","Jamshedpur","Dhanbad",
        "Bengaluru","Mysuru","Mangaluru","Hubballi","Belagavi",
        "Thiruvananthapuram","Kochi","Kozhikode","Thrissur",
        "Bhopal","Indore","Gwalior","Jabalpur",
        "Mumbai","Pune","Nagpur","Nashik","Thane","Aurangabad",
        "Imphal","Churachandpur",
        "Shillong","Tura",
        "Aizawl","Lunglei",
        "Kohima","Dimapur",
        "Bhubaneswar","Cuttack","Rourkela","Berhampur",
        "Amritsar","Ludhiana","Jalandhar",
        "Jaipur","Udaipur","Jodhpur","Kota",
        "Gangtok","Namchi",
        "Chennai","Coimbatore","Madurai","Tiruchirappalli","Salem",
        "Hyderabad","Warangal","Nizamabad",
        "Agartala","Udaipur",
        "Lucknow","Kanpur","Varanasi","Agra","Prayagraj",
        "Dehradun","Haridwar","Haldwani",
        "Kolkata","Siliguri","Durgapur","Asansol"
    ]
}


def build_master_locations():
    states = RAW_LOCATION_DATA.get("state", [])
    cities = RAW_LOCATION_DATA.get("city", [])
    locations = {}

    for state, city in zip(states, cities):
        locations.setdefault(state, set()).add(city)

    return {state: sorted(city_set) for state, city_set in sorted(locations.items())}


MASTER_STATES_WITH_CITIES = build_master_locations()
CITY_TO_STATE = {
    city.strip().lower(): state
    for state, cities in MASTER_STATES_WITH_CITIES.items()
    for city in cities
}
_demo_data_checked = False


# ---------------- MODELS ---------------- #

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)


class School(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    board = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    students = db.Column(db.Integer, nullable=False)
    faculty = db.Column(db.Integer, nullable=False)
    subjects = db.Column(db.String(300), nullable=False)

    reviews = db.relationship("Review", backref="school", lazy=True, cascade="all, delete")


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey("school.id"), nullable=False)


# ---------------- HELPERS ---------------- #

def parse_int(value, min_value=None):
    if value is None or str(value).strip() == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if min_value is not None and parsed < min_value:
        return None
    return parsed


def get_states_with_cities():
    db_locations = (
        db.session.query(School.state, School.city)
        .distinct()
        .order_by(School.state, School.city)
        .all()
    )
    states_with_cities = {state: set(cities) for state, cities in MASTER_STATES_WITH_CITIES.items()}

    for state, city in db_locations:
        states_with_cities.setdefault(state, set()).add(city)

    return {state: sorted(city_set) for state, city_set in sorted(states_with_cities.items())}


def get_available_boards():
    boards = set(ALLOWED_BOARDS)
    db_boards = db.session.query(School.board).distinct().all()
    for (board,) in db_boards:
        if board:
            boards.add(board)
    return sorted(boards)


def load_demo_school_data_if_needed():
    global _demo_data_checked
    if _demo_data_checked:
        return
    _demo_data_checked = True

    csv_candidates = [
        os.environ.get("DEMO_SCHOOLS_CSV", "").strip(),
        r"c:\Users\hp\Downloads\india_school_dataset.csv",
        os.path.join(app.root_path, "india_school_dataset.csv"),
    ]
    csv_path = next((path for path in csv_candidates if path and os.path.exists(path)), None)
    if not csv_path:
        return

    existing_keys = {
        (name, city, board, price)
        for name, city, board, price in db.session.query(
            School.name, School.city, School.board, School.price
        ).all()
    }
    rows_to_insert = []
    with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            city = (row.get("City") or "").strip()
            name = (row.get("School Name") or "").strip()
            board = (row.get("Board") or "").strip()
            price = parse_int(row.get("Annual Fees (INR)"), min_value=0)

            if not city or not name or not board or price is None:
                continue

            school_key = (name, city, board, price)
            if school_key in existing_keys:
                continue

            inferred_state = CITY_TO_STATE.get(city.lower(), "Unknown")
            rows_to_insert.append(
                School(
                    name=name,
                    city=city,
                    state=inferred_state,
                    board=board,
                    price=price,
                    students=0,
                    faculty=0,
                    subjects="Demo data",
                )
            )
            existing_keys.add(school_key)

    if rows_to_insert:
        db.session.bulk_save_objects(rows_to_insert)
        db.session.commit()


def build_filters(source):
    filters = {
        "city": (source.get("city") or "").strip(),
        "state": (source.get("state") or "").strip(),
        "board": (source.get("board") or "").strip(),
        "min_fee": (source.get("min_fee") or "").strip(),
        "max_fee": (source.get("max_fee") or "").strip(),
    }
    return filters


def apply_search_filters(query, filters):
    city = filters["city"]
    state = filters["state"]
    board = filters["board"]
    min_fee = parse_int(filters["min_fee"], min_value=0)
    max_fee = parse_int(filters["max_fee"], min_value=0)

    if min_fee is not None and max_fee is not None and min_fee > max_fee:
        min_fee, max_fee = max_fee, min_fee
        filters["min_fee"], filters["max_fee"] = str(min_fee), str(max_fee)

    if city:
        query = query.filter(School.city.ilike(f"%{city}%"))
    if state:
        query = query.filter(School.state.ilike(f"%{state}%"))
    if board:
        query = query.filter_by(board=board)
    if min_fee is not None:
        query = query.filter(School.price >= min_fee)
    if max_fee is not None:
        query = query.filter(School.price <= max_fee)

    return query


def render_home_page(schools, filters=None):
    if filters is None:
        filters = {"city": "", "state": "", "board": "", "min_fee": "", "max_fee": ""}

    return render_template(
        "home.html",
        schools=schools,
        states_with_cities=get_states_with_cities(),
        available_boards=get_available_boards(),
        selected_state=filters["state"],
        selected_city=filters["city"],
        selected_board=filters["board"],
        selected_min_fee=filters["min_fee"],
        selected_max_fee=filters["max_fee"],
    )


# ---------------- HOME + SEARCH ---------------- #

@app.route("/")
def home():
    load_demo_school_data_if_needed()
    filters = build_filters(request.args)
    schools = apply_search_filters(School.query, filters).all()
    return render_home_page(schools, filters)


@app.route("/search", methods=["POST"])
def search():
    load_demo_school_data_if_needed()
    filters = build_filters(request.form)
    clean_filters = {k: v for k, v in filters.items() if v}
    return redirect(url_for("home", **clean_filters))


# ---------------- SCHOOL DETAIL ---------------- #

@app.route("/school/<int:school_id>")
def school_detail(school_id):
    school = School.query.get_or_404(school_id)

    avg_rating = db.session.query(func.avg(Review.rating)).filter(Review.school_id == school_id).scalar()
    reviews = Review.query.filter_by(school_id=school_id).order_by(Review.id.desc()).all()

    return render_template(
        "school_detail.html",
        school=school,
        reviews=reviews,
        avg_rating=round(avg_rating, 1) if avg_rating else "No ratings",
    )


# ---------------- ADD REVIEW ---------------- #

@app.route("/add_review/<int:school_id>", methods=["POST"])
def add_review(school_id):
    if "user_id" not in session:
        flash("Please log in to add a review.", "error")
        return redirect(url_for("login"))

    rating = parse_int(request.form.get("rating"))
    comment = (request.form.get("comment") or "").strip()

    if rating is None or rating < 1 or rating > 5:
        flash("Rating must be between 1 and 5.", "error")
        return redirect(url_for("school_detail", school_id=school_id))
    if not comment:
        flash("Comment is required.", "error")
        return redirect(url_for("school_detail", school_id=school_id))

    review = Review(rating=rating, comment=comment, user_id=session["user_id"], school_id=school_id)
    db.session.add(review)
    db.session.commit()

    flash("Review submitted.", "success")
    return redirect(url_for("school_detail", school_id=school_id))


# ---------------- AUTH ---------------- #

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not username or not email or not password:
            flash("All signup fields are required.", "error")
            return render_template("signup.html")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered.", "error")
            return render_template("signup.html")

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_password, is_admin=False)

        db.session.add(new_user)
        db.session.commit()
        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            flash("Logged in successfully.", "success")
            return redirect(url_for("home"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You are logged out.", "success")
    return redirect(url_for("home"))


# ---------------- ADMIN DASHBOARD ---------------- #

@app.route("/admin", methods=["GET", "POST"])
def admin_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    if not user or not user.is_admin:
        abort(403)

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        city = (request.form.get("city") or "").strip()
        state = (request.form.get("state") or "").strip()
        board = (request.form.get("board") or "").strip()
        subjects = (request.form.get("subjects") or "").strip()
        price = parse_int(request.form.get("price"), min_value=0)
        students = parse_int(request.form.get("students"), min_value=0)
        faculty = parse_int(request.form.get("faculty"), min_value=0)

        if not all([name, city, state, board, subjects]) or board not in ALLOWED_BOARDS:
            flash("Please provide valid school details.", "error")
            return redirect(url_for("admin_dashboard"))
        if price is None or students is None or faculty is None:
            flash("Price, students, and faculty must be valid non-negative numbers.", "error")
            return redirect(url_for("admin_dashboard"))

        school = School(
            name=name,
            city=city,
            state=state,
            board=board,
            price=price,
            students=students,
            faculty=faculty,
            subjects=subjects,
        )
        db.session.add(school)
        db.session.commit()
        flash("School added successfully.", "success")
        return redirect(url_for("admin_dashboard"))

    schools = School.query.order_by(School.name.asc()).all()
    return render_template("admin_dashboard.html", schools=schools)


# ---------------- RUN ---------------- #

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
