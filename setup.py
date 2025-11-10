#!/usr/bin/env python3
"""Setup script for claude-commands CLI."""

from setuptools import setup

setup(
    name='claude-commands',
    version='1.0.0',
    description='CLI for managing Claude Code commands across multiple projects',
    author='Your Name',
    py_modules=['claude_commands'],
    python_requires='>=3.7',
    entry_points={
        'console_scripts': [
            'claude-commands=claude_commands:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)
