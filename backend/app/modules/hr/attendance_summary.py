"""Daily attendance summary projection for P0.1-08.

The projection is derived from raw attendance events and roster snapshots. It does
not write EmployeeAttendance (the legacy payroll contract) or infer pay statuses.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session

from app.modules.hr.payroll import (
    HRAttendanceDailySummary,
    HRAttendanceSummaryRevision,
    HRAttendanceEvent,
    HRShiftRosterEntry,
)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _minutes(start: datetime, end: datetime) -> int:
    seconds = max(0, (_utc(end) - _utc(start)).total_seconds())
    return int(Decimal(str(seconds / 60)).quantize(Decimal("1")))


def _active_events(db: Session, employee_id: str, work_date: date) -> list[HRAttendanceEvent]:
    rows = db.query(HRAttendanceEvent).filter(
        HRAttendanceEvent.employee_id == employee_id,
        HRAttendanceEvent.work_date == work_date,
        HRAttendanceEvent.voided_at.is_(None),
    ).order_by(HRAttendanceEvent.occurred_at_utc.asc(), HRAttendanceEvent.id.asc()).all()
    superseded = {
        row[0] for row in db.query(HRAttendanceEvent.supersedes_event_id).filter(
            HRAttendanceEvent.supersedes_event_id.is_not(None),
        ).all()
    }
    return [row for row in rows if row.id not in superseded]


def calculate_attendance_projection(db: Session, employee_id: str, work_date: date) -> dict:
    events = _active_events(db, employee_id, work_date)
    roster = db.query(HRShiftRosterEntry).filter_by(employee_id=employee_id, work_date=work_date).first()
    event_ids = [event.id for event in events]
    fingerprint_payload = {
        "events": [
            [event.id, event.event_type, _utc(event.occurred_at_utc).isoformat(), event.break_rule_id]
            for event in events
        ],
        "roster": [
            roster.id, roster.status, roster.version, roster.timezone_name,
            roster.scheduled_start_at_utc.isoformat() if roster.scheduled_start_at_utc else None,
            roster.scheduled_end_at_utc.isoformat() if roster.scheduled_end_at_utc else None,
        ] if roster else None,
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    timezone_name = roster.timezone_name if roster else (events[0].timezone_name if events else "UTC")
    first_in = last_out = None
    work_intervals: list[tuple[datetime, datetime]] = []
    break_intervals: list[tuple[datetime, datetime]] = []
    exceptions: set[str] = set()
    open_work: HRAttendanceEvent | None = None
    open_break: HRAttendanceEvent | None = None

    for event in events:
        instant = _utc(event.occurred_at_utc)
        if event.event_type == "punch_in":
            if open_work is not None:
                exceptions.add("duplicate_punch_in")
            else:
                open_work = event
                first_in = first_in or instant
        elif event.event_type == "punch_out":
            if open_work is None:
                exceptions.add("punch_out_without_punch_in")
            else:
                if instant <= _utc(open_work.occurred_at_utc):
                    exceptions.add("non_positive_work_interval")
                else:
                    work_intervals.append((_utc(open_work.occurred_at_utc), instant))
                    last_out = instant
                open_work = None
                if open_break is not None:
                    exceptions.add("break_not_closed_before_punch_out")
                    open_break = None
        elif event.event_type == "break_start":
            if open_break is not None:
                exceptions.add("duplicate_break_start")
            elif open_work is None:
                exceptions.add("break_without_work_interval")
            else:
                open_break = event
        elif event.event_type == "break_end":
            if open_break is None:
                exceptions.add("break_end_without_break_start")
            else:
                if instant <= _utc(open_break.occurred_at_utc):
                    exceptions.add("non_positive_break_interval")
                else:
                    break_intervals.append((_utc(open_break.occurred_at_utc), instant))
                open_break = None

    if open_work is not None:
        exceptions.add("missing_punch_out")
    if open_break is not None:
        exceptions.add("missing_break_end")

    elapsed_minutes = sum(_minutes(start, end) for start, end in work_intervals)
    break_minutes = sum(_minutes(start, end) for start, end in break_intervals)
    for break_start, break_end in break_intervals:
        if not any(work_start <= break_start and break_end <= work_end for work_start, work_end in work_intervals):
            exceptions.add("break_outside_work_interval")

    if not events:
        classification = "no_events"
    elif exceptions:
        classification = "invalid_sequence" if any(
            code not in {"missing_punch_out", "missing_break_end"} for code in exceptions
        ) else "incomplete"
    elif work_intervals:
        classification = "complete"
    else:
        classification = "incomplete"

    if roster and roster.status in {"weekly_off", "holiday", "cancelled"} and not events:
        exceptions.add("roster_non_working_day")

    return {
        "employee_id": employee_id,
        "work_date": work_date,
        "roster_entry_id": roster.id if roster else None,
        "timezone_name": timezone_name,
        "source_event_ids": event_ids,
        "first_punch_in_utc": first_in,
        "last_punch_out_utc": last_out,
        "elapsed_minutes": elapsed_minutes,
        "paired_break_minutes": break_minutes,
        "classification": classification,
        "exception_codes": sorted(exceptions),
        "input_fingerprint": fingerprint,
    }


def recalculate_attendance_summary(
    db: Session, employee_id: str, work_date: date, *, calculated_by: str,
) -> tuple[HRAttendanceDailySummary, HRAttendanceSummaryRevision, bool]:
    """Persist a current projection and immutable revision; unchanged inputs are idempotent."""
    projection = calculate_attendance_projection(db, employee_id, work_date)
    summary = db.query(HRAttendanceDailySummary).filter_by(
        employee_id=employee_id, work_date=work_date,
    ).first()
    if summary and summary.input_fingerprint == projection["input_fingerprint"]:
        revision = db.query(HRAttendanceSummaryRevision).filter_by(
            employee_id=employee_id, work_date=work_date, revision=summary.current_revision,
        ).first()
        return summary, revision, False

    if summary is None:
        summary = HRAttendanceDailySummary(
            employee_id=employee_id,
            work_date=work_date,
            current_revision=0,
        )
        db.add(summary)
        db.flush()

    revision_number = summary.current_revision + 1
    revision = HRAttendanceSummaryRevision(
        employee_id=employee_id,
        work_date=work_date,
        revision=revision_number,
        **projection,
        calculated_by=calculated_by[:64],
    )
    db.add(revision)
    summary.current_revision = revision_number
    summary.roster_entry_id = projection["roster_entry_id"]
    summary.timezone_name = projection["timezone_name"]
    summary.source_event_ids = projection["source_event_ids"]
    summary.first_punch_in_utc = projection["first_punch_in_utc"]
    summary.last_punch_out_utc = projection["last_punch_out_utc"]
    summary.elapsed_minutes = projection["elapsed_minutes"]
    summary.paired_break_minutes = projection["paired_break_minutes"]
    summary.classification = projection["classification"]
    summary.exception_codes = projection["exception_codes"]
    summary.input_fingerprint = projection["input_fingerprint"]
    summary.calculated_by = calculated_by[:64]
    summary.calculated_at = datetime.now(timezone.utc)
    db.flush()
    return summary, revision, True


def summary_output(summary: HRAttendanceDailySummary, revision: HRAttendanceSummaryRevision | None = None) -> dict:
    return {
        "id": summary.id,
        "employee_id": summary.employee_id,
        "work_date": summary.work_date,
        "current_revision": summary.current_revision,
        "classification": summary.classification,
        "exception_codes": summary.exception_codes,
        "source_event_ids": summary.source_event_ids,
        "roster_entry_id": summary.roster_entry_id,
        "timezone_name": summary.timezone_name,
        "first_punch_in_utc": summary.first_punch_in_utc,
        "last_punch_out_utc": summary.last_punch_out_utc,
        "elapsed_minutes": summary.elapsed_minutes,
        "paired_break_minutes": summary.paired_break_minutes,
        "input_fingerprint": summary.input_fingerprint,
        "calculated_by": summary.calculated_by,
        "calculated_at": summary.calculated_at,
        "revision": {
            "revision": revision.revision,
            "source_event_ids": revision.source_event_ids,
            "exception_codes": revision.exception_codes,
            "classification": revision.classification,
            "calculated_by": revision.calculated_by,
            "calculated_at": revision.calculated_at,
        } if revision else None,
    }
