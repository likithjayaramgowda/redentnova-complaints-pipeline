from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass(frozen=True)
class GraphApp:
    tenant_id: str
    client_id: str
    client_secret: str


def session_with_retries() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST", "PUT", "DELETE"]),
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s


def get_token(app: GraphApp) -> str:
    import msal

    authority = f"https://login.microsoftonline.com/{app.tenant_id}"
    cca = msal.ConfidentialClientApplication(
        client_id=app.client_id,
        authority=authority,
        client_credential=app.client_secret,
    )
    result = cca.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise RuntimeError(
            f"Failed to acquire Graph token: {result.get('error')} {result.get('error_description')}"
        )
    return result["access_token"]


def get_site_id(token: str, hostname: str, site_path: str) -> str:
    site_path = "/" + site_path.strip("/")
    url = f"https://graph.microsoft.com/v1.0/sites/{hostname}:{site_path}"
    s = session_with_retries()
    r = s.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=60)
    r.raise_for_status()
    return r.json()["id"]


def get_default_drive_id(token: str, site_id: str) -> str:
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive"
    s = session_with_retries()
    r = s.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=60)
    r.raise_for_status()
    return r.json()["id"]


def encode_graph_path(remote_folder: str, filename: str) -> str:
    remote_folder = remote_folder.strip("/")
    parts = []
    if remote_folder:
        parts.extend(remote_folder.split("/"))
    parts.append(filename)
    return "/".join(quote(p, safe="") for p in parts)


def upload_file_put_content(
    token: str,
    drive_id: str,
    local_path: Path,
    remote_folder: str,
    remote_filename: Optional[str] = None,
    content_type: str = "text/plain",
):
    name = remote_filename or local_path.name
    remote_path = encode_graph_path(remote_folder=remote_folder, filename=name)
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{remote_path}:/content"
    data = local_path.read_bytes()

    s = session_with_retries()
    r = s.put(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    r.raise_for_status()
    return r.json()
