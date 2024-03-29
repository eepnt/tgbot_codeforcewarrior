import json
import logging
from datetime import datetime
from typing import Any, Optional

import google.cloud.logging
import requests
from cachetools import TTLCache, cached
from google.cloud import firestore, tasks_v2
from google.protobuf import timestamp_pb2

from tgbot.config import config

google.cloud.logging.Client().setup_logging()

try:
    import googleclouddebugger

    googleclouddebugger.enable(breakpoint_enable_canary=False)
except ImportError:
    pass

logger = logging.getLogger(__name__)
session = requests.Session()

resp = session.get(
    "http://metadata.google.internal/computeMetadata/v1/project/project-id",
    headers={"Metadata-Flavor": "Google"}
)
PROJECT_ID = resp.text

# load firestore
db = firestore.Client(project=PROJECT_ID)

# load cloud task config
task_client = tasks_v2.CloudTasksClient()
task_parent = task_client.queue_path(PROJECT_ID, "asia-northeast1", "cfbot-verification")


def make_tg_api_request(endpoint, params: dict[str, Any]) -> requests.Response:
    resp = session.get(
        f"https://api.telegram.org/bot{config['TOKEN']}/{endpoint}",
        params=params,
        timeout=5
    )
    logger.info(f"TG API request: {resp.status_code}")
    return resp


def schedule_task(endpoint: str, data: dict[str, Any], dt: datetime) -> None:
    timestamp = timestamp_pb2.Timestamp()
    timestamp.FromDatetime(dt)

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"{config['FUNCTIONS_URL']}/{endpoint}",
            "headers": {"Content-type": "application/json"},
            "body": json.dumps(data).encode("utf-8")
        },
        "schedule_time": timestamp
    }
    task_client.create_task(parent=task_parent, task=task)


def get_handle(user_id: int) -> Optional[str]:
    doc = db.collection("cfbot_handle").document(str(user_id)).get()
    if doc.exists:
        return doc.to_dict()["handle"]


@cached(cache=TTLCache(maxsize=1, ttl=5))
def get_handles() -> list[str]:
    handles = []
    for doc in db.collection("cfbot_handle").stream():
        handles.append(doc.to_dict()["handle"])
    return handles
