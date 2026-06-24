"""
DesignIR - 统一中间表示 (Intermediate Representation)

设计稿 → DesignIR → 框架代码

所有框架的代码生成器都消费同一个 IR，确保还原度一致性。
"""
from __future__ import annotations

import json
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Union


# ============================================================
# 枚举定义
# ============================================================

class Framework(str, Enum):
    """目标框架"""
    HTML = "html"
    VUE = "vue"
    REACT = "react"
    FLUTTER = "flutter"
    SVELTE = "svelte"


class StylingMode(str, Enum):
    """样式方案"""
    NATIVE_CSS = "native_css"          # 原生 CSS + BEM
    CSS_MODULES = "css_modules"        # CSS Modules
    SCOPED_CSS = "scoped_css"          # Vue scoped style


class SemanticTag(str, Enum):
    """HTML5 语义化标签"""
    DIV = "div"
    HEADER = "header"
    NAV = "nav"
    MAIN = "main"
    SECTION = "section"
    ARTICLE = "article"
    ASIDE = "aside"
    FOOTER = "footer"
    FIGURE = "figure"
    FIGCAPTION = "figcaption"
    DL = "dl"
    DT = "dt"
    DD = "dd"
    TABLE = "table"
    THEAD = "thead"
    TBODY = "tbody"
    TFOOT = "tfoot"
    TR = "tr"
    TH = "th"
    TD = "td"
    CAPTION = "caption"
    UL = "ul"
    OL = "ol"
    LI = "li"
    P = "p"
    SPAN = "span"
    A = "a"
    STRONG = "strong"
    EM = "em"
    SMALL = "small"
    BUTTON = "button"
    FORM = "form"
    FIELDSET = "fieldset"
    LEGEND = "legend"
    LABEL = "label"
    INPUT = "input"
    TEXTAREA = "textarea"
    SELECT = "select"
    OPTION = "option"
    OPTGROUP = "optgroup"
    DIALOG = "dialog"
    DETAILS = "details"
    SUMMARY = "summary"
    H1 = "h1"
    H2 = "h2"
    H3 = "h3"
    H4 = "h4"
    H5 = "h5"
    H6 = "h6"
    HR = "hr"
    PRE = "pre"
    CODE = "code"
    BLOCKQUOTE = "blockquote"
    IMG = "img"
    VIDEO = "video"
    CANVAS = "canvas"
    SVG = "svg"
    I = "i"


class ComponentType(str, Enum):
    """组件功能类型"""
    CONTAINER = "container"
    BUTTON = "button"
    INPUT = "input"
    SELECT = "select"
    TEXTAREA = "textarea"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SWITCH = "switch"
    SLIDER = "slider"
    DATE_PICKER = "date_picker"
    TIME_PICKER = "time_picker"
    UPLOAD = "upload"
    MODAL = "modal"
    DRAWER = "drawer"
    POPOVER = "popover"
    TOOLTIP = "tooltip"
    DROPDOWN = "dropdown"
    MENU = "menu"
    TABS = "tabs"
    TAB = "tab"
    ACCORDION = "accordion"
    CAROUSEL = "carousel"
    TREE = "tree"
    TABLE = "table"
    LIST = "list"
    FORM = "form"
    ALERT = "alert"
    BADGE = "badge"
    TAG = "tag"
    AVATAR = "avatar"
    BREADCRUMB = "breadcrumb"
    PAGINATION = "pagination"
    STEPS = "steps"
    TRANSFER = "transfer"
    CALENDAR = "calendar"
    TIMELINE = "timeline"
    RESULT = "result"
    EMPTY = "empty"
    SKELETON = "skeleton"
    SPINNER = "spinner"
    TOAST = "toast"
    NAVBAR = "navbar"
    SIDEBAR = "sidebar"
    FOOTER = "footer"
    CARD = "card"
    HERO = "hero"
    SEARCH = "search"
    ICON = "icon"
    IMAGE = "image"
    TEXT = "text"
    DIVIDER = "divider"
    SPACER = "spacer"
    PROGRESS = "progress"
    LOADING = "loading"
    LINK = "link"
    STATUS = "status"


# ============================================================
# 属性 / Props
# ============================================================

@dataclass
class PropSpec:
    """组件属性规格"""
    name: str
    type: str  # string, number, boolean, enum, function, node, object
    default: Any = None
    required: bool = False
    enum_values: List[str] = field(default_factory=list)
    description: str = ""
    # 从设计稿推断的值
    inferred_value: Any = None


@dataclass
class StateSpec:
    """组件状态规格"""
    name: str
    type: str  # boolean, string, number, object, array
    default: Any = None
    # 关联的视觉状态映射
    visual_state: str = ""  # default, hover, focus, active, disabled, loading, success, error


@dataclass
class EventSpec:
    """事件规格"""
    name: str
    handler_name: str = ""
    payload_type: str = ""
    description: str = ""
    # 从交互推断
    bubbles: bool = False
    cancelable: bool = False
    # 关联的状态转换
    triggers_transition: str = ""


@dataclass
class SlotSpec:
    """插槽/子元素规格"""
    name: str  # default, prefix, suffix, header, footer, trigger, content
    type: str = "node"  # node, render_func, string
    description: str = ""
    required: bool = False
    # 默认内容
    default_content: Optional[str] = None


# ============================================================
# 样式系统
# ============================================================

@dataclass
class CSSRule:
    """单条 CSS 规则"""
    selector: str
    properties: Dict[str, str] = field(default_factory=dict)
    # BEM 组件信息
    block: str = ""
    element: str = ""
    modifier: str = ""
    state: str = ""
    # 响应式断点
    breakpoint: str = ""  # mobile, tablet, desktop, wide
    # 容器查询
    container_query: str = ""
    # 暗色模式
    dark_mode: bool = False
    # 媒体查询
    media_query: str = ""


@dataclass
class StyleSpec:
    """组件样式规格"""
    block_name: str  # BEM block: .my-component
    # 设计令牌引用
    color_tokens: Dict[str, str] = field(default_factory=dict)
    spacing_tokens: Dict[str, str] = field(default_factory=dict)
    typography_tokens: Dict[str, str] = field(default_factory=dict)
    shadow_tokens: Dict[str, str] = field(default_factory=dict)
    radius_tokens: Dict[str, str] = field(default_factory=dict)
    # 完整 CSS 规则
    rules: List[CSSRule] = field(default_factory=list)
    # 变体样式
    variants: Dict[str, Dict[str, str]] = field(default_factory=dict)
    # 状态样式
    states: Dict[str, Dict[str, str]] = field(default_factory=dict)
    # 响应式样式
    responsive: Dict[str, List[CSSRule]] = field(default_factory=dict)


# ============================================================
# 交互系统
# ============================================================

@dataclass
class StateTransition:
    """状态转换"""
    from_state: str
    to_state: str
    trigger: str  # event, timer, async_complete, condition
    condition: str = ""
    event: str = ""
    side_effects: List[str] = field(default_factory=list)
    debounce_ms: int = 0
    throttle_ms: int = 0


@dataclass
class StateMachine:
    """状态机"""
    name: str
    initial_state: str
    states: List[str] = field(default_factory=list)
    transitions: List[StateTransition] = field(default_factory=list)
    # 异步操作
    async_operations: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class InteractionSpec:
    """交互规格"""
    component_name: str
    component_type: ComponentType
    state_machine: Optional[StateMachine] = None
    # 事件处理
    events: List[EventSpec] = field(default_factory=list)
    # 表单验证规则
    validation_rules: List[Dict[str, Any]] = field(default_factory=list)
    # 副作用
    side_effects: List[Dict[str, str]] = field(default_factory=list)
    # 插件/库依赖
    required_plugins: List[str] = field(default_factory=list)
    # 动画规格
    animation: Optional[Dict[str, Any]] = None
    # 防抖/节流
    debounce_ms: int = 0
    throttle_ms: int = 0


# ============================================================
# 依赖系统
# ============================================================

@dataclass
class DependencySpec:
    """依赖规格"""
    name: str
    version: str = ""
    type: str = "runtime"  # runtime, dev, peer
    reason: str = ""  # 为什么需要这个依赖
    category: str = ""  # ui, form, state, animation, util, etc.
    # 体积估算
    size_estimate_kb: float = 0
    tree_shakable: bool = True
    # 导入方式
    import_statement: str = ""


# ============================================================
# 无障碍系统
# ============================================================

@dataclass
class A11ySpec:
    """无障碍规格"""
    role: str = ""
    aria_label: str = ""
    aria_labelledby: str = ""
    aria_describedby: str = ""
    aria_expanded: str = ""  # "true" | "false" | "" (动态)
    aria_controls: str = ""
    aria_haspopup: str = ""  # "true", "menu", "listbox", "tree", "grid", "dialog"
    aria_selected: str = ""
    aria_checked: str = ""  # "true", "false", "mixed"
    aria_disabled: str = ""
    aria_live: str = ""  # "polite", "assertive", "off"
    aria_current: str = ""  # "page", "step", "location", "date", "time"
    tabindex: int = -1  # -1=不可tab, 0=自然顺序, >0=自定义顺序
    # 键盘导航
    keyboard: Dict[str, str] = field(default_factory=dict)  # key → action
    # 焦点陷阱
    focus_trap: bool = False
    # 焦点恢复
    focus_restore: bool = False


# ============================================================
# 组件 IR
# ============================================================

@dataclass
class ComponentIR:
    """组件中间表示"""
    # 基础信息
    name: str
    component_type: ComponentType = ComponentType.CONTAINER
    description: str = ""

    # 语义化
    semantic_tag: SemanticTag = SemanticTag.DIV
    aria: Optional[A11ySpec] = None

    # Props/Events/Slots
    props: List[PropSpec] = field(default_factory=list)
    state: List[StateSpec] = field(default_factory=list)
    events: List[EventSpec] = field(default_factory=list)
    slots: List[SlotSpec] = field(default_factory=list)

    # 样式
    style: Optional[StyleSpec] = None

    # 交互
    interaction: Optional[InteractionSpec] = None

    # 子组件
    children: List['ComponentIR'] = field(default_factory=list)

    # 来源信息
    design_path: str = ""  # 设计稿中的路径
    design_position: Dict[str, float] = field(default_factory=dict)  # x, y, width, height
    design_styles: Dict[str, Any] = field(default_factory=dict)  # 原始设计样式

    # 框架特定标记
    is_fragment: bool = False
    is_portal: bool = False
    is_composable: bool = False  # 是否需要抽取为独立可复用组件


# ============================================================
# 页面 IR
# ============================================================

@dataclass
class PageIR:
    """页面中间表示"""
    name: str
    route: str = ""
    title: str = ""
    description: str = ""
    # 语义结构
    semantic_tag: SemanticTag = SemanticTag.MAIN
    # 页面组件树
    components: List[ComponentIR] = field(default_factory=list)
    # 页面级状态管理
    state_specs: List[StateSpec] = field(default_factory=list)
    # 页面级交互
    interactions: List[InteractionSpec] = field(default_factory=list)
    # 布局
    layout: str = ""  # default, centered, sidebar, fullscreen
    # 响应式
    responsive_breakpoints: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # SEO
    meta_title: str = ""
    meta_description: str = ""
    meta_keywords: List[str] = field(default_factory=list)


# ============================================================
# 设计令牌
# ============================================================

@dataclass
class DesignTokens:
    """设计令牌系统"""
    # 色彩
    colors: Dict[str, str] = field(default_factory=dict)
    # 语义化色彩
    semantic_colors: Dict[str, Dict[str, str]] = field(default_factory=dict)
    # 字体
    font_families: Dict[str, str] = field(default_factory=dict)
    font_sizes: Dict[str, str] = field(default_factory=dict)
    font_weights: Dict[str, str] = field(default_factory=dict)
    line_heights: Dict[str, str] = field(default_factory=dict)
    letter_spacings: Dict[str, str] = field(default_factory=dict)
    # 间距
    spacing: Dict[str, str] = field(default_factory=dict)
    # 圆角
    radii: Dict[str, str] = field(default_factory=dict)
    # 阴影
    shadows: Dict[str, str] = field(default_factory=dict)
    # 边框
    borders: Dict[str, str] = field(default_factory=dict)
    # 断点
    breakpoints: Dict[str, str] = field(default_factory=dict)
    # z-index 层级
    z_index: Dict[str, str] = field(default_factory=dict)
    # 过渡/动画
    transitions: Dict[str, str] = field(default_factory=dict)
    # 容器
    containers: Dict[str, str] = field(default_factory=dict)


# ============================================================
# 项目级信息
# ============================================================

@dataclass
class ProjectSpec:
    """项目规格"""
    name: str
    framework: Framework
    styling: StylingMode
    # 目录结构
    src_dir: str = "src"
    components_dir: str = "src/components"
    pages_dir: str = "src/pages"
    styles_dir: str = "src/styles"
    utils_dir: str = "src/utils"
    types_dir: str = "src/types"
    hooks_dir: str = "src/hooks"
    # 依赖
    dependencies: List[DependencySpec] = field(default_factory=list)
    dev_dependencies: List[DependencySpec] = field(default_factory=list)
    # 配置
    config: Dict[str, Any] = field(default_factory=dict)
    # 脚本
    scripts: Dict[str, str] = field(default_factory=dict)
    # 现有项目集成
    existing_project: bool = False
    existing_structure: Dict[str, str] = field(default_factory=dict)
    # 保护区域标记
    protected_markers: List[str] = field(default_factory=lambda: ["@lanhu-protected", "@lanhu-start", "@lanhu-end"])


# ============================================================
# DesignIR - 统一中间表示
# ============================================================

@dataclass
class DesignIR:
    """设计稿统一中间表示 - 所有框架代码生成器的输入"""
    # 元信息
    name: str
    framework: Framework = Framework.HTML
    styling: StylingMode = StylingMode.NATIVE_CSS

    # 设计令牌
    tokens: DesignTokens = field(default_factory=DesignTokens)

    # 组件列表
    components: List[ComponentIR] = field(default_factory=list)

    # 页面列表
    pages: List[PageIR] = field(default_factory=list)

    # 交互规格
    interactions: List[InteractionSpec] = field(default_factory=list)

    # 依赖
    dependencies: List[DependencySpec] = field(default_factory=list)

    # 无障碍
    a11y_tree: Optional[A11ySpec] = None

    # 项目规格
    project: Optional[ProjectSpec] = None

    # 原始设计数据引用
    original_url: str = ""
    design_name: str = ""
    design_scale: float = 2.0

    def to_json(self) -> str:
        """序列化为 JSON"""
        def _default(obj):
            if isinstance(obj, Enum):
                return obj.value
            if hasattr(obj, '__dict__'):
                return asdict(obj)
            return str(obj)
        return json.dumps(asdict(self), ensure_ascii=False, indent=2, default=_default)

    def get_component_by_name(self, name: str) -> Optional[ComponentIR]:
        """按名称查找组件"""
        for comp in self.components:
            if comp.name == name:
                return comp
            found = self._find_in_children(comp, name)
            if found:
                return found
        return None

    def _find_in_children(self, comp: ComponentIR, name: str) -> Optional[ComponentIR]:
        for child in comp.children:
            if child.name == name:
                return child
            found = self._find_in_children(child, name)
            if found:
                return found
        return None

    def get_all_components_flat(self) -> List[ComponentIR]:
        """扁平化获取所有组件（包括子组件）"""
        result = []
        for comp in self.components:
            result.append(comp)
            result.extend(self._flatten_children(comp))
        return result

    def _flatten_children(self, comp: ComponentIR) -> List[ComponentIR]:
        result = []
        for child in comp.children:
            result.append(child)
            result.extend(self._flatten_children(child))
        return result

    def get_page_by_route(self, route: str) -> Optional[PageIR]:
        """按路由查找页面"""
        for page in self.pages:
            if page.route == route:
                return page
        return None
