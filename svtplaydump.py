#!/usr/bin/env python
#
#   (C) Copyright 2010 Mikael Frykholm <mikael@frykholm.com>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#   
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#   
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>
#
# Changelog:
# 0.2 added python 2.4 urlparse compatibility
# 0.1 initial release

from BeautifulSoup import BeautifulSoup
from subprocess import *
import re
import json
try:
    import urlparse
except ImportError:
    pass
import urllib2
try:
    import urllib2.urlparse as urlparse
except ImportError:
    pass
import sys

def main(argv=None):
    if argv is None:
        argv=sys.argv
    videoid = re.findall("/video/(.*)[/]*",argv[1])[0]
    
    soup = BeautifulSoup(urllib2.urlopen("http://www.svtplay.se/video/%s/?type=embed"%videoid).read())
    
    flashvars = json.loads(soup.find("param", {"name":"flashvars",'value':True})['value'][5:])
    try:
        title = flashvars['statistics']['title']
    except:
        title = "unnamed"
    if 'dynamicStreams' in flashvars:
        url = flashvars['dynamicStreams'][0].split('url:')[1].split('.mp4,')[0] +'.mp4'
        filename = title+".mp4"
        print Popen(["rtmpdump",u"-o"+filename,"-r", url], stdout=PIPE).communicate()[0]
    if 'pathflv' in flashvars:
        rtmp = flashvars['pathflv'][0]
        filename = title+".flv"
        print Popen(["mplayer","-dumpstream","-dumpfile",filename, rtmp], stdout=PIPE).communicate()[0]
    if 'video' in flashvars:
        url = sorted(flashvars['video']['videoReferences'], key=lambda k: k['bitrate'])[-1]['url']
        filename = title+".mp4"
        print Popen(["rtmpdump",u"-o"+filename,"-r", url], stdout=PIPE).communicate()[0]

    else:
        print "Could not find any streams"
        return

if __name__ == "__main__":
    sys.exit(main())
