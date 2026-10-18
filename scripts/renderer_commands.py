"""Identify Ink text glued to the game's >>> command lines."""
from typing import Any


def command_arguments(story: Any) -> set[str]:
    arguments: set[str] = set()

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            command = False
            glued = False
            for value in node:
                if isinstance(value, str):
                    if value == "<>":
                        glued = True
                    elif value.startswith("^"):
                        if value.startswith("^>>>"):
                            command = True
                        elif command and glued:
                            arguments.add(value)
                        elif not glued:
                            command = False
                        glued = False
                else:
                    visit(value)

    visit(story)
    return arguments
