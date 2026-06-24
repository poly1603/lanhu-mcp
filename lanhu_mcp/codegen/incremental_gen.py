"""
Incremental Generator

基于 git diff 感知的增量生成：
- 检测已有文件变更状态（new/modified/deleted）
- 保护手动修改的区域
- 只更新未手动修改的文件
- 变更报告
"""
import os
import hashlib
import json
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum


class FileStatus(Enum):
    """文件变更状态"""
    NEW = "new"
    MODIFIED = "modified"
    DELETED = "deleted"
    UNCHANGED = "unchanged"
    PROTECTED = "protected"  # 手动修改过，保护


@dataclass
class FileChange:
    """文件变更记录"""
    path: str
    status: FileStatus
    # 内容 hash（用于检测手动修改）
    content_hash: str = ""
    # 原始内容（如果读取过）
    original_content: Optional[str] = None


@dataclass
class IncrementalReport:
    """增量生成报告"""
    total_files: int = 0
    new_files: int = 0
    updated_files: int = 0
    protected_files: int = 0
    skipped_files: int = 0
    changes: List[FileChange] = field(default_factory=list)


class IncrementalGenerator:
    """增量代码生成器"""

    # 标记文件中手动修改的区域
    PROTECT_BEGIN = "// === MANUAL BEGIN ==="
    PROTECT_END = "// === MANUAL END ==="

    def __init__(self, output_dir: str, protect_manual: bool = True):
        self.output_dir = output_dir
        self.protect_manual = protect_manual
        # 缓存已有文件的 hash
        self._existing_hashes: Dict[str, str] = {}

    def analyze_existing(self) -> Dict[str, FileChange]:
        """分析已有目录中的文件状态"""
        changes = {}
        if not os.path.exists(self.output_dir):
            return changes

        for root, dirs, files in os.walk(self.output_dir):
            # 跳过隐藏目录和 node_modules
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]

            for filename in files:
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, self.output_dir).replace("\\", "/")
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    content_hash = hashlib.md5(content.encode()).hexdigest()
                    self._existing_hashes[rel_path] = content_hash
                    changes[rel_path] = FileChange(
                        path=rel_path,
                        status=FileStatus.UNCHANGED,
                        content_hash=content_hash,
                        original_content=content,
                    )
                except IOError:
                    pass

        return changes

    def compute_changes(
        self,
        new_files: Dict[str, str],
        existing: Dict[str, FileChange],
    ) -> IncrementalReport:
        """比较新生成的文件和已有文件，计算变更"""
        report = IncrementalReport()
        report.total_files = len(new_files)

        for rel_path, content in new_files.items():
            new_hash = hashlib.md5(content.encode()).hexdigest()

            if rel_path not in existing:
                # 新文件
                change = FileChange(
                    path=rel_path,
                    status=FileStatus.NEW,
                    content_hash=new_hash,
                )
                report.changes.append(change)
                report.new_files += 1

            elif existing[rel_path].content_hash != new_hash:
                # 文件有变更
                if self.protect_manual and self._has_manual_sections(existing[rel_path].original_content or ""):
                    # 有手动修改区域，标记为保护
                    change = FileChange(
                        path=rel_path,
                        status=FileStatus.PROTECTED,
                        content_hash=new_hash,
                        original_content=existing[rel_path].original_content,
                    )
                    report.changes.append(change)
                    report.protected_files += 1
                else:
                    # 无手动修改区域，可以更新
                    change = FileChange(
                        path=rel_path,
                        status=FileStatus.MODIFIED,
                        content_hash=new_hash,
                    )
                    report.changes.append(change)
                    report.updated_files += 1

            else:
                # 未变更
                change = FileChange(
                    path=rel_path,
                    status=FileStatus.UNCHANGED,
                    content_hash=new_hash,
                )
                report.changes.append(change)
                report.skipped_files += 1

        return report

    def apply_changes(
        self,
        new_files: Dict[str, str],
        report: IncrementalReport,
    ) -> Dict[str, str]:
        """根据报告应用变更，返回实际写入的文件"""
        written = {}

        for change in report.changes:
            if change.status == FileStatus.UNCHANGED:
                continue

            if change.status == FileStatus.PROTECTED:
                # 保护手动修改，只追加新内容
                merged = self._merge_protected(change, new_files.get(change.path, ""))
                if merged:
                    full_path = os.path.join(self.output_dir, change.path)
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(merged)
                    written[change.path] = merged
                continue

            if change.status in (FileStatus.NEW, FileStatus.MODIFIED):
                content = new_files.get(change.path, "")
                if content:
                    full_path = os.path.join(self.output_dir, change.path)
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    written[change.path] = content

        return written

    def _has_manual_sections(self, content: str) -> bool:
        """检查文件是否包含手动修改标记"""
        return self.PROTECT_BEGIN in content and self.PROTECT_END in content

    def _merge_protected(self, change: FileChange, new_content: str) -> str:
        """合并保护区域，保留手动修改的部分"""
        if not change.original_content or not new_content:
            return new_content

        original = change.original_content
        # 提取手动修改区域
        manual_sections = []
        pos = 0
        while True:
            begin = original.find(self.PROTECT_BEGIN, pos)
            if begin == -1:
                break
            end = original.find(self.PROTECT_END, begin)
            if end == -1:
                break
            manual_sections.append(original[begin:end + len(self.PROTECT_END)])
            pos = end + len(self.PROTECT_END)

        if not manual_sections:
            return new_content

        # 在新内容的对应位置插入手动区域
        result = new_content
        for section in manual_sections:
            # 查找新内容中是否有保护标记
            begin = result.find(self.PROTECT_BEGIN)
            if begin != -1:
                end = result.find(self.PROTECT_END, begin)
                if end != -1:
                    result = result[:begin] + section + result[end + len(self.PROTECT_END):]

        return result

    def generate_report_markdown(self, report: IncrementalReport) -> str:
        """生成变更报告 Markdown"""
        lines = [
            "# 增量生成报告",
            "",
            f"- 总文件数: {report.total_files}",
            f"- 新增文件: {report.new_files}",
            f"- 更新文件: {report.updated_files}",
            f"- 保护文件: {report.protected_files}",
            f"- 跳过文件: {report.skipped_files}",
            "",
            "## 变更详情",
            "",
        ]

        for change in report.changes:
            status_emoji = {
                FileStatus.NEW: "🆕",
                FileStatus.MODIFIED: "📝",
                FileStatus.PROTECTED: "🔒",
                FileStatus.UNCHANGED: "✅",
                FileStatus.DELETED: "🗑️",
            }.get(change.status, "❓")
            lines.append(f"- {status_emoji} `{change.path}` ({change.status.value})")

        return "\n".join(lines)


def incremental_generate(
    output_dir: str,
    new_files: Dict[str, str],
    protect_manual: bool = True,
) -> Tuple[Dict[str, str], IncrementalReport]:
    """
    增量生成入口。

    Returns: (实际写入的文件, 变更报告)
    """
    gen = IncrementalGenerator(output_dir, protect_manual)
    existing = gen.analyze_existing()
    report = gen.compute_changes(new_files, existing)
    written = gen.apply_changes(new_files, report)
    return written, report
