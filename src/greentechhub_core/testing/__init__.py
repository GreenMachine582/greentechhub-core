"""greentechhub_core.testing — pytest fixtures for a service's own tests,
behind the optional `[testing]` extra. Nothing loads on install: a service
opts in from its conftest, e.g.

    pytest_plugins = ["greentechhub_core.testing.sqlalchemy"]

See docs/testing.md#fixtures-for-a-services-own-tests.
"""
