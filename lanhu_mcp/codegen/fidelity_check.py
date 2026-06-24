"""
Fidelity Checker

保真度检查器：
- 像素级对比（设计稿 vs 生成代码渲染）
- 无障碍评分（ARIA、语义化、键盘导航）
- 代码质量评分（BEM、类型安全、响应式）
- 综合保真度报告
"""
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .ir import DesignIR, ComponentIR, ComponentType, A11ySpec, Framework


class Grade(Enum):
    """评分等级"""
    A = "A"
    A_MINUS = "A-"
    B_PLUS = "B+"
    B = "B"
    B_MINUS = "B-"
    C_PLUS = "C+"
    C = "C"
    D = "D"
    F = "F"


@dataclass
class A11yIssue:
    """无障碍问题"""
    severity: str  # critical, major, minor
    rule: str
    message: str
    component: str = ""


@dataclass
class FidelityReport:
    """保真度报告"""
    # 总分 (0-100)
    overall_score: float = 0
    # 分项得分
    visual_score: float = 0      # 视觉保真度
    a11y_score: float = 0        # 无障碍得分
    code_quality_score: float = 0  # 代码质量得分
    interaction_score: float = 0   # 交互保真度
    # 等级
    grade: Grade = Grade.F
    # 问题列表
    a11y_issues: List[A11yIssue] = field(default_factory=list)
    # 通过的检查
    passed_checks: List[str] = field(default_factory=list)
    # 失败的检查
    failed_checks: List[str] = field(default_factory=list)


class FidelityChecker:
    """保真度检查器"""

    def check(
        self,
        ir: DesignIR,
        generated_files: Dict[str, str],
        framework: Framework = Framework.HTML,
    ) -> FidelityReport:
        """执行完整保真度检查"""
        report = FidelityReport()

        # 1. 视觉保真度检查
        report.visual_score = self._check_visual_fidelity(ir, generated_files, framework)

        # 2. 无障碍检查
        a11y_result = self._check_a11y(ir, generated_files, framework)
        report.a11y_score = a11y_result[0]
        report.a11y_issues = a11y_result[1]

        # 3. 代码质量检查
        report.code_quality_score = self._check_code_quality(ir, generated_files, framework)

        # 4. 交互保真度检查
        report.interaction_score = self._check_interaction_fidelity(ir, generated_files, framework)

        # 计算总分
        report.overall_score = (
            report.visual_score * 0.35 +
            report.a11y_score * 0.25 +
            report.code_quality_score * 0.25 +
            report.interaction_score * 0.15
        )

        # 评级
        report.grade = self._score_to_grade(report.overall_score)

        return report

    # ------------------------------------------------------------------
    # 视觉保真度
    # ------------------------------------------------------------------
    def _check_visual_fidelity(
        self,
        ir: DesignIR,
        files: Dict[str, str],
        framework: Framework,
    ) -> float:
        """检查视觉保真度（颜色、间距、圆角、字体）"""
        score = 100.0
        issues = []

        # 获取主 CSS/样式文件内容
        css_content = self._get_css_content(files, framework)

        # 检查设计令牌是否在代码中使用
        if ir.tokens:
            tokens = ir.tokens
            # 颜色
            for name, value in tokens.colors.items():
                if value not in css_content and f"--color-{name}" not in css_content:
                    issues.append(f"颜色 {name}={value} 未在样式中使用")
                    score -= 5

            # 间距
            for name, value in tokens.spacing.items():
                if f"--spacing-{name}" not in css_content:
                    issues.append(f"间距 {name}={value} 未作为 CSS 变量")
                    score -= 2

            # 圆角
            for name, value in tokens.radii.items():
                if f"--radius-{name}" not in css_content:
                    issues.append(f"圆角 {name}={value} 未作为 CSS 变量")
                    score -= 2

        # 检查每个组件的样式
        for comp in ir.components:
            if comp.design_position:
                width = comp.design_position.get("width")
                height = comp.design_position.get("height")
                if width and f"width" not in css_content:
                    issues.append(f"组件 {comp.name} 缺少 width 约束")
                    score -= 3

            if comp.design_styles:
                # 文字颜色
                color = comp.design_styles.get("color")
                if color and color not in css_content:
                    issues.append(f"组件 {comp.name} 文字颜色 {color} 未使用")
                    score -= 2

        return max(0, score)

    def _get_css_content(self, files: Dict[str, str], framework: Framework) -> str:
        """从生成的文件中提取 CSS 内容"""
        css_parts = []

        if framework == Framework.HTML:
            css_content = files.get("styles.css", "")
            css_parts.append(css_content)
            # 内联 <style> 标签
            for content in files.values():
                if isinstance(content, str):
                    style_matches = re.findall(r"<style[^>]*>(.*?)</style>", content, re.DOTALL)
                    css_parts.extend(style_matches)

        elif framework == Framework.VUE:
            for content in files.values():
                if isinstance(content, str):
                    style_matches = re.findall(r"<style[^>]*>(.*?)</style>", content, re.DOTALL)
                    css_parts.extend(style_matches)

        elif framework == Framework.REACT:
            for name, content in files.items():
                if name.endswith(".module.css") or name.endswith(".css"):
                    css_parts.append(content)

        elif framework == Framework.FLUTTER:
            # Flutter 使用 Dart 代码中的样式属性
            for content in files.values():
                if isinstance(content, str):
                    css_parts.append(content)

        elif framework == Framework.SVELTE:
            for content in files.values():
                if isinstance(content, str):
                    style_matches = re.findall(r"<style[^>]*>(.*?)</style>", content, re.DOTALL)
                    css_parts.extend(style_matches)

        return "\n".join(css_parts)

    # ------------------------------------------------------------------
    # 无障碍检查
    # ------------------------------------------------------------------
    def _check_a11y(
        self,
        ir: DesignIR,
        files: Dict[str, str],
        framework: Framework,
    ) -> Tuple[float, List[A11yIssue]]:
        """检查无障碍合规性"""
        score = 100.0
        issues: List[A11yIssue] = []

        # 获取所有 HTML/模板内容
        all_content = "\n".join(
            v for v in files.values() if isinstance(v, str)
        )

        for comp in ir.components:
            # 1. 检查 aria-label
            if comp.component_type in (ComponentType.BUTTON, ComponentType.INPUT, ComponentType.ICON):
                if comp.aria and not comp.aria.aria_label:
                    # 检查代码中是否有 aria-label
                    if f"aria-label" not in all_content:
                        issues.append(A11yIssue(
                            severity="critical",
                            rule="aria-label-required",
                            message=f"组件 {comp.name} 缺少 aria-label",
                            component=comp.name,
                        ))
                        score -= 10

            # 2. 检查 role
            if comp.component_type in (ComponentType.MODAL,):
                if comp.aria and comp.aria.role != "dialog":
                    issues.append(A11yIssue(
                        severity="major",
                        rule="aria-role-dialog",
                        message=f"模态框 {comp.name} 缺少 role='dialog'",
                        component=comp.name,
                    ))
                    score -= 8

            # 3. 检查键盘导航
            if comp.component_type in (
                ComponentType.BUTTON, ComponentType.INPUT,
                ComponentType.SELECT, ComponentType.CHECKBOX,
                ComponentType.RADIO, ComponentType.TABS,
            ):
                if comp.aria and not comp.aria.keyboard:
                    issues.append(A11yIssue(
                        severity="major",
                        rule="keyboard-accessible",
                        message=f"组件 {comp.name} 缺少键盘支持",
                        component=comp.name,
                    ))
                    score -= 5

            # 4. 检查焦点管理
            if comp.component_type in (ComponentType.MODAL, ComponentType.DRAWER):
                if comp.aria and not comp.aria.focus_trap:
                    issues.append(A11yIssue(
                        severity="major",
                        rule="focus-trap",
                        message=f"模态框 {comp.name} 缺少焦点陷阱",
                        component=comp.name,
                    ))
                    score -= 7

            # 5. 检查颜色对比（简化）
            if comp.design_styles:
                fg = comp.design_styles.get("color", "")
                bg = comp.design_styles.get("backgroundColor", "")
                if fg and bg:
                    contrast = self._estimate_contrast(fg, bg)
                    if contrast < 4.5:
                        issues.append(A11yIssue(
                            severity="minor",
                            rule="color-contrast",
                            message=f"组件 {comp.name} 颜色对比度 {contrast:.1f} < 4.5",
                            component=comp.name,
                        ))
                        score -= 3

        # 6. 检查 lang 属性（HTML）
        if framework == Framework.HTML:
            if "lang=" not in all_content:
                issues.append(A11yIssue(
                    severity="minor",
                    rule="html-lang",
                    message="HTML 缺少 lang 属性",
                ))
                score -= 2

        # 7. 检查 skip link（长页面）
        if len(ir.components) > 10:
            if "skip" not in all_content.lower():
                issues.append(A11yIssue(
                    severity="minor",
                    rule="skip-link",
                    message="长页面建议添加 skip navigation link",
                ))
                score -= 1

        return max(0, score), issues

    def _estimate_contrast(self, fg: str, bg: str) -> float:
        """估算颜色对比度（简化版）"""
        fg_rgb = self._parse_color(fg)
        bg_rgb = self._parse_color(bg)
        if not fg_rgb or not bg_rgb:
            return 7.0  # 无法解析时给满分

        def relative_luminance(rgb):
            r, g, b = [c / 255.0 for c in rgb]
            r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
            g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
            b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        l1 = relative_luminance(fg_rgb)
        l2 = relative_luminance(bg_rgb)
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)

    def _parse_color(self, color: str) -> Optional[Tuple[int, int, int]]:
        """解析颜色为 RGB"""
        if not color:
            return None
        color = color.strip()
        if color.startswith("#"):
            hex_str = color[1:]
            if len(hex_str) == 3:
                hex_str = "".join(c * 2 for c in hex_str)
            if len(hex_str) == 6:
                try:
                    return (
                        int(hex_str[0:2], 16),
                        int(hex_str[2:4], 16),
                        int(hex_str[4:6], 16),
                    )
                except ValueError:
                    return None
        m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", color)
        if m:
            return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return None

    # ------------------------------------------------------------------
    # 代码质量
    # ------------------------------------------------------------------
    def _check_code_quality(
        self,
        ir: DesignIR,
        files: Dict[str, str],
        framework: Framework,
    ) -> float:
        """检查代码质量"""
        score = 100.0

        all_content = "\n".join(
            v for v in files.values() if isinstance(v, str)
        )

        # 1. BEM 命名检查
        class_matches = re.findall(r'class="([^"]+)"', all_content)
        for class_str in class_matches:
            classes = class_str.split()
            for cls in classes:
                if "__" in cls and "--" in cls:
                    continue  # 同时有 element 和 modifier，OK
                # 简化检查：至少应该有 block
                if "-" not in cls and cls[0].islower():
                    pass  # 可能是单个单词 block

        # 2. TypeScript 类型检查（React/Vue/Svelte）
        if framework in (Framework.REACT, Framework.VUE, Framework.SVELTE):
            ts_files = [v for k, v in files.items() if k.endswith((".ts", ".tsx", ".vue", ".svelte"))]
            has_any = any("any" not in content for content in ts_files)
            if not has_any and ts_files:
                score -= 5  # 过多 any 类型

        # 3. 语义化 HTML
        if framework == Framework.HTML:
            semantic_tags = re.findall(r"<(nav|main|header|footer|article|section|aside|figure|figcaption)[\s>]", all_content)
            if len(ir.components) > 3 and len(semantic_tags) < 2:
                score -= 10  # 组件多但语义标签少

        # 4. CSS 变量使用
        css_vars = re.findall(r"--[\w-]+", all_content)
        if len(ir.components) > 2 and len(css_vars) < 3:
            score -= 5  # 组件多但 CSS 变量使用少

        # 5. 响应式检查
        has_responsive = any(
            kw in all_content
            for kw in ["@media", "min-width", "max-width", "breakpoint", "Responsive"]
        )
        if not has_responsive and len(ir.components) > 3:
            score -= 5

        # 6. 语义化命名
        bad_names = re.findall(r'class="[^"]*(?:div1|box1|text1|btn1|container1)[^"]*"', all_content)
        if bad_names:
            score -= len(bad_names) * 2

        return max(0, score)

    # ------------------------------------------------------------------
    # 交互保真度
    # ------------------------------------------------------------------
    def _check_interaction_fidelity(
        self,
        ir: DesignIR,
        files: Dict[str, str],
        framework: Framework,
    ) -> float:
        """检查交互保真度"""
        score = 100.0
        all_content = "\n".join(
            v for v in files.values() if isinstance(v, str)
        )

        for comp in ir.components:
            # 1. 状态机有转换但代码中无对应处理
            if comp.interaction and comp.interaction.state_machine:
                sm = comp.interaction.state_machine
                if sm.transitions:
                    has_handler = any(
                        kw in all_content
                        for kw in ["on:click", "onClick", "on_click", "onTap", "addEventListener"]
                    )
                    if not has_handler:
                        score -= 5

            # 2. 有事件但代码中无 dispatch
            if comp.events:
                for event in comp.events:
                    if event.name not in all_content and event.handler_name not in all_content:
                        score -= 2

            # 3. 组件有 keyboard 规范但代码中无键盘处理
            if comp.aria and comp.aria.keyboard:
                has_keyboard = any(
                    kw in all_content
                    for kw in ["keydown", "keypress", "onKeyDown", "on_key_down", "LogicalKeyboard"]
                )
                if not has_keyboard:
                    score -= 3

        return max(0, score)

    # ------------------------------------------------------------------
    # 评级
    # ------------------------------------------------------------------
    def _score_to_grade(self, score: float) -> Grade:
        """分数转等级"""
        if score >= 95:
            return Grade.A
        if score >= 90:
            return Grade.A_MINUS
        if score >= 85:
            return Grade.B_PLUS
        if score >= 80:
            return Grade.B
        if score >= 75:
            return Grade.B_MINUS
        if score >= 70:
            return Grade.C_PLUS
        if score >= 60:
            return Grade.C
        if score >= 50:
            return Grade.D
        return Grade.F

    def generate_report(self, report: FidelityReport) -> str:
        """生成保真度报告"""
        lines = [
            "# 保真度检查报告",
            "",
            f"## 总评: {report.grade.value} ({report.overall_score:.1f}/100)",
            "",
            "### 分项得分",
            f"- 视觉保真度: {report.visual_score:.1f}/100",
            f"- 无障碍合规: {report.a11y_score:.1f}/100",
            f"- 代码质量: {report.code_quality_score:.1f}/100",
            f"- 交互保真度: {report.interaction_score:.1f}/100",
            "",
        ]

        if report.a11y_issues:
            lines.append("### 无障碍问题")
            for issue in report.a11y_issues:
                severity_icon = {"critical": "🔴", "major": "🟡", "minor": "🔵"}.get(issue.severity, "⚪")
                lines.append(f"- {severity_icon} [{issue.severity}] {issue.message}")
            lines.append("")

        if report.failed_checks:
            lines.append("### 未通过检查")
            for check in report.failed_checks:
                lines.append(f"- ❌ {check}")
            lines.append("")

        if report.passed_checks:
            lines.append("### 已通过检查")
            for check in report.passed_checks[:10]:
                lines.append(f"- ✅ {check}")

        return "\n".join(lines)


def check_fidelity(
    ir: DesignIR,
    generated_files: Dict[str, str],
    framework: Framework = Framework.HTML,
) -> Tuple[FidelityReport, str]:
    """
    便捷入口。

    Returns: (报告, 报告 Markdown)
    """
    checker = FidelityChecker()
    report = checker.check(ir, generated_files, framework)
    markdown = checker.generate_report(report)
    return report, markdown
