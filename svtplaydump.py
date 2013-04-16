#!/usr/bin/env python3
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
# 0.4 added mirror mode.
# 0.3 added apple streaming playlist parsing and decryption
# 0.2 added python 2.4 urlparse compatibility
# 0.1 initial release

from bs4 import BeautifulSoup
from subprocess import *
import re
from Crypto.Cipher import AES
import struct
import argparse
import requests
import sys, os

def scrape_player_page(url, title):
    """
    Try to scrape the site for video and download. 
    """
    if not url.startswith('http'):
        url = "http://www.svtplay.se" + url
    video = {}
    soup = BeautifulSoup(requests.get(url).text)
    video_player = soup.body('a',{'data-json-href':True})[0]
    if 'oppetarkiv.se' in url:
        flashvars = requests.get("http://www.oppetarkiv.se/%s"%video_player.attrs['data-json-href']+"?output=json").json()
    else:    
        if video_player.attrs['data-json-href'].startswith("/wd"):
            flashvars = requests.get("http://www.svt.se/%s"%video_player.attrs['data-json-href']).json()
        else:    
            flashvars = requests.get("http://www.svtplay.se/%s"%video_player.attrs['data-json-href']+"?output=json").json()
    video['duration'] = video_player.attrs.get('data-length',0)
    video['title'] = title
    if not title:
        video['title'] = soup.find('meta',{'property':'og:title'}).attrs['content'].replace('|','_').replace('/','_')
    if 'dynamicStreams' in flashvars:
        video['url'] = flashvars['dynamicStreams'][0].split('url:')[1].split('.mp4,')[0] +'.mp4'
        filename = video['title']+".mp4"
        print(Popen(["rtmpdump","-o"+filename,"-r", url], stdout=PIPE).communicate()[0])
    if 'pathflv' in flashvars:
        rtmp = flashvars['pathflv'][0]
        filename = video['title']+".flv"
        print(Popen(["mplayer","-dumpstream","-dumpfile",filename, rtmp], stdout=PIPE).communicate()[0])
    if 'video' in flashvars:
        for reference in flashvars['video']['videoReferences']:
            if reference['url'].endswith("m3u8"):
                video['url']=reference['url']
                video['filename'] = video['title']+'.ts'
                if 'statistics' in flashvars:
                    video['category'] = flashvars['statistics']['category']
        download_from_playlist(video)
    else:
        print("Could not find any streams")
        return
    return video

def download_from_playlist(video):
    playlist = parse_playlist(requests.get(video['url']).text)
    if not playlist:
        return
    videourl = sorted(playlist, key=lambda k: int(k['BANDWIDTH']))[-1]['url']
    segments, metadata = parse_segment_playlist(requests.get(videourl).text)
    if "EXT-X-KEY" in metadata:
        key = requests.get(metadata["EXT-X-KEY"]['URI'].strip('"')).text
        decrypt=True
    else:
        decrypt=False
    with open("%s"%video['filename'],"wb") as ofile:
        segment=0
        size = 0
        for url in segments:
            ufile = requests.get(url, stream=True).raw
            print("\r{} MB".format(size/1024/1024))
            sys.stdout.flush()
            if decrypt:
                iv=struct.pack("IIII",segment,0,0,0)
                decryptor = AES.new(key, AES.MODE_CBC, iv)
            while(True):
                buf = ufile.read(4096)
                if not buf:
                    break
                if decrypt:
                    buf = decryptor.decrypt(buf)
                ofile.write(buf)
                size += len(buf)
            segment += 1

def parse_playlist(playlist):
    if not playlist.startswith("#EXTM3U"):
        print(playlist)
        return False
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
             parts = PATTERN.split(row)[1:-1] #do magic re split and keep quotes
             metadata["EXT-X-KEY"] = dict([part.split('=',1) for part in parts if '=' in part]) #throw away the commas and make dict of the pairs
    return(segments, metadata)

def parse_videolist():
    page_num = 1
    soup = BeautifulSoup(requests.get("http://www.svtplay.se/ajax/videospager").text)#this call does not work for getting the pages, we use it for the page totals only
    page_tot = int(soup.find('a',{'data-currentpage':True}).attrs['data-lastpage'])
    videos_per_page = 8
    video_num = 0
    while(page_num <= page_tot):
        base_url = "http://www.svtplay.se/ajax/videos?sida={}".format(page_num)
        soup = BeautifulSoup(requests.get(base_url).text)
        for article in soup.findAll('article'):
            meta = dict(article.attrs)
            video = {}
            video['title'] = meta['data-title']
            video['description'] = meta['data-description']
            video['url'] = dict(article.find('a').attrs)['href']
            video['thumb-url'] = dict(article.find('img',{}).attrs)['src']
            video['num'] = video_num
            video['total'] = page_tot * videos_per_page
            video_num += 1
            yield video
        page_num += 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-r", "--rss", help="Download all files in rss")
    group.add_argument("-u", "--url", help="Download video in url")
    group.add_argument("-m", "--mirror", help="Mirror all files", action="store_true")
    parser.add_argument("-n", "--no_act", help="Just print what would be done, don't do any downloading.", action="store_true")
    args = parser.parse_args()
    if args.rss: 
        import feedparser
        d = feedparser.parse(args.rss)
        for e in d.entries:
            print(("Downloading: %s"%e.title))
            if args.no_act:
                continue
            filename = scrape_player_page(e.link, e.title)
            print(Popen(["avconv","-i",filename,"-vcodec","copy","-acodec","copy", filename+'.mkv'], stdout=PIPE).communicate()[0])
        #print(e.description)
    if args.mirror:
        for video in parse_videolist():
            video['title'] = video['title'].replace('/','_')
            print(video['title']+'.mkv')
            print("{} of {}".format(video['num'], video['total']))
            if os.path.exists(video['title']+'.mkv'):
                print("Skipping") 
                continue
            print("Downloading...")
            if args.no_act:
                continue
            ret = scrape_player_page(video['url'], video['title'])
            print(ret)
            print(Popen(["avconv","-i",video['title']+'.ts',"-vcodec","copy","-acodec","copy", video['title']+'.mkv'], stdout=PIPE).communicate()[0])
            try:
                os.unlink(video['title']+'.ts')
            except:
                import pdb;pdb.set_trace()
    else:
        if not args.no_act:
            video = scrape_player_page(args.url, None)
        print(("Downloaded {}".format(args.url)))   
