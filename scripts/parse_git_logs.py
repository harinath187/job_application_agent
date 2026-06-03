import re
import datetime
from datetime import timezone, timedelta

LOG_PATH = ".git/logs/HEAD"

pattern = re.compile(r'^(?P<old>[0-9a-f]+) (?P<new>[0-9a-f]+) (?P<author>.+?) (?P<epoch>\d+) (?P<tz>[+-]\d{4})\t(?P<msg>.*)$')

target_date = datetime.date(2026, 6, 1)

results = []
with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        m = pattern.match(line.rstrip('\n'))
        if not m:
            continue
        new = m.group('new')
        author = m.group('author')
        epoch = int(m.group('epoch'))
        tz = m.group('tz')
        msg = m.group('msg')

        sign = 1 if tz[0] == '+' else -1
        hours = int(tz[1:3])
        minutes = int(tz[3:5])
        offset = timedelta(hours=hours, minutes=minutes) * sign
        tzinfo = timezone(offset)

        dt = datetime.datetime.fromtimestamp(epoch, tzinfo)

        if dt.date() == target_date:
            results.append((new, dt.isoformat(), author, msg))

if not results:
    print("No commits found on", target_date.isoformat())
else:
    for sha, dt_iso, author, msg in results:
        print("COMMIT:", sha)
        print("DATE:  ", dt_iso)
        print("AUTHOR:", author)
        print("MSG:   ", msg)
        print()
