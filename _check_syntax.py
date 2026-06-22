import ast, sys
filepath = r'D:\WorkBench\lanhu-mcp\lanhu_mcp_server.py'
try:
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()
    ast.parse(source, filename=filepath)
    print('Syntax OK')
    sys.exit(0)
except SyntaxError as e:
    print(f'Syntax Error at line {e.lineno}: {e.msg}')
    print(f'  Text: {e.text}')
    sys.exit(1)
