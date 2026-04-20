from urllib.parse import urlsplit

from flask import request, url_for


def _is_safe_relative_path(target):
    if not target:
        return False
    parsed = urlsplit(target)
    return not parsed.scheme and not parsed.netloc and target.startswith("/")


def get_next_url(default_endpoint):
    candidate = request.args.get("next") or request.form.get("next")
    if _is_safe_relative_path(candidate):
        return candidate
    return url_for(default_endpoint)
