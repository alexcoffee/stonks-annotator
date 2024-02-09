import re


def entity_overlaps(start, end, entities):
    for entity in entities:
        if start >= entity["start"] and end <= entity["end"]:
            return True
    return False


def extract_in_out(next_string, entities):
    match = re.search(r'\b(OUT|IN)\b', next_string.upper())

    if match:
        start, end = match.span()
        entities.append({"start": start, "end": end, "entity": "in_out"})

        return match.group().upper()

    return 'SKIP'


def extract_type(next_string, entities):
    match = re.search(r'\b(SCALP|SWING)\b', next_string.upper())

    if match:
        start, end = match.span()
        entities.append({"start": start, "end": end, "entity": "type"})

        return match.group().upper()

    return None


def extract_ticker(next_string, entities):
    match = re.search(r"(IN|OUT) - ([a-zA-Z]+) -", next_string.upper())

    if match is not None:
        start, end = match.span(2)
        entities.append({"start": start, "end": end, "entity": "ticker"})
        return '$' + match.group(2).lstrip('$').upper()

    match = re.search(r'\$[\w]+', next_string)

    if match is not None:
        start, end = match.span()
        entities.append({"start": start, "end": end, "entity": "ticker"})
        return '$' + match.group().lstrip('$').upper()

    return None


def extract_expiry(next_string, entities):
    next_expiry = ''

    for match in re.finditer(r"\b(0?[1-9]|1[0-2])/(0?[1-9]|[12][0-9]|3[01])\b", next_string):
        start, end = match.span()
        entities.append({"start": start, "end": end, "entity": "expiry"})
        next_expiry = match.group().upper()

    return next_expiry


def extract_strike(next_string, entities):
    out = ""
    strikes = re.finditer(r"\b\d+(\.\d{0,2})?[CP]\b", next_string.upper())

    for i, strike in enumerate(strikes):
        start, end = strike.span()
        if not entity_overlaps(start, end, entities):
            entities.append({"start": start, "end": end, "entity": "strike" if i == 0 else "strike2"})
            out = strike.group().upper()

    return out


def extract_fill(text, entities):
    # Pattern to match numbers, including those with a dollar sign and optional leading digit
    matches_iter = re.finditer(r'\$?\d*(\.\d+)?\b', text)

    def convert_to_float(match):
        num_str = match.group().lstrip('$')
        if num_str.startswith('.'):
            num_str = '0' + num_str
        elif not num_str:  # Skip empty matches resulting from the pattern
            return float('inf')  # Use 'inf' to skip in sorting
        return float(num_str)

    # Convert iterator of match objects to a list, filter out 'inf', and sort by numeric value
    sorted_matches = sorted((m for m in matches_iter if convert_to_float(m) != float('inf')), key=convert_to_float)

    for i, fill in enumerate(sorted_matches or []):
        start, end = fill.span()
        if not entity_overlaps(start, end, entities):
            entities.append({"start": start, "end": end, "entity": "fill" if i == 0 else "fill2"})

    if len(sorted_matches) > 0:
        return sorted_matches[0].group().lstrip('$')

    return ''

