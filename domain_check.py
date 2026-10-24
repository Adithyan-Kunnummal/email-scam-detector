"""
Lookalike-domain check: is a domain an official brand domain, an imitation of one, or unrelated?

No model is trained. A list of official domains (an allowlist) is compared with the
domain being checked, after undoing common tricks:
  - character swaps that look alike (0->o, 1->l, 3->e, 4->a, 5->s, rn->m, vv->w)
  - small typos (one or two letters added, removed, swapped or changed)
  - extra words around the brand (auspost-refund.com, secure-ato-gov.net)
  - the official domain placed in front of another domain (my.gov.au.secure-check.com)
  - the right name on the wrong ending (telstra.co, auspost.xyz, servicesaustralia.com)

Usage:
    from domain_check import DomainChecker
    dc = DomainChecker.from_csv("data/domains_labelled.csv")   # rows with is_scam == 0 are official
    dc.check("auspost-refund.com.au")
    -> {'verdict': 'lookalike', 'imitates': 'auspost.com.au', 'reason': '...'}
"""
import csv
import re

# Registrable-domain suffixes, longest first (enough for Australian and common domains)
SUFFIXES = sorted([
    "com.au", "net.au", "org.au", "edu.au", "gov.au", "asn.au", "id.au", "vic.gov.au",
    "nsw.gov.au", "qld.gov.au", "wa.gov.au", "sa.gov.au", "tas.gov.au", "act.gov.au",
    "nt.gov.au", "com.co", "co.uk", "org.uk", "ac.uk", "co.nz", "com", "net", "org", "edu",
    "gov", "info", "au", "co", "io", "xyz", "top", "online", "site", "live", "app", "biz",
], key=lambda s: -s.count("."))
HOMOGLYPHS = [("rn", "m"), ("vv", "w"), ("0", "o"), ("1", "l"), ("3", "e"), ("4", "a"),
              ("5", "s"), ("8", "b"), ("9", "g")]
GENERIC_WORDS = {"www", "mail", "secure", "login", "verify", "account", "update", "online",
                 "support", "service", "help", "alert", "billing", "payment", "refund", "au",
                 "gov", "portal", "check", "id", "my", "official", "info", "auth", "signin"}
# Only government bodies and education providers can register these endings, so an
# address ending in them cannot be a scammer's lookalike registration.
PROTECTED_SUFFIXES = ("gov.au", "edu.au")
# Country endings sold worldwide as generic ones: the brand's exact name on these is a warning
# sign (telstra.co). On other countries' endings it is usually the brand's own overseas site or
# an unrelated organisation (vodafone.co.nz, up.pt), so the exact name alone is not flagged there.
GENERIC_COUNTRY_ENDINGS = {"co", "io", "me", "tv", "cc", "ws", "tk", "ml", "ga", "cf", "gq", "ly",
                           "to", "so", "pw", "su", "ai", "gg", "sh", "vc", "la", "st", "nu"}
# Brand names that are also everyday words: matched only as the whole name, never
# as part of a longer one (so "humanservices" or "musicservice" are not flagged).
COMMON_WORD_BRANDS = {"service", "transport", "domain", "target", "live", "seek", "belong",
                      "meta", "stan", "up", "zip", "apple", "amazon", "origin", "cyber", "uber"}


def split_domain(domain: str):
    """'login.auspost.com.au' -> ('login.auspost', 'com.au')."""
    d = domain.lower().strip().strip(".")
    for suf in SUFFIXES:
        if d.endswith("." + suf):
            return d[: -len(suf) - 1], suf
    parts = d.rsplit(".", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (d, "")


def normalise(label: str) -> str:
    s = label.lower()
    for a, b in HOMOGLYPHS:
        s = s.replace(a, b)
    return s.replace("-", "")


def damerau(a: str, b: str, cap: int = 3) -> int:
    """Edit distance counting adjacent swaps as one edit (stops early above `cap`)."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev2, prev = None, list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = a[i - 1] != b[j - 1]
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if prev2 is not None and i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        prev2, prev = prev, cur
    return prev[-1]


class DomainChecker:
    def __init__(self, official_domains, extra_official=()):
        """official_domains: real brand domains (rows labelled 0 in domains_labelled.csv).
        extra_official: other genuine domains the brands use (e.g. optusnet.com.au)."""
        self.official = {d.lower().strip() for d in list(official_domains) + list(extra_official) if d.strip()}
        # brand label = the part before the suffix, last label (auspost.com.au -> auspost;
        # my.gov.au -> mygov; service.nsw.gov.au -> servicensw)
        self.brands = {}
        for d in self.official:
            name, suf = split_domain(d)
            label = name.replace(".", "")
            if suf in {"gov.au", "nsw.gov.au", "vic.gov.au"} and len(label) <= 3 and name.count(".") == 0:
                label = label + "gov" if label == "my" else label
            self.brands.setdefault(normalise(label), d)

    @classmethod
    def from_csv(cls, path, domain_col="domain", label_col="is_scam"):
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        return cls(r[domain_col] for r in rows if str(r[label_col]).strip() == "0")

    def _is_official(self, d):
        return d in self.official or any(d.endswith("." + o) for o in self.official)

    def check(self, domain: str) -> dict:
        d = domain.lower().strip().strip(".")
        if not d:
            return {"verdict": "unknown", "imitates": None, "reason": "No domain given."}
        if self._is_official(d):
            return {"verdict": "official", "imitates": None, "reason": f"{d} is an official domain."}

        # Official domain placed at the start of a different domain: auspost.com.au.verify-id.com
        for o in self.official:
            if d.startswith(o + ".") or d.startswith(o + "-"):
                return self._hit(d, o, "puts the real address at the start of a different website")

        # An Australian ending in the MIDDLE of an address (mygov.gov.au.evil.com) means the
        # real-looking part is just a prefix on someone else's website
        m = re.search(r"\.(gov\.au|edu\.au|com\.au|net\.au|org\.au)\.", d + ".")
        if m and m.end() < len(d) + 1:
            front = d[: m.end() - 1]
            return {"verdict": "lookalike", "imitates": front,
                    "reason": f"{d} puts an Australian-looking address ({front}) at the start of a "
                              f"different website."}

        name, suf = split_domain(d)
        if suf.endswith(PROTECTED_SUFFIXES):
            return {"verdict": "unrelated", "imitates": None,
                    "reason": f"Addresses ending in .{suf} can only be registered by government "
                              "or education organisations."}
        # Look only at the registered name (last label before the ending), not at
        # subdomains of other organisations' sites (e.g. up.univ-aix.fr)
        label = name.rsplit(".", 1)[-1]
        words = [w for w in label.split("-") if w]
        joined = normalise(label)
        core = normalise("".join(w for w in words if w not in GENERIC_WORDS))
        candidates = {joined, core} | {normalise(w) for w in words}
        top = d.rsplit(".", 1)[-1]
        foreign = len(top) == 2 and top != "au" and top not in GENERIC_COUNTRY_ENDINGS

        for brand_label, o in self.brands.items():
            n = len(brand_label)
            if foreign and joined == brand_label:     # vodafone.co.nz, up.pt
                continue
            for c in candidates:
                if not c:
                    continue
                if c == brand_label:
                    return self._hit(d, o, "uses the brand name on an unofficial address")
                # typo of the brand name: allowance grows with name length; short names
                # (e.g. nab, ing) are only matched exactly, to avoid flagging unrelated sites.
                # Typos are checked on the whole name only, not on each hyphenated word
                # (so cetus-links.org is not read as a typo of linkt).
                limit = 0 if n <= 4 else (1 if n <= 8 else 2)
                if limit and c in (joined, core) and abs(len(c) - n) <= limit and damerau(c, brand_label, limit) <= limit:
                    return self._hit(d, o, "is spelled almost the same as the real address")
            # brand name embedded in a longer name: auspostrefund, commbankonline
            if n >= 5 and brand_label not in COMMON_WORD_BRANDS and brand_label in joined:
                return self._hit(d, o, "contains the brand name inside a different address")
        return {"verdict": "unrelated", "imitates": None,
                "reason": "Not an official address and does not resemble a known brand."}

    @staticmethod
    def _hit(d, o, why):
        return {"verdict": "lookalike", "imitates": o,
                "reason": f"{d} {why} ({o})."}
