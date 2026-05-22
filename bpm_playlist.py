#!/usr/bin/env python3
"""
Spotify BPM Playlist Builder (GetSongBPM source)

Spotify's Audio Features API is blocked for apps created after 2024-11-27,
so tempo (BPM) comes from getsongbpm.com instead. Requires a free API key:
  https://getsongbpm.com/api  (they require a backlink to their site)

Store the key in config.yaml under:
  getsongbpm:
    api_key: "YOUR_KEY"
or export GETSONGBPM_API_KEY.
"""

import argparse
import json
import os
import random
import re
import time
import yaml
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.yaml"
CACHE_PATH = Path(__file__).parent / "bpm_cache.json"
GSB_BASE = "https://api.getsongbpm.com"


def load_config():
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    cfg['spotify']['client_id'] = (
        os.environ.get('SPOTIFY_CLIENT_ID') or cfg['spotify'].get('client_id'))
    cfg['spotify']['client_secret'] = (
        os.environ.get('SPOTIFY_CLIENT_SECRET') or cfg['spotify'].get('client_secret'))
    if not cfg['spotify']['client_id'] or not cfg['spotify']['client_secret']:
        raise SystemExit(
            "Missing Spotify credentials. Set client_id/client_secret in config.yaml "
            "or export SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET.")
    cfg['_gsb_key'] = (
        os.environ.get('GETSONGBPM_API_KEY')
        or (cfg.get('getsongbpm') or {}).get('api_key'))
    if not cfg['_gsb_key']:
        raise SystemExit(
            "Missing GetSongBPM API key. Get one free at https://getsongbpm.com/api, "
            "then add it to config.yaml under getsongbpm.api_key "
            "or export GETSONGBPM_API_KEY.")
    return cfg


def get_spotify_client(config):
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=config['spotify']['client_id'],
        client_secret=config['spotify']['client_secret'],
        redirect_uri=config['spotify']['redirect_uri'],
        scope=config['spotify']['scope'],
        cache_path=str(Path(__file__).parent / ".cache")
    ))


def get_saved_tracks(sp):
    tracks = []
    results = sp.current_user_saved_tracks(limit=50)
    while results:
        for item in results['items']:
            track = item['track']
            if track and track['id']:
                tracks.append(track)
        print(f"  Fetched {len(tracks)} tracks...", end='\r')
        if results['next']:
            results = sp.next(results)
        else:
            break
    print(f"  Fetched {len(tracks)} tracks total")
    return tracks


def _norm(s):
    """Normalize for comparison: lowercase, strip punctuation and extras."""
    s = s.lower()
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s)          # drop (feat. ...), [remix]
    s = re.sub(r"\s*-\s*(remaster|remix|live|radio).*$", "", s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def load_cache():
    if CACHE_PATH.exists():
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f)


def lookup_bpm(api_key, title, artist, delay):
    """Query GetSongBPM; return tempo (float) only on a confident match, else None."""
    lookup = f"song:{title}+artist:{artist}"
    try:
        r = requests.get(
            f"{GSB_BASE}/search/",
            params={"api_key": api_key, "type": "both", "lookup": lookup},
            timeout=15,
        )
    except requests.RequestException:
        return None
    time.sleep(delay)
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except ValueError:
        return None

    results = data.get("search")
    if not isinstance(results, list) or not results:
        return None

    nt, na = _norm(title), _norm(artist)
    for song in results:
        s_title = _norm(song.get("title", ""))
        s_artist = _norm((song.get("artist") or {}).get("name", ""))
        tempo = song.get("tempo")
        if not tempo:
            continue
        # Confident match: title matches and artist overlaps either direction.
        if s_title == nt and (na in s_artist or s_artist in na):
            try:
                return float(tempo)
            except (ValueError, TypeError):
                return None
    return None


def get_user_playlists(sp, user_id):
    playlists = {}
    results = sp.current_user_playlists(limit=50)
    while results:
        for p in results['items']:
            if p['owner']['id'] == user_id:
                playlists[p['name']] = p['id']
        if results['next']:
            results = sp.next(results)
        else:
            break
    return playlists


def find_or_create_playlist(sp, user_id, name, existing):
    if name in existing:
        return existing[name]
    return sp.user_playlist_create(user_id, name, public=False)['id']


def fmt_duration(ms):
    mins = ms // 60000
    return f"{mins // 60}h {mins % 60}m"


def main():
    parser = argparse.ArgumentParser(description='Build a high-BPM playlist (GetSongBPM tempo data).')
    parser.add_argument('--min-bpm', type=float, default=140, help='Minimum BPM (default 140)')
    parser.add_argument('--max-bpm', type=float, default=None, help='Maximum BPM (optional)')
    parser.add_argument('--hours', type=float, default=None, help='Cap playlist length in hours (optional)')
    parser.add_argument('--name', help='Playlist name (default: "High BPM (<min>+)")')
    parser.add_argument('--no-shuffle', action='store_true', help='Keep library order instead of shuffling')
    parser.add_argument('--delay', type=float, default=0.5, help='Seconds between BPM lookups (default 0.5)')
    args = parser.parse_args()

    name = args.name or f"High BPM ({int(args.min_bpm)}+)"

    print("Spotify BPM Playlist Builder (GetSongBPM)")
    print("=" * 40)

    config = load_config()
    sp = get_spotify_client(config)
    user = sp.current_user()
    user_id = user['id']
    print(f"Logged in as: {user['display_name']}\n")

    print("Fetching your library...")
    tracks = get_saved_tracks(sp)
    if not tracks:
        print("No saved tracks found!")
        return

    print("\nLooking up BPM (cached across runs)...")
    cache = load_cache()
    found, not_found = {}, 0
    for i, t in enumerate(tracks, 1):
        tid = t['id']
        artist = t['artists'][0]['name'] if t['artists'] else ''
        if tid in cache:
            bpm = cache[tid]
        else:
            bpm = lookup_bpm(config['_gsb_key'], t['name'], artist, args.delay)
            cache[tid] = bpm
            if i % 25 == 0:
                save_cache(cache)
        if bpm:
            found[tid] = bpm
        else:
            not_found += 1
        print(f"  {i}/{len(tracks)} looked up ({len(found)} with BPM, {not_found} missing)...", end='\r')
    save_cache(cache)
    print(f"\n  {len(found)} tracks have BPM data, {not_found} not found on GetSongBPM")

    matched = []
    for t in tracks:
        bpm = found.get(t['id'])
        if bpm is None:
            continue
        if bpm >= args.min_bpm and (args.max_bpm is None or bpm <= args.max_bpm):
            matched.append({
                'id': t['id'],
                'name': t['name'],
                'bpm': round(bpm),
                'duration_ms': t.get('duration_ms', 0),
            })

    rng = f"{int(args.min_bpm)}-{int(args.max_bpm)}" if args.max_bpm else f"{int(args.min_bpm)}+"
    print(f"\n{len(matched)} tracks at {rng} BPM")
    if not matched:
        print("Nothing matched that BPM range.")
        return

    if not args.no_shuffle:
        random.shuffle(matched)

    if args.hours:
        target_ms = int(args.hours * 3600 * 1000)
        capped, total = [], 0
        for t in matched:
            if total >= target_ms:
                break
            capped.append(t)
            total += t['duration_ms']
        matched = capped
    total = sum(t['duration_ms'] for t in matched)
    print(f"Selected {len(matched)} tracks ({fmt_duration(total)})")

    print("\nFinding/creating playlist...")
    existing = get_user_playlists(sp, user_id)
    playlist_id = find_or_create_playlist(sp, user_id, name, existing)

    ids = [t['id'] for t in matched]
    sp.playlist_replace_items(playlist_id, ids[:100])
    for i in range(100, len(ids), 100):
        sp.playlist_add_items(playlist_id, ids[i:i + 100])

    print(f"\nDone! '{name}': {len(matched)} tracks, {fmt_duration(total)}")


if __name__ == '__main__':
    main()
