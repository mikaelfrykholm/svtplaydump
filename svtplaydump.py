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
    soup = BeautifulSoup(urllib2.urlopen(argv[1]).read())
    flashvars = urlparse.parse_qs(soup.find("param", {"name":"flashvars",'value':True})['value'])
    title = None
    try:
        title = soup.find("div","info").ul.li.h2.string
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
    else:
        print "Could not find any streams"
        return

if __name__ == "__main__":
    sys.exit(main())
