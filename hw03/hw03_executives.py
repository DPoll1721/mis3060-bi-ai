"""
hw03_executives.py
MIS3060 - Business Intelligence with AI - HW03 (Specification B: Executive Events Pipeline)

Finds executive departures and appointments reported in SEC Form 8-K filings
(Item 5.02) over the past 12 months for five companies and saves them to
hw03/executive_events.csv.

Run from the repo root or from inside hw03/:
    python hw03/hw03_executives.py
"""

import csv
import re
import time
from datetime import date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration (same companies, CIKs and User-Agent as Specification A)
# ---------------------------------------------------------------------------
HEADERS = {"User-Agent": "MIS3060 Villanova dpollo01@villanova.edu"}
REQUEST_PAUSE = 0.2          # seconds between requests (SEC max = 10 req/sec)
NOT_FOUND = "NOT_FOUND"

COMPANIES = [
    ("Apple Inc.", "AAPL", "0000320193"),
    ("Microsoft Corporation", "MSFT", "0000789019"),
    ("NVIDIA Corporation", "NVDA", "0001045810"),
    ("JPMorgan Chase & Co.", "JPM", "0000019617"),
    ("Walmart Inc.", "WMT", "0000104169"),
]

# CSV lives next to this script, i.e. hw03/executive_events.csv
OUTPUT_CSV = Path(__file__).resolve().parent / "executive_events.csv"
CSV_COLUMNS = ["company", "ticker", "cik", "filing_date", "event_type",
               "person_name", "title", "effective_date"]


# ---------------------------------------------------------------------------
# HTTP helper - every request uses the User-Agent and pauses afterwards
# ---------------------------------------------------------------------------
def sec_get(url):
    """GET a URL with the required User-Agent, then pause 0.2 seconds."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response
    finally:
        time.sleep(REQUEST_PAUSE)


# ---------------------------------------------------------------------------
# Steps 2-3: submissions API -> 8-K / Item 5.02 filings from the past 12 months
# ---------------------------------------------------------------------------
def one_year_ago(today):
    """Same calendar day one year earlier (Feb 29 falls back to Feb 28)."""
    try:
        return today.replace(year=today.year - 1)
    except ValueError:
        return today.replace(year=today.year - 1, day=28)


def get_exec_filings(cik, cutoff):
    """Return 8-K filings whose items include 5.02 and were filed on/after cutoff."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    recent = sec_get(url).json()["filings"]["recent"]

    matches = []
    for i, form in enumerate(recent["form"]):
        items = recent["items"][i] or ""
        filing_date = recent["filingDate"][i]
        if form != "8-K" or "5.02" not in items:
            continue
        if datetime.strptime(filing_date, "%Y-%m-%d").date() < cutoff:
            continue
        matches.append({
            "accession": recent["accessionNumber"][i],
            "filing_date": filing_date,
            "primary_doc": recent["primaryDocument"][i],
        })

    matches.sort(key=lambda f: f["filing_date"], reverse=True)
    return matches


# ---------------------------------------------------------------------------
# Step 4: download the full 8-K document and strip HTML to plain text
# ---------------------------------------------------------------------------
def filing_doc_url(cik, accession, primary_doc):
    cik_no_zeros = str(int(cik))
    acc_no_dashes = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_no_zeros}/{acc_no_dashes}/{primary_doc}"


def html_to_text(html):
    """Strip HTML to plain text with whitespace collapsed."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    # Inline XBRL filings hide cover-page metadata in <ix:header>; drop it
    for tag in soup.find_all(re.compile(r"^ix:header$", re.IGNORECASE)):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = (text.replace("\xa0", " ").replace("’", "'").replace("‘", "'")
                .replace("“", '"').replace("”", '"')
                .replace("–", "-").replace("—", "-"))
    return re.sub(r"\s+", " ", text).strip()


def get_plain_text(url):
    return html_to_text(sec_get(url).content)


# ---------------------------------------------------------------------------
# Step 5a: isolate the Item 5.02 section
# ---------------------------------------------------------------------------
ITEM_502 = re.compile(r"\bItem\s*5\.02\b\.?", re.IGNORECASE)
SECTION_END = re.compile(r"\bItem\s*\d{1,2}\.\d{2}\b|\bSIGNATURES?\b", re.IGNORECASE)
# The standard Item 5.02 caption contains the words "Departure", "Election" and
# "Appointment", which would fool the classifier, so it is removed.
ITEM_502_CAPTION = re.compile(
    r"^\s*[.:\-]?\s*Departure of Directors or (?:Certain )?(?:Principal )?Officers.{0,250}?"
    r"Compensatory Arrangements of Certain Officers\.?",
    re.IGNORECASE,
)


def extract_item_502(text):
    """Return the text of the Item 5.02 section (longest candidate), or ''."""
    best = ""
    for start in ITEM_502.finditer(text):
        body_start = start.end()
        end = SECTION_END.search(text, body_start)
        section = text[body_start:end.start() if end else len(text)]
        if len(section) > len(best):
            best = section
    best = ITEM_502_CAPTION.sub("", best, count=1)
    return best.strip()


# ---------------------------------------------------------------------------
# Step 5b: split into sentences
# ---------------------------------------------------------------------------
ABBREVIATIONS = ["Mr.", "Ms.", "Mrs.", "Dr.", "Jr.", "Sr.", "Inc.", "Co.", "Corp.",
                 "No.", "St.", "U.S.", "N.A.", "Ltd."]


def split_sentences(text):
    """Sentence split that does not break on common abbreviations or initials."""
    protected = text
    for abbr in ABBREVIATIONS:
        protected = protected.replace(abbr, abbr.replace(".", "<DOT>"))
    # single capital-letter initials, e.g. "C. Douglas McMillon"
    protected = re.sub(r"\b([A-Z])\.(?=\s+[A-Z])", r"\1<DOT>", protected)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(\"])", protected)
    return [p.replace("<DOT>", ".").strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Step 6: classification hint words
#   departure:   resign, retire, step down, depart  (+ close synonyms)
#   appointment: appoint, elect, name, promote      (+ close synonyms)
# ---------------------------------------------------------------------------
DEPARTURE_HINTS = re.compile(
    r"\b(resign\w*|retire\w*|retirement|step(?:s|ped|ping)? down|depart\w*|"
    r"not (?:to )?(?:stand|seek|be nominated) for re-?election|"
    r"ceas\w* to (?:serve|be)|transition\w* (?:out of|from)|"
    r"leav\w* (?:the Company|the Board|his|her|their)|terminat\w* (?:his|her|their) employment)",
    re.IGNORECASE,
)
APPOINTMENT_HINTS = re.compile(
    r"\b(appoint\w*|(?<!re-)(?<!re)elect(?:ed|s|ing|ion)?\b|"
    r"nam(?:e|es|ed|ing)\b(?!\s+executive\s+officer)|promot\w*|"
    r"succeed\w*|successor|hired?\b|join\w* the Company)",
    re.IGNORECASE,
)


def classify(text):
    """Return a set of event types suggested by the hint words in text."""
    kinds = set()
    if DEPARTURE_HINTS.search(text):
        kinds.add("departure")
    if APPOINTMENT_HINTS.search(text):
        kinds.add("appointment")
    return kinds


def nearest_kind_before(text):
    """For text that comes BEFORE a name ("..., the Board appointed Mr. X"),
    use only the hint word closest to the name, so an earlier word like
    "retirement" in "In connection with Mr. Y's retirement, the Board
    appointed Mr. X" isn't applied to X."""
    last = None
    for kind, pattern in (("departure", DEPARTURE_HINTS), ("appointment", APPOINTMENT_HINTS)):
        for m in pattern.finditer(text):
            if last is None or m.end() > last[0]:
                last = (m.end(), kind)
    return {last[1]} if last else set()


# ---------------------------------------------------------------------------
# Person names
# ---------------------------------------------------------------------------
# One capitalized name word. Apostrophes are allowed only inside a name
# (O'Brien), never as a trailing possessive "'s" (Gawel's).
NAME_WORD = r"(?:Mc|Mac)?[A-Z][a-z]+(?:-[A-Z]?[a-z]+|'[A-Z][a-z]+)*"
FULL_NAME = re.compile(
    r"\b(?:[A-Z]\.\s+)?" + NAME_WORD +                      # optional leading initial
    r"(?:\s+[A-Z]\.)?"                                        # optional middle initial
    r"(?:\s+" + NAME_WORD + r"){1,3}"                       # 2-4 capitalized words total
    r"(?:,?\s+(?:Jr\.|Sr\.|II|III|IV))?"                     # optional suffix
)
HONORIFIC_NAME = re.compile(r"\b(?:Mr|Ms|Mrs|Dr)\.\s+(" + NAME_WORD + r")")
POSSESSIVE_AFTER = re.compile(r"^'s?\b")                     # "'s" (or bare "'") right after a name

# Words that mean a capitalized phrase is a defined term, not a person
# ("Transition Date", "Composite Index", "Compensatory Arrangements").
# Any candidate containing one of these is rejected outright.
PHRASE_WORDS = {
    "Date", "Dates", "Index", "Arrangement", "Arrangements", "Compensatory",
    "Agreement", "Agreements", "Plan", "Plans", "Transition", "Composite",
    "Period", "Term", "Terms", "Policy", "Program", "Separation", "Retention",
    "Severance", "Bonus", "Units", "Shares", "Options", "Salary", "Target",
    "Performance", "Restricted", "Letter", "Award", "Awards", "Effective",
}

# Capitalized words that are never part of a person's name
NAME_STOPWORDS = {
    # company words
    "Apple", "Microsoft", "Nvidia", "NVIDIA", "Jpmorgan", "JPMorgan", "Chase", "Walmart",
    "Inc", "Corporation", "Company", "Companies", "Corp", "Bank", "Club", "Sam's",
    # governance / titles
    "Board", "Directors", "Director", "Committee", "Compensation", "Management",
    "Nominating", "Governance", "Audit", "Chief", "Officer", "Officers", "President",
    "Vice", "Executive", "Senior", "Chairman", "Chair", "Chairwoman", "Chairperson",
    "Treasurer", "Controller", "Counsel", "General", "Secretary", "Corporate", "Global",
    "Group", "Principal", "Financial", "Operating", "Technology", "Legal", "People",
    "Accounting", "Operations", "Human", "Resources", "Independent", "Lead", "Interim",
    "Head", "International", "Retail", "Consumer", "Community", "Commercial",
    "Investment", "Asset", "Wealth", "Banking", "Markets", "Products", "Services",
    "Marketing", "Worldwide", "Hardware", "Software", "Engineering", "Strategy",
    "Division", "Segment", "Business", "Americas", "Shareholders", "Stockholders",
    # document words
    "Item", "Items", "Form", "Exhibit", "Plan", "Agreement", "Letter", "Offer",
    "Section", "Securities", "Exchange", "Commission", "Act", "Current", "Report",
    "Annual", "Meeting", "Stock", "Equity", "Incentive", "Award", "Awards", "Press",
    "Release", "Regulation", "Registrant", "Proxy", "Statement",
    # places
    "United", "States", "America", "Delaware", "California", "Washington", "Arkansas",
    "New", "York", "Santa", "Clara", "Cupertino", "Redmond", "Bentonville",
    # months / sentence starters
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December", "The", "On", "In", "As", "At",
    "Effective", "Following", "Upon", "Pursuant", "Prior", "During", "Under", "This",
    "Such", "Each", "Also", "Additionally", "Further", "Furthermore", "There", "His",
    "Her", "Their", "He", "She", "They", "We", "Our", "Its", "It", "A", "An", "If",
    "Mr", "Ms", "Mrs", "Dr", "Jr", "Sr",
}


SUFFIXES = {"Jr", "Sr", "II", "III", "IV"}


def name_words(name):
    """The full words of a name, ignoring initials ("C.") and suffixes ("Jr.")."""
    words = re.findall(r"[A-Za-z][A-Za-z'\-]*", name)
    return [w for w in words if len(w) > 1 and w not in SUFFIXES]


def trim_candidate(sentence, start, end):
    """Drop stopwords at either edge of a capitalized run, e.g.
    "On March" -> "", "Jane Doe Executive" -> "Jane Doe". Returns (start, end)."""
    tokens = [(start + t.start(), start + t.end(), t.group(0))
              for t in re.finditer(r"[A-Za-z][A-Za-z'\-]*\.?", sentence[start:end])]

    def is_edge_stopword(tok):
        return tok.rstrip(".") in NAME_STOPWORDS

    while tokens and is_edge_stopword(tokens[0][2]):
        tokens.pop(0)
    while tokens and (is_edge_stopword(tokens[-1][2]) or re.fullmatch(r"[A-Z]\.", tokens[-1][2])):
        tokens.pop()
    if not tokens:
        return None
    return tokens[0][0], tokens[-1][1]


def is_person_name(candidate):
    """2-4 capitalized words, none of them a stopword or a defined-term word."""
    words = name_words(candidate)
    if not 2 <= len(words) <= 4:
        return False
    if any(not w[0].isupper() for w in words):
        return False
    if any(w in NAME_STOPWORDS or w in PHRASE_WORDS for w in words):
        return False
    return True


def is_possessive(sentence, end):
    """True if the name ending at `end` is followed by 's (Gawel's, McMillon's)."""
    return bool(POSSESSIVE_AFTER.match(sentence[end:]))


def find_names(sentence):
    """Return [(start, end, name)] for person names in a sentence, in order.
    Full names win; "Mr. Surname" references are returned as the surname only.
    Possessives ("Mr. Gawel's", "McMillon's") are skipped."""
    found = []
    for m in FULL_NAME.finditer(sentence):
        span = trim_candidate(sentence, m.start(), m.end())
        if span is None:
            continue
        start, end = span
        name = sentence[start:end].strip(" ,")
        if is_possessive(sentence, end) or not is_person_name(name):
            continue
        found.append((start, end, name))
    for m in HONORIFIC_NAME.finditer(sentence):
        surname = m.group(1)
        overlaps = any(s <= m.start(1) < e for s, e, _ in found)
        if overlaps or surname in NAME_STOPWORDS or surname in PHRASE_WORDS:
            continue
        if is_possessive(sentence, m.end(1)):
            continue
        found.append((m.start(), m.end(), surname))
    found.sort()
    return found


def contained_in(short, long):
    """True if every word of `short` appears, in order and adjacent, inside `long`
    (initials ignored): "Nora Johnson" in "Suzanne Nora Johnson",
    "John Furner" in "John R. Furner"."""
    s, l = name_words(short), name_words(long)
    if len(s) >= len(l):
        return False
    return any(l[i:i + len(s)] == s for i in range(len(l) - len(s) + 1))


def resolve_name(name, known_full_names):
    """Turn a bare surname ("Maestri") into a full name seen elsewhere in the section."""
    if " " in name:
        return name
    for full in known_full_names:
        words = name_words(full)
        if words and words[-1] == name:
            return full
    return name


# ---------------------------------------------------------------------------
# Titles
# ---------------------------------------------------------------------------
_TITLE_PREFIX = r"(?:(?:Senior|Executive|Corporate|Group|Global|Principal|Interim|Acting|Deputy|Lead|Independent|Co-)[\s-]+)*"
_TITLE_CORE = (
    r"(?:Vice\s+)?(?:Chief\s+[A-Z][a-z]+(?:\s+(?:and\s+)?[A-Z][a-z]+){0,3}\s+Officer"
    r"|(?:Vice\s+)?President|Chairman|Chairwoman|Chairperson|Chair|Director|Controller"
    r"|Treasurer|General\s+Counsel|(?:Corporate\s+)?Secretary|Head)"
)
_ONE_TITLE = _TITLE_PREFIX + _TITLE_CORE
_OF_UNIT = r"(?:,?\s+(?:of|for)\s+(?:the\s+)?[A-Z][\w&.'\-]*(?:\s+(?:and\s+|&\s+)?[A-Z][\w&.'\-]*){0,4})?"
TITLE = re.compile(
    r"(" + _ONE_TITLE + r"(?:\s*(?:,|and|&)\s*(?:" + _ONE_TITLE + r"))*" + _OF_UNIT + r")"
)
BOARD_MEMBER = re.compile(r"\b(?:member of (?:the|its|our) Board|to (?:the|its|our) Board|"
                          r"as an? (?:independent |new )?director\b|"
                          r"(?:the|its|our) Board of Directors)", re.IGNORECASE)


def clean_title(title):
    title = re.sub(r",?\s+(?:of|for)\s+(?:the\s+)?(?:Company|Registrant|Corporation)\b.*$", "", title)
    title = re.sub(r"\s+(?:of|for)\s+(?:the\s+)?Board(?:\s+of\s+Directors)?$", " of the Board", title)
    return title.strip(" ,")


AS_TITLE = re.compile(r"\b(?:as|role of|position of|position as|role as)\s+"
                      r"(?:the\s+Company's\s+|its\s+|our\s+|the\s+|a\s+|an\s+|new\s+)*" + TITLE.pattern)


def extract_title(own_text, name, lead_in=""):
    """Find the person's title using ONLY text from the sentence that names them.
    own_text = from this person's name up to the next person's name in the sentence;
    lead_in  = text before the name, passed only when no other person is named
               earlier in the sentence (e.g. "The Board appointed ... ").
    Returns NOT_FOUND if no title is found there."""
    # 1) "... as (the Company's) Chief Financial Officer", "role/position of ..."
    m = AS_TITLE.search(own_text)
    if m:
        return clean_title(m.group(1))
    # 2) "Name, Chief Financial Officer," or "Name, the Company's Chief ..."
    after_name = re.search(re.escape(name) + r"\s*,\s*(?:\d{2}\s*,\s*)?(?:the Company's\s+|its\s+|our\s+|the\s+)?", own_text)
    if after_name:
        m = TITLE.match(own_text, after_name.end())
        if m:
            return clean_title(m.group(1))
    # 3) any title in this person's part of the sentence
    m = TITLE.search(own_text)
    if m:
        return clean_title(m.group(1))
    # 4) board seat ("to the Board of Directors", "as a director")
    if BOARD_MEMBER.search(own_text) or BOARD_MEMBER.search(lead_in):
        return "Director"
    return NOT_FOUND


# ---------------------------------------------------------------------------
# Effective dates
# ---------------------------------------------------------------------------
MONTH_DATE = r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})"
EFFECTIVE_DATE = re.compile(r"effective\s+(?:as\s+of\s+|on\s+|from\s+)?(?:the\s+close\s+of\s+business\s+on\s+)?" + MONTH_DATE, re.IGNORECASE)
AS_OF_DATE = re.compile(r"\b(?:as of|on|from|until|through)\s+" + MONTH_DATE)
EFFECTIVE_NOW = re.compile(r"effective immediately|with immediate effect", re.IGNORECASE)
LEADING_DATE = re.compile(r"^\s*On\s+" + MONTH_DATE)


def to_iso(date_text):
    try:
        return datetime.strptime(re.sub(r"\s+", " ", date_text), "%B %d, %Y").strftime("%Y-%m-%d")
    except ValueError:
        return NOT_FOUND


def extract_effective_date(window, sentence):
    m = EFFECTIVE_DATE.search(window) or EFFECTIVE_DATE.search(sentence)
    if m:
        return to_iso(m.group(1))
    if EFFECTIVE_NOW.search(window) or EFFECTIVE_NOW.search(sentence):
        lead = LEADING_DATE.search(sentence)         # "On March 3, 2026, ... effective immediately"
        if lead:
            return to_iso(lead.group(1))
    m = AS_OF_DATE.search(window)
    if m:
        return to_iso(m.group(1))
    return NOT_FOUND


# ---------------------------------------------------------------------------
# Step 5c: turn the Item 5.02 section into one event per person
# ---------------------------------------------------------------------------
def extract_events(section):
    """Return a list of dicts: event_type, person_name, title, effective_date.
    A person who both departs one role and is appointed to another is "both";
    different people in the same filing get separate rows."""
    sentences = split_sentences(section)
    known_full_names = [n for s in sentences for _, _, n in find_names(s) if " " in n]

    people = {}          # name -> {"kinds": set, "title": str, "effective_date": str}
    order = []

    for sentence in sentences:
        if not classify(sentence):
            continue
        names = find_names(sentence)
        for idx, (start, end, raw_name) in enumerate(names):
            name = resolve_name(raw_name, known_full_names)
            if len(name_words(name)) < 2:      # unresolved bare surname -> not a full name
                continue
            # Text that belongs to this person: from this name to the next name.
            next_start = names[idx + 1][0] if idx + 1 < len(names) else len(sentence)
            prev_end = names[idx - 1][1] if idx > 0 else 0
            after = sentence[start:next_start]
            before = sentence[prev_end:start]
            kinds = classify(after)
            if not kinds:
                # "X will succeed Mr. Y" / "X will replace Y": Y is the one leaving
                if re.search(r"\b(?:succeed\w*|replac\w*)\s*$", before, re.IGNORECASE):
                    kinds = {"departure"}
                else:
                    kinds = nearest_kind_before(before)
            if not kinds:
                continue
            window = before + after

            # Title text for this person (same sentence only). If the person
            # "will succeed Mr. Y as CFO", the "as CFO" sits in Y's segment,
            # so the successor's text is extended through that segment.
            own_text = after
            if idx + 1 < len(names) and re.search(r"\b(?:succeed\w*|replac\w*)\s*$", after, re.IGNORECASE):
                following_end = names[idx + 2][0] if idx + 2 < len(names) else len(sentence)
                own_text = sentence[start:following_end]
            lead_in = before if idx == 0 else ""

            if name not in people:
                people[name] = {"kinds": set(), "title": NOT_FOUND, "effective_date": NOT_FOUND}
                order.append(name)
            person = people[name]
            person["kinds"] |= kinds
            if person["title"] == NOT_FOUND:
                person["title"] = extract_title(own_text, raw_name, lead_in)
            if person["effective_date"] == NOT_FOUND:
                person["effective_date"] = extract_effective_date(window, sentence)

    # Drop a name that is contained in a longer name from the same filing
    # ("Nora Johnson" inside "Suzanne Nora Johnson").
    order = [n for n in order if not any(contained_in(n, other) for other in order if other != n)]

    events = []
    for name in order:
        kinds = people[name]["kinds"]
        event_type = "both" if len(kinds) == 2 else next(iter(kinds))
        events.append({
            "event_type": event_type,
            "person_name": name,
            "title": people[name]["title"],
            "effective_date": people[name]["effective_date"],
        })
    return events


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def main():
    today = date.today()
    cutoff = one_year_ago(today)
    print(f"Looking for 8-K Item 5.02 filings from {cutoff} to {today}")

    rows = []

    for company, ticker, cik in COMPANIES:
        print(f"\n=== {company} ({ticker}) ===")
        try:
            filings = get_exec_filings(cik, cutoff)
        except Exception as e:
            print(f"WARNING: could not load submissions for {ticker}: {e}")
            continue

        if not filings:
            print(f"{ticker}: No executive events in past 12 months")
            continue

        for filing in filings:
            try:
                url = filing_doc_url(cik, filing["accession"], filing["primary_doc"])
                text = get_plain_text(url)
                section = extract_item_502(text)
                if not section:
                    print(f"WARNING: {ticker} filing {filing['accession']} "
                          f"({filing['filing_date']}) - Item 5.02 section not found, skipping")
                    continue

                events = extract_events(section)
                if not events:
                    # e.g. a 5.02(e) filing about compensation plans only
                    print(f"{ticker} | {filing['filing_date']} | no departure/appointment "
                          f"language found (Item 5.02 may cover compensation only)")
                    continue

                for event in events:
                    row = {
                        "company": company,
                        "ticker": ticker,
                        "cik": cik,
                        "filing_date": filing["filing_date"],
                        **event,
                    }
                    rows.append(row)
                    print(f"{ticker} | {row['filing_date']} | {row['event_type']} | "
                          f"{row['person_name']} | {row['title']}")

            except Exception as e:
                print(f"WARNING: error processing {ticker} filing "
                      f"{filing.get('accession')}: {e} - skipping")
                continue

    # Always write the CSV (headers only if there are zero events)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} executive events to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
