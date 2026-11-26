"""Obtém da NBA, quando é preciso, os detalhes de um jogador (carregamento "preguiçoso"):
  * ensure_details -> data de nascimento, nome completo, histórico de épocas e percurso
  * ensure_shots   -> lançamentos reais de uma época (para os mapas de calor)
Se não houver Internet (ou OFFLINE=1) nada falha: o site usa o que já está na base de dados.
"""
import os
import time
from datetime import datetime

from sqlalchemy import func, select

from . import models
from .nba_utils import TEAMS, api_season, label, n, stat_values

try:
    from nba_api.stats.endpoints import CommonPlayerInfo, PlayerCareerStats, ShotChartDetail
except ImportError:                                  # sem nba_api instalada
    CommonPlayerInfo = PlayerCareerStats = ShotChartDetail = None

OFFLINE = os.getenv("OFFLINE") == "1" or CommonPlayerInfo is None
_tried: set = set()                                  # evita repetir pedidos falhados durante a execução


def _upsert_season(db, p, season, values):
    row = next((s for s in p.seasons if s.season == season), None)
    if row is None:
        row = models.SeasonStat(player_id=p.id, season=season)
        p.seasons.append(row)
    for k, v in values.items():
        setattr(row, k, v)                           # plus_minus (só vem da liga) não é tocado


def _career(df, current_abbr):
    """Agrupa épocas consecutivas na mesma equipa -> percurso (mais recente primeiro)."""
    rows = [(r.SEASON_ID, r.TEAM_ABBREVIATION) for r in df.itertuples() if r.TEAM_ABBREVIATION != "TOT"]
    stints = []
    for sid, abbr in rows:
        y = int(sid[:4])
        if stints and stints[-1]["abbr"] == abbr and stints[-1]["end"] >= y - 1:
            stints[-1]["end"], stints[-1]["n"] = y, stints[-1]["n"] + 1
        else:
            stints.append({"abbr": abbr, "start": y, "end": y, "n": 1})
    out = []
    for i, s in enumerate(reversed(stints)):
        cur = i == 0 and s["abbr"] == current_abbr
        period = f"{s['start']} – {'atual' if cur else s['end'] + 1}"
        note = "Equipa atual" if cur else (f"{s['n']} época" + ("s" if s["n"] > 1 else ""))
        out.append((period, TEAMS.get(s["abbr"], s["abbr"]), note))
    return out


def ensure_details(db, p):
    # Se o jogador já tinha detalhes carregados numa versão anterior, mas ainda
    # não tem os campos do draft, permite uma consulta única para os completar.
    draft_loaded = p.draft_year is not None or p.draft_round is not None or p.draft_number is not None
    if (p.details_loaded and draft_loaded) or OFFLINE or ("d", p.id) in _tried or not p.nba_id:
        return
    _tried.add(("d", p.id))
    try:
        info = CommonPlayerInfo(player_id=p.nba_id, timeout=20).get_data_frames()[0].iloc[0]
        if info.get("BIRTHDATE"):
            p.birth_date = datetime.fromisoformat(str(info["BIRTHDATE"])[:10]).date()
        if not p.full_name or p.full_name == p.name:
            p.full_name = info.get("DISPLAY_FIRST_LAST") or p.name
        p.draft_year = n(info.get("DRAFT_YEAR"))
        p.draft_round = n(info.get("DRAFT_ROUND"))
        p.draft_number = n(info.get("DRAFT_NUMBER"))
        time.sleep(.6)
        df = PlayerCareerStats(player_id=p.nba_id, per_mode36="PerGame", timeout=20).get_data_frames()[0]
        for sid, grp in df.groupby("SEASON_ID", sort=False):
            r = grp.iloc[0]                           # em trocas de equipa a 1.ª linha é o total (TOT)
            values = stat_values(r)
            values["team"] = r["TEAM_ABBREVIATION"]
            _upsert_season(db, p, label(sid), values)
        if not p.career:
            for i, (a, b, c) in enumerate(_career(df, p.team_abbr)):
                p.career.append(models.CareerStop(ord=i, period=a, team=b, note=c))
        p.details_loaded = True
        db.commit()
    except Exception as e:                            # noqa: BLE001
        db.rollback()
        print(f"[nba] detalhes de {p.name} indisponíveis: {e}")


def ensure_shots(db, p, season):
    """Garante os lançamentos reais da época (substitui os simulados, se existirem)."""
    key = ("s", p.id, season)
    if OFFLINE or key in _tried or not p.nba_id:
        return
    real = db.scalar(select(func.count()).select_from(models.Shot).where(
        models.Shot.player_id == p.id, models.Shot.season == season, models.Shot.simulated.is_(False)))
    if real:
        return
    _tried.add(key)
    try:
        df = ShotChartDetail(team_id=0, player_id=p.nba_id, season_nullable=api_season(season),
                             season_type_all_star="Regular Season", context_measure_simple="FGA",
                             timeout=25).get_data_frames()[0]
    except Exception as e:                            # noqa: BLE001
        print(f"[nba] lançamentos de {p.name} {season} indisponíveis: {e}")
        return
    if df.empty:
        return
    db.query(models.Shot).filter_by(player_id=p.id, season=season).delete()
    db.bulk_insert_mappings(models.Shot, [
        dict(player_id=p.id, season=season, loc_x=float(r.LOC_X), loc_y=float(r.LOC_Y),
             made=bool(r.SHOT_MADE_FLAG), simulated=False) for r in df.itertuples()])
    db.commit()
