from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from database import get_db
from database.models import (
    MovieModel,
    CountryModel,
    GenreModel,
    ActorModel,
    LanguageModel,
    MovieStatusEnum,
)

from schemas.movies import (
    MovieListResponseSchema,
    MovieDetailSchema,
    MovieCreateSchema,
    MovieUpdateSchema,
    MovieStatus,
)


router = APIRouter(prefix="/movies")


@router.get("/", response_model=MovieListResponseSchema)
async def get_movies(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    total_query = await db.execute(select(func.count(MovieModel.id)))
    total_items = total_query.scalar_one()
    total_pages = (total_items + per_page - 1) // per_page

    if total_items == 0 or page > total_pages:
        raise HTTPException(status_code=404, detail="No movies found.")

    offset = (page - 1) * per_page
    result = await db.execute(
        select(MovieModel)
        .order_by(MovieModel.id.desc())
        .offset(offset)
        .limit(per_page)
        .options(
            selectinload(MovieModel.country),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages),
        )
    )
    movies = result.scalars().all()

    BASE_PATH = "/theater/movies/"
    next_page = (
        f"{BASE_PATH}?page={page + 1}&per_page={per_page}"
        if page < total_pages
        else None
    )
    prev_page = (
        f"{BASE_PATH}?page={page - 1}&per_page={per_page}"
        if page > 1
        else None
    )

    return {
        "movies": movies,
        "prev_page": prev_page,
        "next_page": next_page,
        "total_pages": total_pages,
        "total_items": total_items,
    }


@router.get("/{movie_id}/", response_model=MovieDetailSchema)
async def get_movie_details(
    movie_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(MovieModel)
        .where(MovieModel.id == movie_id)
        .options(
            selectinload(MovieModel.country),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages),
        )
    )
    result = await db.execute(query)
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found.",
        )

    return movie


@router.post("/", response_model=MovieDetailSchema, status_code=status.HTTP_201_CREATED)
async def create_movie(
        movie_data: MovieCreateSchema,
        db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(MovieModel).where(
            MovieModel.name == movie_data.name,
            MovieModel.date == movie_data.date,
        )
    )
    existing_movie = existing.scalar_one_or_none()
    if existing_movie:
        raise HTTPException(
            status_code=409,
            detail=f"A movie with the name '{movie_data.name}' and release date '{movie_data.date}' already exists.",
        )

    async def get_or_create(model, **kwargs):
        result = await db.execute(select(model).filter_by(**kwargs))
        instance = result.scalar_one_or_none()
        if instance:
            return instance
        instance = model(**kwargs)
        db.add(instance)
        await db.flush()
        return instance

    country_result = await db.execute(
        select(CountryModel).where(CountryModel.code == movie_data.country)
    )
    country = country_result.scalar_one_or_none()
    if not country:
        country = CountryModel(code=movie_data.country, name=None)
        db.add(country)
        await db.flush()

    genres = [
        await get_or_create(GenreModel, name=genre) for genre in movie_data.genres
    ]
    actors = [
        await get_or_create(ActorModel, name=actor_name) for actor_name in movie_data.actors
    ]
    languages = [
        await get_or_create(LanguageModel, name=language)
        for language in movie_data.languages
    ]
    
    status_value = MovieStatusEnum(movie_data.status.value)
    
    movie = MovieModel(
        name=movie_data.name,
        date=movie_data.date,
        score=movie_data.score,
        overview=movie_data.overview,
        status=status_value,
        budget=movie_data.budget,
        revenue=movie_data.revenue,
        country_id=country.id,
    )

    movie.genres.extend(genres)
    movie.actors.extend(actors)
    movie.languages.extend(languages)

    db.add(movie)
    await db.commit()
    
    # Re-query with relationships loaded instead of using refresh with attribute_names
    result = await db.execute(
        select(MovieModel)
        .where(MovieModel.id == movie.id)
        .options(
            selectinload(MovieModel.country),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages),
        )
    )
    movie = result.scalar_one()
    
    return movie


@router.patch("/{movie_id}/", response_model=dict)
async def update_movie(
    movie_id: int,
    movie_update: MovieUpdateSchema,
    db: AsyncSession = Depends(get_db),
):
    update_data = movie_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Invalid input data.")

    result = await db.execute(
        select(MovieModel)
        .where(MovieModel.id == movie_id)
        .options(
            selectinload(MovieModel.country),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages),
        )
    )
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )

    if "score" in update_data:
        if update_data["score"] < 0 or update_data["score"] > 100:
            raise HTTPException(status_code=400, detail="Invalid input data.")

    if "budget" in update_data:
        if update_data["budget"] < 0:
            raise HTTPException(status_code=400, detail="Invalid input data.")

    if "revenue" in update_data:
        if update_data["revenue"] < 0:
            raise HTTPException(status_code=400, detail="Invalid input data.")

    if "status" in update_data:
        allowed_statuses = [status.value for status in MovieStatusEnum]
        status_value = (
            update_data["status"].value
            if isinstance(update_data["status"], MovieStatus)
            else update_data["status"]
        )
        if status_value not in allowed_statuses:
            raise HTTPException(status_code=400, detail="Invalid input data.")

    if "date" in update_data:
        if update_data["date"] > date.today() + timedelta(days=365):
            raise HTTPException(status_code=400, detail="Invalid input data.")

    if "name" in update_data:
        if len(update_data["name"]) > 255:
            raise HTTPException(status_code=400, detail="Invalid input data.")

    for field, value in update_data.items():
        setattr(movie, field, value)

    await db.commit()
    await db.refresh(movie)

    return {"detail": "Movie updated successfully."}


@router.delete("/{movie_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_movie(
    movie_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MovieModel).where(MovieModel.id == movie_id)
    )
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )

    await db.delete(movie)
    await db.commit()
    return None
