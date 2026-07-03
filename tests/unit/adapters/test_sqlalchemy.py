from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter


# Test Models
class Team(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    headquarters: str = Field(index=True)
    heroes: list["Hero"] = Relationship(
        back_populates="team", sa_relationship_kwargs={"lazy": "selectin"}
    )


class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    secret_name: str
    age: int | None = Field(default=None, index=True)
    team_id: int | None = Field(default=None, foreign_key="team.id")
    team: Team | None = Relationship(
        back_populates="heroes", sa_relationship_kwargs={"lazy": "selectin"}
    )


# Pytest Fixture for adapter setup
@pytest.fixture
async def engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


# Tests
@pytest.mark.anyio
async def test_adapter_init_invalid_model():
    with (
        patch("hyperadmin.adapters.sqlalchemy.inspect", return_value=None),
        pytest.raises(ValueError, match="Could not inspect model"),
    ):
        SQLAlchemyAdapter(model=MagicMock(), engine=MagicMock())


@pytest.mark.anyio
async def test_create(engine):
    hero_adapter = SQLAlchemyAdapter(model=Hero, engine=engine)
    hero_data = {"name": "Deadpond", "secret_name": "Dive Wilson"}
    created_hero = await hero_adapter.create(hero_data)
    assert created_hero.id is not None

    async with AsyncSession(engine) as session:
        hero_in_db = await session.get(Hero, created_hero.id)
        assert hero_in_db is not None
        assert hero_in_db.name == hero_data["name"]


@pytest.mark.anyio
async def test_get(engine):
    hero_adapter = SQLAlchemyAdapter(model=Hero, engine=engine)
    async with AsyncSession(engine) as session:
        hero_1 = Hero(name="Deadpond", secret_name="Dive Wilson")
        session.add(hero_1)
        await session.commit()
        await session.refresh(hero_1)
        pk = hero_1.id

    retrieved_hero = await hero_adapter.get(pk=pk)
    assert retrieved_hero.id == pk


@pytest.mark.anyio
async def test_list(engine):
    hero_adapter = SQLAlchemyAdapter(model=Hero, engine=engine)
    async with AsyncSession(engine) as session:
        hero_1 = Hero(name="Spider-Boy", secret_name="Pedro Parqueador", age=16)
        hero_2 = Hero(name="Rusty-Man", secret_name="Tommy Sharp", age=48)
        hero_3 = Hero(name="Captain North", secret_name="Esteban Rogelios", age=93)
        session.add_all([hero_1, hero_2, hero_3])
        await session.commit()

    # Test basic list
    items, total_count = await hero_adapter.list()
    assert total_count == 3
    assert len(items) == 3

    # Test pagination
    items, total_count = await hero_adapter.list(page=2, page_size=2)
    assert total_count == 3
    assert len(items) == 1
    assert items[0].name == "Captain North"

    # Test filtering
    items, total_count = await hero_adapter.list(filters={"name": "Rusty-Man"})
    assert total_count == 1
    assert len(items) == 1
    assert items[0].secret_name == "Tommy Sharp"

    # Test search
    items, total_count = await hero_adapter.list(search="Pedro")
    assert total_count == 1
    assert len(items) == 1
    assert items[0].name == "Spider-Boy"

    # Test ordering
    items, total_count = await hero_adapter.list(order_by="age")
    assert items[0].name == "Spider-Boy"
    items, total_count = await hero_adapter.list(order_by="-age")
    assert items[0].name == "Captain North"


@pytest.mark.anyio
async def test_update(engine):
    hero_adapter = SQLAlchemyAdapter(model=Hero, engine=engine)
    async with AsyncSession(engine) as session:
        hero_1 = Hero(name="Deadpond", secret_name="Dive Wilson")
        session.add(hero_1)
        await session.commit()
        await session.refresh(hero_1)
        pk = hero_1.id

    updated_data = {"name": "Deadpool"}
    updated_hero = await hero_adapter.update(pk=pk, data=updated_data)
    assert updated_hero.name == "Deadpool"

    async with AsyncSession(engine) as session:
        hero_in_db = await session.get(Hero, pk)
        assert hero_in_db.name == "Deadpool"


@pytest.mark.anyio
async def test_update_not_found(engine):
    hero_adapter = SQLAlchemyAdapter(model=Hero, engine=engine)
    updated_hero = await hero_adapter.update(pk=999, data={"name": "Deadpool"})
    assert updated_hero is None


@pytest.mark.anyio
async def test_delete(engine):
    hero_adapter = SQLAlchemyAdapter(model=Hero, engine=engine)
    async with AsyncSession(engine) as session:
        hero_1 = Hero(name="Deadpond", secret_name="Dive Wilson")
        session.add(hero_1)
        await session.commit()
        await session.refresh(hero_1)
        pk = hero_1.id

    await hero_adapter.delete(pk=pk)

    async with AsyncSession(engine) as session:
        hero_in_db = await session.get(Hero, pk)
        assert hero_in_db is None


@pytest.mark.anyio
async def test_delete_not_found(engine):
    hero_adapter = SQLAlchemyAdapter(model=Hero, engine=engine)
    await hero_adapter.delete(pk=999)


@pytest.mark.anyio
async def test_get_schema(engine):
    hero_adapter = SQLAlchemyAdapter(model=Hero, engine=engine)
    schema = await hero_adapter.get_schema()
    assert isinstance(schema, dict)
    assert "properties" in schema
    assert "name" in schema["properties"]


@pytest.mark.anyio
async def test_get_related(engine):
    team_adapter = SQLAlchemyAdapter(model=Team, engine=engine)
    hero_adapter = SQLAlchemyAdapter(model=Hero, engine=engine)
    async with AsyncSession(engine) as session:
        team_preventers = Team(name="Preventers", headquarters="Sharp Tower")
        hero_deadpond = Hero(name="Deadpond", secret_name="Dive Wilson", team=team_preventers)
        session.add(team_preventers)
        session.add(hero_deadpond)
        await session.commit()
        await session.refresh(team_preventers)
        await session.refresh(hero_deadpond)
        team_pk = team_preventers.id
        hero_pk = hero_deadpond.id

    related_heroes = await team_adapter.get_related(pk=team_pk, field="heroes")
    assert len(related_heroes) == 1
    assert related_heroes[0].name == "Deadpond"

    retrieved_team = await hero_adapter.get_related(pk=hero_pk, field="team")
    assert len(retrieved_team) == 1
    assert retrieved_team[0].name == "Preventers"


@pytest.mark.anyio
async def test_get_related_no_inspector(engine):
    team_adapter = SQLAlchemyAdapter(model=Team, engine=engine)
    with patch.object(team_adapter, "inspector", None):
        related = await team_adapter.get_related(pk=1, field="heroes")
        assert related == []


@pytest.mark.anyio
async def test_get_related_not_found(engine):
    team_adapter = SQLAlchemyAdapter(model=Team, engine=engine)
    related = await team_adapter.get_related(pk=999, field="heroes")
    assert related == []


@pytest.mark.anyio
async def test_get_related_is_none(engine):
    hero_adapter = SQLAlchemyAdapter(model=Hero, engine=engine)
    team_adapter = SQLAlchemyAdapter(model=Team, engine=engine)
    async with AsyncSession(engine) as session:
        team = Team(name="Team with no heroes", headquarters="Empty Base")
        hero = Hero(name="Lonely", secret_name="Alone", team=None)
        session.add(team)
        session.add(hero)
        await session.commit()
        await session.refresh(team)
        await session.refresh(hero)
        team_pk = team.id
        hero_pk = hero.id

    # Test many-to-one relationship when it's None
    related_team = await hero_adapter.get_related(pk=hero_pk, field="team")
    assert related_team == []

    # Test one-to-many relationship when it's empty
    related_heroes = await team_adapter.get_related(pk=team_pk, field="heroes")
    assert related_heroes == []


@pytest.mark.anyio
async def test_get_related_attribute_error(engine):
    team_adapter = SQLAlchemyAdapter(model=Team, engine=engine)
    async with AsyncSession(engine) as session:
        team = Team(name="Team", headquarters="Base")
        session.add(team)
        await session.commit()
        await session.refresh(team)
        pk = team.id
    related = await team_adapter.get_related(pk=pk, field="non_existent_field")
    assert related == []
