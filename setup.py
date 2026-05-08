"""
Grid Dispatch Agent - 轻量化智能Agent框架
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="grid-dispatch-agent",
    version="1.0.0",
    author="SpeedOnline",
    author_email="467718583@qq.com",
    description="轻量化通用智能Agent框架，通过Skill机制实现业务定制",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/467718584/grid-dispatch-agent",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.25.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
        ],
        "word": [
            "python-docx>=0.8.11",
        ],
    },
    entry_points={
        "console_scripts": [
            "grid-agent=grid_agent.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "grid_agent": ["skills/*.json"],
    },
)
