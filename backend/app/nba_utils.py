"""Funções auxiliares para converter os dados da NBA (nba_api) para o nosso formato."""
import math
from datetime import date

TEAMS = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets", "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers", "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons", "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers",
    "LAC": "LA Clippers", "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies", "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves", "NOP": "New Orleans Pelicans", "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder", "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs", "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz", "WAS": "Washington Wizards", "NJN": "New Jersey Nets", "SEA": "Seattle SuperSonics",
    "NOH": "New Orleans Hornets", "NOK": "New Orleans/Oklahoma City Hornets", "VAN": "Vancouver Grizzlies",
    "CHH": "Charlotte Hornets", "WSB": "Washington Bullets",
}
POSITIONS = {"G": "Base", "F": "Extremo", "C": "Poste", "G-F": "Base/Extremo", "F-G": "Extremo/Base",
             "F-C": "Extremo/Poste", "C-F": "Poste/Extremo"}
COUNTRIES = {
    "USA": "Estados Unidos", "Canada": "Canadá", "France": "França", "Germany": "Alemanha", "Spain": "Espanha",
    "Serbia": "Sérvia", "Slovenia": "Eslovénia", "Greece": "Grécia", "Cameroon": "Camarões", "Australia": "Austrália",
    "Nigeria": "Nigéria", "Lithuania": "Lituânia", "Latvia": "Letónia", "Turkey": "Turquia", "Brazil": "Brasil",
    "Japan": "Japão", "Italy": "Itália", "Croatia": "Croácia", "Georgia": "Geórgia", "Finland": "Finlândia",
    "Sweden": "Suécia", "Ukraine": "Ucrânia", "Mexico": "México", "South Sudan": "Sudão do Sul", "Senegal": "Senegal",
    "Dominican Republic": "República Dominicana", "Bahamas": "Bahamas", "Belgium": "Bélgica", "Netherlands": "Países Baixos",
    "Switzerland": "Suíça", "Poland": "Polónia", "Czech Republic": "Chéquia", "Great Britain": "Reino Unido",
    "United Kingdom": "Reino Unido", "Israel": "Israel", "China": "China", "Egypt": "Egito", "Haiti": "Haiti",
    "DR Congo": "R.D. Congo", "Democratic Republic of the Congo": "R.D. Congo", "Congo": "Congo", "Montenegro": "Montenegro",
    "Bosnia and Herzegovina": "Bósnia e Herzegovina", "Austria": "Áustria", "Argentina": "Argentina", "Venezuela": "Venezuela",
}


def n(v):
    """Número ou None (NaN/vazio -> None)."""
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def label(season_id: str) -> str:               # "2025-26" -> "2025/26"
    return season_id.replace("-", "/")


def api_season(lbl: str) -> str:                # "2025/26" -> "2025-26"
    return lbl.replace("/", "-")


def current_season_id(today: date | None = None) -> str:
    t = today or date.today()
    y = t.year if t.month >= 10 else t.year - 1
    return f"{y}-{str(y + 1)[-2:]}"


def previous_seasons(count: int, today: date | None = None) -> list[str]:
    y = int(current_season_id(today)[:4])
    return [f"{y - i}-{str(y - i + 1)[-2:]}" for i in range(count)]


def height_cm(h):                               # "6-9" -> 206
    try:
        ft, inch = str(h).split("-")
        return round((int(ft) * 12 + int(inch)) * 2.54)
    except (ValueError, AttributeError):
        return None


def weight_kg(w):
    try:
        return round(int(float(w)) * 0.45359)
    except (ValueError, TypeError):
        return None


def jersey(j):
    j = str(j or "").strip()
    return int(j) if j.isdigit() else None


def pt_position(p):
    return POSITIONS.get(str(p or "").strip(), str(p or "").strip() or "—")


def pt_country(c):
    c = str(c or "").strip()
    return COUNTRIES.get(c, c or "—")


def stat_values(r) -> dict:
    """Linha da NBA (médias por jogo) -> campos de SeasonStat. Percentagens de 0-1 para 0-100."""
    g = lambda k: n(r[k]) if k in r else None
    pc = lambda k: (g(k) * 100 if g(k) is not None else None)
    return dict(games=int(g("GP") or 0), minutes=g("MIN"), pts=g("PTS"), reb=g("REB"), ast=g("AST"),
                stl=g("STL"), blk=g("BLK"), tov=g("TOV"), pf=g("PF"), fg_pct=pc("FG_PCT"), tp_pct=pc("FG3_PCT"))
