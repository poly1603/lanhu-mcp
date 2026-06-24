"""Lanhu MCP Codegen - 设计稿到生产级前端代码的转换引擎"""

from lanhu_mcp.codegen.ir import (
    DesignIR,
    ComponentIR,
    PropSpec,
    StateSpec,
    EventSpec,
    SlotSpec,
    StyleSpec,
    CSSRule,
    InteractionSpec,
    StateMachine,
    StateTransition,
    DependencySpec,
    A11ySpec,
    SemanticTag,
    Framework,
    StylingMode,
)
from lanhu_mcp.codegen.semantic import SemanticAnalyzer
from lanhu_mcp.codegen.style_system import BEMNamer, CSSVariableGenerator, ComponentStyleGenerator
from lanhu_mcp.codegen.interaction import InteractionInference
from lanhu_mcp.codegen.dependency_detector import DependencyDetector

__all__ = [
    "DesignIR",
    "ComponentIR",
    "PropSpec",
    "StateSpec",
    "EventSpec",
    "SlotSpec",
    "StyleSpec",
    "CSSRule",
    "InteractionSpec",
    "StateMachine",
    "StateTransition",
    "DependencySpec",
    "A11ySpec",
    "SemanticTag",
    "Framework",
    "StylingMode",
    "SemanticAnalyzer",
    "BEMNamer",
    "CSSVariableGenerator",
    "ComponentStyleGenerator",
    "InteractionInference",
    "DependencyDetector",
]
