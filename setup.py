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
        # add other requirements as needed
    ],
    extras_require={},
    entry_points={
        "console_scripts": [
            "oanda-bot=oanda_bot.app:main",
            "oanda-research=oanda_bot.research.run_research:main",
        ],
    },
)
