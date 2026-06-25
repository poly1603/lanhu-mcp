"""Unit tests for recent-project tracking in lanhu_mcp.core.projects.

Dependency-free: redirects the data dir to a temp folder so no real
``%APPDATA%`` cache is touched.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lanhu_mcp.core import projects as projects_core


class RecentProjectsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        tmp_dir = Path(self._tmp.name)
        self._orig_dir = projects_core.DATA_DIR
        self._orig_file = projects_core.RECENT_PROJECTS_FILE
        projects_core.DATA_DIR = tmp_dir
        projects_core.RECENT_PROJECTS_FILE = tmp_dir / "recent_projects.json"

    def tearDown(self) -> None:
        projects_core.DATA_DIR = self._orig_dir
        projects_core.RECENT_PROJECTS_FILE = self._orig_file
        self._tmp.cleanup()

    def test_empty_when_no_file(self) -> None:
        self.assertEqual(projects_core.recent_projects(), [])

    def test_record_and_read_back(self) -> None:
        projects_core.record_recent_project(
            {"id": "1", "team_id": "t1", "name": "A", "url": "u1"}, account_id="acc")
        items = projects_core.recent_projects("acc")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "A")
        self.assertTrue(items[0]["opened_at"])

    def test_most_recent_first_and_dedup(self) -> None:
        projects_core.record_recent_project({"id": "1", "team_id": "t1", "name": "A"})
        projects_core.record_recent_project({"id": "2", "team_id": "t1", "name": "B"})
        # Re-open A -> moves to front, no duplicate.
        projects_core.record_recent_project({"id": "1", "team_id": "t1", "name": "A2"})
        items = projects_core.recent_projects()
        self.assertEqual([it["id"] for it in items], ["1", "2"])
        self.assertEqual(items[0]["name"], "A2")

    def test_limit_enforced(self) -> None:
        for i in range(15):
            projects_core.record_recent_project({"id": str(i), "team_id": "t", "name": str(i)})
        items = projects_core.recent_projects(limit=10)
        self.assertEqual(len(items), 10)
        # Newest id (14) is first.
        self.assertEqual(items[0]["id"], "14")

    def test_account_scoping(self) -> None:
        projects_core.record_recent_project({"id": "1", "team_id": "t", "name": "A"}, account_id="acc1")
        projects_core.record_recent_project({"id": "2", "team_id": "t", "name": "B"}, account_id="acc2")
        only1 = projects_core.recent_projects("acc1")
        self.assertEqual([it["id"] for it in only1], ["1"])

    def test_invalid_project_ignored(self) -> None:
        projects_core.record_recent_project({}, account_id="acc")
        self.assertEqual(projects_core.recent_projects(), [])


if __name__ == "__main__":
    unittest.main()
