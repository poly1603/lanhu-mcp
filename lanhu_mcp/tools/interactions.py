"""交互/状态提取 - 从Axure原型中提取交互规格"""
from typing import Optional


def extract_interactions_from_axure(axure_data: dict) -> dict:
    """
    从 Axure 页面数据中提取交互规格。

    Args:
        axure_data: Axure 页面数据（含 annotations, objectPaths）

    Returns:
        包含 click_areas, form_inputs, scroll, states 的交互规格
    """
    if not axure_data:
        return {'click_areas': [], 'form_inputs': [], 'scroll': {}, 'states': []}

    annotations = axure_data.get('page', {}).get('annotations', [])
    object_paths = axure_data.get('objectPaths', {})

    click_areas = []
    form_inputs = []
    states = []

    for annotation in annotations:
        owner_id = annotation.get('ownerId', '')
        label = annotation.get('label', '')
        note_html = annotation.get('注释', '') or annotation.get('note', '') or annotation.get('description', '')
        note_text = _strip_html(note_html) if note_html else ''

        # 从标注文本中提取交互信息
        interaction = _parse_interaction_from_note(note_text, label)

        if interaction:
            if interaction.get('type') == 'click':
                click_areas.append({
                    'name': label,
                    'note': note_text[:200],
                    **interaction,
                })
            elif interaction.get('type') == 'input':
                form_inputs.append({
                    'name': label,
                    'note': note_text[:200],
                    **interaction,
                })

    return {
        'click_areas': click_areas,
        'form_inputs': form_inputs,
        'scroll': {},
        'states': states,
    }


def _strip_html(html: str) -> str:
    """去除HTML标签"""
    import re
    if not html:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', str(html), flags=re.IGNORECASE)
    text = re.sub(r'</p\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _parse_interaction_from_note(note_text: str, label: str) -> Optional[dict]:
    """从标注文本中解析交互类型"""
    if not note_text:
        return None

    note_lower = note_text.lower()

    # 识别点击交互
    click_keywords = ['点击', '跳转', '进入', '切换', '打开', '关闭', '展开', '收起',
                       'click', 'tap', 'navigate', 'go to', 'switch to']
    for kw in click_keywords:
        if kw in note_lower:
            # 提取目标页面
            target = None
            import re
            patterns = [
                r'(?:跳转|进入|打开|切换到?|点击进入?|go to|navigate to)\s*[「「【《]?(.+?)[」」】》]?',
                r'(?:→|->|➡)\s*(.+?)(?:\n|$)',
            ]
            for pat in patterns:
                m = re.search(pat, note_text, re.IGNORECASE)
                if m:
                    target = m.group(1).strip()
                    break

            return {
                'type': 'click',
                'action': kw,
                'target': target,
            }

    # 识别输入交互
    input_keywords = ['输入', '填写', '搜索', '输入框', '表单', 'input', 'search', 'form', '填写表单']
    for kw in input_keywords:
        if kw in note_lower:
            validation = None
            import re
            patterns = [
                r'(?:校验|验证|validate)[：:]\s*(.+?)(?:\n|$)',
                r'(?:格式|format)[：:]\s*(.+?)(?:\n|$)',
                r'(\d+位(?:数字|字母|字符))',
            ]
            for pat in patterns:
                m = re.search(pat, note_text, re.IGNORECASE)
                if m:
                    validation = m.group(1).strip()
                    break

            required = '必填' in note_text or 'required' in note_lower
            return {
                'type': 'input',
                'input_type': 'text',
                'validation': validation,
                'required': required,
            }

    # 识别滚动交互
    scroll_keywords = ['滚动', '滑动', '上下滑', 'scroll', 'swipe']
    for kw in scroll_keywords:
        if kw in note_lower:
            return {
                'type': 'scroll',
                'direction': 'vertical' if '上下' in note_text or 'vertical' in note_lower else 'horizontal',
            }

    # 识别状态变化
    state_keywords = ['状态', '禁用', '不可点击', 'loading', 'disabled', 'state', 'disabled']
    for kw in state_keywords:
        if kw in note_lower:
            return {
                'type': 'state',
                'state': kw,
            }

    return None


def extract_interactions_from_screenshot(page_text: str) -> dict:
    """
    从页面截图文本中提取交互线索。

    Args:
        page_text: 从Playwright提取的页面文本

    Returns:
        交互线索列表
    """
    import re

    clues = []

    # 识别按钮文本
    button_patterns = [
        r'(?:按钮|button)[：:]\s*(.+?)(?:\n|$)',
        r'[\[【](.+?)[】\]]\s*(?:按钮|button)',
    ]
    for pat in button_patterns:
        for m in re.finditer(pat, page_text, re.IGNORECASE):
            clues.append({'type': 'button', 'text': m.group(1).strip()})

    # 识别表单提示
    form_patterns = [
        r'(?:请输入|请填写|请输入您的|请输入正确的)\s*(.+?)(?:\n|$)',
        r'placeholder[：:]\s*(.+?)(?:\n|$)',
    ]
    for pat in form_patterns:
        for m in re.finditer(pat, page_text, re.IGNORECASE):
            clues.append({'type': 'input', 'placeholder': m.group(1).strip()})

    # 识别链接/导航
    nav_patterns = [
        r'(?:去|查看|查看更多|查看详情|了解更多)\s*(.+?)(?:\n|$)',
    ]
    for pat in nav_patterns:
        for m in re.finditer(pat, page_text, re.IGNORECASE):
            clues.append({'type': 'navigation', 'target': m.group(1).strip()})

    return {'clues': clues[:20]}
