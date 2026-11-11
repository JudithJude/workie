import logging
import time

import requests

log = logging.getLogger("workie")

session = requests.Session()
session.headers["User-Agent"] = "workie-jobboard/1.0 (personal job search)"


def get_json(url, *, params=None, headers=None, retries=3, timeout=30):
    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(f"{r.status_code}", response=r)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            if attempt == retries:
                log.warning("GET %s failed: %s", url, e)
                return None
            time.sleep(2 * attempt)


def post_json(url, *, payload, headers=None, retries=2, timeout=120):
    for attempt in range(1, retries + 1):
        try:
            r = session.post(url, json=payload, headers=headers, timeout=timeout)
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(f"{r.status_code}", response=r)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            if attempt == retries:
                log.warning("POST %s failed: %s", url, e)
                return None
            time.sleep(3 * attempt)
