# app.py
import streamlit as st
import re
import json
import hashlib
from datetime import datetime, date
from difflib import get_close_matches
import pandas as pd

# -----------------------------
# Basic config and styling
# -----------------------------
st.set_page_config(
    page_title="CalMate 🍽️⚡",
    page_icon="🍎",
    layout="centered",
)

PRIMARY_BG = """
<style>
/* Vibrant gradient background */
.stApp {
    background: linear-gradient(135deg, #FFE6E6 0%, #FFF9E6 40%, #E6FFF3 75%, #E6F0FF 100%);
}
/* Fancy cards */
div[data-testid="stMetric"] > div {
    background: rgba(255,255,255,0.8);
    border-radius: 16px;
    padding: 14px;
}
/* Input boxes */
input, textarea {
    border-radius: 10px !important;
}
/* Colorful headers */
h1, h2, h3 {
    color: #2A2A2A;
}
.small-note {
    font-size: 0.9rem;
    color: #333;
    background: rgba(255,255,255,0.6);
    padding: 8px 12px;
    border-radius: 8px;
    display: inline-block;
}
.badge {
    display: inline-block;
    padding: 8px 12px;
    border-radius: 12px;
    font-weight: 600;
    margin-right: 8px;
}
.badge-green { background: #D9FBEA; color: #0B7A43; }
.badge-yellow { background: #FFF3C9; color: #8A6C00; }
.badge-red { background: #FFD9D9; color: #8A0B0B; }
.tip {
    background: #F7F9FC;
    border: 1px dashed #B7C4D0;
    padding: 12px;
    border-radius: 12px;
    color: #2A3A4A;
}
</style>
"""
st.markdown(PRIMARY_BG, unsafe_allow_html=True)

# -----------------------------
# Simple persistent storage
# -----------------------------
DB_FILE = "calmate_db.json"

def _hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def load_db():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"users": {}}

def save_db(db):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2)
    except Exception:
        pass  # If saving fails, session will still work

# -----------------------------
# Food calorie database (per typical serving)
# -----------------------------
FOOD_DB = {
    # Indian staples
    "roti": 80, "chapati": 80, "paratha": 180, "naan": 260, "puri": 100,
    "rice (1 cup)": 206, "brown rice (1 cup)": 215, "biryani (1 plate)": 550,
    "dal (1 cup)": 180, "sambar (1 cup)": 150, "rasam (1 cup)": 60,
    "idli (1 piece)": 58, "dosa (1):": 180, "vada (1)": 140, "uttapam (1)": 220,
    "poha (1 plate)": 250, "upma (1 bowl)": 250, "pav bhaji (1 plate)": 450,
    "chole (1 cup)": 280, "rajma (1 cup)": 260,
    "paneer butter masala (1 cup)": 450, "kadai paneer (1 cup)": 320,
    "butter chicken (1 cup)": 420, "chicken curry (1 cup)": 300,
    "mutton curry (1 cup)": 450, "fish curry (1 cup)": 320,
    "egg (1)": 78, "omelette (2 eggs)": 190,
    "maggi (1 packet)": 330,
    # Snacks & street
    "samosa (1)": 250, "pakora (5 pcs)": 300, "chicken roll (1)": 380,
    "kachori (1)": 200, "jalebi (100 g)": 400, "golgappa (6)": 150,
    # Beverages
    "chai (1 cup)": 100, "coffee (1 cup)": 60, "lassi (1 glass)": 250,
    "buttermilk (1 glass)": 70, "soda (1 can)": 140,
    # Western/common
    "pizza slice (1)": 285, "burger (1)": 500, "fries (medium)": 365,
    "sandwich (1)": 300, "pasta (1 cup)": 220,
    # Breakfast & sides
    "bread slice (1)": 70, "butter (1 tbsp)": 102, "ghee (1 tbsp)": 120,
    "curd (1 cup)": 200, "yogurt (1 cup)": 150, "milk (1 cup)": 120,
    "oats (1 cup cooked)": 160, "quinoa (1 cup cooked)": 220,
    "cornflakes (1 cup)": 100,
    # Fruits
    "apple (1)": 95, "banana (1)": 105, "orange (1)": 62, "grapes (1 cup)": 104,
    # Desserts
    "gulab jamun (1)": 150, "ladoo (1)": 185, "kheer (1 bowl)": 300, "halwa (1 bowl)": 350,
    # Salads
    "salad (1 bowl)": 120,
}

# Common synonyms map
SYNONYMS = {
    "chapathi": "chapati",
    "chapathi roti": "roti",
    "parantha": "paratha",
    "tea": "chai",
    "coffee": "coffee",
    "paneer butter": "paneer butter masala (1 cup)",
    "butter paneer": "paneer butter masala (1 cup)",
    "chicken biryani": "biryani (1 plate)",
    "veg biryani": "biryani (1 plate)",
    "curd": "yogurt (1 cup)",
    "dahi": "yogurt (1 cup)",
    "bhaji": "pav bhaji (1 plate)",
    "fried potatoes": "fries (medium)",
    "french fries": "fries (medium)",
    "omelet": "omelette (2 eggs)",
    "maggi noodles": "maggi (1 packet)",
}

# Quantity words to numbers
WORD_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "a": 1, "an": 1,
}

# -----------------------------
# Parsing and estimation helpers
# -----------------------------
def normalize_food_name(name: str) -> str:
    n = name.strip().lower()
    n = re.sub(r"\s+", " ", n)
    # Apply synonyms
    for k, v in SYNONYMS.items():
        if k in n:
            return v
    # Try exact key first
    if n in FOOD_DB:
        return n
    # Fuzzy match
    candidates = list(FOOD_DB.keys())
    match = get_close_matches(n, candidates, n=1, cutoff=0.7)
    if match:
        return match[0]
    return n  # return original for fallback estimation

def extract_quantity(text: str) -> int:
    # Look for explicit numbers
    m = re.search(r"(\d+)", text)
    if m:
        return max(1, int(m.group(1)))
    # Word numbers
    for w, v in WORD_NUM.items():
        if re.search(rf"\b{w}\b", text):
            return v
    # Common unit phrases implying 1 serving
    if re.search(r"\b(cup|bowl|plate|slice|piece|pcs|glass)\b", text):
        return 1
    return 1

def estimate_calories_free_text(item_text: str) -> tuple:
    """
    Returns (resolved_name, calories_for_item)
    """
    qty = extract_quantity(item_text)
    name = normalize_food_name(item_text)
    if name in FOOD_DB:
        # If the base name already includes serving info, quantity multiplies servings
        cals = FOOD_DB[name] * qty
        return name, cals

    # Fallback heuristics for unknown foods
    base = 150  # generic per-serving baseline
    text = item_text.lower()
    if any(w in text for w in ["fried", "deep fry", "pakora", "bhaji"]):
        base += 200
    if any(w in text for w in ["butter", "cream", "cheese", "paneer", "ghee"]):
        base += 150
    if any(w in text for w in ["sweet", "dessert", "sugar", "syrup", "jamun", "jalebi", "halwa", "kheer"]):
        base += 180
    if any(w in text for w in ["grilled", "boiled", "steamed", "salad", "soup"]):
        base -= 50
    base = max(50, base)
    return f"{item_text.strip()} (estimated)", base * qty

# -----------------------------
# Suggestions engine
# -----------------------------
ALT_SUGGESTIONS = {
    "paratha": "Swap paratha with chapati/roti 🫓 to cut oil and save ~80–100 kcal per piece.",
    "biryani": "Try veg pulao 🍚 or smaller portion biryani; pair with salad to fill up.",
    "paneer butter masala": "Choose kadai paneer 🌶️ or palak paneer; ask for less butter/ghee.",
    "fries": "Baked sweet potato wedges 🍠 or roasted chana.",
    "burger": "Grilled chicken or paneer sandwich 🥪 with whole wheat bread, skip extra cheese.",
    "pizza": "Thin-crust veggie pizza 🍕, go easy on cheese, add a side salad.",
    "samosa": "Air-fried samosa or chana chaat 🥗; limit to one.",
    "jalebi": "Fresh fruit 🍎 or a small piece of dark chocolate.",
    "halwa": "Fruit yogurt 🍓 or kheer with less sugar.",
}

def generate_alternatives(food_items: list) -> list:
    tips = []
    for f in food_items:
        key = f.lower()
        for k, msg in ALT_SUGGESTIONS.items():
            if k in key:
                tips.append(msg)
    # Generic guidance
    tips.append("Choose grilled/roasted over fried 🔥→🍽️, and ask for less butter/ghee.")
    tips.append("Add a fiber boost: salad, veggies, dal 🥗 to feel full with fewer calories.")
    return list(dict.fromkeys(tips))  # unique

def activity_suggestions(total_kcal: int) -> list:
    suggestions = []
    # Light activity ranges (very rough, for general info only)
    suggestions.append("Take a brisk walk 🚶‍♀️ 20–30 minutes after meals to support digestion and energy.")
    suggestions.append("Try 10–15 minutes of bodyweight moves 💪 (squats, lunges, planks) to feel active.")
    suggestions.append("On busy days, split short walks: 3×10 minutes 🕒.")
    if total_kcal > 2200:
        suggestions.append("If intake is higher than usual, consider a longer walk today 🌤️ or add light yoga 🧘.")
    return suggestions

# -----------------------------
# Session and user state
# -----------------------------
if "user" not in st.session_state:
    st.session_state.user = None
if "entries" not in st.session_state:
    st.session_state.entries = {}  # {date_str: [ {raw, name, kcal} ]}
if "today" not in st.session_state:
    st.session_state.today = date.today().isoformat()

# -----------------------------
# Auth UI
# -----------------------------
def auth_panel():
    st.markdown("# CalMate 🍽️⚡")
    st.markdown("Track what you eat, see calories, and get smart swaps + activity nudges. ✨")

    tab_login, tab_signup = st.tabs(["🔑 Login", "📝 Sign up"])

    with tab_login:
        st.subheader("Welcome back")
        uname = st.text_input("Username")
        pw = st.text_input("Password", type="password")
        remember = st.checkbox("Remember me on this device")
        if st.button("Login 🚀", type="primary"):
            db = load_db()
            users = db.get("users", {})
            if uname in users and users[uname]["pw"] == _hash_pw(pw):
                st.session_state.user = uname
                st.success(f"Logged in as {uname} 🎉")
                # Load user entries
                st.session_state.entries = users[uname].get("entries", {})
                if remember:
                    # Store a flag in the db
                    users[uname]["remember"] = True
                    db["users"] = users
                    save_db(db)
                st.experimental_rerun()
            else:
                st.error("Invalid credentials. Try again or sign up.")

    with tab_signup:
        st.subheader("Create your account")
        suname = st.text_input("Choose a username")
        spw = st.text_input("Choose a password", type="password")
        if st.button("Create account 🌟"):
            if not suname or not spw:
                st.warning("Please enter both username and password.")
            else:
                db = load_db()
                users = db.get("users", {})
                if suname in users:
                    st.error("Username already exists. Pick another.")
                else:
                    users[suname] = {
                        "pw": _hash_pw(spw),
                        "entries": {},
                        "remember": True,
                    }
                    db["users"] = users
                    save_db(db)
                    st.success("Account created! You can log in now.")
                    st.session_state.user = suname
                    st.session_state.entries = {}
                    st.experimental_rerun()

# -----------------------------
# Dashboard UI
# -----------------------------
def dashboard():
    user = st.session_state.user
    st.markdown(f"### Hi {user} 👋")
    st.markdown(
        "<span class='badge badge-green'>Fuel smart</span>"
        "<span class='badge badge-yellow'>Feel good</span>"
        "<span class='badge badge-red'>Have fun</span>",
        unsafe_allow_html=True
    )

    # Date selector
    today_str = st.session_state.today
    selected_date = st.date_input("Pick a date", value=datetime.fromisoformat(today_str).date())
    today_str = selected_date.isoformat()
    st.session_state.today = today_str

    # Input area
    st.markdown("#### Add what you ate 🍽️")
    st.markdown(
        "<div class='small-note'>Examples: "
        "2 roti, 1 cup dal, chicken biryani, 1 samosa, chai, paneer butter masala</div>",
        unsafe_allow_html=True
    )
    raw_text = st.text_area("Enter items separated by commas or new lines", height=120, placeholder="e.g., 2 roti, dal (1 cup), chai, 1 samosa")

    col_add, col_clear = st.columns([3,1])
    with col_add:
        if st.button("Add to today ➕", type="primary"):
            items = [i for i in re.split(r"[,\\n]+", raw_text) if i.strip()]
            added = []
            for it in items:
                name, kcal = estimate_calories_free_text(it)
                entry = {"raw": it.strip(), "name": name, "kcal": int(round(kcal))}
                st.session_state.entries.setdefault(today_str, []).append(entry)
                added.append(entry)
            if added:
                st.success(f"Added {len(added)} item(s) to {today_str} ✅")
                # Persist
                db = load_db()
                db.setdefault("users", {})
                db["users"].setdefault(user, {"pw": "", "entries": {}, "remember": True})
                db["users"][user]["entries"] = st.session_state.entries
                save_db(db)
    with col_clear:
        if st.button("Clear today 🗑️"):
            st.session_state.entries[today_str] = []
            db = load_db()
            db["users"][user]["entries"] = st.session_state.entries
            save_db(db)

    # Compute totals
    day_entries = st.session_state.entries.get(today_str, [])
    total_kcal = sum(e["kcal"] for e in day_entries)
    carbs_guess = int(total_kcal * 0.5)  # rough macro visualization
    protein_guess = int(total_kcal * 0.2)
    fat_guess = int(total_kcal * 0.3)

    # Metrics row
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Today's calories 🔢", f"{total_kcal} kcal")
    with c2:
        st.metric("Items logged 🧾", f"{len(day_entries)}")
    with c3:
        st.metric("Date 📅", today_str)

    # Macro bars (illustrative only)
    st.markdown("#### Energy breakdown (illustrative) 🌈")
    macro_df = pd.DataFrame({
        "Macro": ["Carbs", "Protein", "Fat"],
        "kcal": [carbs_guess, protein_guess, fat_guess]
    }).set_index("Macro")
    st.bar_chart(macro_df)

    # Entries table
    if day_entries:
        st.markdown("#### What you logged today 🗒️")
        st.dataframe(pd.DataFrame(day_entries), use_container_width=True)
    else:
        st.info("No items yet. Add your first entry above! ✍️")

    # Suggestions
    st.markdown("#### Smart swaps & tips 🌱")
    alt_tips = generate_alternatives([e["name"] for e in day_entries])
    for tip in alt_tips:
        st.markdown(f"- **Tip:** {tip}")

    st.markdown("#### Move a little, feel a lot 🏃")
    for s in activity_suggestions(total_kcal):
        st.markdown(f"- **Suggestion:** {s}")

    # Daily target visualization
    st.markdown("#### Daily target tracker 🎯")
    target = st.slider("Choose a daily target (kcal)", min_value=1500, max_value=3000, value=2000, step=100)
    pct = min(1.0, total_kcal / target if target else 0)
    st.progress(pct, text=f"{int(pct*100)}% of {target} kcal")

    # Logout
    st.divider()
    left, right = st.columns([1,1])
    with left:
        if st.button("Logout 🔒"):
            # Save before logout
            db = load_db()
            if st.session_state.user in db.get("users", {}):
                db["users"][st.session_state.user]["entries"] = st.session_state.entries
                save_db(db)
            st.session_state.user = None
            st.experimental_rerun()
    with right:
        if st.button("Reset account data ♻️"):
            db = load_db()
            if st.session_state.user in db.get("users", {}):
                db["users"][st.session_state.user]["entries"] = {}
                save_db(db)
            st.session_state.entries = {}
            st.success("Your data has been reset for a fresh start.")

# -----------------------------
# App entrypoint
# -----------------------------
db = load_db()
# Auto-login if "remember"
if st.session_state.user is None:
    # Try auto-login if a single remembered user exists on this device
    remembered_users = [u for u, d in db.get("users", {}).items() if d.get("remember")]
    if len(remembered_users) == 1:
        st.session_state.user = remembered_users[0]

if st.session_state.user:
    dashboard()
else:
    auth_panel()
