from datetime import date
from decimal import Decimal
from typing import Annotated, Optional
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class CountrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: Optional[str]
    name: Optional[str]


class GenreSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class ActorSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class LanguageSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class MovieListItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    date: date
    score: float
    overview: str


class MovieListResponseSchema(BaseModel):
    movies: list[MovieListItemSchema]
    prev_page: str | None
    next_page: str | None
    total_pages: int
    total_items: int


class MovieDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    date: date
    score: float
    overview: str
    status: str
    budget: float
    revenue: float
    country: Optional[CountrySchema]
    genres: list[GenreSchema]
    actors: list[ActorSchema]
    languages: list[LanguageSchema]


class MovieCreateSchema(BaseModel):
    name: str = Field(max_length=255)
    date: date
    score: float = Field(ge=0, le=100)
    overview: str
    status: str
    budget: Annotated[Decimal, Field(ge=0)]
    revenue: Annotated[Decimal, Field(ge=0)]
    country: str
    genres: list[str]
    actors: list[str]
    languages: list[str]


class MovieStatus(str, Enum):
    released = "Released"
    post_production = "Post Production"
    in_production = "In Production"


class MovieUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = None
    date: Optional[date] = None
    score: Optional[float] = None
    overview: Optional[str] = None
    status: Optional[MovieStatus] = None
    budget: Optional[float] = None
    revenue: Optional[float] = None
