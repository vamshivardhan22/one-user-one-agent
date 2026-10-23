from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

def parse_time(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None

def iso(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if value else None

def age_seconds(received_at, occurred_at):
    received, occurred = parse_time(received_at), parse_time(occurred_at)
    if not received or not occurred:
        return None
    return max(0.0, (received - occurred).total_seconds())

def ist_day(value):
    parsed = parse_time(value)
    return parsed.astimezone(IST).date().isoformat() if parsed else None

def is_quiet_hours(value):
    parsed = parse_time(value)
    if not parsed:
        return True
    hour = parsed.astimezone(IST).hour
    return hour >= 22 or hour < 8
