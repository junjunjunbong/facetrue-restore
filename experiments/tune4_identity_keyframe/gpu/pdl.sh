#!/bin/bash
# usage: pdl.sh <repo> <file> <size> <outdir>  — 16 parallel ranged curls with resume
R=$1; F=$2; S=$3; D=$4; N=16; U=https://huggingface.co/$R/resolve/main/$F; O=$D/$F
mkdir -p $(dirname $O); [ -f $O ] && [ $(stat -c %s $O) -eq $S ] && { echo "OK $F"; exit 0; }
P=$(( (S + N - 1) / N ))
part() { i=$1; a=$((i*P)); b=$((a+P-1)); [ $b -ge $S ] && b=$((S-1)); want=$((b-a+1))
  for t in $(seq 1 20); do have=$(stat -c %s $O.part.$i 2>/dev/null || echo 0); [ "$have" -ge "$want" ] && return 0
    curl -sL --speed-limit 50000 --speed-time 30 -r $((a+have))-$b $U >> $O.part.$i; done; }
for i in $(seq 0 $((N-1))); do part $i & done; wait
cat $(for i in $(seq 0 $((N-1))); do echo $O.part.$i; done) > $O && rm $O.part.*
[ $(stat -c %s $O) -eq $S ] && echo "OK $F" || echo "BAD $F"
