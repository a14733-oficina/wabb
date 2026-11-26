"""API REST do WABB (FastAPI). Documentação automática em /docs."""
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from . import auth, details, heatmap, models
from .database import Base, engine, get_db

Base.metadata.create_all(engine)


def ensure_draft_columns():
    """Adiciona os campos do draft a bases SQLite/MySQL já existentes."""
    columns = {c["name"] for c in inspect(engine).get_columns("players")}
    with engine.begin() as conn:
        for name in ("draft_year", "draft_round", "draft_number"):
            if name not in columns:
                conn.execute(text(f"ALTER TABLE players ADD COLUMN {name} INTEGER"))


ensure_draft_columns()
app = FastAPI(title="WABB – What About Basketball", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

SORTS = {"pts", "reb", "ast", "stl", "blk", "tov", "plus_minus", "age", "name", "games"}
TREND = {"pts": "Pontos", "reb": "Ressaltos", "ast": "Assistências", "stl": "Roubos de bola", "blk": "Cortes",
         "tov": "Perdas de bola", "plus_minus": "+/-", "fg_pct": "LC%", "tp_pct": "3P%"}
SEASON_COLS = ("season", "team", "games", "minutes", "pts", "reb", "ast", "stl", "blk", "tov", "pf",
               "fg_pct", "tp_pct", "plus_minus")


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=6, max_length=128)


def current_user(request: Request, db: Session = Depends(get_db)):
    session = auth.read_session(request.cookies.get("wabb_session"))
    if not session:
        raise HTTPException(401, "Sessão terminada. Inicia sessão novamente.")
    user = db.get(models.User, int(session["sub"]))
    if not user:
        raise HTTPException(401, "Utilizador não encontrado.")
    return user


@app.post("/api/auth/register")
def register(credentials: Credentials, response: Response, db: Session = Depends(get_db)):
    username = credentials.username.strip().lower()
    if not username.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(400, "O nome de utilizador só pode conter letras, números, _ ou -.")
    if db.scalar(select(models.User).where(models.User.username == username)):
        raise HTTPException(409, "Esse utilizador já existe.")
    user = models.User(username=username, password_hash=auth.hash_password(credentials.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    response.set_cookie("wabb_session", auth.create_session(user.id, user.username), httponly=True,
                        max_age=auth.SESSION_SECONDS, samesite="lax", secure=False)
    return {"username": user.username}


@app.post("/api/auth/login")
def login(credentials: Credentials, response: Response, db: Session = Depends(get_db)):
    username = credentials.username.strip().lower()
    user = db.scalar(select(models.User).where(models.User.username == username))
    if not user or not auth.verify_password(credentials.password, user.password_hash):
        raise HTTPException(401, "Utilizador ou palavra-passe incorretos.")
    response.set_cookie("wabb_session", auth.create_session(user.id, user.username), httponly=True,
                        max_age=auth.SESSION_SECONDS, samesite="lax", secure=False)
    return {"username": user.username}


@app.get("/api/auth/me")
def me(user: models.User = Depends(current_user)):
    return {"username": user.username}


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie("wabb_session")
    return {"ok": True}


def norm(s: str) -> str:
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()


def photo(nba_id):
    return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{int(nba_id)}.png" if pd.notna(nba_id) and nba_id else None


def age_of(birth, ref=None):
    if birth is not None and pd.notna(birth):
        b = pd.to_datetime(birth).date()
        t = date.today()
        return t.year - b.year - ((t.month, t.day) < (b.month, b.day))
    return int(ref) if ref is not None and pd.notna(ref) else None


def get_player(db: Session, slug: str) -> models.Player:
    p = db.scalar(select(models.Player).where(models.Player.slug == slug))
    if not p:
        raise HTTPException(404, "Jogador não encontrado")
    return p


@app.get("/api/filters")
def filters(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    df = pd.read_sql(select(models.Player.team, models.Player.position, models.Player.nationality), db.connection())
    u = lambda c: sorted(df[c].dropna().unique().tolist())
    return {"teams": u("team"), "positions": u("position"), "nationalities": u("nationality")}


@app.get("/api/players")
def list_players(q: str = "", team: str = "", position: str = "", nationality: str = "", min_games: int = 0,
                 sort: str = "pts", page: int = 1, limit: int = 25, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Lista/pesquisa paginada. Junta jogadores e a época mais recente e filtra/ordena com Pandas."""
    con = db.connection()
    pdf = pd.read_sql(select(models.Player.__table__), con)
    if pdf.empty:
        return {"total": 0, "items": []}
    sdf = (pd.read_sql(select(models.SeasonStat.__table__), con)
           .sort_values("season", ascending=False).drop_duplicates("player_id"))
    df = pdf.merge(sdf[["player_id", "season", "games", "pts", "reb", "ast", "stl", "blk", "tov", "plus_minus"]],
                   left_on="id", right_on="player_id", how="left")
    df["age"] = pd.to_numeric(df.apply(lambda r: age_of(r.birth_date, r.age_ref), axis=1), errors="coerce")
    df["photo_url"] = df.nba_id.map(photo)
    if q:
        df = df[df["name"].map(norm).str.contains(norm(q), regex=False)]
    for col, val in (("team", team), ("position", position), ("nationality", nationality)):
        if val:
            df = df[df[col] == val]
    if min_games:
        df = df[df.games.fillna(0) >= min_games]
    sort = sort if sort in SORTS else "pts"
    df = df.sort_values(sort, ascending=sort in ("age", "name"), na_position="last")
    total, limit, page = len(df), min(max(limit, 1), 100), max(page, 1)
    df = df.iloc[(page - 1) * limit: page * limit]
    cols = ["slug", "name", "number", "team", "team_abbr", "position", "nationality", "age", "photo_url",
            "season", "games", "pts", "reb", "ast", "stl", "blk", "tov", "plus_minus"]
    out = df[cols].astype(object)
    return {"total": total, "items": out.where(out.notna(), None).to_dict("records")}


@app.get("/api/players/{slug}")
def player(slug: str, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_player(db, slug)
    details.ensure_details(db, p)                     # data de nascimento, histórico e percurso (se houver rede)
    return {"slug": p.slug, "name": p.name, "full_name": p.full_name or p.name,
            "birth_date": p.birth_date.isoformat() if p.birth_date else None,
            "age": age_of(p.birth_date, p.age_ref), "height_cm": p.height_cm, "weight_kg": p.weight_kg,
            "position": p.position, "nationality": p.nationality, "number": p.number, "team": p.team,
            "team_abbr": p.team_abbr, "nba_id": p.nba_id, "photo_url": photo(p.nba_id),
            "draft": {"year": p.draft_year, "round": p.draft_round, "number": p.draft_number},
            "career": [{"period": c.period, "team": c.team, "note": c.note} for c in p.career],
            "seasons": sorted(({k: getattr(s, k) for k in SEASON_COLS} for s in p.seasons),
                              key=lambda s: s["season"], reverse=True)}


@app.get("/api/players/{slug}/trend")
def trend(slug: str, stat: str = "pts", user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_player(db, slug)
    stat = stat if stat in TREND else "pts"
    seasons = [{k: getattr(s, k) for k in SEASON_COLS} for s in p.seasons]
    return Response(heatmap.trend_figure(seasons, stat, TREND[stat]), media_type="application/json")


def shots_df(db: Session, p: models.Player, season: str | None):
    seasons = sorted({s.season for s in p.seasons if (s.games or 0) > 0 and s.season >= "1996/97"}, reverse=True)
    if not seasons:
        raise HTTPException(404, "Sem épocas com lançamentos para este jogador")
    season = season if season in seasons else seasons[0]
    details.ensure_shots(db, p, season)               # lançamentos reais da NBA (se houver rede)
    rows = db.execute(select(models.Shot.loc_x, models.Shot.loc_y, models.Shot.made, models.Shot.simulated)
                      .where(models.Shot.player_id == p.id, models.Shot.season == season)).all()
    df = pd.DataFrame(rows, columns=["loc_x", "loc_y", "made", "simulated"])
    df["made"] = df["made"].astype(bool)
    return df, season, seasons


@app.get("/api/players/{slug}/shots/summary")
def shots_summary(slug: str, season: str | None = None, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    df, season, seasons = shots_df(db, get_player(db, slug), season)
    return {"season": season, "seasons": seasons, "available": not df.empty,
            "simulated": bool(df.simulated.any()), **heatmap.zone_summary(df)}


@app.get("/api/players/{slug}/shots/heatmap")
def shots_heatmap(slug: str, season: str | None = None, mode: str = "volume", user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    df, _, _ = shots_df(db, get_player(db, slug), season)
    return Response(heatmap.heat_figure(df, "efficiency" if mode == "efficiency" else "volume"),
                    media_type="application/json")


@app.get("/api/players/{slug}/shots/distance.png")
def shots_distance(slug: str, season: str | None = None, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    df, _, _ = shots_df(db, get_player(db, slug), season)
    if df.empty:
        raise HTTPException(404, "Sem lançamentos")
    return Response(heatmap.distance_png(df), media_type="image/png")


# O frontend é servido pela própria API (http://localhost:8000)
FRONT = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/", StaticFiles(directory=FRONT, html=True), name="frontend")
