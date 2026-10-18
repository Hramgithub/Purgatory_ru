"""Identify Ink text glued to the game's >>> command lines."""
from typing import Any


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


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument('story', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    story = json.loads(args.story.read_text(encoding='utf-8-sig'))
    paths = command_locations(story, 'ui-character-creation')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(paths, indent=2) + '\n', encoding='utf-8')
    print(f'Indexed {len(paths)} character creation commands')
