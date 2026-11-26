"""Importa dados REAIS da NBA através da biblioteca nba_api (stats.nba.com).

Uso (na pasta backend):   python -m app.ingest_nba            -> todos os jogadores
                          python -m app.ingest_nba lebron-james

Requer ligação à Internet. Substitui os lançamentos simulados pelos reais e atualiza as médias por jogo.
Nota: a NBA limita pedidos; por isso há pausas entre chamadas e a importação pode falhar se for bloqueada.
"""
import sys
import time

from nba_api.stats.endpoints import PlayerCareerStats, ShotChartDetail
from sqlalchemy import select

from . import models
from .database import SessionLocal, Base, engine

PAUSE = 1.5


def api_season(label: str) -> str:          # "2025/26" -> "2025-26"
    return label.replace("/", "-")


def ingest_stats(db, p, last=5):
    df = PlayerCareerStats(player_id=p.nba_id, per_mode36="PerGame", timeout=30).get_data_frames()[0]
    df = df.drop_duplicates("SEASON_ID", keep="first").tail(last)           # TOT vem primeiro nas trocas de equipa
    for _, r in df.iterrows():
        label = r.SEASON_ID.replace("-", "/")
        label = label[:5] + label[5:].zfill(2)[-2:]
        row = db.scalar(select(models.SeasonStat).where(models.SeasonStat.player_id == p.id, models.SeasonStat.season == label)) \
            or models.SeasonStat(player_id=p.id, season=label)
        row.team, row.games, row.minutes = r.TEAM_ABBREVIATION, int(r.GP), float(r.MIN)
        row.pts, row.reb, row.ast, row.stl, row.blk, row.tov, row.pf = (float(r[c]) for c in ("PTS", "REB", "AST", "STL", "BLK", "TOV", "PF"))
        row.fg_pct, row.tp_pct = float(r.FG_PCT) * 100, float(r.FG3_PCT) * 100
        db.add(row)
    db.commit()


def ingest_shots(db, p, season):
    df = ShotChartDetail(team_id=0, player_id=p.nba_id, season_nullable=api_season(season),
                         season_type_all_star="Regular Season", context_measure_simple="FGA",
                         timeout=30).get_data_frames()[0]
    db.query(models.Shot).filter_by(player_id=p.id, season=season).delete()
    db.bulk_insert_mappings(models.Shot, [
        dict(player_id=p.id, season=season, loc_x=float(r.LOC_X), loc_y=float(r.LOC_Y),
             made=bool(r.SHOT_MADE_FLAG), simulated=False) for r in df.itertuples()])
    db.commit()
    return len(df)


def main(slugs):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for p in db.scalars(select(models.Player)):
            if slugs and p.slug not in slugs:
                continue
            print("→", p.name)
            try:
                ingest_stats(db, p); time.sleep(PAUSE)
                for s in sorted({x.season for x in p.seasons}, reverse=True)[:5]:
                    print("   lançamentos", s, ingest_shots(db, p, s)); time.sleep(PAUSE)
            except Exception as e:                      # continua com o jogador seguinte
                db.rollback()
                print("   erro:", e)


if __name__ == "__main__":
    main(sys.argv[1:])
