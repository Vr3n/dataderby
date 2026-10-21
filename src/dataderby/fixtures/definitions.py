"""Dagster definitions for the fixture calendar."""

from __future__ import annotations

from dagster import (
    Definitions,
    ScheduleDefinition,
    define_asset_job,
)

from dataderby.fixtures.assets import (
    FixtureSettings,
    fixture_calendar_complete,
    fixture_counts_match_source,
    fixture_kickoffs_are_ist,
    fixture_match_numbers_unique,
    fixtures_table,
    raw_fixture_csvs,
)

fixture_refresh_job = define_asset_job(
    name="fixture_refresh_job",
    selection=[raw_fixture_csvs, fixtures_table],
    description="Refresh the fixture calendar every morning.",
)

fixture_refresh_schedule = ScheduleDefinition(
    name="fixture_refresh_daily",
    job=fixture_refresh_job,
    cron_schedule="0 6 * * *",
    execution_timezone="Asia/Kolkata",
)

defs = Definitions(
    assets=[raw_fixture_csvs, fixtures_table],
    asset_checks=[
        fixture_kickoffs_are_ist,
        fixture_counts_match_source,
        fixture_match_numbers_unique,
        fixture_calendar_complete,
    ],
    jobs=[fixture_refresh_job],
    schedules=[fixture_refresh_schedule],
    resources={"settings": FixtureSettings()},
)
