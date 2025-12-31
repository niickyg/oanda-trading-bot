from setuptools import setup, find_packages

setup(
    name="oanda_bot",
    version="0.1.0",
    description="OANDA trading bot and research toolkit",
    author="Nick Guerriero",
    author_email="nickguerriero@example.com",
    packages=find_packages(include=["oanda_bot", "oanda_bot.*"]),
    install_requires=[
        # runtime dependencies
        "oandapyV20",
        "numpy",
        "python-json-logger",
        "streamlit",
        "jinja2",
        "schedule",
        "python-dotenv",
        "ccxt",
        "backtrader",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-timeout>=2.4.0",
            "flake8",
            "watchdog",
        ],
    },
    entry_points={
        "console_scripts": [
            "oanda-bot=oanda_bot.app:main",
            "oanda-research=oanda_bot.research.run_research:main",
        ],
    },
)
