"""Importa TODOS os jogadores ativos da NBA com estatísticas reais (fonte: stats.nba.com via nba_api).

Uso (na pasta backend, precisa de Internet):
    python -m app.ingest_league                         -> época atual + 4 anteriores
    python -m app.ingest_league --seasons 2026-27 2025-26

São poucos pedidos: 1 para a lista de jogadores + 1 por época (médias por jogo de toda a liga, incl. +/-).
Os restantes detalhes (data de nascimento, percurso, lançamentos) são obtidos quando se abre um jogador.
"""
import argparse
import time

from nba_api.stats.endpoints import LeagueDashPlayerStats, PlayerIndex
from sqlalchemy import select

from . import models
from .database import Base, SessionLocal, engine
from .nba_utils import (current_season_id, height_cm, jersey, label, n, previous_seasons, pt_country,
                        pt_position, stat_values, weight_kg)

PAUSE = 2


def import_players(db, season_id):
    df = PlayerIndex(season=season_id, active_nullable=1, historical_nullable=0, timeout=60).get_data_frames()[0]
    if "ROSTER_STATUS" in df:
        df = df[df.ROSTER_STATUS == 1]
    known = {p.nba_id: p for p in db.scalars(select(models.Player))}
    slugs = {p.slug for p in known.values()}
    for r in df.itertuples():
        p = known.get(int(r.PERSON_ID))
        if p is None:
            slug = r.PLAYER_SLUG or f"jogador-{r.PERSON_ID}"
            if slug in slugs:
                slug = f"{slug}-{r.PERSON_ID}"
            p = models.Player(nba_id=int(r.PERSON_ID), slug=slug, details_loaded=False)
            db.add(p)
            slugs.add(slug)
            known[p.nba_id] = p
        p.name = f"{r.PLAYER_FIRST_NAME} {r.PLAYER_LAST_NAME}".strip()
        p.full_name = p.full_name or p.name
        p.number = jersey(r.JERSEY_NUMBER)
        p.position = pt_position(r.POSITION)
        p.height_cm, p.weight_kg = height_cm(r.HEIGHT), weight_kg(r.WEIGHT)
        p.nationality = pt_country(r.COUNTRY)
        has_team = (n(r.TEAM_ID) or 0) != 0
        p.team = f"{r.TEAM_CITY or ''} {r.TEAM_NAME or ''}".strip() if has_team else "Sem equipa"
        p.team_abbr = (r.TEAM_ABBREVIATION or "FA") if has_team else "FA"
    db.commit()
    print(f"{len(df)} jogadores ativos importados.")
    return known


def import_stats(db, season_id, known, is_latest):
    df = LeagueDashPlayerStats(season=season_id, per_mode_detailed="PerGame",
                               season_type_all_star="Regular Season", timeout=90).get_data_frames()[0]
    lbl = label(season_id)
    existing = {(s.player_id, s.season): s for s in db.scalars(select(models.SeasonStat).where(models.SeasonStat.season == lbl))}
    count = 0
    for _, r in df.iterrows():
        p = known.get(int(r["PLAYER_ID"]))
        if p is None:
            continue
        s = existing.get((p.id, lbl)) or models.SeasonStat(player_id=p.id, season=lbl)
        for k, v in stat_values(r).items():
            setattr(s, k, v)
        s.team, s.plus_minus = r["TEAM_ABBREVIATION"], n(r.get("PLUS_MINUS"))
        db.add(s)
        if is_latest and n(r.get("AGE")) is not None:
            p.age_ref = int(r["AGE"])
        count += 1
    db.commit()
    print(f"{season_id}: {count} linhas de estatísticas.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", default=previous_seasons(5))
    seasons = ap.parse_args().seasons
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        known = import_players(db, current_season_id())
        db.flush()
        known = {p.nba_id: p for p in db.scalars(select(models.Player))}
        for i, s in enumerate(seasons):
            time.sleep(PAUSE)
            import_stats(db, s, known, is_latest=(i == 0))
    print("Concluído. Arranque a API com: uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
