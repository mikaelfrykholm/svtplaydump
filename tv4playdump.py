#!/usr/bin/env python3.4

import requests
import svtplaydump
import os.path
from pathlib import Path


def get_hls_playlist(url):
    ret = requests.get(url).json()
    #import pdb;pdb.set_trace()
    videourl = None
    if isinstance(ret['playback']['items']['item'], list):
        videourl = sorted(ret['playback']['items']['item'], key=lambda k: int(k['bitrate']))[-1]['url']
    else:
        videourl = ret['playback']['items']['item']['url']
    return videourl

res = requests.get("http://webapi.tv4play.se/video/programs/search.json?categoryids=pokemon&start=0&rows=1000").json()
videos = []
#import pdb;pdb.set_trace()
for vid in res['results']:
    video = {}
    video['title'] = vid['name']
    video['description'] = vid['lead']
    video['url'] = get_hls_playlist("http://premium.tv4play.se/api/web/asset/{}/play.json?protocol=hls&videoFormat=MP4+WVM+SMI".format(vid['href']))
    video['filename'] = Path("{} {}.ts".format(vid['ontime'],vid['name']))
    videos.append(video)
    if video['filename'].with_suffix('.mkv').exists():
        print("Skipping {}".format(video['filename'].with_suffix('.mkv')))
        continue
    svtplaydump.download_from_playlist(video)
    svtplaydump.remux(video)
