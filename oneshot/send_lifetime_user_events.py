#!/usr/bin/env python3
import argparse
import time

import arrow
from sqlalchemy import func

from app.events.event_dispatcher import EventDispatcher
from app.events.generated.event_pb2 import UserPlanChanged, EventContent
from app.models import PartnerUser, User
from app.db import Session

parser = argparse.ArgumentParser(
    prog="Backfill alias", description="Send lifetime users to proton"
)
parser.add_argument(
    "-s", "--start_pu_id", default=0, type=int, help="Initial partner_user_id"
)
parser.add_argument(
    "-e", "--end_pu_id", default=0, type=int, help="Last partner_user_id"
)

args = parser.parse_args()
pu_id_start = args.start_pu_id
max_pu_id = args.end_pu_id
if max_pu_id == 0:
    max_pu_id = Session.query(func.max(PartnerUser.id)).scalar()

print(f"Checking partner user {pu_id_start} to {max_pu_id}")
step = 1000
done = 0
start_time = time.time()
with_lifetime = 0
for batch_start in range(pu_id_start, max_pu_id, step):
    users = (
        Session.query(User)
        .join(PartnerUser, PartnerUser.user_id == User.id)
        .filter(
            PartnerUser.id >= batch_start,
            PartnerUser.id < batch_start + step,
            User.lifetime == True,  # noqa :E712
        )
    ).all()
    for user in users:
        # Just in case the == True cond is wonky
        if not user.lifetime:
            continue
        with_lifetime += 1
        event = UserPlanChanged(plan_end_time=arrow.get("2038-01-01").timestamp)
        EventDispatcher.send_event(user, EventContent(user_plan_change=event))
        Session.flush()
    Session.commit()
    elapsed = time.time() - start_time
    last_batch_id = batch_start + step
    time_per_alias = elapsed / (last_batch_id)
    remaining = max_pu_id - last_batch_id
    time_remaining = remaining / time_per_alias
    hours_remaining = time_remaining / 60.0
    print(
        f"\PartnerUser {batch_start}/{max_pu_id} {with_lifetime} {hours_remaining:.2f} mins remaining"
    )
print(f"With SL lifetime {with_lifetime}")
