import re

def clean_emails(raw_list):
    seen = set()
    cleaned = []

    for raw in raw_list:
        if not raw or not isinstance(raw, str):
            continue

        e = raw.strip().lower()

        # --- Remove spaces and illegal characters ---
        e = re.sub(r'\s+', '', e)
        e = re.sub(r'[^a-z0-9._@+-]', '', e)

        # --- Fix structural issues ---
        e = e.replace("..", ".")
        e = re.sub(r'\.+@', '@', e)     # remove dots before @
        e = re.sub(r'@\.+', '@', e)     # remove dots after @
        e = re.sub(r'^\.', '', e)       # remove leading dots
        e = re.sub(r'\.$', '', e)       # remove trailing dots

        # --- Common domain corrections ---
        domain_fixes = {
            "@gmlil.": "@gmail.",
            "@gamil.": "@gmail.",
            "@gnail.": "@gmail.",
            "@hotmial.": "@hotmail.",
            "@outlok.": "@outlook.",
            "@iclouds.": "@icloud.",
            "@yahho.": "@yahoo.",
            "@webd.": "@web.de",
            "@webde.": "@web.de",
            "@gmxde.": "@gmx.de",
            "@outlookde.": "@outlook.de",
            "@freenetde.": "@freenet.de",
            "@t-online": "@t-online.de",
            "@aolde.": "@aol.de",
            "@comcastnet.": "@comcast.net",
        }
        for wrong, correct in domain_fixes.items():
            if wrong in e:
                e = e.replace(wrong, correct)

        # --- Auto-add missing top-level domains ---
        if re.match(r"^[\w\.-]+@[\w-]+$", e):  # missing dot-TLD
            if e.endswith("@gmail"):
                e += ".com"
            elif e.endswith("@hotmail") or e.endswith("@outlook") or e.endswith("@yahoo") or e.endswith("@aol") or e.endswith("@icloud"):
                e += ".com"
            elif e.endswith("@web") or e.endswith("@gmx") or e.endswith("@t-online") or e.endswith("@freenet"):
                e += ".de"
            else:
                e += ".com"  # default fallback

        # --- Validate email structure ---
        if not re.match(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$", e):
            continue

        # --- Deduplicate and store ---
        if e not in seen:
            seen.add(e)
            cleaned.append(e)

    # --- Sort neatly by domain then username ---
    cleaned.sort(key=lambda x: (x.split("@")[1], x.split("@")[0]))
    return cleaned
