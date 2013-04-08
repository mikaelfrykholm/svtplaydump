from distribute_setup import use_setuptools
use_setuptools()
from setuptools import setup
setup(
    name = "svtplaydump",
    version = "0.5",
    description = "Download from svtplay.se",
    author = "Mikael Frykholm",
    author_email = "mikael@frykholm.com",
    url = "https://github.com/mikaelfrykholm/svtplaydump",
    keywords = ["svtplay"],
    install_requires=['beautifulsoup4', 'feedparser', 'requests'],
    classifiers = [
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Development Status :: 4 - Beta",
        "Environment :: Other Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Operating System :: OS Independent",
        ],
    long_description = """\
svtplaydump downloads svtplay content for offline viewing.

Use like this:
svtplaydump.py -u http://www.svtplay.se/video/128812/jakten-pa-bernhard
"""
)
