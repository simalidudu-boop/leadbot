"""
ai/prompts.py — the prompts sent to whatever LLM provider we end up using.
Edit these to taste.
"""

SYSTEM_PROMPT = """You are an expert web designer who creates beautiful, modern,
single-page business websites. You output only valid, self-contained HTML
with inline CSS. No JavaScript frameworks. No external dependencies.
The site must be mobile-responsive and look like a real, professional
small-business website (not a template placeholder). Use a tasteful color
palette appropriate to the industry. Include realistic, on-brand copy.
Add a contact section with clickable WhatsApp, tel:, and mailto: links
when the info is available.
"""

SITE_PROMPT = """Generate a complete single-file HTML page for this small business.

Business name: {name}
Industry/category: {category}
City, country: {city}, {country}
Address: {address}
Phone: {phone}
Email: {email}
Hours (guess based on industry if not given): Mon–Fri 8am–5pm, Sat 9am–1pm
Social handles: {socials}

Requirements:
- One self-contained HTML file with inline CSS (no external assets)
- Sections: Header (with business name), Hero, About, Services, Why Choose
  Us, Testimonials (2-3 realistic fictional ones — make them feel real for
  the local market), Contact (with clickable tel:, mailto:, WhatsApp, and
  Google Maps link if address present), Footer
- Use a tasteful color palette appropriate to the industry. Provide both
  --primary and --accent CSS variables.
- Use a Google Fonts link in the <head> (we will keep it but it should not
  break layout if it fails to load).
- Mobile-first responsive (looks great on a 360px screen).
- All copy must be in English unless the city/country clearly suggests
  another language (e.g. use French in some ZA/ZM areas, Swahili in KE).
  Default: English.
- Add a clickable WhatsApp button using this format:
  https://wa.me/{{country_code}}?text=Hi%20{{encoded_name}}
  where country_code is the international dial code (ZA=27, ZW=263,
  ZM=260, BW=267, KE=254). If phone is given, use that; otherwise omit
  the WhatsApp button.
- The whole HTML must be under 25 KB.

Output only the HTML. No commentary, no markdown fences, no preamble."""


# Country code map for the WhatsApp link
DIAL_CODES = {
    "ZA": "27", "ZW": "263", "ZM": "260", "BW": "267", "KE": "254",
}

COUNTRY_NAMES = {
    "ZA": "South Africa", "ZW": "Zimbabwe", "ZM": "Zambia",
    "BW": "Botswana", "KE": "Kenya",
}
