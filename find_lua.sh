#!/system/bin/sh
PID=$1
KW=$2
grep -E 'rw-p' /proc/$PID/maps | while read line; do
  range=$(echo "$line" | awk '{print $1}')
  s=$(echo "$range" | cut -d- -f1)
  e=$(echo "$range" | cut -d- -f2)
  start=$((0x$s)); end=$((0x$e)); len=$((end-start))
  if [ $len -le 0 ] || [ $len -gt 268435456 ]; then continue; fi
  blk=$((start/4096)); cnt=$((len/4096))
  if dd if=/proc/$PID/mem bs=4096 skip=$blk count=$cnt 2>/dev/null | grep -a -q "$KW"; then
    echo "FOUND $range len=$len"
  fi
done
