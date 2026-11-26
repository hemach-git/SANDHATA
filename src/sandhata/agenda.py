"""Daily action list computed from stored tracker records. No model calls."""
from datetime import timedelta

CLOSED=('Hired','Rejected','Withdrawn','Cancelled')
WAITING=('Applied','Screening','Interviewing')

def build_agenda(applications,today,horizon_days=7,stale_days=14):
    """Split open applications into overdue, upcoming and quiet ones."""
    overdue=[];upcoming=[];stale=[]
    for item in applications:
        if item['status'] in CLOSED: continue
        follow=item.get('follow_up')
        if follow and follow<today: overdue.append(item)
        elif follow and follow<=today+timedelta(days=horizon_days): upcoming.append(item)
        # A future follow-up date means the next step is already planned.
        elif not follow and item['status'] in WAITING and item['updated_at'].date()<=today-timedelta(days=stale_days): stale.append(item)
    by_date=lambda item:item['follow_up']
    return dict(overdue=sorted(overdue,key=by_date),upcoming=sorted(upcoming,key=by_date),
                stale=sorted(stale,key=lambda item:item['updated_at']))

def _escape(text):
    return text.replace('\\','\\\\').replace(';','\\;').replace(',','\\,').replace('\r','').replace('\n','\\n')

def _fold(line):
    """iCalendar lines are limited to 75 octets; continuation lines start with a space."""
    parts=[];current=''
    for char in line:
        if len((current+char).encode('utf-8'))>74: parts.append(current);current=''
        current+=char
    return '\r\n '.join(parts+[current])

def follow_up_calendar(applications,stamp):
    """All-day calendar entries for follow-up dates. Notes are deliberately left out."""
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//SANDHATA//Follow ups//EN']
    for item in applications:
        day=item.get('follow_up')
        if not day: continue
        lines+=['BEGIN:VEVENT',f"UID:{item['id']}@sandhata",'DTSTAMP:'+stamp.strftime('%Y%m%dT%H%M%SZ'),
                'DTSTART;VALUE=DATE:'+day.strftime('%Y%m%d'),
                'DTEND;VALUE=DATE:'+(day+timedelta(days=1)).strftime('%Y%m%d'),
                'SUMMARY:'+_escape(f"Follow up: {item['title']} at {item['company']}"),'END:VEVENT']
    return ('\r\n'.join(_fold(line) for line in lines+['END:VCALENDAR'])+'\r\n').encode('utf-8')
