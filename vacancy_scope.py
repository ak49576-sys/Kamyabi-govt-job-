"""Fail-closed scope policy for vacancies collected from broad job portals."""
import re

ALLOWED_CATEGORIES = (
    "central_government",
    "state_government",
    "railways",
    "public_sector_banking",
    "armed_forces",
    "psu",
)

PRIVATE_MARKERS = re.compile(
    r"\bprivate\s+(?:sector|limited|bank)\b|\bpvt\.?\s*ltd\b|"
    r"\b(?:hdfc|icici|axis|kotak|indusind|yes)\s+bank\b",
    re.IGNORECASE,
)
CATEGORY_MARKERS = {
    "railways": re.compile(
        r"\bindian railways?\b|\brailway recruitment (?:board|cell)\b|"
        r"\b(?:rrb|rrc|ircon|irctc|dfccil|rites|rvnl|railtel|konkan railway)\b",
        re.IGNORECASE,
    ),
    "public_sector_banking": re.compile(
        r"\breserve bank of india\b|\bstate bank of india\b|"
        r"\binstitute of banking personnel selection\b|\b(?:rbi|sbi|ibps|nabard|sidbi)\b|"
        r"\b(?:bank of baroda|bank of india|canara bank|union bank of india|"
        r"indian bank|punjab national bank|central bank of india|uco bank|"
        r"bank of maharashtra|punjab and sind bank)\b",
        re.IGNORECASE,
    ),
    "armed_forces": re.compile(
        r"\bindian (?:army|navy|air force|coast guard)\b|"
        r"\barmed forces\b|\bterritorial army\b|\bassam rifles\b",
        re.IGNORECASE,
    ),
    "psu": re.compile(
        r"\bpublic sector (?:undertaking|enterprise|unit)\b|\bmaharatna\b|\bnavratna\b|"
        r"\b(?:ntpc|ongc|iocl|hpcl|bpcl|bhel|sail|gail|coal india|powergrid|"
        r"nhpc|nmdc|bel|hal|oil india|nuclear power corporation|npcil)\b",
        re.IGNORECASE,
    ),
    "central_government": re.compile(
        r"\b(?:government|govt\.?)(?: of)? india\b|\bcentral government\b|"
        r"\bministry of\b|\bunion public service commission\b|"
        r"\bstaff selection commission\b",
        re.IGNORECASE,
    ),
    "state_government": re.compile(
        r"\bstate government\b|\bstate govt\b|\bgovernment of "
        r"(?:andhra pradesh|arunachal pradesh|assam|bihar|chhattisgarh|goa|gujarat|"
        r"haryana|himachal pradesh|jharkhand|karnataka|kerala|madhya pradesh|"
        r"maharashtra|manipur|meghalaya|mizoram|nagaland|odisha|punjab|rajasthan|"
        r"sikkim|tamil nadu|telangana|tripura|uttar pradesh|uttarakhand|west bengal)\b|"
        r"\bstate public service commission\b|\bstate selection board\b",
        re.IGNORECASE,
    ),
}


def _text(record):
    fields = ("title", "employer", "employerName", "organisation", "organization",
              "department", "sector", "description")
    return " ".join(str(record.get(field, "")) for field in fields)


def _government_flag(record):
    for key in ("isGovernmentJob", "governmentJob", "is_government_job"):
        if key in record:
            value = record[key]
            return value is True or str(value).strip().lower() == "true"
    sector = str(record.get("sector", "")).strip().lower()
    return sector in {"government", "government sector", "public sector", "psu"}


def classify_vacancy(record):
    """Return one permitted category or None. Ambiguity always rejects."""
    if not isinstance(record, dict) or not _government_flag(record):
        return None
    text = _text(record)
    if PRIVATE_MARKERS.search(text):
        return None
    for category in ("railways", "public_sector_banking", "armed_forces", "psu",
                     "central_government", "state_government"):
        if CATEGORY_MARKERS[category].search(text):
            return category
    return None


def filter_allowed(records):
    allowed, rejected = [], []
    for record in records:
        category = classify_vacancy(record)
        if category:
            item = dict(record)
            item["scope_category"] = category
            allowed.append(item)
        else:
            rejected.append({"record": record, "reason": "outside or unverified government scope"})
    return allowed, rejected
