"""Reject unrelated streets and municipalities returned by fuzzy providers."""
import re
import unicodedata
from difflib import SequenceMatcher
from app.services.route_planning import normalize_geocoding_address


def plain(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value.lower()) if not unicodedata.combining(c))


def street_name(value):
    value = re.sub(r'^(rua|avenida|estrada|travessa|viela|praca)\s+', '', plain(value))
    return value.strip().replace('ph', 'f')


def street_matches(address, result):
    normalized = normalize_geocoding_address(address)
    city = re.search(r',\s*([^,]+),\s*[A-Z]{2}(?:\s*,|\s*$)', normalized)
    if not city:
        return []
    expected_city = plain(city[1].strip())
    expected_street = street_name(normalized.split(',')[0])
    preceding = normalized[:city.start()].rstrip(' ,').split(',')[-1].strip()
    candidates = []
    for point in result.get('candidates', []):
        parts = [plain(part.strip()) for part in point['address'].split(',')]
        if not point.get('street_found') or expected_city not in parts:
            continue
        actual_street = street_name(parts[0])
        if re.findall(r'\d+', expected_street) != re.findall(r'\d+', actual_street):
            continue
        if len(expected_street) < 3 and not any(plain(preceding) in part for part in parts[1:]):
            continue
        if actual_street != expected_street and (len(expected_street) < 6 or SequenceMatcher(None, expected_street, actual_street).ratio() < .9):
            continue
        candidates.append(point)
    # Prefer matching neighborhood segments when a street has multiple results.
    candidates.sort(key=lambda p: -sum(len(part.strip()) for part in p['address'].split(',')[1:]
                                      if len(part.strip()) > 3 and plain(part.strip()) in plain(normalized)))
    return candidates
