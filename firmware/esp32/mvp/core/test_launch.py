"""Include new domain tests in the established `manage.py test core` command."""
from backend.tests.test_launch import LaunchTests
from backend.tests.test_event_concurrency import EventConcurrencyTests
from backend.tests.test_tag_portal import TagPortalTests, TagPortalConcurrencyTests
