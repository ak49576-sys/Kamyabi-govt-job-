"""Publish newly visible Kamyabi jobs to a connected Buffer X channel.

The first run records the current open jobs without posting old listings. Every
later run handles at most one new job so its receipt can be committed promptly.
"""
import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SITE_API = 'https://kamyabi.in/api/v1/jobs'
BUFFER_API = 'https://api.buffer.com'
STATE_PATH = Path('x-published-jobs.json')
SLUG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')


def fetch_jobs():
    request = Request(SITE_API, headers={'Accept': 'application/json', 'Cache-Control': 'no-cache'})
    with urlopen(request, timeout=30) as response:
        document = json.load(response)
    if not isinstance(document, dict) or not isinstance(document.get('jobs'), list):
        raise ValueError('Unexpected Kamyabi jobs response')
    return document['jobs']


def open_job(job, today):
    if not isinstance(job, dict) or job.get('status') != 'APPLICATION_OPEN':
        return False
    job_id, title = job.get('job_id'), job.get('title')
    if not isinstance(job_id, str) or not SLUG.fullmatch(job_id) or not isinstance(title, str) or not title.strip():
        return False
    start, end = job.get('application_start_date'), job.get('application_last_date')
    try:
        start_date = datetime.strptime(start[:10], '%Y-%m-%d').date()
        end_date = datetime.strptime(end[:10], '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return False
    # Avoid upcoming, expired and sentinel-date records. This API exposes only
    # public jobs; a future review should also enforce source quality upstream.
    return start_date <= today <= end_date and (end_date - today).days <= 180


def read_state(path=STATE_PATH):
    if not path.exists():
        return None
    state = json.loads(path.read_text())
    if not isinstance(state, dict) or state.get('version') != 1 or not isinstance(state.get('seen'), dict):
        raise ValueError('Invalid X publication state; refusing to repeat posts')
    return state


def write_state(state, path=STATE_PATH):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def post_text(job):
    deadline = job['application_last_date'][:10]
    url = f"https://kamyabi.in/jobs/{job['job_id']}"
    suffix = f'\nApply by {deadline}\n{url}'
    prefix = 'New government job: '
    title = ' '.join(job['title'].split())
    maximum = 275 - len(prefix) - len(suffix)
    if maximum < 10:
        raise ValueError('Post URL too long')
    if len(title) > maximum:
        title = title[:maximum - 1].rstrip() + '…'
    return prefix + title + suffix


def buffer_request(query, key, variables=None):
    data = json.dumps({'query': query, 'variables': variables or {}}).encode()
    request = Request(BUFFER_API, data=data, headers={
        'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
    }, method='POST')
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    if not isinstance(result, dict) or result.get('errors'):
        raise ValueError('Buffer GraphQL request failed')
    return result.get('data') or {}


def verify_x_channel(key, channel_id):
    # Restrict this automation to X, even if a wrong channel ID is configured.
    query = f'query {{ channel(input: {{ id: {json.dumps(channel_id)} }}) {{ id service name }} }}'
    channel = buffer_request(query, key).get('channel')
    if not isinstance(channel, dict) or channel.get('id') != channel_id or channel.get('service') != 'twitter':
        raise ValueError('Configured Buffer channel is not a connected X account')
    return channel.get('name')


def publish(job, key, channel_id):
    query = '''mutation CreateJobPost($input: CreatePostInput!) {
      createPost(input: $input) {
        __typename
        ... on PostActionSuccess { post { id status } }
        ... on MutationError { message }
      }
    }'''
    data = buffer_request(query, key, {'input': {
        'text': post_text(job), 'channelId': channel_id,
        'schedulingType': 'automatic', 'mode': 'shareNow',
    }})
    result = data.get('createPost')
    if not isinstance(result, dict) or result.get('__typename') != 'PostActionSuccess' or not result.get('post', {}).get('id'):
        raise ValueError('Buffer did not confirm post creation; check Buffer before retrying')
    return result['post']['id']


def run(jobs, state, today, send=None):
    eligible = {j['job_id']: j for j in jobs if open_job(j, today)}
    if state is None:
        if not eligible:
            raise ValueError('No open jobs for initial baseline; check the public API before activating')
        return {'version': 1, 'seen': {key: {'baseline': True} for key in eligible}}, 'baseline', None
    unseen = sorted(set(eligible) - set(state['seen']))
    if not unseen:
        return state, 'unchanged', None
    job = eligible[unseen[0]]
    if send is None:
        return state, 'preview', job
    post_id = send(job)
    state['seen'][job['job_id']] = {'buffer_post_id': post_id, 'posted_at': datetime.now(ZoneInfo('Asia/Kolkata')).isoformat()}
    return state, 'posted', job


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--publish', action='store_true', help='Post at most one new job via Buffer')
    parser.add_argument('--state', type=Path, default=STATE_PATH)
    args = parser.parse_args()
    try:
        jobs = fetch_jobs()
        state = read_state(args.state)
        today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
        sender = None
        if args.publish and state is not None:
            key, channel_id = os.getenv('BUFFER_API_KEY', ''), os.getenv('BUFFER_X_CHANNEL_ID', '')
            if not key or not channel_id or '\n' in key or '\n' in channel_id:
                raise ValueError('Buffer X channel secrets are missing')
            verify_x_channel(key, channel_id)
            sender = lambda job: publish(job, key, channel_id)
        state, outcome, job = run(jobs, state, today, sender)
        if args.publish and outcome in ('baseline', 'posted'):
            write_state(state, args.state)
        print(json.dumps({'outcome': outcome, 'job_id': job['job_id'] if job else None}))
        return 0
    except Exception as error:
        # Do not print API response bodies or secrets.
        print(json.dumps({'outcome': 'error', 'reason': str(error) if isinstance(error, ValueError) else type(error).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
