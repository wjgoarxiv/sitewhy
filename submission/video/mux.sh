#!/bin/bash
# Join intro + recorded take + outro and mix the narration under them.
# Usage: bash mux.sh TAKE_DIR COVER_DIR OUT_MP4
#   TAKE_DIR  = record.mjs output (take.webm, shots.json, audio/*.aiff)
#   COVER_DIR = cover.mjs output (intro.mp4, outro.mp4)
# Each narration line (narration.txt: shot|id|text) starts at the cue time record.mjs logged for it;
# intro lines start 0.5 s into the intro, outro lines 0.6 s into the outro. Fails on overlap or overflow.
set -euo pipefail
TAKE_DIR="$1"; COVER_DIR="$2"; OUT="$3"
HERE="$(cd "$(dirname "$0")" && pwd)"
AUDIO="$TAKE_DIR/audio"
dur() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }
INTRO_S=$(dur "$COVER_DIR/intro.mp4"); OUTRO_S=$(dur "$COVER_DIR/outro.mp4")

SCHED=$(python3 - "$TAKE_DIR/shots.json" "$AUDIO" "$HERE/narration.txt" "$INTRO_S" "$OUTRO_S" <<'EOF'
import json, subprocess, sys
shots = json.load(open(sys.argv[1]))
audio, narr_path, intro_s, outro_s = sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
take_s = (shots['trimEndMs'] - shots['trimStartMs']) / 1000.0
total = intro_s + take_s + outro_s
def dur(p):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())
lines = [l.rstrip('\n').split('|', 2) for l in open(narr_path) if l.strip()]
sched, cursor = [], {'intro': 0.5, 'outro': intro_s + take_s + 0.6}
for shot, nid, _ in lines:
    d = dur(f'{audio}/{nid}.aiff')
    if shot in cursor:
        start = cursor[shot]
    elif nid in shots['cues']:
        start = intro_s + (shots['cues'][nid] - shots['trimStartMs']) / 1000.0
    else:
        continue
    if shot in cursor:
        cursor[shot] = start + d + 0.35
    sched.append((nid, start, d))
sched.sort(key=lambda x: x[1])
for (a, s0, d0), (b, s1, _) in zip(sched, sched[1:]):
    assert s0 + d0 <= s1 + 0.05, f'{a} (ends {s0 + d0:.2f}) overlaps {b} (starts {s1:.2f})'
last = sched[-1]
assert last[1] + last[2] <= total - 0.2, f'{last[0]} runs past the end ({last[1] + last[2]:.2f} > {total:.2f})'
print(f'#TOTAL {total:.3f} {take_s:.3f}')
for nid, s0, d0 in sched:
    print(f'{nid} {int(s0 * 1000)} {d0:.2f}')
EOF
)
TOTAL=$(echo "$SCHED" | awk '/^#TOTAL/ {print $2}'); TAKE_S=$(echo "$SCHED" | awk '/^#TOTAL/ {print $3}')
TRIM_S=$(python3 -c "import json;print(json.load(open('$TAKE_DIR/shots.json'))['trimStartMs']/1000)")
echo "$SCHED" | grep -v '^#'

INPUTS=""; FILTER=""; i=0
while read -r nid ms _; do
  [ -n "$nid" ] || continue
  INPUTS="$INPUTS -i $AUDIO/$nid.aiff"
  FILTER="${FILTER}[$i:a]adelay=${ms}|${ms}[a$i];"
  i=$((i + 1))
done < <(echo "$SCHED" | grep -v '^#')
AMIX=$(python3 -c "print(''.join(f'[a{k}]' for k in range($i)))")
# shellcheck disable=SC2086 # intentional word-splitting of the ffmpeg input list
ffmpeg -v error -y $INPUTS -filter_complex \
  "${FILTER}${AMIX}amix=inputs=$i:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,apad=whole_dur=${TOTAL}[pad]" \
  -map "[pad]" -ar 44100 -c:a pcm_s16le "$TAKE_DIR/mix.wav"

ffmpeg -v error -y -i "$COVER_DIR/intro.mp4" -ss "$TRIM_S" -t "$TAKE_S" -i "$TAKE_DIR/take.webm" \
  -i "$COVER_DIR/outro.mp4" -i "$TAKE_DIR/mix.wav" -filter_complex \
  "[0:v]fps=25,scale=1920:1080,format=yuv420p[v0];[1:v]fps=25,scale=1920:1080,format=yuv420p[v1];\
[2:v]fps=25,scale=1920:1080,format=yuv420p[v2];[v0][v1][v2]concat=n=3:v=1:a=0[v]" \
  -map "[v]" -map 3:a -c:v libx264 -preset slow -crf 28 -maxrate 2200k -bufsize 4400k -pix_fmt yuv420p \
  -c:a aac -b:a 160k -movflags +faststart -t "$TOTAL" "$OUT"
echo "wrote $OUT"
ffprobe -v error -show_entries stream=codec_name,width,height -show_entries format=duration,size -of default=noprint_wrappers=1 "$OUT"
