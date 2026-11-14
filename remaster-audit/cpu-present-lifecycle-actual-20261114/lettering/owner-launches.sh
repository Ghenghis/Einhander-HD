# usage: c1r4run.sh <key.png> <dry-run|write> [expect]
set -u
O=/c/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui
K=$1; M=$2; X=${3:-}
sleep 1; T=$(date -u +%Y%m%dT%H%M%SZ); tag=${K:9:8}
R=$O/receipts/C1r4-$M-$tag-$T; E=$R-envelope.json
test -e $R -o -e $E && { echo EXISTS; exit 9; }
mkdir $R && cp /c/github/Einhander/.claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support/watchdog/run_rc2_envelope_r1.py $R/executed-watchdog.py || exit 9
[ "$(sha256sum $R/executed-watchdog.py|cut -c1-64)" = fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36 ] || { echo WRAPPER_PIN; exit 9; }
[ "$(sha256sum $O/c1-stroke-void/ui_c1_stroke_void_r4.py|cut -c1-64)" = 4b21da8314d688fb36c1d2cc982bb824fef91b663b8cd1a66ada3c36e86c30a0 ] || { echo TOOL_PIN; exit 9; }
EX=""; [ "$M" = write ] && EX="--expect-voids $X"
cd $O/c1-stroke-void
echo "start $K $M $T"
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 C:/Python314/python.exe -I -B $R/executed-watchdog.py --out "$(cygpath -m $E)" --cpu 13 --timeout 60 --max-job-mib 1024 --no-window --max-cpu 60 --min-free-gib 16 -- C:/Python314/python.exe -I -B C:/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui/c1-stroke-void/ui_c1_stroke_void_r4.py --key $K --mode $M $EX
echo "wrapper_exit=$?"
echo "ENVELOPE=$E"
