import re
from difflib import get_close_matches

# Expanded list of common email domains
COMMON_DOMAINS = [
    "gmail.com", "yahoo.com", "ymail.com", "outlook.com", "hotmail.com",
    "icloud.com", "aol.com", "protonmail.com", "zoho.com", "live.com",
    "msn.com", "example.com", "gmx.com", "yandex.com", "me.com",
    "tutanota.com", "fastmail.com", "mail.com", "web.de", "gmx.de", "t-online.de"
]

# Known typos and their corrections
TYPO_CORRECTIONS = {
    "gamil.com": "gmail.com",
    "gmai.com": "gmail.com",
    "gmaill.com": "gmail.com",
    "gmaik.com": "gmail.com",
    "gmaul.com": "gmail.com",
    "gmal.com": "gmail.com",
    "gnail.com": "gmail.com",
    "gmial.com": "gmail.com",
    "gimail.com": "gmail.com",
    "gmail.con": "gmail.com",
    "gmail.co": "gmail.com",
    "gmail.cim": "gmail.com",
    "gmail.cm": "gmail.com",
    "yahho.com": "yahoo.com",
    "yaho.com": "yahoo.com",
    "yahoo.co": "yahoo.com",
    "hotmal.com": "hotmail.com",
    "hotnail.com": "hotmail.com",
    "hotmial.com": "hotmail.com",
    "hotmai.com": "hotmail.com",
    "hotmil.com": "hotmail.com",
    "outlok.com": "outlook.com",
    "outllok.com": "outlook.com",
    "outloook.com": "outlook.com",
    "icloud.co": "icloud.com",
    "protonmaill.com": "protonmail.com",
    "proton.me.": "proton.me",
    "gmxde": "gmx.de",
    "webd.de": "web.de"
}

# Email regex pattern
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

# Text normalization patterns
DEOBF_PATTERNS = [
    (r"\s*\(?\s*at\s*\)?\s*", "@"),
    (r"\s*\(?\s*dot\s*\)?\s*", "."),
    (r"\s*\[at\]\s*", "@"),
    (r"\s*\[dot\]\s*", "."),
    (r"\s*@,\.*\s*", "@"),  # fixes @,.gmai.com etc.
    (r"\s+@\s+", "@"),
]

def deobfuscate(s: str) -> str:
    s = s.strip().lower()
    for pat, repl in DEOBF_PATTERNS:
        s = re.sub(pat, repl, s, flags=re.IGNORECASE)
    return s

def normalize(email: str) -> str:
    email = deobfuscate(email)
    email = email.strip("<>\"' ,;:!()[]")
    email = re.sub(r"@{2,}", "@", email)
    email = re.sub(r"\.{2,}", ".", email)
    email = re.sub(r"\s*@\s*", "@", email)
    email = re.sub(r"\s+", "", email)
    email = re.sub(r"@[,\.]+", "@", email)
    if "@" in email:
        local, domain = email.split("@", 1)
        local = local.strip(".")
        domain = domain.strip(".")
        email = f"{local}@{domain}"
    return email

def correct_domain(email: str) -> tuple[str, bool]:
    if "@" not in email:
        return email, False
    local, domain = email.split("@", 1)
    domain = domain.strip().lower()

    # Apply typo corrections
    if domain in TYPO_CORRECTIONS:
        return f"{local}@{TYPO_CORRECTIONS[domain]}", True

    # Add missing TLD if domain looks like gmail or yahoo
    if "." not in domain:
        guess = domain + ".com"
        if guess in COMMON_DOMAINS:
            return f"{local}@{guess}", True

    # Fuzzy matching for close domains
    match = get_close_matches(domain, COMMON_DOMAINS, n=1, cutoff=0.7)
    if match:
        return f"{local}@{match[0]}", True

    return f"{local}@{domain}", False

def is_valid(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email))

def clean_emails(raw_list):
    seen = set()
    cleaned = []
    for raw in raw_list:
        if not raw or not isinstance(raw, str):
            continue
        e = normalize(raw)
        e, fixed = correct_domain(e)
        e = e.replace("..", ".").replace("@@", "@")
        if not is_valid(e):
            continue
        if e not in seen:
            seen.add(e)
            cleaned.append(e)
    cleaned.sort(key=lambda x: (x.split("@")[1], x.split("@")[0]))
    
    # Save result as text file
    with open("cleaned_emails.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned))
    
    return cleaned

# Example test
if __name__ == "__main__":
    test_emails = [
        "james059@,.gmai.com",
        "john.doe@gmil.con",
        "mary @ yahho . com",
        "peter@outlok.com",
        "frank@icloud.co",
        "bob@webd.de",
        "tom@@hotmail.com",
    ]

    cleaned = clean_emails(test_emails)
    print("\n✅ Cleaned Emails:")
    for e in cleaned:
        print(" -", e)

    print("\n💾 Saved as cleaned_emails.txt")
