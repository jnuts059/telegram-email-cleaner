import re
from difflib import get_close_matches

# Common email domains for typo correction
COMMON_DOMAINS = [
    "gmail.com", "yahoo.com", "ymail.com", "outlook.com", "hotmail.com",
    "icloud.com", "aol.com", "protonmail.com", "zoho.com", "live.com",
    "msn.com", "example.com", "gmx.com", "yandex.com", "me.com"
]

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

DEOBF_PATTERNS = [
    (r"\s*\(?\s*at\s*\)?\s*", "@"),
    (r"\s*\(?\s*dot\s*\)?\s*", "."),
    (r"\s*\[at\]\s*", "@"),
    (r"\s*\[dot\]\s*", "."),
    (r"\s*\(?\s*where\s*\)?\s*", "@"),
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
    # Replace multiple @ or ..
    email = re.sub(r"@{2,}", "@", email)
    email = re.sub(r"\.{2,}", ".", email)
    # Remove spaces and stray chars around @
    email = re.sub(r"\s*@\s*", "@", email)
    email = re.sub(r"\s+", "", email)
    # Remove trailing/leading dots in local part
    if "@" in email:
        local, domain = email.split("@", 1)
        local = local.strip(".")
        email = f"{local}@{domain}"
    return email

def correct_domain(email: str) -> tuple[str, bool]:
    if "@" not in email:
        return email, False
    local, domain = email.split("@", 1)
    domain = domain.strip(". ")
    # Add missing TLD (.com)
    if "." not in domain:
        guess = domain + ".com"
        if guess in COMMON_DOMAINS:
            return f"{local}@{guess}", True
    # Fuzzy correction for typos
    match = get_close_matches(domain, COMMON_DOMAINS, n=1, cutoff=0.7)
    if match:
        corrected = f"{local}@{match[0]}"
        return corrected, match[0] != domain
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
        # quick sanity cleanup again
        e = e.replace("..", ".").replace("@@", "@")
        if not is_valid(e):
            continue
        if e not in seen:
            seen.add(e)
            cleaned.append(e)
    # Sort alphabetically (domain → local part)
    cleaned.sort(key=lambda x: (x.split("@")[1], x.split("@")[0]))
    return cleaned

# === Example use ===
if __name__ == "__main__":
    raw_emails = [
        "john doe.@ymail", "john..doe@gmail.com", ".alice@yahoo.com",
        "bob[at]yahoo[dot]com", "dave@@hotmail.com", "mary@icloud",
        "peter @ protonmail . com", "eve@icloud.com ", "Eve@icloud.com",
        "frank@gnail.con", "george @ outlook . com", "carol(at)example(dot)com",
        " invalid@@@something ", "no_at_symbol.com", "jane.doe@gmail.com",
        "john.doe.@gmail.com"
    ]

    cleaned = clean_emails(raw_emails)

    print("\n✅ Cleaned & Sorted Emails:")
    for e in cleaned:
        print(" -", e)

    # Save to file
    with open("cleaned_emails.txt", "w") as f:
        for e in cleaned:
            f.write(e + "\n")

    print("\n💾 Saved to cleaned_emails.txt")