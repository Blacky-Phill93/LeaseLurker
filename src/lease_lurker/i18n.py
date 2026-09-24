"""Small built-in translation catalog for the two supported locales."""

from __future__ import annotations

from collections.abc import Callable

SUPPORTED_LOCALES = {"de", "en"}

CATALOGS: dict[str, dict[str, str]] = {
    "de": {
        "app_title": "LeaseLurker",
        "search": "Suchen",
        "search_placeholder": "Hostname, IP- oder MAC-Adresse",
        "all_leases": "Alle Leases",
        "refresh": "Jetzt aktualisieren",
        "language": "Sprache",
        "results": "Ergebnisse",
        "no_results": "Keine passenden aktiven Leases gefunden.",
        "hostname": "Hostname",
        "device_name": "Gerätename",
        "ip_address": "IP-Adresse",
        "mac_address": "MAC-Adresse",
        "vendor": "Hersteller",
        "subnet": "Subnetz",
        "subnet_navigation": "Subnetzauswahl",
        "expires": "Gültig bis",
        "remaining": "Restlaufzeit",
        "unknown": "Unbekannt",
        "empty": "Nicht gesetzt",
        "previous": "Zurück",
        "next": "Weiter",
        "page": "Seite",
        "of": "von",
        "stale_warning": "Kea ist derzeit nicht erreichbar. Angezeigt wird der Stand vom",
        "unavailable": "Lease-Daten sind derzeit nicht verfügbar.",
        "refreshed": "Aktualisiert",
        "lease_singular": "Lease",
        "lease_plural": "Leases",
        "theme_toggle": "Farbschema wechseln",
        "theme_light": "Hellen Modus aktivieren",
        "theme_dark": "Dunklen Modus aktivieren",
    },
    "en": {
        "app_title": "LeaseLurker",
        "search": "Search",
        "search_placeholder": "Hostname, IP or MAC address",
        "all_leases": "All leases",
        "refresh": "Refresh now",
        "language": "Language",
        "results": "Results",
        "no_results": "No matching active leases found.",
        "hostname": "Hostname",
        "device_name": "Device name",
        "ip_address": "IP address",
        "mac_address": "MAC address",
        "vendor": "Vendor",
        "subnet": "Subnet",
        "subnet_navigation": "Subnet selection",
        "expires": "Expires",
        "remaining": "Remaining",
        "unknown": "Unknown",
        "empty": "Not set",
        "previous": "Previous",
        "next": "Next",
        "page": "Page",
        "of": "of",
        "stale_warning": "Kea is currently unavailable. Showing data from",
        "unavailable": "Lease data is currently unavailable.",
        "refreshed": "Refreshed",
        "lease_singular": "lease",
        "lease_plural": "leases",
        "theme_toggle": "Change color theme",
        "theme_light": "Enable light mode",
        "theme_dark": "Enable dark mode",
    },
}


def select_locale(cookie: str | None, accept_language: str | None, default: str) -> str:
    if cookie in SUPPORTED_LOCALES:
        return cookie
    for item in (accept_language or "").split(","):
        candidate = item.split(";", 1)[0].strip().split("-", 1)[0].lower()
        if candidate in SUPPORTED_LOCALES:
            return candidate
    return default


def translator(locale: str) -> Callable[[str], str]:
    catalog = CATALOGS.get(locale, CATALOGS["de"])
    return lambda key: catalog.get(key, key)
