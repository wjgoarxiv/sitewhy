#!/bin/bash
# Mux narration under the final take. Usage: bash mux.sh TAKE_WEBM SHOTS_JSON OUT_MP4
# Reads submission/video/narration.txt (shot|aiff|text). Each line is placed at
# its shot start + 1.0 s (then back-to-back with 0.35 s gaps); fails on overflow.
set -euo pipefail
TAKE="$1"; SHOTS="$2"; OUT="$3"
HERE="$(dirname "$0")"
AUDIO=/tmp/t7-audio
mkdir -p "$AUDIO"
say -v Samantha -r 185 -o "$AUDIO/probe.aiff" "probe" || { echo "Samantha voice missing"; exit 1; }
while IFS='|' read -r shot id text; do
  [ -n "$id" ] || continue
  say -v Samantha -r 185 -o "$AUDIO/$id.aiff" "$text"
done < "$HERE/narration.txt"
VDUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$TAKE")
SCHED=$(python3 - "$SHOTS" "$AUDIO" "$HERE/narration.txt" <<'EOF'
import json, subprocess, sys
shots = json.load(open(sys.argv[1]))
log = shots['log'] if isinstance(shots, dict) else shots
narr = [l.rstrip('\n').split('|', 2) for l in open(sys.argv[3]) if l.strip()]
def dur(p):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'csv=p=0', p], capture_output=True, text=True)
    return float(r.stdout.strip())
durs = {n: dur(f"{sys.argv[2]}/{n}.aiff") for _, n, _ in narr}
starts = {}
for i, (shot, nid, _) in enumerate(narr):
    s = next(e for e in log if e['name'] == shot)['tMs'] / 1000.0
    if nid in starts:
        prev = starts[nid]
    else:
        prev = None
    if shot not in [n[0] for n in narr[:narr.index([shot, nid, _])]]:
        t = s + 1.0
    else:
        same = [k for (sh, k) in [(a, b) for a, b, _ in narr] if sh == shot]
        t = starts[same[same.index(nid) - 1]][1] + 0.35
    starts[nid] = (int(t * 1000), t + durs[nid])
for i, e in enumerate(log):
    end = (log[i + 1]['tMs'] / 1000.0) if i + 1 < len(log) else float('inf')
    for shot, nid, _ in narr:
        if shot == e['name']:
            st, en = starts[nid]
            assert en <= end - 0.4, f"{nid} overflows shot {shot}"
for nid, (ms, _) in starts.items():
    print(f"{nid} {ms}")
EOF
)
echo "$SCHED"
INPUTS=""; FILTER=""
i=0
# Shots.json timestamps start after the warm-up visit; shift narration onto video time.
OFFSET_MS=${OFFSET_MS:-0}
while read -r nid ms; do
  [ -n "$nid" ] || continue
  ms=$((ms + OFFSET_MS))
  INPUTS="$INPUTS -i $AUDIO/$nid.aiff"
  FILTER="${FILTER}[$i:a]adelay=${ms}|${ms}[a$i];"
  i=$((i + 1))
done <<< "$SCHED"
AMIX=$(python3 -c "print(''.join(f'[a{k}]' for k in range($i)))")
# shellcheck disable=SC2086 # intentional word-splitting of the ffmpeg input list
ffmpeg -v error -y $INPUTS -filter_complex \
  "${FILTER}${AMIX}amix=inputs=$i:normalize=0[mix];[mix]apad=whole_dur=${VDUR}[pad]" \
  -map "[pad]" -c:a pcm_s16le "$AUDIO/mix.wav"
ffmpeg -v error -y -i "$TAKE" -i "$AUDIO/mix.wav" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -movflags +faststart -t "$VDUR" "$OUT"
echo "wrote $OUT"
ffprobe -v error -show_entries stream=codec_name,width,height -show_entries format=duration -of default=noprint_wrappers=1 "$OUT"
