#!/usr/bin/env python3
"""Setup script for claude-commands and claude-skills CLIs."""

from setuptools import setup, find_packages

setup(
    name='claude-commands',
    version='2.0.0',
    description='CLI for managing Claude Code commands, skills, and CLAUDE.md deployments',
    author='Christopher Henry',
    py_modules=['claude_commands'],
    packages=find_packages(),
    python_requires='>=3.11',
    install_requires=[
        'PyYAML>=6.0',
        'ruamel.yaml>=0.17',
    ],
    entry_points={
        'console_scripts': [
            'claude-commands=claude_commands:main',
            'claude-skills=claude_skills.cli:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
    ],
)
