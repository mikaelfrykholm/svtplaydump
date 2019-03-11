#!/usr/bin/python3
from pathlib import Path
import requests
import youtube_dl
import os

def videos():
    totpages = requests.get("https://www.svtplay.se/api/latest").json()['totalPages']
    for page in range(1,totpages):
        resp = requests.get(f"https://www.svtplay.se/api/latest?page={page}").json()
        for video in resp['data']:
           yield video

def find_genre(video):
    for cluster in video['clusters']:
        if cluster['clusterType'] == 'main':
            return cluster['name']
    return "Ingen genre"

def download(video):
#    print(video)
    if video['live']:
        return
    genre = find_genre(video)
    path = Path(genre)
    if not path.is_dir():
        Path(genre).mkdir()
    if not video['movie']: #We have a Series, make a folder
        path = Path(genre) / Path(video['programTitle'].replace('/','_'))
        if not path.exists():
            path.mkdir()
    postprocessors = []
    postprocessors.append( { 'key': 'EmbedThumbnail', })
    postprocessors.append( { 'key': 'FFmpegMetadata', })
    ydl_opts = { 'download_archive': 'svtplay.archive',
                 'writesubtitles': True, 
                 'allsubtitles': True,
                 'writethumbnail': True, 
                 'outtmpl' : f'{path}/%(title)s-%(id)s.%(ext)s',
                 'postprocessors': postprocessors, }
    extra_info = { 'id': video['id'],
                   'title': video['programTitle'] + ' - ' + video['title'],
                   'description': video.get('description',''),
                   'thumbnail':video.get('thumbnail','').replace('{format}','large')} 

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info("http://svtplay.se/"+video['contentUrl'], extra_info=extra_info)
       
if __name__ == "__main__":
    for video in videos():
        print(video['programTitle'])
        download(video)
