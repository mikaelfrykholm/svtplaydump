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

from bs4 import BeautifulSoup, Doctype
from subprocess import *
import re
from Crypto.Cipher import AES
import struct
import argparse
import requests
import sys, os
import socket
import feedparser
from datetime import datetime, timezone
class Video(dict):
    def __init__(self, *args, **kwargs):
        self.update(dict(*args, **kwargs))  # use the free update to set keys

    def __setattr__(self, name, value):
        return self.__setitem__(name,value)
        
    def __getattr__(self, name):
        return self.__getitem__(name)
        
    def is_downloaded(self):
        raise("NotImplemented")

def scrape_player_page(video):
    """
    Try to scrape the site for video and download. 
    """
    if not video['url'].startswith('http'):
        video['url'] = "http://www.svtplay.se" + video['url']
    soup = BeautifulSoup(requests.get(video['url']).text)
    video_player = soup.body('a',{'data-json-href':True})[0]
    if 'oppetarkiv.se' in video['url']:
        flashvars = requests.get("http://www.oppetarkiv.se/%s"%video_player.attrs['data-json-href']+"?output=json").json()
    else:    
        if video_player.attrs['data-json-href'].startswith("/wd"):
            flashvars = requests.get("http://www.svt.se/%s"%video_player.attrs['data-json-href']).json()
        else:    
            flashvars = requests.get("http://www.svtplay.se/%s"%video_player.attrs['data-json-href']+"?output=json").json()
    video['duration'] = video_player.attrs.get('data-length',0)
    if not video['title']:
        video['title'] = soup.find('meta',{'property':'og:title'}).attrs['content'].replace('|','_').replace('/','_')
    if not 'genre' in video:
        if soup.find(text='Kategori:'):
            video['genre'] = soup.find(text='Kategori:').parent.parent.a.text
        else:
            video['genre'] = 'Ingen Genre' 
    if 'dynamicStreams' in flashvars:
        video['url'] = flashvars['dynamicStreams'][0].split('url:')[1].split('.mp4,')[0] +'.mp4'
        filename = video['title']+".mp4"
        print(Popen(["rtmpdump","-o"+filename,"-r", url], stdout=PIPE).communicate()[0])
    if 'pathflv' in flashvars:
        rtmp = flashvars['pathflv'][0]
        filename = video['title']+".flv"
        print(Popen(["mplayer","-dumpstream","-dumpfile",filename, rtmp], stdout=PIPE).communicate()[0])
    if not 'timestamp' in video:
        if soup.find_all(datetime=True):
            xmldate_str = soup.find_all(datetime=True)[0].attrs['datetime']
            video['timestamp'] = datetime(*feedparser._parse_date_w3dtf(xmldate_str)[:6]) #naive in utc
            video['timestamp'] = video['timestamp'].replace(tzinfo=timezone.utc).astimezone(tz=None) #convert to local time
    if 'video' in flashvars:
        for reference in flashvars['video']['videoReferences']:
            if 'm3u8' in reference['url']:
                video['url']=reference['url']
                video['filename'] = video['title']+'.ts'
                if 'statistics' in flashvars:
                    video['category'] = flashvars['statistics']['category']
        download_from_playlist(video)
    if not 'url' in video:
        print("Could not find any streams")
        return False
    return video

def download_from_playlist(video):
    playlist = parse_playlist(requests.get(video['url']).text)
    if not playlist:
        return
    videourl = sorted(playlist, key=lambda k: int(k['BANDWIDTH']))[-1]['url']
    if not videourl.startswith('http'): #if relative path
        videourl = "{}/{}".format(os.path.dirname(video['url']), videourl) 
    segments, metadata = parse_segment_playlist(videourl)
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
            print("\r{0:.2f} MB".format(size/1024/1024),end="")
            sys.stdout.flush()
            if decrypt:
                iv=struct.pack("IIII",segment,0,0,0)
                decryptor = AES.new(key, AES.MODE_CBC, iv)
            while(True):
                try:
                    buf = ufile.read(4096)
                except (socket.error, TypeError) as e:
                    print("Error reading, skipping file")
                    print(e)
                    return
                if not buf:
                    break
                if decrypt:
                    buf = decryptor.decrypt(buf)
                ofile.write(buf)
                size += len(buf)
            segment += 1

    if 'thumb-url' in video:
        video['thumb'] = requests.get(video['thumb-url'],stream=True).raw

def parse_playlist(playlist):
    if not playlist.startswith("#EXTM3U"):
        print(playlist)
        return False
    playlist = playlist.splitlines()
    while not 'EXT-X-STREAM-INF' in playlist[0]:
        playlist = playlist[1:]
    items=[]
    for (metadata_string,url) in zip(playlist[0::2], playlist[1::2]):
        md = Video()
        if not 'EXT-X-STREAM-INF' in metadata_string.split(':')[0]:
            continue
        for item in metadata_string.split(':')[1].split(','):
            if '=' in item:
                md.update([item.split('='),]) 
        md['url']=url
        items.append(md)
    return items 

def parse_segment_playlist(playlisturl):
    playlist = requests.get(playlisturl).text
    assert playlist.startswith("#EXTM3U")
    PATTERN = re.compile(r'''((?:[^,"']|"[^"]*"|'[^']*')+)''')
    segments = []
    next_is_url=False
    metadata = {}
    for row in playlist.splitlines():
        if next_is_url:
            if not row.startswith('http'): #if relative path
                row = "{}/{}".format(os.path.dirname(playlisturl), row) 
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
            video = Video()
            video['title'] = meta['data-title']
            video['description'] = meta['data-description']
            video['url'] = dict(article.find('a').attrs)['href']
            video['thumb-url'] = dict(article.find('img',{}).attrs)['src']
            video['num'] = video_num
            video['total'] = page_tot * videos_per_page
            video_num += 1
            yield video
        page_num += 1

def remux(video, xml=None):
    basename = video['filename'].split('.ts')[0]
    if 'genre' in video:
        if not os.path.exists(video['genre']):
            os.mkdir(video['genre'])
        video['path'] = os.path.join(video['genre'],basename+'.mkv')
    else:
        video['path'] = basename+'.mkv' 
    command = ["mkvmerge","-o",video['path'], '--title',video['title']]

    if xml:
        with open(basename+'.xml','w') as f:
            f.write(xml)
            command.extend(['--global-tags',basename+'.xml'])           
    if 'thumb' in video:
        with open('thumbnail.jpg','wb') as f: #FIXME use title instead for many downloaders
            f.write(video['thumb'].read())
            command.extend(['--attachment-description', "Thumbnail",
                 '--attachment-mime-type', 'image/jpeg',
                 '--attach-file', 'thumbnail.jpg'])
    command.append(video['filename'])
    print(Popen(command, stdout=PIPE).communicate()[0])
    for fname in (video['filename'], basename+'.xml','thumbnail.jpg'):
        try:
            os.unlink(fname)
        except:
            pass
    if 'timestamp' in video:
        try:
            os.utime(video['path'], times=(video['timestamp'].timestamp(),video['timestamp'].timestamp()))
        except FileNotFoundError as e:
            print(e)
            
    
def mkv_metadata(video):
    root = BeautifulSoup(features='xml')
    root.append(Doctype('Tags SYSTEM "matroskatags.dtd"'))
    tags = root.new_tag("Tags")
    tag = root.new_tag("Tag")
    tags.append(tag)
    root.append(tags)
    keep = ('title','description', 'url','genre')
    targets = root.new_tag("Targets")
    ttv = root.new_tag("TargetTypeValue")
    ttv.string = str(50)
    targets.append(ttv)
    tag.append(targets)
    for key in video:
        if not key in keep:
            continue
        simple = root.new_tag('Simple')
        name = root.new_tag('Name')
        name.string=key.upper()
        simple.append(name)
        sstring = root.new_tag('String')
        sstring.string=video[key]
        simple.append(sstring)
        tag.append(simple)
    return str(root)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-r", "--rss", help="Download all files in rss")
    group.add_argument("-u", "--url", help="Download video in url")
    group.add_argument("-m", "--mirror", help="Mirror all files", action="store_true")
    parser.add_argument("-n", "--no_act", help="Just print what would be done, don't do any downloading.", action="store_true")
    parser.add_argument("--no_remux", help="Don't remux into mkv", action="store_true")
    
    args = parser.parse_args()
    if args.rss: 
        d = feedparser.parse(args.rss)
        for e in d.entries:
            print(("Downloading: %s"%e.title))
            if args.no_act:
                continue
            video = scrape_player_page({'title':e.title,'url':e.link})
            if args.no_remux:
                continue
            self.remux(video)
        #print(e.description)
    if args.mirror:
        if not os.path.exists('.seen'):
            os.mkdir('.seen')
        for video in parse_videolist():
            video['title'] = video['title'].replace('/','_')
            print(video['title']+'.mkv')
            print("{} of {}".format(video['num'], video['total']))
            
            if os.path.exists(os.path.join('.seen',video['title'])):
                print("Skipping") 
                continue
            print("Downloading...")
            if args.no_act:
                continue
            open(os.path.join('.seen',video['title']),'w').close() #touch
            video = scrape_player_page(video)
            if args.no_remux:
                continue
            xml = mkv_metadata(video)
            remux(video, xml)
            
    else:
        if not args.no_act:
            video = scrape_player_page({'url':args.url})
        if not args.no_remux:
            remux({'title':e.title})
        print(("Downloaded {}".format(args.url)))   
