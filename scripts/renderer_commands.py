"""Identify Ink text glued to the game's >>> command lines."""
from typing import Any
import re


def command_locations(story: Any, command_name: str) -> list[str]:
    """Map compiled JSON addresses to Ink runtime content paths."""
    locations = []

    def visit(node: Any, path: tuple[str, ...]) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == 'root' and not path:
                    visit(value, ())
                else:
                    visit(value, path + (key,))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                if value == '^>>> ' + command_name:
                    locations.append('.'.join(path + (str(index),)))
                elif isinstance(value, list):
                    visit(value, path + (str(index),))
                elif isinstance(value, dict):
                    # A container's final dictionary holds named children, not an indexed child.
                    visit(value, path)

    visit(story, ())
    return locations


def command_arguments(story: Any) -> set[str]:
    arguments: set[str] = set()

    def visit(node: Any, inherited_command: bool = False) -> None:
        if isinstance(node, dict):
            for value in node.values():
                visit(value, inherited_command)
        elif isinstance(node, list):
            command = inherited_command
            pending_break = False
            for value in node:
                if isinstance(value, str):
                    if value == "<>":
                        pending_break = False
                    elif value == "\n":
                        pending_break = True
                    elif value.startswith("^"):
                        if pending_break:
                            command = False
                        if value.startswith("^>>>"):
                            command = True
                        elif command:
                            arguments.add(value)
                        pending_break = False
                else:
                    visit(value, command and not pending_break)

    visit(story)
    return arguments


def renderer_contracts(story: Any) -> dict[tuple, tuple[str, str]]:
    """Index immutable renderer syntax at EVERY compiled occurrence.

    Margin helpers output a quoted metadata field via ``^^\"`` and a later
    ``^\"``. The closing quote is not a quotation mark in the visible prose.
    Social-summary keys precede quoted translated descriptions, or are bare
    three-field section headers. Never infer these contracts from RU text.
    """
    contracts = {}
    arguments = command_arguments(story)

    def visit(node, path=()):
        if isinstance(node, dict):
            for key, child in node.items():
                visit(child, path + (key,))
        elif isinstance(node, list):
            margin_pending = False
            for index, child in enumerate(node):
                address = path + (index,)
                if child == '^^"':
                    contracts[address] = ('exact', child)
                    margin_pending = True
                elif isinstance(child, str) and margin_pending and child.startswith('^'):
                    if child.startswith('^"'):
                        contracts[address] = ('prefix', '^"')
                    margin_pending = False
                visit(child, address)
        elif isinstance(node, str):
            if not node.startswith('^'):
                contracts[path] = ('exact', node)  # Ink bytecode, not prose.
            elif node.startswith('^>>>'):
                prefix = node.split('"', 1)[0]
                contracts[path] = ('prefix', prefix)
            elif match := re.match(r'^\^"?\s*@[A-Za-z][^\s]*', node):
                contracts[path] = ('prefix', match[0])
            elif match := re.match(r'^\^(?:HEADER|INFO|SMALL|MARGIN|INV|STYLE [A-Z]+):', node):
                contracts[path] = ('prefix', match[0])
            elif node in arguments:
                # Quoted keyed descriptions in ui-social-choices, not text
                # continued inside an already-open UI parameter.
                match = re.match(r'^\^\s+[A-Za-z0-9_-]+\s+"', node)
                if match:
                    contracts[path] = ('prefix', match[0])
                elif re.fullmatch(r'\^\s+\d+-[\w-]+\s+\d+-[\w-]+\s+\d+\s*', node):
                    contracts[path] = ('exact', node)
    visit(story)
    for record in technical_literal_paths(story):
        contracts[record['path']] = ('exact', record['literal'])
    return contracts


def technical_literal_paths(story: Any) -> list[dict]:
    """Conservative bytecode evidence: comparison operands and external args.

    Do not classify every Ink ``str`` as technical: choice labels also use str.
    No-argument externals consume no string, even if a label precedes them.
    """
    result = []
    operators = {'==', '!=', '>', '<', '>=', '<=', '?', '!?'}

    def visit(node, path=()):
        if isinstance(node, dict):
            for key, child in node.items():
                visit(child, path + (key,))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                if (isinstance(value, str) and value.startswith('^') and index > 0
                        and node[index - 1] == 'str' and index + 2 < len(node)
                        and node[index + 1] == '/str'):
                    following = node[index + 2]
                    usage = None
                    if isinstance(following, str) and following in operators:
                        usage = 'comparison-rhs'
                    elif (isinstance(following, dict) and index + 3 < len(node)
                          and isinstance(node[index + 3], str) and node[index + 3] in operators
                          and ('VAR?' in following or ('x()' in following and not following.get('exArgs', 0)))):
                        usage = 'comparison-lhs'
                    elif isinstance(following, dict) and following.get('exArgs', 0) > 0:
                        usage = 'external-argument'
                    if usage:
                        result.append({'path': path + (index,), 'literal': value, 'usage': usage})
                visit(value, path + (index,))
    visit(story)
    return result


def contract_errors(source: Any, translated: Any) -> list[dict]:
    errors = []
    for path, (kind, expected) in renderer_contracts(source).items():
        value = translated
        try:
            for key in path:
                value = value[key]
            valid = isinstance(value, str) and (value == expected if kind == 'exact'
                                                 else value.startswith(expected))
        except (IndexError, KeyError, TypeError):
            valid = False
        if not valid:
            errors.append({'path': list(path), 'contract': kind,
                           'syntax': expected})
    return errors


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument('story', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--command', default='ui-character-creation')
    args = parser.parse_args()
    story = json.loads(args.story.read_text(encoding='utf-8-sig'))
    paths = command_locations(story, args.command)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(paths, indent=2) + '\n', encoding='utf-8')
    print(f'Indexed {len(paths)} {args.command} commands')
