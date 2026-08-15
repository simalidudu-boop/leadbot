"""
config.py — central configuration loader.

Reads .env, exposes typed settings, defines country metadata, defaults,
templates seed data, and scoring rules. All other modules import from here.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load .env from the project root (one level up from this file's parent)
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


# ────────────────────────────────────────────────────────────────────
# Logging
# ────────────────────────────────────────────────────────────────────
def _setup_logging() -> logging.Logger:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    return logging.getLogger("leadbot")


log = _setup_logging()


# ────────────────────────────────────────────────────────────────────
# Country metadata
# ────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Country:
    code: str                  # ISO 3166-1 alpha-2
    name: str
    lat: float                 # capital / centroid
    lng: float
    bbox_km: float             # search radius from centroid (start small)
    cities: list[str] = field(default_factory=list)
    timezone_offset_hours: int = 2     # vs UTC
    yellowpages_url: str = ""

    def utc_offset(self) -> int:
        return self.timezone_offset_hours


# Curated city centroids. The scraper fans out from each.
COUNTRIES: dict[str, Country] = {
    "ZA": Country(
        code="ZA", name="South Africa",
        lat=-26.2041, lng=28.0473, bbox_km=40,
        cities=[
            "Johannesburg", "Sandton", "Pretoria", "Cape Town", "Durban",
            "Port Elizabeth", "Bloemfontein", "East London", "Polokwane",
            "Nelspruit", "Kimberley", "Rustenburg", "Pietermaritzburg",
        ],
        timezone_offset_hours=2,
        yellowpages_url="https://www.yellowpages.co.za/",
    ),
    "ZW": Country(
        code="ZW", name="Zimbabwe",
        lat=-17.8252, lng=31.0335, bbox_km=30,
        cities=[
            "Harare", "Bulawayo", "Mutare", "Gweru", "Masvingo",
            "Kwekwe", "Chitungwiza", "Epworth", "Norton", "Marondera",
        ],
        timezone_offset_hours=2,
        yellowpages_url="https://www.yellowpages.co.zw/",
    ),
    "ZM": Country(
        code="ZM", name="Zambia",
        lat=-15.3875, lng=28.3228, bbox_km=30,
        cities=[
            "Lusaka", "Kitwe", "Ndola", "Kabwe", "Chingola",
            "Mufulira", "Livingstone", "Luanshya", "Kasama",
        ],
        timezone_offset_hours=2,
        yellowpages_url="https://www.yellowpages.co.zm/",
    ),
    "BW": Country(
        code="BW", name="Botswana",
        lat=-24.6282, lng=25.9231, bbox_km=30,
        cities=[
            "Gaborone", "Francistown", "Molepolole", "Maun", "Serowe",
            "Selibe Phikwe", "Kanye", "Mahalapye",
        ],
        timezone_offset_hours=2,
        yellowpages_url="https://www.yellowpages.co.bw/",
    ),
    "KE": Country(
        code="KE", name="Kenya",
        lat=-1.2921, lng=36.8219, bbox_km=40,
        cities=[
            "Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret",
            "Thika", "Nyeri", "Machakos", "Meru", "Kitale",
        ],
        timezone_offset_hours=3,
        yellowpages_url="https://www.yellowpages.co.ke/",
    ),
}


def active_countries() -> list[Country]:
    raw = os.getenv("COUNTRIES", "ZA,ZW,ZM,BW,KE")
    codes = [c.strip().upper() for c in raw.split(",") if c.strip()]
    return [COUNTRIES[c] for c in codes if c in COUNTRIES]


# ────────────────────────────────────────────────────────────────────
# Settings
# ────────────────────────────────────────────────────────────────────
@dataclass
class Settings:
    # AI
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = ""
    mistral_api_key: str = ""
    cohere_api_key: str = ""
    groq_api_key: str = ""

    # Scrapers
    geoapify_key: str = ""
    serpapi_key: str = ""
    yelp_api_key: str = ""
    opencorporates_key: str = ""

    # Hosting
    github_token: str = ""
    github_demo_org: str = ""
    cloudflare_pages_api_token: str = ""
    cloudflare_pages_account_id: str = ""
    netlify_token: str = ""

    # Email
    gmail_webhook_url: str = ""
    brevo_api_key: str = ""
    resend_api_key: str = ""
    mailersend_api_key: str = ""
    from_email: str = "hello@example.com"
    from_name: str = "Your Name"

    # Discord
    discord_webhook_url: str = ""

    # Google Sheets
    sheets_credentials: str = ""          # file path OR base64 JSON
    sheet_id: str = ""

    # Legacy — kept for backward compat but unused
    google_sheets_credentials: str = ""
    google_sheet_id: str = ""

    # Notion CRM
    notion_api_key: str = ""
    notion_database_id: str = ""
    notion_parent_page_id: str = ""

    # Socials
    instagram_username: str = ""
    instagram_password: str = ""
    facebook_page_access_token: str = ""

    # Bot behavior
    daily_email_cap: int = 20
    warmup_days: int = 14
    send_window_local_start: int = 9
    send_window_local_end: int = 11
    lead_page_size: int = 20
    dry_run: bool = False

    # Derived
    countries: list[Country] = field(default_factory=list)
    timezone_offsets: dict[str, int] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Settings":
        s = cls()

        # AI
        s.cloudflare_account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
        s.cloudflare_api_token = os.getenv("CLOUDFLARE_API_TOKEN", "")
        s.mistral_api_key = os.getenv("MISTRAL_API_KEY", "")
        s.cohere_api_key = os.getenv("COHERE_API_KEY", "")
        s.groq_api_key = os.getenv("GROQ_API_KEY", "")

        # Scrapers
        s.geoapify_key = os.getenv("GEOAPIFY_KEY", "")
        s.serpapi_key = os.getenv("SERPAPI_KEY", "")
        s.yelp_api_key = os.getenv("YELP_API_KEY", "")
        s.opencorporates_key = os.getenv("OPENCORPORATES_KEY", "")

        # Hosting
        s.github_token = os.getenv("GITHUB_TOKEN", "")
        s.github_demo_org = os.getenv("GITHUB_DEMO_ORG", "")
        s.cloudflare_pages_api_token = os.getenv("CLOUDFLARE_PAGES_API_TOKEN", "")
        s.cloudflare_pages_account_id = os.getenv("CLOUDFLARE_PAGES_ACCOUNT_ID", "")
        s.netlify_token = os.getenv("NETLIFY_TOKEN", "")

        # Email
        s.gmail_webhook_url = os.getenv("GMAIL_WEBHOOK_URL", "")
        s.brevo_api_key = os.getenv("BREVO_API_KEY", "")
        s.resend_api_key = os.getenv("RESEND_API_KEY", "")
        s.mailersend_api_key = os.getenv("MAILERSEND_API_KEY", "")
        s.from_email = os.getenv("FROM_EMAIL", "hello@example.com")
        s.from_name = os.getenv("FROM_NAME", "Your Name")

        # Discord
        s.discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "")

        # Sheets
        s.sheets_credentials = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "")
        s.sheet_id = os.getenv("GOOGLE_SHEET_ID", "")

        # Notion CRM
        s.notion_api_key = os.getenv("NOTION_API_KEY", "")
        s.notion_database_id = os.getenv("NOTION_DATABASE_ID", "")
        s.notion_parent_page_id = os.getenv("NOTION_PARENT_PAGE_ID", "")

        # Socials
        s.instagram_username = os.getenv("INSTAGRAM_USERNAME", "")
        s.instagram_password = os.getenv("INSTAGRAM_PASSWORD", "")
        s.facebook_page_access_token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "")

        # Behavior
        try:
            s.daily_email_cap = int(os.getenv("DAILY_EMAIL_CAP", "20"))
        except ValueError:
            s.daily_email_cap = 20
        try:
            s.warmup_days = int(os.getenv("WARMUP_DAYS", "14"))
        except ValueError:
            s.warmup_days = 14
        try:
            s.send_window_local_start = int(os.getenv("SEND_WINDOW_LOCAL_START", "9"))
        except ValueError:
            s.send_window_local_start = 9
        try:
            s.send_window_local_end = int(os.getenv("SEND_WINDOW_LOCAL_END", "11"))
        except ValueError:
            s.send_window_local_end = 11
        try:
            s.lead_page_size = int(os.getenv("LEAD_PAGE_SIZE", "20"))
        except ValueError:
            s.lead_page_size = 20

        s.dry_run = os.getenv("DRY_RUN", "false").lower() in ("1", "true", "yes")
        s.countries = active_countries()
        s.timezone_offsets = {
            c.code: c.timezone_offset_hours for c in s.countries
        }

        return s


# ────────────────────────────────────────────────────────────────────
# Lead scoring
# ────────────────────────────────────────────────────────────────────
SCORE_RULES = {
    "no_website": 10,
    "no_socials": 5,
    "has_phone": 3,
    "has_address": 2,
    "in_official_registry": 3,
    "high_value_category": 2,   # trades/professional services/retail
    "multi_source_match": 4,    # found by 2+ scrapers
    "country_priority": 2,      # ZA, KE
}


def score_lead(lead: dict[str, Any]) -> tuple[int, dict[str, int]]:
    """Return (total_score, breakdown). Higher = better."""
    breakdown: dict[str, int] = {}

    if not lead.get("website"):
        breakdown["no_website"] = SCORE_RULES["no_website"]
    if not (lead.get("instagram") or lead.get("facebook")
            or lead.get("linkedin") or lead.get("tiktok")):
        breakdown["no_socials"] = SCORE_RULES["no_socials"]
    if lead.get("phone") and lead["phone"] not in ("", "N/A", None):
        breakdown["has_phone"] = SCORE_RULES["has_phone"]
    if lead.get("address") and lead["address"] not in ("", "N/A", None):
        breakdown["has_address"] = SCORE_RULES["has_address"]
    if lead.get("registry_hit"):
        breakdown["in_official_registry"] = SCORE_RULES["in_official_registry"]
    if _is_high_value_category(lead.get("category", "")):
        breakdown["high_value_category"] = SCORE_RULES["high_value_category"]
    if lead.get("source_count", 1) >= 2:
        breakdown["multi_source_match"] = SCORE_RULES["multi_source_match"]
    if lead.get("country") in ("ZA", "KE"):
        breakdown["country_priority"] = SCORE_RULES["country_priority"]

    return sum(breakdown.values()), breakdown


HIGH_VALUE_CATEGORIES = {
    "trades", "plumber", "electrician", "roofer", "builder", "carpenter",
    "hvac", "mechanic", "panel_beater", "towing",
    "hairdresser", "barber", "beauty", "salon", "spa", "nails",
    "restaurant", "cafe", "bakery", "butchery", "tavern", "eatery",
    "guest_house", "lodge", "bnb", "hotel", "accommodation",
    "clinic", "doctor", "dentist", "physio", "vet",
    "lawyer", "attorney", "accountant", "consultant", "agency",
    "shop", "store", "boutique", "pharmacy", "hardware",
    "school", "tutor", "driving_school", "creche",
    "gym", "fitness", "yoga", "martial_arts",
    "auto", "car_dealer", "car_wash", "tyres",
    "florist", "events", "wedding", "photography", "videography",
    "logistics", "courier", "moving", "trucking",
    "agriculture", "farm", "nursery", "landscaping",
    "cleaning", "laundry", "pest_control", "security",
    "tailor", "clothing", "fashion",
    "construction", "civil_engineering", "architect",
}


def _is_high_value_category(category: str) -> bool:
    if not category:
        return False
    c = category.lower()
    return any(tok in c for tok in HIGH_VALUE_CATEGORIES)


# ────────────────────────────────────────────────────────────────────
# Templates — seed data; the Sheets `Templates` tab is the source of truth
# after first run, this is just the bootstrap.
# ────────────────────────────────────────────────────────────────────
DEFAULT_TEMPLATES: dict[str, dict[str, str]] = {
    "email_initial": {
        "subject": "I built a quick website mockup for {{name}}",
        "body": (
            "Hi {{name}},\n\n"
            "I came across {{business_name}} in {{city}} and noticed you don't "
            "have a website yet — which means customers searching Google for "
            "{{category}} in your area can't find you.\n\n"
            "I made a free demo mockup for you (took me 5 minutes):\n"
            "{{demo_url}}\n\n"
            "If you like the look, I can have the real version live on "
            "{{suggested_domain}} within 48 hours — fully mobile-friendly, "
            "with WhatsApp click-to-chat, Google Maps, and your hours/services "
            "all wired up.\n\n"
            "Reply YES if you'd like a quote, or NO if not interested.\n\n"
            "Cheers,\n{{sender_name}}\n{{sender_email}}\n\n"
            "P.S. If you'd rather I didn't email again, just reply STOP.\n"
        ),
    },
    "email_followup_1": {
        "subject": "Re: I built a quick website mockup for {{name}}",
        "body": (
            "Hi {{name}},\n\n"
            "Just bumping this — did you get a chance to look at the mockup?\n"
            "Here's the link again: {{demo_url}}\n\n"
            "If now isn't the right time, totally understand. Otherwise I'm "
            "happy to jump on a 10-min WhatsApp call to walk through what "
            "the finished site would include.\n\n"
            "{{sender_name}}\n"
        ),
    },
    "email_followup_2": {
        "subject": "Quick question about {{business_name}}",
        "body": (
            "Hi {{name}},\n\n"
            "One quick question: is the lack of a website costing you "
            "customers, or are you mostly word-of-mouth? Either way is fine — "
            "just want to know if the mockup would be useful.\n\n"
            "Here's the demo again in case: {{demo_url}}\n\n"
            "{{sender_name}}\n"
        ),
    },
    "email_followup_final": {
        "subject": "Closing the loop — last email from me",
        "body": (
            "Hi {{name}},\n\n"
            "This is my last follow-up on the website mockup. No hard "
            "feelings if the timing's off — I know running a business in "
            "{{city}} keeps you busy.\n\n"
            "The demo will stay live for a few more months at {{demo_url}}, "
            "in case you change your mind.\n\n"
            "Wishing you a great week.\n\n"
            "{{sender_name}}\n"
        ),
    },
    "dm_instagram": {
        "body": (
            "Hi {{name}} 👋 I made a quick website mockup for "
            "{{business_name}} — figured I'd DM since I couldn't find an "
            "email. Check it out: {{demo_url}} . "
            "Cheers, {{sender_name}}"
        ),
    },
    "dm_facebook": {
        "body": (
            "Hi {{name}}, I made a free website mockup for "
            "{{business_name}}: {{demo_url}} . Let me know if you'd like "
            "the real version. — {{sender_name}}"
        ),
    },
}


# ────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────
LEAD_COLUMNS = [
    "name", "country", "city", "category", "address", "phone", "email",
    "website", "instagram", "facebook", "linkedin", "tiktok", "source",
    "lead_score", "status", "demo_url", "screenshot_url", "first_sent_at",
    "last_touch_at", "followup_count", "notes", "lead_id", "score_breakdown",
]

VALID_STATUSES = {
    "New", "Contacted", "No Response", "Interested", "Bought",
    "Not Interested", "Bounced", "Paused",
}

NO_EMAIL_COLUMNS = [
    "name", "country", "city", "category", "address", "phone", "website",
    "instagram", "facebook", "linkedin", "tiktok", "source", "lead_score",
    "discord_notified_at", "dm_attempted_at", "dm_status", "lead_id",
]

# Big chains/brands that show up in OSM but always have a real site elsewhere
CHAIN_BLACKLIST = [
    "mica", "cashbuild", "builders warehouse", "builders", "talisman",
    "chamberlains", "pennypincher", "makro", "game", "build it",
    "ritebuild", "plumlink", "bathroom bizarre", "voltex",
    "totalenergies", "total energies", "engen", "shell", "bp ", "sasol",
    "caltex", "puma energy",
    "pick n pay", "woolworths", "checkers", "spar", "shoprite",
    "edgars", "jet", "mr price", "ackermans", "pep", "truworths",
    "clicks", "dis-chem", "dischem",
    "mtn", "vodacom", "telkom", "rain", "cell c", "cell-c",
    "standard bank", "fnb", "absa", "nedbank", "capitec",
    "debonairs", "kfc", "nando's", "nandos", "steers", "wimpy",
    "mcdonald", "burger king", "kfc", "dominos", "pizza hut",
    "amazon", "takealot", "bid or buy", "bidorbuy", "makro",
    "uber", "bolt", "taxify",
]


def is_chain(name: str) -> bool:
    if not name:
        return False
    lname = name.lower()
    return any(b in lname for b in CHAIN_BLACKLIST)
