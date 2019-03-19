#!/usr/bin/python3
from pathlib import Path
import requests
import youtube_dl
import os
import datetime 

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

def svtplay_meta2xml(meta):

    return f"""
    <Tags>
      <Tag>
        <Simple>
          <Name>TITLE</Name>
          <String>{meta['programTitle']} - {meta['title']}</String>
        </Simple>
        <Simple>
          <Name>DESCRIPTION</Name>
          <String>{meta['shortDescription']}</String>
        </Simple>
        <Simple>
          <Name>DATE_RELEASED</Name>
          <String>{meta['year']}</String>
        </Simple>
        <Simple>
          <Name>SYNOPSIS</Name>
          <String>{meta['description']}</String>
        </Simple>
      </Tag>
    </Tags>
    """

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
    apa = video['id']
#    import pdb;pdb.set_trace()
    if video['season'] == 0 and not video['movie']: #not a series, something like Rapport
        validf = datetime.datetime.strptime(video['validFrom'],'%Y-%m-%dT%H:%M:%S%z')
        valids = validf.strftime("%Y-%m-%dT%H")
        title = f"{video['programTitle']} {valids}"
    if not video['movie'] and video['season'] != 0:
        title = f"{video['programTitle']} S{video['season']}E{video['episodeNumber']} {video['title']}"
    with open(f"{path}/{video['id']}.xml","w") as xmlfile:
        xmlfile.write(svtplay_meta2xml(video))
    add_subs = ''
    if video['closedCaptioned']:
        add_subs = f"'{path}/'*{apa}*.vtt"
    ydl_opts = { 'download_archive': 'svtplay.archive',
                 'writesubtitles': True, 
                 'allsubtitles': True,
                 'writethumbnail': True, 
                 'outtmpl' : f'{path}/%(title)s-%(id)s.%(ext)s',
                 'source_address': '0.0.0.0',
                 'postprocessors': [
                  {
                  'key': 'ExecAfterDownload',
                  'exec_cmd': f"echo {{}} && mkvmerge --global-tags '{path}'/{apa}.xml --attach-file '{path}/'*{apa}*jpg '{path}'/*{apa}*.mp4 {add_subs} -o '{path}/{title}.mkv' && rm '{path}'/*{apa}*",
                  }]
                }
    extra_info = { 'id': apa,
                   'title': title,
                   'thumbnail':video.get('thumbnail','').replace('{format}','large')} 
    xml = svtplay_meta2xml(video)
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info("http://svtplay.se/"+video['contentUrl'], extra_info=extra_info)
       
if __name__ == "__main__":
    for video in videos():
        print(video['programTitle'])
        download(video)
