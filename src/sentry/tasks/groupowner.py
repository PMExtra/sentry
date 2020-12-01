from __future__ import absolute_import, print_function

import logging

from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

from sentry.eventstore.models import Event
from sentry.eventstore.processing import event_processing_store
from sentry.models import Project, Release
from sentry.models.groupowner import GroupOwner, GroupOwnerType
from sentry.tasks.base import instrumented_task
from sentry.utils import metrics
from sentry.utils.committers import get_serialized_event_file_committers

PREFERRED_GROUP_OWNERS = 2
MIN_COMMIT_SCORE = 2
OWNER_CACHE_LIFE = 3600  # seconds
PREFERRED_GROUP_OWNER_AGE = timedelta(days=1)
GROUP_PROCESSING_DELAY = timedelta(
    minutes=10
)  # Minimum time between processing the same group id again

logger = logging.getLogger("tasks.groupowner")


@instrumented_task(
    name="sentry.tasks.process_suspect_commits",
    queue="group_owners.process_suspect_commits",
    default_retry_delay=5,
    max_retries=5,
)
def process_suspect_commits(group_id, event_cache_key, **kwargs):
    metrics.incr("sentry.tasks.process_suspect_commits.start")
    with metrics.timer("sentry.tasks.process_suspect_commits"):
        if not group_id:
            metrics.incr(
                "sentry.tasks.process_suspect_commits.skipped", tags={"detail": "no_group_id"}
            )
            return

        data = event_processing_store.get(event_cache_key)
        if not data:
            metrics.incr(
                "sentry.tasks.process_suspect_commits.skipped", tags={"detail": "no_event_store"}
            )
            logger.info(
                "process_suspect_commits.skipped",
                extra={"cache_key": event_cache_key, "reason": "missing_cache"},
            )
            return

        can_process = True
        cache_key = "workflow-owners-ingestion:group-{}".format(group_id)
        owner_data = cache.get(cache_key)

        if owner_data and owner_data["count"] >= PREFERRED_GROUP_OWNERS:
            # Only process once per OWNER_CACHE_LIFE seconds for groups already populated with owenrs.
            metrics.incr(
                "sentry.tasks.process_suspect_commits.skipped", tags={"detail": "too_many_owners"}
            )
            can_process = False
        elif owner_data and owner_data["time"] > timezone.now() - GROUP_PROCESSING_DELAY:
            # Smaller delay for groups without PREFERRED_GROUP_OWNERS owners yet
            metrics.incr(
                "sentry.tasks.process_suspect_commits.skipped", tags={"detail": "group_delay"}
            )
            can_process = False
        else:
            event = Event(
                project_id=data["project"], event_id=data["event_id"], group_id=group_id, data=data
            )
            project = Project.objects.get_from_cache(id=event.project_id)
            owners = GroupOwner.objects.filter(
                group_id=event.group_id,
                project=project,
                organization_id=project.organization_id,
                type=GroupOwnerType.SUSPECT_COMMIT.value,
            )
            owner_count = owners.count()
            if owner_count >= PREFERRED_GROUP_OWNERS:
                # We have enough owners already - so see if any are old.
                # If so, we can delete it and replace with a fresh one.
                owners = owners.filter(
                    date_added__lte=timezone.now() - PREFERRED_GROUP_OWNER_AGE
                ).order_by("-date_added")
                if not owners.exists():
                    metrics.incr(
                        "sentry.tasks.process_suspect_commits.aborted",
                        tags={"detail": "maxed_owners_none_old"},
                    )
                    can_process = False

            owner_data = {"count": owner_count, "time": timezone.now()}
            cache.set(cache_key, owner_data, OWNER_CACHE_LIFE)

        if can_process:
            try:
                metrics.incr("sentry.tasks.process_suspect_commits.calculated")
                committers = get_serialized_event_file_committers(project, event)
                # TODO(Chris F.) We would like to store this commit information so that we can get perf gains
                # and synced information on the Issue details page.
                # There are issues with this...like mutable commits and commits coming in after events.
                for committer in committers:
                    if (
                        "score" in committer["commits"][0]
                        and committer["commits"][0]["score"] >= MIN_COMMIT_SCORE
                    ):
                        if "id" in committer["author"]:
                            owner_id = committer["author"]["id"]
                            go, created = GroupOwner.objects.update_or_create(
                                group_id=event.group_id,
                                type=GroupOwnerType.SUSPECT_COMMIT.value,
                                user_id=owner_id,
                                project=project,
                                organization_id=project.organization_id,
                                defaults={
                                    "date_added": timezone.now()
                                },  # Updates date of an existing owner, since we just matched them with this new event,
                            )
                            if created:
                                owner_count += 1
                                if owner_count > PREFERRED_GROUP_OWNERS:
                                    owners.first().delete()
                        else:
                            # TODO(Chris F.) We actually need to store and display these too, somehow. In the future.
                            pass
            except Release.DoesNotExist:
                logger.info(
                    "process_suspect_commits.skipped",
                    extra={"cache_key": event_cache_key, "reason": "no_release"},
                )

        event_processing_store.delete_by_key(event_cache_key)
