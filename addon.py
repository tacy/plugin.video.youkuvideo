# -*- coding: utf-8 -*-
import re
import json
import urllib2
from collections import OrderedDict
from cStringIO import StringIO
from xbmcswift2 import Plugin
from xbmcswift2 import xbmcgui

plugin = Plugin()
dialog = xbmcgui.Dialog()
filters = plugin.get_storage('ftcache')


@plugin.route('/')
def showcatalog():
    """
    show catalog list
    """
    result = _http('http://www.youku.com/v/')
    print result
    catastr = re.search(r'yk-filter-panel">(.*?)yk-filter-handle',
                        result, re.S)
    catalogs = re.findall(r'href="(.*?)".*?>(.*?)</a>', catastr.group(1))
    menus = [{
        'label': catalog[-1].decode('utf-8'),
        'path': plugin.url_for('showmovie',
                            url='http://www.youku.com{0}'.format(catalog[0])),
    } for catalog in catalogs]
    return menus

@plugin.route('/movies/<url>')
def showmovie(url):
    """
    show movie list
    """
    #filter key, e.g. 'http://www.youku.com/v_showlist/c90'
    urlsps = re.findall(r'(.*?/[a-z]_*\d+)', url)
    key = urlsps[0]
    #filter movie by filters
    if 'change' in url:
        url = key
        for k, v in filters[key].iteritems():
            if '筛选' in k: continue
            fts = [m[1] for m in v]
            selitem = dialog.select(k, fts)
            if selitem is not -1:
                url = '{0}{1}'.format(url,v[selitem][0])
        url='{0}.html'.format(url)
        print '*'*80, url

    result = _http(url)

    #get catalog filter list, filter will be cache
    #filters item example:
    #   key:'http://www.youku.com/v_olist/c_97'
    #   value: '{'地区':('_a_大陆', '大陆', ...)}
    if key not in filters:
        filterstr = re.search(r'yk-filter-panel">(.*?)yk-filter-handle',
                            result, re.S)
        filtertypes = re.findall(r'<label>(.*?)<.*?<ul>(.*?)</ul>',
                                 filterstr.group(1), re.S)
        types = OrderedDict()
        for filtertype in filtertypes[1:]:
            typeitems = re.findall(r'(_*[a-z]+_*[^_]+?).html">(.*?)</a>',
                                       filtertype[1], re.S)
            typeitems.insert(0, ('', '全部'))
            types[filtertype[0]] = typeitems
        yksorts = re.findall(r'yk-sort-item(.*?)/ul>', result, re.S)
        for seq, yksort in enumerate(yksorts):
            if 'v_olist' in key:
                sorts = re.findall(r'(_s_\d+)(_d_\d+).*?>(.*?)</a>', yksort)
                types['排序{0}'.format(seq)] = [(s[seq], s[2]) for s in sorts]
            else:
                sorts = re.findall(r'(d\d+)(s\d+).*?>(.*?)</a>', yksort)
                types['排序{0}'.format(seq)] = [(s[not seq], s[2]) for s in sorts]
        filters[key] = types

    #get movie list
    mstr = r'{0}{1}{2}'.format('[vp]-thumb">\s+<img src="(.*?)" alt="(.*?)">',
                               '.*?"[pv]-thumb-tag[lr]b"><.*?">([^<]+?)',
                               '<.*?"[pv]-link">\s+<a href="(.*?)"')
    movies = re.findall(mstr, result, re.S)
    #deduplication movie item
    #movies = [(k,v) for k,v in OrderedDict(movies).iteritems()]

    #add pre/next item
    pagestr = re.search(r'class="yk-pages">(.*?)</ul>',
                        result, re.S)
    if pagestr:
        pre = re.findall(r'class="prev" title="(.*?)">\s*<a href="(.*?)"',
                         pagestr.group(1))
        if pre: movies.append(('', pre[0][0], '',
                               'http://www.youku.com{0}'.format(pre[0][1])))
        nex = re.findall(r'class="next" title="(.*?)">\s*<a href="(.*?)"',
                         pagestr.group(1))
        if nex: movies.append(('', nex[0][0], '',
                               'http://www.youku.com{0}'.format(nex[0][1])))
        cpg = re.findall(r'class="current">.*?>(\d+)<', pagestr.group(1))
        tpg = re.findall(r'class="pass".*?>(\d+)<', pagestr.group(1), re.S)

        #add fliter item
        pagetitle = '【第{0}页/共{1}页】【[COLOR FFFF0000]过滤条件选择)[/COLOR]】'
        movies.insert(0, ('', pagetitle.format(cpg[0], tpg[0] if tpg else '1'),
                          '', '{0}change'.format(url)))
    maptuple = (('olist', 'showmovie'), ('showlist', 'showmovie'),
                ('show_page', 'showepisode'), ('v_show/', 'playmovie'))
    menus = []
    #0 is thunmnailimg, 1 is title, 2 is status, 3 is url
    for seq, m in enumerate(movies):
        routeaddr = filter(lambda x: x[0] in m[3], maptuple)
        menus.append({
            'label': '{0}. {1}【{2}】'.format(seq, m[1], m[2]).decode(
                'utf-8') if m[0] else m[1].decode('utf-8'),
            'path': plugin.url_for(routeaddr[0][1] ,url=m[3]),
            'thumbnail': m[0],
        })
    return menus

@plugin.route('/episodes/<url>')
def showepisode(url):
    """
    show episodes list
    """
    result = _http(url)
    episodestr = re.search(r'id="episode_wrap">(.*?)<div id="point_wrap',
                           result, re.S)
    patt = re.compile(r'(http://v.youku.com/v_show/.*?.html)".*?>([^<]+?)</a')
    episodes = patt.findall(episodestr.group(1))

    #some catalog not episode, e.g. most movie
    if not episodes:
        playurl = re.search(r'class="btnplay" href="(.*?)"', result)
        if not playurl:
            playurl = re.search(r'btnplayposi".*?"(http:.*?)"', result)
        if not playurl:
            playurl = re.search(r'btnplaytrailer.*?(http:.*?)"', result)
        playmovie(playurl.group(1))
    else:
        elists = re.findall(r'<li data="(reload_\d+)" >', result)
        epiurlpart = url.replace('page', 'episode')
        for elist in elists:
            epiurl = epiurlpart + '?divid={0}'.format(elist)
            result = _http(epiurl)
            epimore = patt.findall(result)
            episodes.extend(epimore)

        menus = [{
            'label': episode[1].decode('utf-8'),
            'path': plugin.url_for('playmovie', url=episode[0]),
            } for episode in episodes]
        return menus

@plugin.route('/play/<url>')
def playmovie(url):
    """
    play movie
    """
    stypes = OrderedDict((('原画', 'hd3'), ('超清', 'hd2'),
                          ('高清', 'mp4'), ('标清', 'flv')))
    #get movie metadata (json format)
    vid = url[-18:-5]
    moviesurl="http://v.youku.com/player/getPlayList/VideoIDS/{0}".format(vid)
    result = _http(moviesurl)
    movinfo = json.loads(result.replace('\r\n',''))
    movdat = movinfo['data'][0]
    streamfids = movdat['streamfileids']
    stype = 'flv'

    # user select streamtype
    if len(streamfids) > 1:
        selstypes = [k for k,v in stypes.iteritems() if v in streamfids]
        selitem = dialog.select('清晰度', selstypes)
        if selitem is not -1:
            stype = stypes[selstypes[selitem]]

    #stream file format type is mp4 or flv
    ftype = 'mp4' if stype is 'mp4' else 'flv'
    fileid = getfileid(streamfids[stype], int(movdat['seed']))
    movsegs = movdat['segs'][stype]
    rooturl = 'http://f.youku.com/player/getFlvPath/sid/00_00/st'
    segurls = []
    for movseg in movsegs:
        #youku split stream file to seg
        segid = '{0}{1:02X}{2}'.format(fileid[0:8],
                                       int(movseg['no']) ,fileid[10:])
        kstr = movseg['k']
        segurl = '{0}/{1}/fileid/{2}?K={3}'.format(rooturl, ftype, segid, kstr)
        segurls.append(segurl)
    movurl = 'stack://{0}'.format(' , '.join(segurls))
    listitem=xbmcgui.ListItem()
    listitem.setInfo(type="Video", infoLabels={'Title': 'c'})
    xbmc.Player().play(movurl, listitem)

def getfileid(streamid, seed):
    """
    get dynamic stream file id
    Arguments:
    - `streamid`: e.g. '48*60*21*...*13*'
    - `seed`: mix str seed
    """
    source = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'\
             '/\\:._-1234567890'
    index = 0
    mixed = []
    for i in range(len(source)):
        seed = (seed * 211 + 30031) % 65536
        index =  seed * len(source) / 65536
        mixed.append(source[index])
        source = source.replace(source[index],"")
    mixstr = ''.join(mixed)
    attr = streamid[:-1].split('*')
    res = ""
    for item in attr:
        res +=  mixstr[int(item)]
    return res

def _http(url):
    """
    open url
    """
    req = urllib2.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) {0}{1}'.
                   format('AppleWebKit/537.36 (KHTML, like Gecko) ',
                          'Chrome/28.0.1500.71 Safari/537.36'))
    conn = urllib2.urlopen(req)
    content = conn.read()
    conn.close()
    return content

if __name__ == '__main__':
    #filters.clear()
    plugin.run()
