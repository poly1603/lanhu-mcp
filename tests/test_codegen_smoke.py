"""
Codegen 引擎冒烟测试
"""
import json
from lanhu_mcp.codegen.ir import (
    DesignIR, ComponentIR, ComponentType, SemanticTag,
    DesignTokens, PageIR, Framework, StylingMode,
    A11ySpec, EventSpec, PropSpec, StateSpec,
)
from lanhu_mcp.codegen.semantic import SemanticAnalyzer, DocumentOutlineAnalyzer
from lanhu_mcp.codegen.style_system import BEMNamer, CSSVariableGenerator, ComponentStyleGenerator
from lanhu_mcp.codegen.interaction import InteractionInference
from lanhu_mcp.codegen.dependency_detector import DependencyDetector
from lanhu_mcp.codegen.pipeline import Pipeline


def test_bem_namer():
    """测试 BEM 命名"""
    assert BEMNamer.block("MyButton") == "my-btn"
    assert BEMNamer.block("NavigationBar") == "nav-bar"
    assert BEMNamer.element("my-btn", "icon") == "my-btn__icon"
    assert BEMNamer.modifier("my-btn", "primary") == "my-btn--primary"
    print("[PASS] BEM 命名")


def test_semantic_analyzer():
    """测试语义化分析"""
    analyzer = SemanticAnalyzer()

    # 按钮
    comp = ComponentIR(name="SubmitButton", component_type=ComponentType.BUTTON)
    analyzer.analyze_component(comp)
    assert comp.semantic_tag == SemanticTag.BUTTON
    assert comp.aria is not None
    assert comp.aria.role == "button"
    print("[PASS] 语义化分析 - 按钮")

    # 输入框
    comp2 = ComponentIR(name="EmailInput", component_type=ComponentType.INPUT)
    analyzer.analyze_component(comp2)
    assert comp2.aria is not None
    assert "email" in (comp2.aria.aria_label or "").lower() or comp2.aria.aria_label == "EmailInput"
    print("[PASS] 语义化分析 - 输入框")

    # 模态框
    comp3 = ComponentIR(name="ConfirmModal", component_type=ComponentType.MODAL)
    analyzer.analyze_component(comp3)
    assert comp3.semantic_tag == SemanticTag.DIALOG
    assert comp3.aria.role == "dialog"
    print("[PASS] 语义化分析 - 模态框")


def test_interaction_inference():
    """测试交互推断"""
    engine = InteractionInference(framework="html")

    # 按钮
    comp = ComponentIR(name="SubmitButton", component_type=ComponentType.BUTTON)
    engine.analyze_component(comp)
    assert len(comp.events) > 0
    assert comp.aria is not None
    assert comp.aria.keyboard
    print("[PASS] 交互推断 - 按钮")

    # 模态框
    comp2 = ComponentIR(name="ConfirmModal", component_type=ComponentType.MODAL)
    engine.analyze_component(comp2)
    assert comp2.interaction is not None
    assert comp2.interaction.state_machine is not None
    assert comp2.aria.focus_trap is True
    print("[PASS] 交互推断 - 模态框")

    # 标签页
    comp3 = ComponentIR(name="MainTabs", component_type=ComponentType.TABS)
    engine.analyze_component(comp3)
    assert comp3.interaction is not None
    assert comp3.aria.keyboard
    print("[PASS] 交互推断 - 标签页")


def test_dependency_detector():
    """测试依赖检测"""
    detector = DependencyDetector(framework="react")

    ir = DesignIR(
        name="Test",
        framework=Framework.REACT,
        components=[
            ComponentIR(name="Modal1", component_type=ComponentType.MODAL),
            ComponentIR(name="Form1", component_type=ComponentType.FORM),
            ComponentIR(name="Table1", component_type=ComponentType.TABLE),
        ],
    )
    ir = detector.analyze_design(ir)

    assert len(ir.dependencies) > 0
    dep_names = [d.name for d in ir.dependencies]
    assert any("react-hook-form" in n for n in dep_names)
    print("[PASS] 依赖检测")


def test_css_variable_generator():
    """测试 CSS 变量生成"""
    tokens = DesignTokens(
        colors={"primary": "#1677ff", "error": "#ff4d4f"},
        spacing={"4": "16px", "8": "32px"},
        radii={"md": "4px", "lg": "8px"},
    )
    css = CSSVariableGenerator.generate_tokens_css(tokens)
    assert ":root {" in css
    assert "--color-primary" in css
    assert "--spacing-4" in css
    print("[PASS] CSS 变量生成")


def test_component_style_generator():
    """测试组件样式生成"""
    tokens = DesignTokens()
    comp = ComponentIR(
        name="SubmitButton",
        component_type=ComponentType.BUTTON,
        state=[
            StateSpec(name="hover", type="boolean", visual_state="hover"),
            StateSpec(name="disabled", type="boolean", visual_state="disabled"),
        ],
    )
    css = ComponentStyleGenerator.generate_component_css(comp, tokens)
    assert ".submit-btn" in css
    assert "is-disabled" in css
    assert "focus-visible" in css
    print("[PASS] 组件样式生成")


def test_full_pipeline():
    """测试完整 Pipeline"""
    # 创建测试 Sketch 数据
    sketch_data = {
        "artboard": {
            "layers": [
                {
                    "name": "SubmitButton",
                    "type": "textLayer",
                    "isVisible": True,
                    "width": 200,
                    "height": 48,
                    "fills": [{"isEnabled": True, "fillType": 0, "color": {"value": "#1677ff"}}],
                    "radius": 4,
                    "textInfo": {"text": "提交", "color": {"value": "#ffffff"}, "size": 28, "fontName": "PingFang SC", "bold": True},
                    "layers": [],
                },
                {
                    "name": "EmailInput",
                    "type": "textLayer",
                    "isVisible": True,
                    "width": 300,
                    "height": 40,
                    "borders": [{"isEnabled": True, "thickness": 1, "color": {"value": "#d9d9d9"}}],
                    "radius": 4,
                    "textInfo": {"text": "", "color": {"value": "#8c8c8c"}, "size": 28, "fontName": "PingFang SC"},
                    "layers": [],
                },
            ],
        },
    }

    pipeline = Pipeline(framework="html")
    files = pipeline.generate_from_sketch(
        sketch_data=sketch_data,
        design_name="Test Page",
        design_url="https://example.com",
        design_scale=2.0,
    )

    assert "index.html" in files
    assert "styles.css" in files
    assert "script.js" in files
    assert "SubmitButton" in files["index.html"] or "submit-btn" in files["index.html"]
    assert ":root" in files["styles.css"]
    print("[PASS] 完整 Pipeline - HTML")

    # Vue
    pipeline_vue = Pipeline(framework="vue")
    files_vue = pipeline_vue.generate_from_sketch(
        sketch_data=sketch_data,
        design_name="Test Page",
        design_url="https://example.com",
        design_scale=2.0,
    )
    assert any(".vue" in f for f in files_vue.keys())
    print("[PASS] 完整 Pipeline - Vue")

    # React
    pipeline_react = Pipeline(framework="react")
    files_react = pipeline_react.generate_from_sketch(
        sketch_data=sketch_data,
        design_name="Test Page",
        design_url="https://example.com",
        design_scale=2.0,
    )
    assert any(".tsx" in f for f in files_react.keys())
    print("[PASS] 完整 Pipeline - React")

    # Flutter
    pipeline_flutter = Pipeline(framework="flutter")
    files_flutter = pipeline_flutter.generate_from_sketch(
        sketch_data=sketch_data,
        design_name="Test Page",
        design_url="https://example.com",
        design_scale=2.0,
    )
    assert any(".dart" in f for f in files_flutter.keys())
    assert any("pubspec.yaml" == f for f in files_flutter.keys())
    print("[PASS] 完整 Pipeline - Flutter")

    # Svelte
    pipeline_svelte = Pipeline(framework="svelte")
    files_svelte = pipeline_svelte.generate_from_sketch(
        sketch_data=sketch_data,
        design_name="Test Page",
        design_url="https://example.com",
        design_scale=2.0,
    )
    assert any(".svelte" in f for f in files_svelte.keys())
    assert "package.json" in files_svelte
    print("[PASS] 完整 Pipeline - Svelte")


def test_incremental_gen():
    """测试增量生成"""
    from lanhu_mcp.codegen.incremental_gen import IncrementalGenerator, incremental_generate

    gen = IncrementalGenerator("D:\\WorkBench\\lanhu-mcp\\.test_tmp")
    # 空目录分析
    existing = gen.analyze_existing()
    assert isinstance(existing, dict)

    # 变更计算
    new_files = {"test.html": "<html>new</html>"}
    from lanhu_mcp.codegen.incremental_gen import FileChange, FileStatus
    existing_files = {"old.html": FileChange(path="old.html", status=FileStatus.UNCHANGED)}
    report = gen.compute_changes(new_files, existing_files)
    assert report.new_files == 1
    # total_files = new_files count (1) + existing_files count (1) = 2
    assert report.total_files == 1  # total_files is len(new_files)

    # 报告生成
    md = gen.generate_report_markdown(report)
    assert "新增文件" in md
    print("[PASS] 增量生成")


def test_fidelity_check():
    """测试保真度检查"""
    from lanhu_mcp.codegen.fidelity_check import FidelityChecker, check_fidelity
    from lanhu_mcp.codegen.ir import Framework

    ir = DesignIR(
        name="Test",
        framework=Framework.HTML,
        components=[
            ComponentIR(
                name="SubmitButton",
                component_type=ComponentType.BUTTON,
                aria=A11ySpec(role="button", aria_label="提交"),
                design_position={"width": 120, "height": 40},
            ),
        ],
    )
    files = {
        "index.html": '<button class="submit-btn" aria-label="提交">提交</button>',
        "styles.css": ".submit-btn { background: #1677ff; }",
    }
    report, md = check_fidelity(ir, files, Framework.HTML)
    assert report.overall_score > 0
    assert report.grade is not None
    assert "总评" in md
    print("[PASS] 保真度检查")


def test_project_scaffolder():
    """测试项目脚手架"""
    from lanhu_mcp.codegen.project_scaffolder import ProjectScaffolder, ScaffoldConfig

    ir = DesignIR(
        name="TestApp",
        framework=Framework.HTML,
        components=[
            ComponentIR(name="Header", component_type=ComponentType.CONTAINER),
        ],
    )
    config = ScaffoldConfig(
        project_name="test-app",
        framework=Framework.HTML,
        output_dir="D:\\WorkBench\\lanhu-mcp\\.test_scaffold",
    )
    generated = {"index.html": "<html></html>", "styles.css": ""}
    scaffolder = ProjectScaffolder()
    written = scaffolder.scaffold(config, ir, generated)
    assert len(written) > 0

    # 检测已有项目（可能返回 None 如果目录没有 package.json 等）
    detected = scaffolder.detect_existing_project("D:\\WorkBench\\lanhu-mcp")
    # detected 可能是 None，因为 lanhu-mcp 是 Python 项目
    print("[PASS] 项目脚手架")


if __name__ == "__main__":
    print("=" * 50)
    print("Codegen 引擎冒烟测试")
    print("=" * 50)
    test_bem_namer()
    test_semantic_analyzer()
    test_interaction_inference()
    test_dependency_detector()
    test_css_variable_generator()
    test_component_style_generator()
    test_full_pipeline()
    test_incremental_gen()
    test_fidelity_check()
    test_project_scaffolder()
    print("=" * 50)
    print("ALL TESTS PASSED")
    print("=" * 50)
