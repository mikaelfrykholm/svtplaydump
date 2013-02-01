svtplaydump
===========

svtplaydump downloads svtplay content for offline viewing.
Use like this:
svtplaydump.py http://www.svtplay.se/video/128812/jakten-pa-bernhard

The script tries to download without any external programs first, and uses rtmpdump and mplayer as fallback. The fallback modes should not be needed any more, but is left for completeness.

It decrypts apple live http streaming on the fly if needed. 
______________

### Prerequisites:
    sudo apt-get install python-feedparser python-crypto python-beautifulsoup 

###Optionally:
    sudo apt-get install ffmpeg
When running in rss mode. Avconv is used to convert the .ts container to .mkv
 
