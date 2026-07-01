"""Unit tests for extracted collaboration message storage."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lanhu_mcp.core import messages


class MessageStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_data_dir = messages.DATA_DIR
        messages.DATA_DIR = Path(self._tmp.name)

    def tearDown(self) -> None:
        messages.DATA_DIR = self._orig_data_dir
        self._tmp.cleanup()

    def test_normalize_role(self) -> None:
        self.assertEqual(messages.normalize_role("Python 后端开发"), "后端")
        self.assertEqual(messages.normalize_role("React 前端"), "前端")
        self.assertEqual(messages.normalize_role("iOS 工程师"), "客户端")
        self.assertEqual(messages.normalize_role(""), "未知")

    def test_save_and_read_message(self) -> None:
        store = messages.MessageStore("p1")
        saved = store.save_message(
            summary="S",
            content="C",
            author_name="张三",
            author_role="后端",
            mentions=["前端"],
            project_name="项目",
            doc_id="d1",
        )
        self.assertEqual(saved["id"], 1)
        listed = store.get_messages(user_role="前端")
        self.assertEqual(len(listed), 1)
        self.assertNotIn("content", listed[0])
        self.assertTrue(listed[0]["mentions_me"])

    def test_update_delete_and_detail(self) -> None:
        store = messages.MessageStore("p1")
        store.save_message("S", "C", "张三", "后端")
        updated = store.update_message(1, "李四", "前端", summary="S2")
        self.assertEqual(updated["summary"], "S2")
        detail = store.get_message_by_id(1)
        self.assertEqual(detail["content"], "C")
        self.assertTrue(store.delete_message(1))
        self.assertIsNone(store.get_message_by_id(1))

    def test_grouped_messages(self) -> None:
        p1 = messages.MessageStore("p1")
        p1.save_message("S1", "C1", "张三", "后端", doc_id="d1", doc_name="D")
        p1.save_message("S2", "C2", "李四", "前端", mentions=["所有人"], doc_id="d1", doc_name="D")
        grouped = messages.MessageStore(project_id=None).get_all_messages_grouped(user_role="产品", user_name="李四")
        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]["message_count"], 2)
        self.assertEqual(grouped[0]["mentions_me_count"], 1)
        self.assertTrue(any(m.get("is_mine") for m in grouped[0]["messages"]))

    def test_clean_message_dict(self) -> None:
        msg = {"author_name": "张三", "updated_at": None, "updated_by_name": None, "updated_by_role": None}
        cleaned = messages.clean_message_dict(msg, "张三")
        self.assertFalse(cleaned["is_edited"])
        self.assertTrue(cleaned["is_mine"])
        self.assertNotIn("updated_by_name", cleaned)


if __name__ == "__main__":
    unittest.main()
