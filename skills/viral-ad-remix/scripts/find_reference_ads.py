#!/usr/bin/env python3
"""List and download top-performing ads from TikTok Creative Center (Top Ads) without a browser.

usage:
  find_reference_ads.py search --country KR --objective app_install --period 180 --order like --limit 20 [--keyword 앱테크] [--lang ko]
  find_reference_ads.py download AD_ID [AD_ID ...] --out DIR

This uses the public website's internal API (unofficial, may change or rate-limit, read-only).
Downloaded videos carry a "TikTok Creative Center" watermark and belong to their advertisers:
use them only as structural references (e.g. as the source of a recreate/remake job), never republish them.

Objectives: traffic=1 app_install=2 conversion=3 video_view=4 reach=5 lead_generation=8 product_sales=15 app_promotion=16
"""
import argparse, hashlib, json, os, sys, time, urllib.parse, urllib.request, uuid

API = 'https://ads.tiktok.com/creative_radar_api/v1/'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
OBJ = {'traffic': 1, 'app_install': 2, 'conversion': 3, 'video_view': 4, 'reach': 5, 'lead_generation': 8, 'product_sales': 15, 'app_promotion': 16}
_SECRET = 'A7B&9z#1G6$2K@8M!3'  # public constant used by the website's request signing


def web_id():
    body = json.dumps({'app_id': 345918, 'url': 'https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en',
                       'user_agent': UA, 'referer': '', 'user_unique_id': ''}).encode()
    req = urllib.request.Request('https://mcs-sg.tiktokv.com/v1/user/webid', data=body, headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=20))['web_id']


def headers(uid, wid):
    ts = int(time.time())
    h = hashlib.md5(f'{_SECRET}-{wid or uid}-{ts}'.encode()).hexdigest()
    sign = ''.join(format(int(h[i], 16) ^ int(h[i + 16], 16), 'x') for i in range(16))
    out = {'accept': 'application/json', 'user-agent': UA, 'referer': 'https://ads.tiktok.com/business/creativecenter/',
           'anonymous-user-id': uid, 'timestamp': str(ts), 'user-sign': sign}
    if wid:
        out['web-id'] = wid
    return out


def get(path, uid, wid):
    req = urllib.request.Request(API + path, headers=headers(uid, wid))
    j = json.load(urllib.request.urlopen(req, timeout=30))
    if j.get('code'):
        raise SystemExit(f"API error {j.get('code')}: {j.get('msg')}")
    return j['data']


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('search')
    s.add_argument('--country', default='KR'); s.add_argument('--period', type=int, default=180, choices=[7, 30, 180])
    s.add_argument('--objective', choices=OBJ); s.add_argument('--keyword'); s.add_argument('--lang')
    s.add_argument('--order', default='like', choices=['like', 'ctr', 'for_you', 'cvr', 'impression'])
    s.add_argument('--limit', type=int, default=20); s.add_argument('--page', type=int, default=1)
    s.add_argument('--json', help='also save raw results to this file')
    d = sub.add_parser('download')
    d.add_argument('ids', nargs='+'); d.add_argument('--out', default='reference_ads')
    a = ap.parse_args()
    uid, wid = str(uuid.uuid4()), None
    try:
        wid = web_id()
    except Exception as e:
        print('web id unavailable, continuing without it:', e, file=sys.stderr)

    if a.cmd == 'search':
        q = {'period': a.period, 'page': a.page, 'limit': min(a.limit, 20), 'country_code': a.country, 'order_by': a.order}
        if a.objective: q['objective'] = OBJ[a.objective]
        if a.keyword: q['keyword'] = a.keyword
        if a.lang: q['ad_language'] = a.lang
        data = get('top_ads/v2/list?' + urllib.parse.urlencode(q), uid, wid)
        mats = data.get('materials', [])
        for m in mats:
            v = m.get('video_info') or {}
            print(f"{m['id']} | likes {m.get('like', 0):>7} | ctr {m.get('ctr', 0):.2f} | {v.get('duration', 0):5.1f}s | "
                  f"{m.get('objective_key', '').replace('campaign_objective_', '')} | {(m.get('ad_title') or '').replace(chr(10), ' ')[:70]}")
        if a.json:
            json.dump(mats, open(a.json, 'w'), ensure_ascii=False, indent=1)
        print('detail page (login required):  https://ads.tiktok.com/business/creativecenter/topads/<id>/pc/en', file=sys.stderr)
    else:
        os.makedirs(a.out, exist_ok=True)
        for ad in a.ids:
            data = get(f'top_ads/v2/detail?material_id={ad}', uid, wid)
            urls = (data.get('video_info') or {}).get('video_url') or {}
            url = urls.get('720p') or next(iter(urls.values()), None)
            if not url:
                print(ad, 'no video url'); continue
            path = os.path.join(a.out, f'{ad}.mp4')
            req = urllib.request.Request(url, headers={'user-agent': UA})
            open(path, 'wb').write(urllib.request.urlopen(req, timeout=60).read())
            print(path, f"{(data.get('video_info') or {}).get('duration', 0):.1f}s", (data.get('ad_title') or '')[:60])


if __name__ == '__main__':
    main()
