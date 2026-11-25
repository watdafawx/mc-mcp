#!/bin/bash
# usage: run_one.sh <brief> <arm: oh|os|ns|nh> <x> <z>
cd /x/Dev/Minecraft/mc-mcp/architect
brief=$1; arm=$2; x=$3; z=$4
case $brief in
 factory) T="a red-brick Victorian factory complex for a Create + Mekanism base, with a clock tower and smoke stacks";;
 lotus) T="a tall red timber refinery tower with stacked pagoda roofs, side workshops and a crane, steampunk";;
 station) T="a white research station with an orange stripe, a ring lab around a core tower, glass labs and a landing pad";;
esac
PY=.venv/Scripts/python.exe
log=exports/ab_test/logs/${brief}_${arm}.log
start=$(date +%s)
case $arm in
 oh) $PY architect.py --prompt --freecam --max-cost 0.5 -s ab/${brief}_oh --x $x --y 120 --z $z "$T" > $log 2>&1;;
 os) ARCHITECT_MODEL=claude-sonnet-5-5 $PY architect.py --prompt --freecam --max-cost 1.0 -s ab/${brief}_os --x $x --y 120 --z $z "$T" > $log 2>&1;;
 ns) $PY architect.py --design -s ab/${brief}_ns --x $x --y 120 --z $z "$T" > $log 2>&1;;
 nh) ARCHITECT_DESIGN_MODEL=claude-haiku-5-5 $PY architect.py --design -s ab/${brief}_nh --x $x --y 120 --z $z "$T" > $log 2>&1;;
esac
echo "exit=$? wall=$(( $(date +%s)-start ))s" | tee -a $log
tail -15 $log | cut -c1-200
