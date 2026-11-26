"""Strict, bounded CSV intake for application trackers."""
import csv
import io
from datetime import datetime, date, timezone
from urllib.parse import urlsplit
from .config import AppError

WORK_ARRANGEMENTS = ['', 'OnSite', 'Hybrid', 'Remote']
JOB_TYPES = ['', 'Contract', 'Contract to Hire', 'Full Time', 'Part Time', 'Temporary', 'Freelance', 'Internship', 'Seasonal', 'Other']

def job_type(value):
    key = value.strip().lower().replace('-', '').replace(' ', '')
    choices = {item.lower().replace(' ', ''): item for item in JOB_TYPES}
    if key not in choices:
        raise ValueError('job_type must be one of: ' + ', '.join(JOB_TYPES[1:]) + ', or blank')
    return choices[key]

def work_arrangement(value):
    key = value.strip().lower().replace('-', '').replace(' ', '')
    choices = {'': '', 'onsite': 'OnSite', 'hybrid': 'Hybrid', 'remote': 'Remote'}
    if key not in choices:
        raise ValueError('work_arrangement must be OnSite, Hybrid, Remote, or blank')
    return choices[key]

COLUMNS = ['title', 'company', 'status', 'original_url', 'applied_at', 'follow_up', 'notes', 'description', 'location', 'work_arrangement', 'salary_description', 'job_type', 'recruiter']
TEMPLATE = (','.join(COLUMNS) + '\nSoftware Engineer,Example Company,Applied,https://example.com/jobs/123,2026-01-15,,Follow up next week,,"Charlotte, NC",Hybrid,$150k base plus bonus,Full Time,Jane Smith - Example Recruiting\n').encode()

def parse_tracker(data, statuses):
    if len(data) > 5 * 1024 * 1024:
        raise AppError('Upload a CSV under 5 MB.')
    try:
        reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline=''))
        if not reader.fieldnames or not {'title', 'company'}.issubset(reader.fieldnames):
            raise AppError('CSV headers must include title and company. Download the template.')
        result = []
        for number, raw in enumerate(reader, 2):
            if number > 1001:
                raise AppError('Upload at most 1,000 rows at a time.')
            if None in raw or any(v is None for v in raw.values()):
                raise AppError(f'Row {number}: column count does not match the headers.')
            row = {k: raw.get(k, '').strip() for k in COLUMNS}
            row['status'] = row['status'] or 'Saved'
            try:
                if not row['title'] or len(row['title']) > 300 or not row['company'] or len(row['company']) > 200:
                    raise ValueError('title and company are required (300/200 characters maximum)')
                if row['status'] not in statuses:
                    raise ValueError('unknown status')
                if len(row['location']) > 400:
                    raise ValueError('location must be at most 400 characters')
                row['work_arrangement'] = work_arrangement(row['work_arrangement'])
                if len(row['salary_description']) > 400:
                    raise ValueError('salary_description must be at most 400 characters')
                row['job_type'] = job_type(row['job_type'])
                if len(row['recruiter']) > 400: raise ValueError('recruiter must be at most 400 characters')
                if len(row['notes']) > 10000 or len(row['description']) > 150000 or any('\x00' in v for v in row.values()):
                    raise ValueError('notes or description exceeds limits, or contains null characters')
                url = urlsplit(row['original_url'])
                if row['original_url'] and (url.scheme != 'https' or not url.hostname):
                    raise ValueError('posting URL must use HTTPS')
                value = row['applied_at']
                row['applied_at'] = datetime.fromisoformat(value.replace('Z', '+00:00')) if value else None
                if row['applied_at']:
                    row['applied_at'] = row['applied_at'].replace(tzinfo=row['applied_at'].tzinfo or timezone.utc)
                    if row['applied_at'] > datetime.now(timezone.utc):
                        raise ValueError('applied_at cannot be in the future')
                row['follow_up'] = date.fromisoformat(row['follow_up']) if row['follow_up'] else None
            except ValueError as exc:
                raise AppError(f'Row {number}: {exc}.') from exc
            result.append(row)
        if not result:
            raise AppError('The CSV contains no tracker rows.')
        return result
    except (UnicodeError, csv.Error) as exc:
        raise AppError('Use a UTF-8 CSV with properly quoted fields.') from exc
