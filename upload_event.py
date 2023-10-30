import os
import random, treq
from twisted.internet.task import react
from pydantic import BaseModel
from dotenv import load_dotenv


class BitsEvent(BaseModel):
    user_name: str = None
    user_id: int = None
    channel_name: str
    bits_used: int
    total_bits_used: int = None


class SubEvent(BaseModel):
    user_name: str = None
    user_id: int = None
    channel_name: str
    is_gift: bool
    cumulative_months: int = None
    streak_months: int = None
    multi_month_duration: int
    sub_plan: str


# import twisted.internet._sslverify as v
# v.platformTrust = lambda : None
load_dotenv()
ROOTURL = os.getenv("ROOTURL")
APIKEY = os.getenv("APIKEY")


def upload_bits_event(reactor, Bits: BitsEvent):
    try_count = 0

    def handle_error(failure):
        nonlocal try_count
        try_count += 1
        if try_count < 3:
            delay = random.randint(5, 15)
            print(f"Retry {try_count} in {delay} seconds")
            reactor.callLater(delay, upload_bits_event, url, Bits)
        else:
            print("Request failed after 3 tries")

    url = f"{ROOTURL}/rest/v1/Bits"

    headers = {
        "user-agent": "TwitchSubAgent",
        "apikey": APIKEY,
        "authorization": f"Bearer {APIKEY}",
        "content-type": "application/json",
        "prefer": "return=minimal",
    }
    d = treq.post(url, json=Bits.model_dump(), headers=headers)
    d.addErrback(handle_error)

    return d


def upload_subscription(reactor, Sub: SubEvent):
    try_count = 0

    def handle_error(failure):
        nonlocal try_count
        try_count += 1
        if try_count < 3:
            delay = random.randint(5, 15)
            print(f"Retry {try_count} in {delay} seconds")
            reactor.callLater(delay, upload_bits_event, Sub)
        else:
            print("Request failed after 3 tries")

    url = f"{ROOTURL}/rest/v1/Subs"
    headers = {
        "user-agent": "TwitchSubAgent",
        "apikey": APIKEY,
        "authorization": f"Bearer {APIKEY}",
        "content-type": "application/json",
        "prefer": "return=minimal",
    }
    d = treq.post(url, json=Sub.model_dump(), headers=headers)
    d.addErrback(handle_error)

    return d


def refresh_token(token):
    pass


if __name__ == "main":
    a = BitsEvent(
        user_name="12",
        user_id=12,
        channel_name="virgil246",
        bits_used=12,
        total_bits_used=123,
    )
    react(upload_bits_event, [a])
