"""openfootball 队名与内部三字码映射。"""

from __future__ import annotations

import re

NAME_TO_KEY: dict[str, str] = {
    "Mexico": "MEX",
    "South Africa": "RSA",
    "South Korea": "KOR",
    "Korea Republic": "KOR",
    "Czech Republic": "CZE",
    "Czechia": "CZE",
    "Canada": "CAN",
    "Bosnia & Herzegovina": "BIH",
    "Qatar": "QAT",
    "Switzerland": "SUI",
    "Brazil": "BRA",
    "Morocco": "MAR",
    "Haiti": "HAI",
    "Scotland": "SCO",
    "USA": "USA",
    "Paraguay": "PAR",
    "Australia": "AUS",
    "Turkey": "TUR",
    "Türkiye": "TUR",
    "Germany": "GER",
    "Curaçao": "CUW",
    "Ivory Coast": "CIV",
    "Côte d'Ivoire": "CIV",
    "Ecuador": "ECU",
    "Netherlands": "NED",
    "Japan": "JPN",
    "Sweden": "SWE",
    "Tunisia": "TUN",
    "Belgium": "BEL",
    "Egypt": "EGY",
    "Iran": "IRN",
    "IR Iran": "IRN",
    "New Zealand": "NZL",
    "Spain": "ESP",
    "Cape Verde": "CPV",
    "Cabo Verde": "CPV",
    "Saudi Arabia": "KSA",
    "Uruguay": "URU",
    "France": "FRA",
    "Senegal": "SEN",
    "Iraq": "IRQ",
    "Norway": "NOR",
    "Argentina": "ARG",
    "Algeria": "ALG",
    "Austria": "AUT",
    "Jordan": "JOR",
    "Portugal": "POR",
    "DR Congo": "COD",
    "Congo DR": "COD",
    "Uzbekistan": "UZB",
    "Colombia": "COL",
    "England": "ENG",
    "Croatia": "CRO",
    "Ghana": "GHA",
    "Panama": "PAN",
}

DISPLAY_CODE: dict[str, str] = {
    "MEX": "MX", "RSA": "ZA", "KOR": "KR", "CZE": "CZ", "CAN": "CA", "BIH": "BA",
    "QAT": "QA", "SUI": "CH", "BRA": "BR", "MAR": "MA", "HAI": "HT", "SCO": "SX",
    "USA": "US", "PAR": "PY", "AUS": "AU", "TUR": "TR", "GER": "DE", "CUW": "CW",
    "CIV": "CI", "ECU": "EC", "NED": "NL", "JPN": "JP", "SWE": "SE", "TUN": "TN",
    "BEL": "BE", "EGY": "EG", "IRN": "IR", "NZL": "NZ", "ESP": "ES", "CPV": "CV",
    "KSA": "SA", "URU": "UY", "FRA": "FR", "SEN": "SN", "IRQ": "IQ", "NOR": "NO",
    "ARG": "AR", "ALG": "DZ", "AUT": "AT", "JOR": "JO", "POR": "PT", "COD": "CD",
    "UZB": "UZ", "COL": "CO", "ENG": "GB", "CRO": "HR", "GHA": "GH", "PAN": "PA",
}


def team_key(name: str) -> str:
    if name in NAME_TO_KEY:
        return NAME_TO_KEY[name]
    slug = re.sub(r"[^A-Za-z]", "", name.upper())[:3]
    return slug or "UNK"
