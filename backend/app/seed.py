"""Cria as tabelas e carrega os dados iniciais.   Uso (na pasta backend):  python -m app.seed

Os lançamentos (coordenadas) são SIMULADOS a partir das percentagens reais de cada época, para a
aplicação funcionar sem rede. Para dados reais use:  python -m app.ingest_nba
"""
import numpy as np
from .database import Base, engine, SessionLocal
from . import models
from .seed_data import PLAYERS


def gen_shots(rng, n, fg, tp, share3):
    """Gera n lançamentos coerentes com o LC% (fg) e o 3P% (tp) da época."""
    n3 = int(n * share3)
    n2 = n - n3
    npaint = int(n2 * .6)
    nmid = n2 - npaint
    px = rng.normal(0, 35, npaint).clip(-78, 78)
    py = np.abs(rng.normal(20, 35, npaint)).clip(0, 140)
    ang = rng.uniform(.1, np.pi - .1, nmid)
    r = rng.uniform(100, 225, nmid)
    mx, my = r * np.cos(ang), r * np.sin(ang)
    nc = int(n3 * .2)
    cx = rng.choice([-1, 1], nc) * rng.uniform(222, 248, nc)
    cy = rng.uniform(-40, 85, nc)
    na = n3 - nc
    ang = rng.uniform(.15, np.pi - .15, na)
    r = np.maximum(rng.normal(255, 10, na), 240)
    ax_, ay = r * np.cos(ang), r * np.sin(ang)
    x = np.concatenate([px, mx, cx, ax_])
    y = np.concatenate([py, my, cy, ay])
    p3 = tp / 100
    p2 = float(np.clip((fg / 100 * n - p3 * n3) / max(n2, 1), .2, .85))
    pp = min(p2 * 1.12, .85)                                    # perto do cesto acerta-se mais
    pm = float(np.clip((p2 * n2 - pp * npaint) / max(nmid, 1), .2, .85))
    prob = np.concatenate([np.full(npaint, pp), np.full(nmid, pm), np.full(n3, p3)])
    return x, y, rng.random(n) < prob


def main():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    rng = np.random.default_rng(2026)
    with SessionLocal() as db:
        for d in PLAYERS:
            d = dict(d)
            career, seasons, share3 = d.pop("career"), d.pop("seasons"), d.pop("share3")
            p = models.Player(**d)
            p.career = [models.CareerStop(ord=i, period=a, team=b, note=c) for i, (a, b, c) in enumerate(career)]
            p.seasons = [models.SeasonStat(**s) for s in seasons]
            db.add(p)
            db.flush()
            for s in seasons:
                n = max(40, round(s["games"] * s["pts"] * .75))
                x, y, made = gen_shots(rng, n, s["fg_pct"], s["tp_pct"], share3)
                db.bulk_insert_mappings(models.Shot, [
                    dict(player_id=p.id, season=s["season"], loc_x=float(a), loc_y=float(b), made=bool(m), simulated=True)
                    for a, b, m in zip(x, y, made)])
        db.commit()
    print("Base de dados criada com", len(PLAYERS), "jogadores.")


if __name__ == "__main__":
    main()
