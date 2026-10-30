#!/bin/bash
# parallel range download: pdl.sh URL OUT N
URL=$1; OUT=$2; N=${3:-16}
SIZE=$(curl -sIL "$URL" | grep -i '^content-length' | tail -1 | tr -d '\r' | awk '{print $2}')
echo "size $SIZE $OUT"
P=$((SIZE / N + 1)); mkdir -p "$OUT.parts"
for i in $(seq 0 $((N-1))); do
  S=$((i*P)); E=$(( (i+1)*P - 1 )); [ $E -ge $SIZE ] && E=$((SIZE-1))
  ( for t in 1 2 3 4 5; do
      have=$(stat -c %s "$OUT.parts/$i" 2>/dev/null || echo 0); want=$((E-S+1))
      [ "$have" -ge "$want" ] && break
      curl -sL -r $((S+have))-$E "$URL" >> "$OUT.parts/$i"
    done ) &
done
wait
cat $(for i in $(seq 0 $((N-1))); do echo "$OUT.parts/$i"; done) > "$OUT.tmp"
[ "$(stat -c %s "$OUT.tmp")" = "$SIZE" ] && mv "$OUT.tmp" "$OUT" && rm -rf "$OUT.parts" && echo "OK $OUT" || echo "BAD $OUT"
