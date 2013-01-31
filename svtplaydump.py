#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
# 0.3 added apple streaming playlist parsing and decryption
# 0.2 added python 2.4 urlparse compatibility
# 0.1 initial release

from BeautifulSoup import BeautifulSoup
from subprocess import *
import re
import json
from Crypto.Cipher import AES
import struct
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
    try:
        videoid = re.findall("/video/(.*)[/]*",argv[1])[0]
        soup = BeautifulSoup(urllib2.urlopen("http://www.svtplay.se/video/%s/?type=embed"%videoid).read())
        flashvars = json.loads(soup.find("param", {"name":"flashvars",'value':True})['value'][5:])
    except(IndexError):
        page = urllib2.urlopen(argv[1]).read()
        videoid = re.findall("svt_article_id=(.*)[&]*",page)[0]
        flashvars = json.loads(urllib2.urlopen("http://www.svt.se/wd?widgetId=248134&sectionId=1024&articleId=%s&position=0&format=json&type=embed&contextSectionId=1024"%videoid).read())
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
        for reference in flashvars['video']['videoReferences']:
            if reference['url'].endswith("m3u8"):
                url=reference['url']
        download_from_playlist(url, title+'.ts')
    else:
        print "Could not find any streams"
        return

def download_from_playlist(url, title):
    playlist = parse_playlist(urllib2.urlopen(url).read())
    videourl = sorted(playlist, key=lambda k: int(k['BANDWIDTH']))[-1]['url']
    segments, metadata = parse_segment_playlist(urllib2.urlopen(videourl).read())
    if "EXT-X-KEY" in metadata:
        key = urllib2.urlopen(metadata["EXT-X-KEY"]['URI'].strip('"')).read()
        decrypt=True
    else:
        decrypt=False
    with open("%s"%title,"w") as ofile:
        segment=0
        for url in segments:
            print "Downloading: %s"%(url)
            ufile = urllib2.urlopen(url)
            if decrypt:
                iv=struct.pack("IIII",segment,0,0,0)
                decryptor = AES.new(key, AES.MODE_CBC, iv)
            while(True):
                buf = ufile.read(1024)
                if buf:
                    if decrypt:
                        buf = decryptor.decrypt(buf)
                    ofile.write(buf)
                else:
                    ufile.close()
                    break
            segment += 1

def parse_playlist(playlist):
    assert playlist.startswith("#EXTM3U")
    playlist = playlist.splitlines()[1:]
    items=[]
    for (metadata_string,url) in zip(playlist[0::2], playlist[1::2]):
        md = dict()
        assert 'EXT-X-STREAM-INF' in metadata_string.split(':')[0]
        for item in metadata_string.split(':')[1].split(','):
            if '=' in item:
                md.update([item.split('='),]) 
        md['url']=url
        items.append(md)
    return items 

def parse_segment_playlist(playlist):
    assert playlist.startswith("#EXTM3U")
    PATTERN = re.compile(r'''((?:[^,"']|"[^"]*"|'[^']*')+)''')
    segments = []
    next_is_url=False
    metadata = {}
    for row in playlist.splitlines():
        if next_is_url:
            segments.append(row)
            next_is_url=False
            continue
        if 'EXTINF' in row:
            next_is_url=True
        if "EXT-X-KEY" in row:
             row = row.split(':',1)[1] #skip first part
             parts = PATTERN.split(row)[1:-1] #do magic re split and keep quoting
             metadata["EXT-X-KEY"] = dict([part.split('=',1) for part in parts if '=' in part]) #throw away the commas and make dict of the pairs
    return(segments, metadata)   

if __name__ == "__main__":
    sys.exit(main())
