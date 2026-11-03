"""Weekly SP municipal rotation, Decreto 58.584/2018, art. 1.

Informational schedule only: holidays, suspensions, exemptions and the
restricted area must be considered separately before operating a vehicle.
"""
import re

DAYS = {
    "1": "Segunda-feira", "2": "Segunda-feira",
    "3": "Terça-feira", "4": "Terça-feira",
    "5": "Quarta-feira", "6": "Quarta-feira",
    "7": "Quinta-feira", "8": "Quinta-feira",
    "9": "Sexta-feira", "0": "Sexta-feira",
}


def restriction_day(plate: str) -> str | None:
    normalized = plate.replace("-", "").replace(" ", "").upper()
    if not re.fullmatch(r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}", normalized):
        return None
    return DAYS[normalized[-1]]
