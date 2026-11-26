"""Tabelas da base de dados."""
from sqlalchemy import Column, Integer, String, Float, Date, Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(40), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)


class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True)
    slug = Column(String(60), unique=True, index=True, nullable=False)
    nba_id = Column(Integer, unique=True, index=True)   # id oficial da NBA (fotografia e importação)
    name = Column(String(80), nullable=False)
    full_name = Column(String(120))
    birth_date = Column(Date)
    height_cm = Column(Integer)
    weight_kg = Column(Integer)
    position = Column(String(20))
    nationality = Column(String(40))
    number = Column(Integer)
    team = Column(String(60))
    team_abbr = Column(String(5))
    draft_year = Column(Integer)
    draft_round = Column(Integer)
    draft_number = Column(Integer)
    age_ref = Column(Integer)                      # idade conhecida quando ainda não há data de nascimento
    details_loaded = Column(Boolean, default=False)  # True depois de obter data de nascimento/histórico
    career = relationship("CareerStop", cascade="all,delete-orphan", order_by="CareerStop.ord")
    seasons = relationship("SeasonStat", cascade="all,delete-orphan")


class CareerStop(Base):
    __tablename__ = "career_stops"
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("players.id"), index=True)
    ord = Column(Integer)
    period = Column(String(20))
    team = Column(String(60))
    note = Column(String(80))


class SeasonStat(Base):
    """Médias por jogo da fase regular."""
    __tablename__ = "season_stats"
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("players.id"), index=True)
    season = Column(String(7))                     # ex.: 2025/26
    team = Column(String(5))
    games = Column(Integer)
    minutes = Column(Float)
    pts = Column(Float)
    reb = Column(Float)
    ast = Column(Float)
    stl = Column(Float)
    blk = Column(Float)
    tov = Column(Float)
    pf = Column(Float)
    fg_pct = Column(Float)
    tp_pct = Column(Float)
    plus_minus = Column(Float)
    __table_args__ = (UniqueConstraint("player_id", "season", name="uq_player_season"),)


class Shot(Base):
    """Um lançamento. Coordenadas no formato da NBA (1 unidade = 1/10 de pé, cesto em 0,0)."""
    __tablename__ = "shots"
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    season = Column(String(7))
    loc_x = Column(Float)
    loc_y = Column(Float)
    made = Column(Boolean)
    simulated = Column(Boolean, default=False)     # True = dados gerados para demonstração
    __table_args__ = (Index("ix_shots_player_season", "player_id", "season"),)
